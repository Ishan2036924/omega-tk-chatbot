"""
Integration tests for the /api/chat endpoint and helper functions.

Tests are split into two groups:

  No-key tests  — run without OPENAI_API_KEY.  Tests the hardcoded
                  greeting/thanks/capabilities shortcuts and helper functions.

  Live tests    — skipped when OPENAI_API_KEY is absent.  Use the real
                  retriever + generator (loaded inline via patch) to test
                  the full off-topic → fallback, concept → explanation,
                  and code → code-block paths.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import app as app_module
from app import (
    app,
    _handle_conversational,
    build_retrieval_query,
    parse_llm_response,
    HistoryMessage,
)

HAS_OPENAI_KEY = bool(os.getenv("OPENAI_API_KEY"))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def pipeline_ready():
    """
    Patch _retriever and _generator to non-None stubs so _chat_logic() routes
    past the "pipeline not initialised" early-return guard.

    Only the hardcoded shortcut paths (greeting / thanks / capabilities) are
    reachable without a real API key — they return before classify_intent().
    """
    with patch.object(app_module, "_retriever", MagicMock()), \
         patch.object(app_module, "_generator", MagicMock(model="gpt-4o-mini")):
        yield


# ── parse_llm_response ────────────────────────────────────────────────────────

class TestParseResponse:
    def test_extracts_python_code_block(self):
        raw = "Here is the code:\n```python\nprint('hello')\n```"
        explanation, code, language = parse_llm_response(raw)
        assert code == "print('hello')"
        assert language == "python"
        assert "Here is the code" in explanation

    def test_no_code_block_returns_full_text_as_explanation(self):
        raw = "OEOmega is used for conformer generation."
        explanation, code, _ = parse_llm_response(raw)
        assert explanation == raw
        assert code is None

    def test_empty_response(self):
        explanation, code, _ = parse_llm_response("")
        assert explanation == ""
        assert code is None

    def test_bare_code_fence_still_parsed(self):
        raw = "```\nfrom openeye import oechem\n```"
        _, code, _ = parse_llm_response(raw)
        assert code == "from openeye import oechem"

    def test_explanation_before_code_is_preserved(self):
        raw = "This generates conformers.\n```python\nomega.Build(mol)\n```"
        explanation, code, _ = parse_llm_response(raw)
        assert "This generates conformers" in explanation
        assert code == "omega.Build(mol)"


# ── build_retrieval_query ─────────────────────────────────────────────────────

class TestBuildRetrievalQuery:
    def test_normal_query_unchanged(self):
        msg = "how do I generate conformers with OEOmega"
        assert build_retrieval_query(msg, []) == msg

    def test_short_followup_with_history_is_enriched(self):
        history = [HistoryMessage(role="user", content="generate conformers for aspirin")]
        result = build_retrieval_query("now use dense sampling", history)
        assert "context:" in result
        assert "aspirin" in result

    def test_long_query_not_treated_as_followup(self):
        long_msg = (
            "how do I configure OEOmegaOptions to use dense sampling "
            "with a maximum of 200 conformers and an energy window of 10 kcal/mol"
        )
        result = build_retrieval_query(
            long_msg,
            [HistoryMessage(role="user", content="previous question")],
        )
        assert result == long_msg  # too long to be enriched

    def test_empty_history_returns_original_query(self):
        result = build_retrieval_query("also add error handling", [])
        assert result == "also add error handling"

    def test_followup_signal_triggers_enrichment(self):
        history = [HistoryMessage(role="user", content="use OEOmega classic mode")]
        result = build_retrieval_query("change it to dense", history)
        assert "context:" in result


# ── _handle_conversational ────────────────────────────────────────────────────

class TestHandleConversational:
    def test_hi_returns_greeting_response(self):
        resp = _handle_conversational("hi")
        assert resp is not None
        assert resp.is_fallback is False
        assert "Omega TK" in resp.explanation

    def test_hello_with_exclamation_returns_greeting(self):
        resp = _handle_conversational("hello!")
        assert resp is not None
        assert "Omega TK" in resp.explanation

    def test_hey_returns_greeting(self):
        resp = _handle_conversational("hey")
        assert resp is not None

    def test_thanks_returns_welcome_response(self):
        resp = _handle_conversational("thanks")
        assert resp is not None
        assert "welcome" in resp.explanation.lower()

    def test_thank_you_is_matched(self):
        resp = _handle_conversational("thank you")
        assert resp is not None

    def test_what_can_you_do_returns_capabilities(self):
        resp = _handle_conversational("what can you do")
        assert resp is not None
        # capabilities response mentions at least one real feature
        assert any(kw in resp.explanation for kw in ["OEFlipper", "conformer", "Omega"])

    def test_technical_query_returns_none(self):
        resp = _handle_conversational("generate conformers using OEOmega classic sampling")
        assert resp is None

    def test_offtopic_query_returns_none(self):
        resp = _handle_conversational("what is the weather like today")
        assert resp is None


# ── HTTP endpoint: no-key tests ───────────────────────────────────────────────

async def test_chat_pipeline_not_ready_returns_fallback():
    """
    With no fixture, _retriever and _generator are None → pipeline guard fires
    and every chat request gets a 'still initialising' fallback.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"message": "hi", "history": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fallback"] is True
    assert "initialising" in (data.get("fallback_message") or "").lower()


async def test_chat_greeting_returns_hardcoded_response(pipeline_ready):
    """'hi' short-circuits inside _handle_conversational — no LLM call needed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"message": "hi", "history": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fallback"] is False
    assert "Omega TK" in data["explanation"]


async def test_chat_thanks_returns_hardcoded_response(pipeline_ready):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"message": "thanks", "history": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fallback"] is False
    assert "welcome" in data["explanation"].lower()


async def test_chat_capabilities_returns_hardcoded_response(pipeline_ready):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            json={"message": "what can you do", "history": []},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fallback"] is False


async def test_chat_session_id_accepted(pipeline_ready):
    """session_id field is forwarded without error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={
            "message": "hello",
            "history": [],
            "session_id": "test-session-abc123",
        })
    assert resp.status_code == 200


async def test_chat_history_field_accepted(pipeline_ready):
    """History messages are forwarded without error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={
            "message": "hi",
            "history": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        })
    assert resp.status_code == 200


# ── HTTP endpoint: live pipeline tests (need OPENAI_API_KEY) ─────────────────

def _real_pipeline():
    """Load the real retriever and generator once per live test."""
    from retriever import get_retriever
    from generator import get_generator
    return get_retriever(), get_generator()


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
async def test_live_offtopic_returns_fallback():
    """Off-topic query → LLM classifies as OFF_TOPIC → is_fallback=True."""
    retriever, generator = _real_pipeline()
    with patch.object(app_module, "_retriever", retriever), \
         patch.object(app_module, "_generator", generator):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/chat", json={
                "message": "what is the capital of France",
                "history": [],
            }, timeout=30.0)
    assert resp.status_code == 200
    assert resp.json()["is_fallback"] is True


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
async def test_live_concept_query_returns_explanation():
    """Concept query → CONVERSATION intent → explanation in response."""
    retriever, generator = _real_pipeline()
    with patch.object(app_module, "_retriever", retriever), \
         patch.object(app_module, "_generator", generator):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/chat", json={
                "message": "what is OEOmega",
                "history": [],
            }, timeout=30.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fallback"] is False
    assert data["explanation"]


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
async def test_live_code_query_returns_code_block():
    """Code query → CODE intent → code block present in response."""
    retriever, generator = _real_pipeline()
    with patch.object(app_module, "_retriever", retriever), \
         patch.object(app_module, "_generator", generator):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/chat", json={
                "message": "generate conformers for a molecule using OEOmega",
                "history": [],
            }, timeout=60.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fallback"] is False
    assert data["code"] is not None
    assert len(data["code"]) > 50   # non-trivial code block


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
async def test_live_attempts_field_present():
    """Code response should include an attempts count >= 1."""
    retriever, generator = _real_pipeline()
    with patch.object(app_module, "_retriever", retriever), \
         patch.object(app_module, "_generator", generator):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/chat", json={
                "message": "write code to enumerate stereoisomers with OEFlipper",
                "history": [],
            }, timeout=60.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("attempts", 0) >= 1
