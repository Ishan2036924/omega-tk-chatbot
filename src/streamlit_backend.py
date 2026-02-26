"""
Backend adapter for Streamlit UI: runs the same pipeline as chat.py
but returns structured {path, explanation, code} for the UI.

Expects to be imported with src/ on sys.path (app.py adds it).
"""

import re

from guardrails import (
    check_intent,
    check_retrieval_confidence,
    IntentResult,
    RetrievalResult,
)
from fallback_responses import (
    INVALID_INTENT_MSG,
    LOW_CONFIDENCE_MSG,
    NO_RESULTS_MSG,
)

OFFICIAL_DOCS_URL = "https://docs.eyesopen.com/toolkits/python/omegatk/"


def _parse_llm_response(response: str) -> tuple[str | None, str | None]:
    """
    Parse LLM output into explanation (before code block) and code (inside block).
    Expects format: optional text, then ```python ... ``` or ``` ... ```
    """
    if not response or not response.strip():
        return None, None

    # Match ```python ... ``` or ``` ... ```
    code_block = re.search(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if code_block:
        code = code_block.group(1).strip()
        explanation = response[: code_block.start()].strip()
        if not explanation:
            explanation = None
        return explanation or None, code

    # No code block: treat full response as explanation
    return response.strip(), None


def get_chat_response(query: str) -> dict:
    """
    Run the full RAG pipeline (guardrails + retriever + generator) and return
    a dict suitable for the Streamlit UI.

    Returns:
        dict with keys: path ("success" | "invalid_intent" | "no_results" | "low_confidence"),
                       explanation (str | None), code (str | None)
    """
    # Layer 1: Intent check
    intent_result = check_intent(query)
    if intent_result == IntentResult.INVALID:
        return {
            "path": "invalid_intent",
            "explanation": INVALID_INTENT_MSG,
            "code": None,
        }

    # Lazy load retriever and generator (they load FAISS and OpenAI on first use)
    from retriever import get_retriever
    from generator import get_generator

    retriever = get_retriever()
    chunks = retriever.retrieve(query)
    retrieval_result = check_retrieval_confidence(chunks)

    if retrieval_result == RetrievalResult.NO_RESULTS:
        return {
            "path": "no_results",
            "explanation": NO_RESULTS_MSG,
            "code": None,
        }

    if retrieval_result == RetrievalResult.LOW_CONFIDENCE:
        return {
            "path": "low_confidence",
            "explanation": LOW_CONFIDENCE_MSG,
            "code": None,
        }

    # Success: generate and parse
    context = retriever.format_context(chunks)
    generator = get_generator()
    response = generator.generate(context=context, question=query)
    explanation, code = _parse_llm_response(response)

    return {
        "path": "success",
        "explanation": explanation,
        "code": code,
    }
