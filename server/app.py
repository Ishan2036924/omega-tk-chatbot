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

import os
import re
import sys
import time
import hashlib
import json
import logging
import io
import base64
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta, timezone

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR     = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Header, Depends
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

# ── Supabase (optional — graceful degradation if not configured) ───────────────
_supabase_client = None


def _get_supabase():
    """Return a Supabase client, or None if env vars are missing."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialised.")
    except Exception as exc:
        logger.warning("Supabase init failed: %s", exc)
    return _supabase_client


# ── JWT auth dependency ───────────────────────────────────────────────────────

def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract user_id from a Supabase JWT Bearer token.
    Returns None gracefully if no token present, secret missing, or verification fails.
    Requires SUPABASE_JWT_SECRET env var (Supabase dashboard → Settings → API → JWT Settings).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        return None
    try:
        import jwt as _pyjwt
        payload = _pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return payload.get("sub")  # Supabase stores user_id in the 'sub' claim
    except Exception as exc:
        logger.debug("JWT verification failed: %s", exc)
        return None


def _sb_save_message(
    session_id: str,
    role: str,
    content: str,
    user_id: Optional[str] = None,
) -> None:
    """Persist a chat turn to chat_history. Fire-and-forget."""
    sb = _get_supabase()
    if sb is None:
        return
    try:
        record: dict = {"session_id": session_id, "role": role, "content": content}
        if user_id:
            record["user_id"] = user_id
        sb.table("chat_history").insert(record).execute()
    except Exception as exc:
        logger.warning("Supabase chat_history insert failed: %s", exc)


def _sb_log_query(
    session_id: str,
    message: str,
    response: "ChatResponse",
    intent: str,
    faiss_score: Optional[float],
    latency_ms: int,
    user_id: Optional[str] = None,
) -> None:
    """Log query analytics to queries_log. Fire-and-forget."""
    sb = _get_supabase()
    if sb is None:
        return
    try:
        record: dict = {
            "session_id": session_id,
            "message": message,
            "intent": intent,
            "is_fallback": response.is_fallback,
            "has_code": response.code is not None,
            "attempts": response.attempts,
            "faiss_score": faiss_score,
            "latency_ms": latency_ms,
        }
        if user_id:
            record["user_id"] = user_id
        sb.table("queries_log").insert(record).execute()
    except Exception as exc:
        logger.warning("Supabase queries_log insert failed: %s", exc)


def _response_text(response: "ChatResponse") -> str:
    """Flatten a ChatResponse into a plain string for storage."""
    if response.is_fallback:
        return response.fallback_message or ""
    parts = []
    if response.explanation:
        parts.append(response.explanation)
    if response.code:
        parts.append(f"```{response.language or 'python'}\n{response.code}\n```")
    return "\n\n".join(parts)


def _sb_upsert_session(session_id: str, user_id: str, title: str = "Omega TK Session") -> None:
    """Create or update a row in chat_sessions so the left panel can list all sessions. Fire-and-forget."""
    sb = _get_supabase()
    if sb is None:
        return
    try:
        sb.table("chat_sessions").upsert({
            "id": session_id,
            "user_id": user_id,
            "title": title,
            "last_active": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logger.warning("Session upsert failed: %s", exc)


# ── Knowledge base helpers ────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Simple recursive character text splitter."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, start + overlap, end)
                if idx > start:
                    end = idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(start + 1, end - overlap)
    return chunks


def _embed_text(text: str) -> list[float]:
    """Embed text using text-embedding-3-small (same model as FAISS index)."""
    response = _generator.client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000],
    )
    return response.data[0].embedding


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two embedding vectors."""
    import numpy as np
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    norm = float(np.linalg.norm(a_arr) * np.linalg.norm(b_arr))
    return float(np.dot(a_arr, b_arr) / norm) if norm > 0 else 0.0


def _retrieve_knowledge(
    query: str,
    session_id: str,
    user_id: Optional[str] = None,
    top_k: int = 3,
    threshold: float = 0.25,
) -> list[dict]:
    """
    Retrieve relevant user-uploaded knowledge chunks via in-Python cosine similarity.
    Prefers querying by user_id (cross-session, permanent) when available;
    falls back to session_id for unauthenticated callers.
    """
    sb = _get_supabase()
    if sb is None or _generator is None:
        return []
    try:
        base = sb.table("knowledge_chunks").select("id, source, text, embedding")
        if user_id:
            rows = base.eq("user_id", user_id).execute().data
        else:
            rows = base.eq("session_id", session_id).execute().data
        if not rows:
            return []
        query_emb = _embed_text(query)
        scored = []
        for r in rows:
            emb = r.get("embedding")
            if isinstance(emb, list) and emb:
                sim = _cosine_sim(query_emb, emb)
                if sim >= threshold:
                    scored.append({"text": r["text"], "source": r["source"], "score": sim})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    except Exception as exc:
        logger.warning("Knowledge retrieval failed: %s", exc)
        return []


# ── File extraction helpers ────────────────────────────────────────────────────

def _extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages[:20]]
        return "\n\n".join(p for p in pages if p.strip())[:8000]
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def _extract_image_text_sync(content: bytes, content_type: str) -> str:
    """Send image to GPT-4o vision and return extracted text/description."""
    try:
        if _generator is None:
            return ""
        b64 = base64.b64encode(content).decode()
        data_url = f"data:{content_type};base64,{b64}"
        completion = _generator.client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": (
                        "Extract all visible text from this image. If the image shows code, "
                        "transcribe it exactly. If it shows a diagram or chart, describe it "
                        "technically. Be thorough."
                    )},
                ],
            }],
            max_tokens=1000,
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Image extraction failed: %s", exc)
        return ""


# ── Prompt templates ──────────────────────────────────────────────────────────

# Path A — conversational: used as a system message, no forced code block.
_CONVERSATIONAL_SYSTEM = """\
You are the Omega TK Code Assistant — a knowledgeable, friendly AI that helps \
engineers work with OpenEye's Omega Toolkit for molecular conformer generation.

CONVERSATION RULES:
1. Respond naturally like a helpful colleague, not a code generator.
2. Do NOT include a code block unless the user explicitly asks for code.
3. Match response length to question complexity:
   - Simple factual questions ("what is X?") → 3-5 sentences naming the class/function, \
what it does, and a key use case.
   - Conceptual questions ("explain Y", "difference between A and B") → 2-3 short paragraphs \
covering purpose, key parameters or methods with typical values, and practical guidance on \
when to use it.
   - Always name the relevant API classes (OEOmegaOptions, OEFlipperOptions, OEMacrocycleOmega, \
etc.) and mention 1-2 concrete parameter examples (e.g. SetMaxConfs(200), \
OEOmegaSampling_Dense) so the user knows exactly what to call.
4. If the user asks to verify or check code from the conversation, \
analyze it step-by-step and give a direct verdict ("Yes, that code is correct because..." \
or "No, line X has an issue: ...").
5. If the user asks a yes/no question, start with Yes or No, then explain in 2-4 sentences.
6. Stay within the domain of Omega TK and computational chemistry.
7. Reference conversation history naturally when the user uses "that", "this", \
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
Before the code block, write a structured explanation with these four parts \
(each 1-3 sentences, no headings needed — just flowing prose):

1. **Purpose** — what the code accomplishes and why this approach is used.
2. **Key classes & options** — name every significant class (OEOmega, OEOmegaOptions, \
OEFlipperOptions, OEMacrocycleOmega, etc.) and explain what each one controls, \
including any important parameter values (e.g. OEOmegaSampling_Classic vs Dense, \
SetMaxConfs(), SetDielectricConst()).
3. **5-step pattern** — briefly confirm how the code follows the standard OpenEye pattern: \
molecule streams → options → Build() → return code check.
4. **Output & caveats** — what the output file contains, any edge cases or \
things the user should watch out for (e.g. stereochemistry, macrocycle detection, \
file format requirements).

Then provide the complete, working Python code block.

Always follow the 5-step OpenEye Omega pattern:
1. **Molecule Streams** — oemolistream / oemolostream
2. **Constants** — OEOmegaSampling_Classic / Dense / Pose / ROCS / FastROCS
3. **Options** — OEOmegaOptions(mode), OEMacrocycleOmegaOptions, OEFlipperOptions
4. **Execute** — omega.Build(mol)
5. **Error handling** — OEOmegaReturnCode_Success, OEGetOmegaError(ret_code)

Required import: `from openeye import oechem, oeomega`

## Response
Write the explanation (4 parts, flowing prose), then a ```python ... ``` code block:"""


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
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    explanation: str
    code: Optional[str]
    language: Optional[str]
    is_fallback: bool
    fallback_message: Optional[str]
    attempts: int = 1


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    feedback: str   # "up" | "down"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "pipeline_loaded": _retriever is not None and _generator is not None,
        "model": OPENAI_MODEL,
    }


@app.post("/api/feedback")
def feedback_endpoint(
    request: FeedbackRequest,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Record thumbs-up / thumbs-down for a single bot response."""
    sb = _get_supabase()
    if sb is None:
        return {"ok": False, "reason": "Supabase not configured"}
    try:
        record: dict = {
            "session_id": request.session_id,
            "message_id": request.message_id,
            "feedback": request.feedback,
        }
        if user_id:
            record["user_id"] = user_id
        sb.table("feedback").insert(record).execute()
        return {"ok": True}
    except Exception as exc:
        logger.warning("Supabase feedback insert failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


# ── Analytics endpoint ────────────────────────────────────────────────────────

@app.get("/api/analytics")
def analytics_endpoint():
    """Return query stats for the last 24 h from Supabase queries_log."""
    sb = _get_supabase()
    if sb is None:
        return {
            "error": "Supabase not configured",
            "total_queries": 0, "code_requests": 0,
            "guardrail_blocks": 0, "avg_latency": 0,
            "hourly_counts": [], "recent_queries": [],
        }
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        rows = (
            sb.table("queries_log")
            .select("*")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .execute()
            .data
        )

        total      = len(rows)
        code_req   = sum(1 for r in rows if r.get("has_code"))
        blocks     = sum(1 for r in rows if r.get("is_fallback"))
        latencies  = [r["latency_ms"] for r in rows if r.get("latency_ms")]
        avg_lat    = int(sum(latencies) / len(latencies)) if latencies else 0

        # Build hourly buckets
        hour_counts: dict[str, int] = {}
        for r in rows:
            try:
                ts = r.get("created_at", "")
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                key = dt.strftime("%H:00")
                hour_counts[key] = hour_counts.get(key, 0) + 1
            except Exception:
                pass

        now = datetime.now(timezone.utc)
        hourly = [
            {"hour": (now - timedelta(hours=i)).strftime("%H:00"),
             "count": hour_counts.get((now - timedelta(hours=i)).strftime("%H:00"), 0)}
            for i in range(23, -1, -1)
        ]

        recent = [
            {
                "session_id":  r.get("session_id", ""),
                "timestamp":   r.get("created_at", ""),
                "message":     (r.get("message") or "")[:60],
                "intent":      r.get("intent", "—"),
                "is_fallback": r.get("is_fallback", False),
                "has_code":    r.get("has_code", False),
                "latency_ms":  r.get("latency_ms", 0),
                "feedback":    {"up": 0, "down": 0},  # filled in after feedback query
            }
            for r in rows[:20]
        ]

        # ── Feedback stats ────────────────────────────────────────────────────
        feedback_data = {"total_helpful": 0, "total_not_helpful": 0, "helpful_rate": None, "feedback_by_session": {}}
        try:
            fb_rows = sb.table("feedback").select("session_id, feedback").execute().data
            total_helpful    = sum(1 for r in fb_rows if r.get("feedback") == "up")
            total_not_helpful = sum(1 for r in fb_rows if r.get("feedback") == "down")
            total_fb = total_helpful + total_not_helpful
            helpful_rate = round(total_helpful / total_fb * 100) if total_fb > 0 else None
            fb_by_session: dict[str, dict] = {}
            for r in fb_rows:
                sid = r.get("session_id")
                fb  = r.get("feedback")
                if sid:
                    if sid not in fb_by_session:
                        fb_by_session[sid] = {"up": 0, "down": 0}
                    if fb in ("up", "down"):
                        fb_by_session[sid][fb] += 1
            feedback_data = {
                "total_helpful": total_helpful,
                "total_not_helpful": total_not_helpful,
                "helpful_rate": helpful_rate,
                "feedback_by_session": fb_by_session,
            }
            # Annotate recent queries with per-session feedback
            for q in recent:
                qsid = q.get("session_id", "")
                q["feedback"] = fb_by_session.get(qsid, {"up": 0, "down": 0})
        except Exception as fb_exc:
            logger.warning("Feedback analytics failed: %s", fb_exc)

        return {
            "total_queries": total, "code_requests": code_req,
            "guardrail_blocks": blocks, "avg_latency": avg_lat,
            "hourly_counts": hourly, "recent_queries": recent,
            **feedback_data,
        }
    except Exception as exc:
        logger.error("Analytics error: %s", exc)
        return {"error": str(exc), "total_queries": 0, "code_requests": 0,
                "guardrail_blocks": 0, "avg_latency": 0,
                "hourly_counts": [], "recent_queries": [],
                "total_helpful": 0, "total_not_helpful": 0, "helpful_rate": None}


# ── Transcription endpoint ────────────────────────────────────────────────────

@app.post("/api/transcribe")
async def transcribe_endpoint(audio: UploadFile = File(...)):
    """Receive a browser audio blob and return Whisper transcription text."""
    if _generator is None:
        raise HTTPException(status_code=503, detail="Pipeline not ready")
    try:
        content = await audio.read()
        filename = audio.filename or "recording.webm"
        content_type = audio.content_type or "audio/webm"
        audio_file = (filename, io.BytesIO(content), content_type)
        result = _generator.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return {"text": result.text}
    except Exception as exc:
        logger.error("Transcribe error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── History endpoint ─────────────────────────────────────────────────────────

@app.get("/api/history/{session_id}")
def history_endpoint(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Return stored chat history for a session (ASC order).
    When the user is authenticated the query is scoped to their user_id so
    they cannot read another user's session history."""
    sb = _get_supabase()
    if sb is None:
        return []
    try:
        query = (
            sb.table("chat_history")
            .select("role, content, created_at")
            .eq("session_id", session_id)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        rows = query.order("created_at", desc=False).execute().data
        return rows
    except Exception as exc:
        logger.warning("History load failed: %s", exc)
        return []


@app.get("/api/sessions")
def sessions_endpoint(user_id: Optional[str] = Depends(get_current_user)):
    """Return all chat sessions for the authenticated user, ordered by last_active DESC.
    Used by the LeftPanel to populate the full session history list on login."""
    if not user_id:
        return []
    sb = _get_supabase()
    if sb is None:
        return []
    try:
        rows = (
            sb.table("chat_sessions")
            .select("id, title, created_at, last_active")
            .eq("user_id", user_id)
            .order("last_active", desc=True)
            .execute()
            .data
        )
        return rows
    except Exception as exc:
        logger.warning("Sessions load failed: %s", exc)
        return []


# ── Knowledge base endpoints ──────────────────────────────────────────────────

@app.post("/api/knowledge")
async def add_knowledge_endpoint(
    text: str = Form(...),
    source: str = Form("user_text"),
    session_id: str = Form(...),
    user_id: Optional[str] = Depends(get_current_user),
):
    """Chunk, embed, and store pasted text into Supabase knowledge_chunks."""
    sb = _get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    if _generator is None:
        raise HTTPException(status_code=503, detail="Pipeline not ready")
    chunks = _chunk_text(text.strip(), chunk_size=400, overlap=50)
    if not chunks:
        raise HTTPException(status_code=400, detail="No text content to add")
    inserted = 0
    for chunk in chunks:
        try:
            emb = _embed_text(chunk)
            record: dict = {
                "session_id": session_id,
                "source": source,
                "text": chunk,
                "embedding": emb,
            }
            if user_id:
                record["user_id"] = user_id
            sb.table("knowledge_chunks").insert(record).execute()
            inserted += 1
        except Exception as exc:
            logger.warning("Knowledge chunk insert failed: %s", exc)
    logger.info("Knowledge: inserted %d chunks from source '%s'", inserted, source)
    return {"chunks_added": inserted, "source": source}


@app.post("/api/knowledge-file")
async def add_knowledge_file_endpoint(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    user_id: Optional[str] = Depends(get_current_user),
):
    """Upload a file, extract text, chunk and embed into knowledge_chunks."""
    sb = _get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    if _generator is None:
        raise HTTPException(status_code=503, detail="Pipeline not ready")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large — max 5 MB")
    fname = (file.filename or "").lower()
    ctype = file.content_type or "application/octet-stream"
    source = file.filename or "uploaded_file"
    if fname.endswith(".pdf"):
        text = _extract_pdf_text(content)
    elif fname.endswith((".md", ".txt")):
        text = content.decode("utf-8", errors="replace")[:16000]
    elif fname.endswith((".png", ".jpg", ".jpeg")) or ctype.startswith("image/"):
        text = await asyncio.to_thread(_extract_image_text_sync, content, ctype)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type — use PDF, TXT, MD, or image")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")
    chunks = _chunk_text(text, chunk_size=400, overlap=50)
    inserted = 0
    for chunk in chunks:
        try:
            emb = _embed_text(chunk)
            record: dict = {
                "session_id": session_id,
                "source": source,
                "text": chunk,
                "embedding": emb,
            }
            if user_id:
                record["user_id"] = user_id
            sb.table("knowledge_chunks").insert(record).execute()
            inserted += 1
        except Exception as exc:
            logger.warning("Knowledge file chunk insert failed: %s", exc)
    logger.info("Knowledge file: inserted %d chunks from '%s'", inserted, source)
    return {"chunks_added": inserted, "source": source}


@app.get("/api/knowledge/{session_id}")
def list_knowledge_endpoint(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user),
):
    """List unique knowledge sources. When authenticated, returns all sources
    for the user across every session (permanent knowledge base).
    Falls back to session-scoped listing for unauthenticated requests."""
    sb = _get_supabase()
    if sb is None:
        return []
    try:
        base = sb.table("knowledge_chunks").select("id, source, created_at")
        if user_id:
            rows = base.eq("user_id", user_id).order("created_at", desc=False).execute().data
        else:
            rows = base.eq("session_id", session_id).order("created_at", desc=False).execute().data
        sources: dict[str, dict] = {}
        for r in rows:
            src = r["source"]
            if src not in sources:
                sources[src] = {
                    "id": r["id"],
                    "source": src,
                    "chunk_count": 0,
                    "created_at": r["created_at"],
                }
            sources[src]["chunk_count"] += 1
        return list(sources.values())
    except Exception as exc:
        logger.warning("List knowledge failed: %s", exc)
        return []


@app.delete("/api/knowledge/{chunk_id}")
def delete_knowledge_endpoint(
    chunk_id: str,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Delete all chunks sharing the same source as the given chunk_id.
    When authenticated, scopes deletion to the user_id so users cannot delete
    each other's knowledge. Falls back to session_id scope for unauthenticated calls."""
    sb = _get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        row = (
            sb.table("knowledge_chunks")
            .select("source, session_id, user_id")
            .eq("id", chunk_id)
            .execute()
            .data
        )
        if not row:
            raise HTTPException(status_code=404, detail="Chunk not found")
        source     = row[0]["source"]
        session_id = row[0]["session_id"]
        chunk_owner = row[0].get("user_id")

        # Scope delete by user_id when auth is available
        if user_id and chunk_owner:
            if chunk_owner != user_id:
                raise HTTPException(status_code=403, detail="Not authorised to delete this chunk")
            sb.table("knowledge_chunks").delete().eq("user_id", user_id).eq("source", source).execute()
        else:
            sb.table("knowledge_chunks").delete().eq("session_id", session_id).eq("source", source).execute()

        logger.info("Knowledge: deleted all chunks for source '%s'", source)
        return {"ok": True, "deleted_source": source}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Delete knowledge failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Chat-with-file endpoint ───────────────────────────────────────────────────

@app.post("/api/chat-file", response_model=ChatResponse)
async def chat_file_endpoint(
    message: str = Form(...),
    history_json: str = Form("[]"),
    session_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: Optional[str] = Depends(get_current_user),
):
    """Accept multipart/form-data chat request with an optional file attachment."""
    # ── Parse history ──────────────────────────────────────────────────────────
    try:
        history = [HistoryMessage(**h) for h in json.loads(history_json)]
    except Exception:
        history = []

    # ── Extract file text ──────────────────────────────────────────────────────
    extra_context = ""
    if file:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            return ChatResponse(
                explanation="", code=None, language=None,
                is_fallback=True,
                fallback_message="File too large — maximum size is 5 MB.",
            )
        fname = (file.filename or "").lower()
        ctype = file.content_type or "application/octet-stream"
        if fname.endswith(".pdf"):
            extra_context = _extract_pdf_text(content)
        elif fname.endswith((".md", ".txt")):
            extra_context = content.decode("utf-8", errors="replace")[:8000]
        elif fname.endswith((".png", ".jpg", ".jpeg")) or ctype.startswith("image/"):
            extra_context = await asyncio.to_thread(
                _extract_image_text_sync, content, ctype
            )
        if extra_context:
            logger.info("File '%s' extracted: %d chars", file.filename, len(extra_context))

    # ── Run pipeline ───────────────────────────────────────────────────────────
    req = ChatRequest(message=message, history=history, session_id=session_id)
    t0 = int(time.time() * 1000)
    sid = session_id or "anon"
    _sb_save_message(sid, "user", message, user_id=user_id)

    response, intent, top_score = _chat_logic(req, extra_context=extra_context, user_id=user_id)

    latency = int(time.time() * 1000) - t0
    _sb_save_message(sid, "assistant", _response_text(response), user_id=user_id)
    _sb_log_query(sid, message, response, intent, top_score, latency, user_id=user_id)
    if user_id and sid not in ("anon", ""):
        _sb_upsert_session(sid, user_id)
    return response


def _chat_logic(
    request: ChatRequest,
    extra_context: str = "",
    user_id: Optional[str] = None,
) -> tuple[ChatResponse, str, Optional[float]]:
    """
    Core chat pipeline. Returns (response, intent_label, top_faiss_score).

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
        return (
            ChatResponse(
                explanation="", code=None, language=None,
                is_fallback=True,
                fallback_message="Server is still initialising. Please retry in a moment.",
            ),
            "UNKNOWN", None,
        )

    # ── Step 0: Instant hardcoded handler ─────────────────────────────────────
    conv = _handle_conversational(request.message)
    if conv is not None:
        logger.info("Hardcoded shortcut: %s", request.message[:60])
        return conv, "GREETING", None

    # ── Step 1: LLM intent classification ─────────────────────────────────────
    intent = classify_intent(request.message, request.history)
    logger.info("Intent: %s | %s", intent, request.message[:60])

    # ── Step 2a: GREETING (belt-and-suspenders) ───────────────────────────────
    if intent == "GREETING":
        return (
            ChatResponse(explanation=_GREETING_RESPONSE, code=None, language=None,
                         is_fallback=False, fallback_message=None),
            "GREETING", None,
        )

    # ── Step 2b: OFF_TOPIC ────────────────────────────────────────────────────
    if intent == "OFF_TOPIC":
        return (
            ChatResponse(explanation="", code=None, language=None,
                         is_fallback=True, fallback_message=INVALID_INTENT_MSG),
            "OFF_TOPIC", None,
        )

    # ── Steps 3–4 shared: summary + retrieval ────────────────────────────────
    summary = _get_summary(request.history)
    if summary:
        logger.info("Summary injected (%d chars)", len(summary))

    retrieval_query = build_retrieval_query(request.message, request.history)
    if retrieval_query != request.message:
        logger.info("Retrieval query enriched: %s", retrieval_query[:100])

    threshold = _THRESHOLD_CONVERSATION if intent == "CONVERSATION" else _THRESHOLD_CODE

    try:
        chunks = _retrieve(retrieval_query, threshold)
    except Exception as exc:
        logger.error("Retrieval error: %s", exc, exc_info=True)
        if intent == "CONVERSATION":
            chunks = []
        else:
            return (
                ChatResponse(explanation="", code=None, language=None,
                             is_fallback=True, fallback_message="Retrieval error. Please try again."),
                "CODE", None,
            )

    top_score: Optional[float] = chunks[0]["score"] if chunks else None

    # ── Knowledge base retrieval (user-scoped when auth'd, else session-scoped) ─
    knowledge_chunks: list[dict] = []
    if user_id or (request.session_id and request.session_id not in ("anon", "")):
        try:
            knowledge_chunks = _retrieve_knowledge(
                retrieval_query,
                session_id=request.session_id or "anon",
                user_id=user_id,
            )
            if knowledge_chunks:
                logger.info(
                    "Knowledge base: %d chunk(s) for %s",
                    len(knowledge_chunks),
                    f"user {user_id}" if user_id else f"session {request.session_id}",
                )
        except Exception as kexc:
            logger.warning("Knowledge retrieval error: %s", kexc)

    # ── Build merged context ──────────────────────────────────────────────────
    faiss_context = _retriever.format_context(chunks) if chunks else ""
    if knowledge_chunks:
        kb_text = "\n\n".join(
            f"[Knowledge Base — {c['source']}]\n{c['text']}"
            for c in knowledge_chunks
        )
        context = f"[User Knowledge Base]\n{kb_text}"
        if faiss_context:
            context += f"\n\n[Retrieved Documentation]\n{faiss_context}"
    else:
        context = faiss_context

    # Inject file attachment text ahead of retrieved docs
    if extra_context:
        file_section = f"[Attached file content]\n{extra_context}\n"
        context = (file_section + "\n[Retrieved documentation]\n" + context) if context else file_section

    # ── Step 3: CONVERSATION path ─────────────────────────────────────────────
    if intent == "CONVERSATION":
        if chunks:
            retrieval_result = check_retrieval_confidence(chunks, threshold=threshold)
            if retrieval_result in (RetrievalResult.NO_RESULTS, RetrievalResult.LOW_CONFIDENCE):
                context = ""

        raw = generate_conversational_response(
            context=context,
            question=request.message,
            history=request.history,
            summary=summary,
        )
        if raw is None:
            return (
                ChatResponse(explanation="", code=None, language=None,
                             is_fallback=True, fallback_message="API error. Please try again."),
                "CONVERSATION", top_score,
            )

        explanation, code, language = parse_llm_response(raw)
        return (
            ChatResponse(explanation=explanation, code=code, language=language,
                         is_fallback=False, fallback_message=None, attempts=1),
            "CONVERSATION", top_score,
        )

    # ── Step 4: CODE path ─────────────────────────────────────────────────────
    intent_result = check_intent(request.message)
    if intent_result == IntentResult.INVALID:
        logger.info("L1 rejected: %s", request.message[:60])
        return (
            ChatResponse(explanation="", code=None, language=None,
                         is_fallback=True, fallback_message=INVALID_INTENT_MSG),
            "CODE", None,
        )

    retrieval_result = check_retrieval_confidence(chunks, threshold=threshold)

    if retrieval_result == RetrievalResult.NO_RESULTS:
        logger.info("L2 rejected (no results): %s", request.message[:60])
        return (
            ChatResponse(explanation="", code=None, language=None,
                         is_fallback=True, fallback_message=NO_RESULTS_MSG),
            "CODE", None,
        )

    if retrieval_result == RetrievalResult.LOW_CONFIDENCE:
        logger.info("L2 rejected (low confidence): %s", request.message[:60])
        return (
            ChatResponse(explanation="", code=None, language=None,
                         is_fallback=True, fallback_message=LOW_CONFIDENCE_MSG),
            "CODE", None,
        )

    raw, attempts = generate_with_history_and_retry(
        context=context,
        question=request.message,
        history=request.history,
        summary=summary,
    )

    if raw is None:
        return (
            ChatResponse(explanation="", code=None, language=None,
                         is_fallback=True, fallback_message=VALIDATION_FALLBACK_MSG),
            "CODE", top_score,
        )

    explanation, code, language = parse_llm_response(raw)
    return (
        ChatResponse(explanation=explanation, code=code, language=language,
                     is_fallback=False, fallback_message=None, attempts=attempts),
        "CODE", top_score,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    user_id: Optional[str] = Depends(get_current_user),
):
    """Thin wrapper: runs _chat_logic then logs to Supabase (fire-and-forget)."""
    t0 = int(time.time() * 1000)
    session_id = request.session_id or "anon"

    _sb_save_message(session_id, "user", request.message, user_id=user_id)

    response, intent, top_score = _chat_logic(request, user_id=user_id)

    latency = int(time.time() * 1000) - t0
    _sb_save_message(session_id, "assistant", _response_text(response), user_id=user_id)
    _sb_log_query(session_id, request.message, response, intent, top_score, latency, user_id=user_id)
    if user_id and session_id not in ("anon", ""):
        _sb_upsert_session(session_id, user_id)

    return response


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
