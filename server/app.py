"""FastAPI server wrapping the Omega TK RAG Chatbot pipeline.

New three-path router (per request):
  Pre-guardrail  — hardcoded greetings/thanks (instant, no LLM)
  classify_intent — LLM routes to GREETING | CONVERSATION | CODE | OFF_TOPIC
    GREETING     → hardcoded response
    OFF_TOPIC    → fallback warning
    CONVERSATION → retrieve context → GPT with conversational system prompt (no code)
    CODE         → Layer 1 → retrieve → GPT code prompt → Layer 3 validate + retry

History is injected into OpenAI calls directly (src/ is never modified).
Summarization: when history > 6 turns, older turns are summarised into 2-3 sentences
so context is preserved beyond the 6-message window.
"""

import re
import sys
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR     = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# src/ imports (read-only — never modify these files)
from retriever import get_retriever
from generator import get_generator
from guardrails import (
    check_intent,
    check_retrieval_confidence,
    IntentResult,
    RetrievalResult,
)
from fallback_responses import INVALID_INTENT_MSG, LOW_CONFIDENCE_MSG, NO_RESULTS_MSG
from config import OPENAI_MODEL

# server/ imports
from validator import validate_code

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_HISTORY    = 6    # recent turns injected into every LLM call
MAX_RETRIES    = 5    # max generation attempts before giving up
SUMMARY_AFTER  = 6    # summarise history older than this many messages

VALIDATION_FALLBACK_MSG = (
    "I wasn't able to generate valid code for this query after several attempts. "
    "Please try rephrasing, or check the official docs: "
    "https://docs.eyesopen.com/toolkits/python/omegatk/"
)

# ── Prompt templates ──────────────────────────────────────────────────────────

# Path A — conversational: used as a system message, no forced code block.
_CONVERSATIONAL_SYSTEM = """\
You are the Omega TK Code Assistant — a knowledgeable, friendly AI that helps \
engineers work with OpenEye's Omega Toolkit for molecular conformer generation.

CONVERSATION RULES:
1. Respond naturally like a helpful colleague, not a code generator.
2. Do NOT include a code block unless the user explicitly asks for code.
3. Keep responses concise — 2-4 sentences for simple questions, \
up to a paragraph for explanations.
4. If the user asks to verify or check code from the conversation, \
analyze it and give a direct answer ("Yes, that code is correct because...").
5. If the user asks a yes/no question, start with Yes or No, then briefly explain.
6. You can reference Omega TK concepts: OEOmega, OEOmegaOptions, OEFlipper, \
sampling modes (Classic, Dense, Pose, ROCS), Build(), return codes, molecule streams, etc.
7. Stay within the domain of Omega TK and computational chemistry.
8. Reference conversation history naturally when the user uses "that", "this", \
"it", or similar references.

Retrieved documentation context (use this to ground your answer):
{context}{summary_section}"""

# Path B — code generation: used as a user message, code block required.
_CODE_PROMPT = """\
You are an expert Python developer specialising in the OpenEye Omega Toolkit \
for molecular conformer generation.

Use the retrieved documentation below to answer the user's question.

## Retrieved Documentation
{context}

## User Question
{question}

## Instructions
Provide a 3-5 sentence explanation of what the code does and how it works, \
then a complete, working Python code block.

Always follow the 5-step OpenEye Omega pattern:
1. **Molecule Streams** — oemolistream / oemolostream
2. **Constants** — OEOmegaSampling_Classic / Dense / Pose / ROCS / FastROCS
3. **Options** — OEOmegaOptions(mode), OEMacrocycleOmegaOptions, OEFlipperOptions
4. **Execute** — omega.Build(mol)
5. **Error handling** — OEOmegaReturnCode_Success, OEGetOmegaError(ret_code)

Required import: `from openeye import oechem, oeomega`

## Response
Provide a 3-5 line explanation, then a ```python ... ``` code block:"""


# ── Pre-guardrail conversational handler ─────────────────────────────────────
# Instant responses (no LLM) for common conversational patterns.

_GREETING_WORDS = {"hi", "hello", "hey", "hiya", "howdy", "greetings", "sup", "yo"}

_HELP_WORDS = {
    "what can you do", "what do you do", "help me", "how can you help",
    "what topics", "what can i ask", "what do you know", "capabilities",
    "what are you", "who are you", "tell me what you can",
}

_THANKS_WORDS = {
    "thanks", "thank you", "thank u", "thx", "ty",
    "that was helpful", "that helped", "great", "perfect", "awesome",
    "bye", "goodbye", "see you", "later",
}

_GREETING_RESPONSE = (
    "Hello! I'm the Omega TK Code Assistant. I can help you generate Python code "
    "for OpenEye's conformer generation toolkit. Try asking me to generate conformers, "
    "enumerate stereochemistry with Flipper, configure OEOmegaOptions, or explain "
    "sampling modes like Classic vs Dense."
)

_CAPABILITIES_RESPONSE = (
    "I'm a specialized assistant for the OpenEye Omega Toolkit. Here's what I can help with:\n\n"
    "• **Generate conformer code** — single molecules, databases, or batch pipelines\n"
    "• **Enumerate stereochemistry** — using OEFlipper for R/S and E/Z isomers\n"
    "• **Configure Omega options** — sampling modes (Classic, Dense, Pose, ROCS), "
    "max conformers, energy windows, RMS thresholds\n"
    "• **Explain concepts** — what is OEOmega, difference between sampling modes\n"
    "• **Verify code** — analyze and confirm whether generated code is correct\n"
    "• **Handle errors** — return codes, OEGetOmegaError, retry logic\n\n"
    "All answers are grounded in the official OpenEye documentation."
)

_THANKS_RESPONSE = (
    "You're welcome! Let me know if you have any other questions about the Omega Toolkit."
)


def _handle_conversational(message: str) -> Optional["ChatResponse"]:
    """
    Instant check for greetings/help/thanks — no LLM call needed.
    Returns a ChatResponse if matched, otherwise None.
    """
    lower = message.lower().strip().rstrip("!.,?")

    if lower in _GREETING_WORDS:
        return ChatResponse(explanation=_GREETING_RESPONSE, code=None, language=None,
                            is_fallback=False, fallback_message=None)

    first_word = lower.split()[0] if lower.split() else ""
    if first_word in _GREETING_WORDS and len(lower.split()) <= 4:
        return ChatResponse(explanation=_GREETING_RESPONSE, code=None, language=None,
                            is_fallback=False, fallback_message=None)

    if any(phrase in lower for phrase in _HELP_WORDS):
        return ChatResponse(explanation=_CAPABILITIES_RESPONSE, code=None, language=None,
                            is_fallback=False, fallback_message=None)

    if any(phrase in lower for phrase in _THANKS_WORDS):
        return ChatResponse(explanation=_THANKS_RESPONSE, code=None, language=None,
                            is_fallback=False, fallback_message=None)

    return None


# ── LLM Intent Classifier ─────────────────────────────────────────────────────
# Uses GPT-4o-mini for smart routing: ~300ms, ~20 tokens.

_CLASSIFY_SYSTEM = """\
You are a query classifier for an Omega TK code assistant.
Classify the user's message into exactly one category:

- GREETING: greetings, thanks, goodbye, social pleasantries
- CONVERSATION: questions about capabilities, verification requests ("verify this",
  "is this correct?", "yes or no?"), conceptual questions ("what is OEOmega?",
  "explain sampling modes", "what should I be aware of?"), follow-up discussion
  about previous responses, questions about what the tool can do
- CODE: explicit requests to generate, write, create, produce, or show
  Python code or scripts
- OFF_TOPIC: anything unrelated to Omega TK, OpenEye, conformer generation,
  or computational chemistry

Respond with ONLY the category name, nothing else."""


def _keyword_classify_fallback(message: str) -> str:
    """
    Keyword-based fallback used when classify_intent() API call fails.
    Maps to CONVERSATION or CODE (never GREETING/OFF_TOPIC — those are handled
    by _handle_conversational and Layer 1 respectively).
    """
    lower = message.lower()
    concept_signals = {
        "what is", "what are", "what does", "explain", "describe",
        "difference between", "compare", "why", "when should", "tell me",
        "how does", "verify", "correct", "check", "yes or no", "can i use",
        "should i", "what should", "what else",
    }
    if any(sig in lower for sig in concept_signals):
        return "CONVERSATION"
    return "CODE"


def classify_intent(message: str, history: list) -> str:
    """
    Use GPT-4o-mini to classify query into GREETING|CONVERSATION|CODE|OFF_TOPIC.

    Passes last 2 history messages as context so "verify this code" / "can I use
    this?" resolve correctly to the referenced content.

    Falls back to keyword matching on API error.
    """
    # Build context snippet from recent history
    history_ctx = ""
    recent = history[-2:] if history else []
    if recent:
        lines = []
        for h in recent:
            role = "Assistant" if h.role in ("bot", "assistant") else "User"
            lines.append(f"{role}: {h.content[:200]}")
        history_ctx = "\n\nRecent conversation:\n" + "\n".join(lines)

    user_content = f"Message: {message}{history_ctx}"

    try:
        completion = _generator.client.chat.completions.create(
            model=_generator.model,
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        raw = completion.choices[0].message.content.strip().upper()
        if raw in {"GREETING", "CONVERSATION", "CODE", "OFF_TOPIC"}:
            return raw
        logger.warning("Unexpected classify_intent result: %r — using keyword fallback", raw)
        return _keyword_classify_fallback(message)
    except Exception as exc:
        logger.error("classify_intent error: %s — using keyword fallback", exc)
        return _keyword_classify_fallback(message)


# ── Conversation summarization ────────────────────────────────────────────────
# When history exceeds SUMMARY_AFTER messages, older turns are condensed into
# a 2-3 sentence summary so GPT retains context beyond the sliding window.

_SUMMARIZE_SYSTEM = """\
Summarize this conversation between a user and an Omega TK code assistant \
in 2-3 concise sentences. Focus on: what the user is working on, what code was \
generated, what decisions were made, and any preferences mentioned.
Do NOT include actual code in the summary. Be brief and factual."""

# In-memory cache: history-hash → summary string
_session_summaries: dict[str, str] = {}


def _history_key(messages: list) -> str:
    """Stable hash for a list of history messages (role + first 100 chars each)."""
    data = [(m.role, m.content[:100]) for m in messages]
    return hashlib.md5(json.dumps(data).encode()).hexdigest()


def summarize_history(old_messages: list) -> str:
    """
    Summarize a list of older HistoryMessage objects into 2-3 sentences.
    Returns empty string on failure (graceful fallback to no summary).
    """
    if not old_messages:
        return ""

    formatted = []
    for m in old_messages:
        role = "Assistant" if m.role in ("bot", "assistant") else "User"
        # Strip code blocks from history to keep summary compact
        content = re.sub(r"```[\s\S]*?```", "[code block]", m.content)
        formatted.append(f"{role}: {content[:300]}")

    try:
        completion = _generator.client.chat.completions.create(
            model=_generator.model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_SYSTEM},
                {"role": "user", "content": "\n".join(formatted)},
            ],
            temperature=0.3,
            max_tokens=120,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("summarize_history error: %s", exc)
        return ""


def _get_summary(history: list) -> str:
    """
    Return a cached or freshly generated summary of messages older than
    the SUMMARY_AFTER window. Returns "" if history is short enough.
    """
    if len(history) <= SUMMARY_AFTER:
        return ""

    old_messages = history[:-SUMMARY_AFTER]
    key = _history_key(old_messages)

    if key in _session_summaries:
        return _session_summaries[key]

    summary = summarize_history(old_messages)
    if summary:
        _session_summaries[key] = summary
        # Prevent unbounded growth — evict oldest entry when cache is large
        if len(_session_summaries) > 200:
            oldest_key = next(iter(_session_summaries))
            del _session_summaries[oldest_key]

    return summary


# ── Startup ───────────────────────────────────────────────────────────────────
_retriever = None
_generator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _retriever, _generator
    logger.info("Loading RAG pipeline...")
    _retriever = get_retriever()
    _generator = get_generator()
    logger.info("Pipeline ready.")
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Omega TK Chat API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_THRESHOLD_CODE        = 0.30
_THRESHOLD_CONVERSATION = 0.20   # conversational phrasing scores lower vs technical docs


def _retrieve(query: str, threshold: float) -> list[dict]:
    """
    Retrieve FAISS chunks with a custom similarity threshold.
    Bypasses the hard-coded SIMILARITY_THRESHOLD in src/config.py.
    """
    from config import TOP_K
    emb = _retriever.embed_query(query)
    scores, indices = _retriever.index.search(emb, TOP_K)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        if score >= threshold:
            chunk = _retriever.chunks[idx].copy()
            chunk["score"] = float(score)
            results.append(chunk)
    return results


def parse_llm_response(raw: str) -> tuple[str, Optional[str], str]:
    """Split a raw LLM response into (explanation, code, language)."""
    match = re.search(r"```(?:python)?\n?(.*?)```", raw, re.DOTALL)
    if match:
        code = match.group(1).strip()
        explanation = raw[: match.start()].strip() or "Here is the Python code:"
        return explanation, code, "python"
    return raw.strip(), None, "python"


_FOLLOWUP_SIGNALS = {
    "that", "it", "this", "those", "them", "same", "previous",
    "change", "modify", "update", "switch", "replace",
    "now", "also", "add", "remove", "instead", "too",
}


def build_retrieval_query(message: str, history: list) -> str:
    """
    For short follow-up queries, enrich the FAISS retrieval string with all prior
    user turns so the embedding captures the full conversation intent.
    """
    words = set(message.lower().split())
    is_followup = len(message.split()) < 12 and bool(words & _FOLLOWUP_SIGNALS)

    if not is_followup or not history:
        return message

    prior_user_msgs = [
        h.content for h in history if h.role == "user" and h.content.strip()
    ]
    if not prior_user_msgs:
        return message

    combined = " | ".join(m[:80] for m in prior_user_msgs)
    return f"{message} (context: {combined[:200]})"


# ── Generation: Path A — Conversational ──────────────────────────────────────

def generate_conversational_response(
    context: str,
    question: str,
    history: list,
    summary: str = "",
) -> Optional[str]:
    """
    Generate a natural-language response (no forced code block).
    Uses a system message + history so the LLM behaves like a helpful colleague.
    """
    summary_section = (
        f"\n\nPrevious conversation context:\n{summary}" if summary else ""
    )
    system_content = _CONVERSATIONAL_SYSTEM.format(
        context=context or "(no documentation retrieved)",
        summary_section=summary_section,
    )

    messages = [{"role": "system", "content": system_content}]

    for h in history[-MAX_HISTORY:]:
        role = "assistant" if h.role in ("bot", "assistant") else "user"
        if h.content.strip():
            messages.append({"role": role, "content": h.content})

    messages.append({"role": "user", "content": question})

    try:
        completion = _generator.client.chat.completions.create(
            model=_generator.model,
            messages=messages,
            temperature=0.4,
            max_tokens=800,
        )
        return completion.choices[0].message.content
    except Exception as exc:
        logger.error("OpenAI API error (conversational): %s", exc)
        return None


# ── Generation: Path B — Code with Layer 3 retry ─────────────────────────────

def _build_code_messages(
    context: str,
    question: str,
    history: list,
    summary: str = "",
    retry_note: str = "",
) -> list[dict]:
    """Assemble the messages array for the code generation call."""
    messages = []

    # Inject summary as a system-level message so it survives the history window
    if summary:
        messages.append({
            "role": "system",
            "content": f"Previous conversation summary: {summary}",
        })

    # Recent history
    for h in history[-MAX_HISTORY:]:
        role = "assistant" if h.role in ("bot", "assistant") else "user"
        if h.content.strip():
            messages.append({"role": role, "content": h.content})

    # Current turn with RAG prompt
    user_content = _CODE_PROMPT.format(context=context, question=question)
    if retry_note:
        user_content += f"\n\nIMPORTANT: {retry_note}"

    messages.append({"role": "user", "content": user_content})
    return messages


def generate_with_history_and_retry(
    context: str,
    question: str,
    history: list,
    summary: str = "",
) -> tuple[Optional[str], int]:
    """
    Generate a code response, validate it (Layer 3), retry up to MAX_RETRIES times.

    Returns:
        (raw_response_str, attempt_count)  on success
        (None, MAX_RETRIES)                if all attempts fail
    """
    retry_note = ""

    for attempt in range(1, MAX_RETRIES + 1):
        messages = _build_code_messages(
            context, question, history,
            summary=summary, retry_note=retry_note,
        )

        try:
            completion = _generator.client.chat.completions.create(
                model=_generator.model,
                messages=messages,
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error("OpenAI API error on attempt %d: %s", attempt, exc)
            retry_note = "The previous API call failed. Please try again."
            continue

        raw = completion.choices[0].message.content
        _, code, _ = parse_llm_response(raw)

        if code is None:
            retry_note = (
                "Your response did not contain a Python code block. "
                "Provide a ```python ... ``` block."
            )
            logger.warning("Attempt %d: no code block — retrying", attempt)
            continue

        is_valid, failure_reason = validate_code(code)
        if is_valid:
            logger.info("Validated on attempt %d", attempt)
            return raw, attempt

        retry_note = failure_reason
        logger.warning("Attempt %d failed Layer 3: %s", attempt, failure_reason)

    logger.error("All %d attempts failed validation", MAX_RETRIES)
    return None, MAX_RETRIES


# ── Schemas ───────────────────────────────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str       # "user" | "bot" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []


class ChatResponse(BaseModel):
    explanation: str
    code: Optional[str]
    language: Optional[str]
    is_fallback: bool
    fallback_message: Optional[str]
    attempts: int = 1


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "pipeline_loaded": _retriever is not None and _generator is not None,
        "model": OPENAI_MODEL,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Router:
      0. Pre-guardrail — instant hardcoded responses for greetings/thanks
      1. classify_intent() — LLM routes to GREETING|CONVERSATION|CODE|OFF_TOPIC
      2. GREETING  → hardcoded response
         OFF_TOPIC → fallback warning
         CONVERSATION → retrieve (lenient threshold) → conversational LLM
         CODE      → Layer 1 → retrieve → code LLM + Layer 3 validate + retry
      Both CONVERSATION and CODE paths inject history summary when len(history) > 6.
    """
    if _retriever is None or _generator is None:
        return ChatResponse(
            explanation="", code=None, language=None,
            is_fallback=True,
            fallback_message="Server is still initialising. Please retry in a moment.",
        )

    # ── Step 0: Instant hardcoded handler ─────────────────────────────────────
    conv = _handle_conversational(request.message)
    if conv is not None:
        logger.info("Hardcoded shortcut: %s", request.message[:60])
        return conv

    # ── Step 1: LLM intent classification ─────────────────────────────────────
    intent = classify_intent(request.message, request.history)
    logger.info("Intent: %s | %s", intent, request.message[:60])

    # ── Step 2a: GREETING (belt-and-suspenders) ───────────────────────────────
    if intent == "GREETING":
        return ChatResponse(explanation=_GREETING_RESPONSE, code=None, language=None,
                            is_fallback=False, fallback_message=None)

    # ── Step 2b: OFF_TOPIC ────────────────────────────────────────────────────
    if intent == "OFF_TOPIC":
        return ChatResponse(explanation="", code=None, language=None,
                            is_fallback=True, fallback_message=INVALID_INTENT_MSG)

    # ── Steps 3–4 shared: summary + retrieval ────────────────────────────────
    summary = _get_summary(request.history)
    if summary:
        logger.info("Summary injected (%d chars)", len(summary))

    retrieval_query = build_retrieval_query(request.message, request.history)
    if retrieval_query != request.message:
        logger.info("Retrieval query enriched: %s", retrieval_query[:100])

    # Choose threshold: CONVERSATION uses looser threshold (natural language scores lower)
    threshold = _THRESHOLD_CONVERSATION if intent == "CONVERSATION" else _THRESHOLD_CODE

    try:
        chunks = _retrieve(retrieval_query, threshold)
    except Exception as exc:
        logger.error("Retrieval error: %s", exc, exc_info=True)
        if intent == "CONVERSATION":
            chunks = []   # fall through to conversational response with no context
        else:
            return ChatResponse(explanation="", code=None, language=None,
                                is_fallback=True, fallback_message="Retrieval error. Please try again.")

    context = _retriever.format_context(chunks) if chunks else ""

    # ── Step 3: CONVERSATION path ─────────────────────────────────────────────
    if intent == "CONVERSATION":
        # If retrieval found nothing, we still respond using history + LLM knowledge
        if chunks:
            retrieval_result = check_retrieval_confidence(chunks, threshold=threshold)
            if retrieval_result in (RetrievalResult.NO_RESULTS, RetrievalResult.LOW_CONFIDENCE):
                context = ""  # respond without docs rather than blocking

        raw = generate_conversational_response(
            context=context,
            question=request.message,
            history=request.history,
            summary=summary,
        )
        if raw is None:
            return ChatResponse(explanation="", code=None, language=None,
                                is_fallback=True, fallback_message="API error. Please try again.")

        explanation, code, language = parse_llm_response(raw)
        return ChatResponse(
            explanation=explanation,
            code=code,
            language=language,
            is_fallback=False,
            fallback_message=None,
            attempts=1,
        )

    # ── Step 4: CODE path ─────────────────────────────────────────────────────

    # Layer 1: intent filter (belt-and-suspenders for code generation)
    intent_result = check_intent(request.message)
    if intent_result == IntentResult.INVALID:
        logger.info("L1 rejected: %s", request.message[:60])
        return ChatResponse(explanation="", code=None, language=None,
                            is_fallback=True, fallback_message=INVALID_INTENT_MSG)

    # Layer 2: retrieval confidence
    retrieval_result = check_retrieval_confidence(chunks, threshold=threshold)

    if retrieval_result == RetrievalResult.NO_RESULTS:
        logger.info("L2 rejected (no results): %s", request.message[:60])
        return ChatResponse(explanation="", code=None, language=None,
                            is_fallback=True, fallback_message=NO_RESULTS_MSG)

    if retrieval_result == RetrievalResult.LOW_CONFIDENCE:
        logger.info("L2 rejected (low confidence): %s", request.message[:60])
        return ChatResponse(explanation="", code=None, language=None,
                            is_fallback=True, fallback_message=LOW_CONFIDENCE_MSG)

    # Layer 3: generate + validate + retry
    raw, attempts = generate_with_history_and_retry(
        context=context,
        question=request.message,
        history=request.history,
        summary=summary,
    )

    if raw is None:
        return ChatResponse(explanation="", code=None, language=None,
                            is_fallback=True, fallback_message=VALIDATION_FALLBACK_MSG)

    explanation, code, language = parse_llm_response(raw)
    return ChatResponse(
        explanation=explanation,
        code=code,
        language=language,
        is_fallback=False,
        fallback_message=None,
        attempts=attempts,
    )


# ── Static file serving ───────────────────────────────────────────────────────
_client_dist = _PROJECT_ROOT / "client" / "dist"

if _client_dist.exists():
    _assets_dir = _client_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    index_path = _client_dist / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse(
        status_code=200,
        content={
            "message": "API is running. Build the frontend to serve the UI.",
            "hint": "cd client && npm install && npm run build",
        },
    )


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        app_dir=str(_THIS_DIR),
    )
