"""Thin FastAPI entry-point for the Omega TK chatbot.

Exposes:
  GET  /health  — liveness probe → {"status": "ok"}
  POST /chat    — simplified chat API with session management

This wraps the existing pipeline in server/app.py without modifying it.
Session history is kept in memory keyed by session_id.
The RAG pipeline is initialised lazily on first /chat request.
"""

import sys
from pathlib import Path
from collections import defaultdict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Omega TK Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazily-loaded pipeline state
_pipeline_ready = False

# In-memory session store: session_id → list of HistoryMessage objects
_sessions: dict[str, list] = defaultdict(list)


def _ensure_pipeline():
    """Import and initialise the RAG pipeline on first use."""
    global _pipeline_ready
    if _pipeline_ready:
        return

    import app as _app_module  # noqa: F401 — triggers module-level imports
    from app import get_retriever, get_generator  # initialise global state
    import app as _m
    _m._retriever = get_retriever()
    _m._generator = get_generator()
    _pipeline_ready = True


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    response: str


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        _ensure_pipeline()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Pipeline unavailable: {exc}") from exc

    import app as _app_module

    history = _sessions[req.session_id]
    inner_req = _app_module.ChatRequest(message=req.message, history=history)
    result = _app_module.chat_endpoint(inner_req)

    # Flatten the rich response into a single string
    if result.is_fallback:
        response_text = result.fallback_message or "I'm unable to answer that question."
    else:
        parts = []
        if result.explanation:
            parts.append(result.explanation)
        if result.code:
            lang = result.language or "python"
            parts.append(f"```{lang}\n{result.code}\n```")
        response_text = "\n\n".join(parts) if parts else "No response generated."

    # Update session history (keep last 6 turns)
    history.append(_app_module.HistoryMessage(role="user", content=req.message))
    history.append(_app_module.HistoryMessage(role="assistant", content=response_text))
    _sessions[req.session_id] = history[-12:]

    return ChatResponse(response=response_text)
