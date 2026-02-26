"""
Omega TK RAG Chatbot — Streamlit UI
Uses the same pipeline as chat.py (guardrails + retriever + generator).
Run from repo root: streamlit run app.py
"""

import sys
from pathlib import Path

# Add src/ to path so we can import streamlit_backend and it can import guardrails, retriever, etc.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st
import streamlit.components.v1 as components
import json

# Page config (must be first Streamlit command)
st.set_page_config(
    page_title="Omega TK Code Assistant",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-family: 'Georgia', 'Cambria', serif; color: #0d7377; font-weight: 600; margin-bottom: 0.25rem; }
    .sub-header { color: #5c5c5c; font-size: 0.95rem; margin-bottom: 1.5rem; }
    .explanation-box {
        background: linear-gradient(135deg, #e8e8e8 0%, #f0f0f0 100%);
        border-left: 4px solid #0d7377;
        padding: 1rem 1.25rem; margin: 0.75rem 0 0.5rem 0;
        border-radius: 0 8px 8px 0; font-size: 0.95rem; line-height: 1.5; color: #2d2d2d;
    }
    div[data-testid="stCodeBlock"] {
        background: #1e1e1e !important; border-radius: 8px; padding: 1rem 1.25rem;
        margin: 0.5rem 0 0.25rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    div[data-testid="stCodeBlock"] pre { margin: 0; color: #d4d4d4; }
    .guardrail-box { padding: 1rem 1.25rem; margin: 0.75rem 0 1.25rem 0; border-radius: 0 8px 8px 0; font-size: 0.95rem; line-height: 1.5; }
    .guardrail-box.invalid-intent { background: #e3f2fd; border-left: 4px solid #1976d2; color: #0d47a1; }
    .guardrail-box.no-results { background: #fff3e0; border-left: 4px solid #e65100; color: #5c2e00; }
    .guardrail-box.low-confidence { background: #fff8e6; border-left: 4px solid #e6a800; color: #5c4a00; }
    .guardrail-box a { color: inherit; text-decoration: underline; }
    .user-msg {
        background: #e3f2fd; border-radius: 12px 12px 4px 12px; padding: 0.75rem 1rem;
        margin: 0.5rem 0 0.5rem auto; max-width: 85%; margin-left: auto; border: 1px solid #90caf9;
    }
    [data-testid="stSidebar"] .sidebar-title { font-weight: 600; color: #0d7377; margin-top: 1rem; }
    #MainMenu { visibility: hidden; } footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

OFFICIAL_DOCS_URL = "https://docs.eyesopen.com/toolkits/python/omegatk/"

GUARDRAIL_RESPONSES = {
    "invalid_intent": (
        "I'm designed to help with OpenEye Omega Toolkit code and questions. "
        "I can help you generate conformers, enumerate stereoisomers, and write Omega TK code. "
        "What would you like to build?"
    ),
    "no_results": (
        "I don't have information about this in my knowledge base. "
        "This might be outside the scope of the Omega Toolkit, or try rephrasing. "
        f"Official docs: {OFFICIAL_DOCS_URL}"
    ),
    "low_confidence": (
        "I'm not confident I have accurate information about this specific topic. "
        "Try rephrasing your question, or check the official docs: "
        f"{OFFICIAL_DOCS_URL}"
    ),
}


def render_copy_button(code: str, key_suffix: str) -> None:
    code_escaped = json.dumps(code)
    html = f"""
    <div style="margin-top: 0.5rem;">
        <button id="copy-btn-{key_suffix}" type="button" style="background: #0d7377; color: white; border: none; padding: 0.4rem 0.9rem; border-radius: 6px; font-size: 0.85rem; cursor: pointer;">Copy code</button>
        <span id="copy-msg-{key_suffix}" style="margin-left: 0.5rem; font-size: 0.85rem; color: #0d7377;"></span>
    </div>
    <script>
        (function() {{
            var code = {code_escaped};
            var btn = document.getElementById('copy-btn-{key_suffix}');
            var msg = document.getElementById('copy-msg-{key_suffix}');
            btn.addEventListener('click', function() {{
                navigator.clipboard.writeText(code).then(function() {{
                    msg.textContent = 'Copied!';
                    setTimeout(function() {{ msg.textContent = ''; }}, 2000);
                }});
            }});
        }})();
    </script>
    """
    components.html(html, height=50)


def backend_query(question: str) -> dict:
    """Call the real RAG pipeline and return {path, explanation, code}."""
    try:
        from streamlit_backend import get_chat_response
        return get_chat_response(question)
    except FileNotFoundError as e:
        return {
            "path": "no_results",
            "explanation": (
                "FAISS index not found. Run **python src/ingest.py** from the project root to build the index, then restart the app."
            ),
            "code": None,
        }
    except ValueError as e:
        if "OPENAI_API_KEY" in str(e):
            return {
                "path": "no_results",
                "explanation": "**OPENAI_API_KEY** is not set. Create a `.env` file in the project root with your OpenAI API key.",
                "code": None,
            }
        raise


if "messages" not in st.session_state:
    st.session_state.messages = []


# Sidebar
with st.sidebar:
    st.markdown("### Omega TK Code Assistant")
    st.markdown("*RAG chatbot for OpenEye conformer generation*")
    st.markdown("---")
    st.markdown('<p class="sidebar-title">Try an example</p>', unsafe_allow_html=True)
    examples = [
        "Generate conformers for one molecule from an input file and write output",
        "Generate conformers for a database of molecules (loop over stream)",
        "Enumerate unspecified stereochemistry (Flipper) and write isomers",
        "How to set maximum number of conformers?",
        "How do I handle Omega return codes?",
    ]
    for i, ex in enumerate(examples):
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.prefill_query = ex
            st.rerun()
    st.markdown("---")
    st.caption("**Guardrail tests:**")
    for i, text in enumerate(["What's the weather today?", "How do I use pandas dataframe?"]):
        if st.button(text, key=f"guard_{i}", use_container_width=True):
            st.session_state.prefill_query = text
            st.rerun()
    st.markdown("---")
    st.markdown("**In scope:** conformers, Flipper, Omega options, error handling.")
    with st.expander("Guardrail paths"):
        st.caption("**success** — Code generated. **invalid_intent** — Off-topic. **no_results** — No docs. **low_confidence** — Score < 0.35.")
    st.caption("AAI 6670 — Northeastern University")


# Main
st.markdown('<p class="main-header">Omega TK Intelligent Code Assistant</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Ask about OpenEye Omega TK. Get explanation and Python code grounded in the docs.</p>',
    unsafe_allow_html=True,
)

query_input_placeholder = "e.g. Generate conformers for one molecule from an input file"
if "prefill_query" in st.session_state:
    query_input_placeholder = st.session_state.prefill_query
    del st.session_state.prefill_query

user_query = st.chat_input("Ask about Omega TK...")
if user_query is None and "prefill_query" not in st.session_state and query_input_placeholder != "e.g. Generate conformers for one molecule from an input file":
    user_query = query_input_placeholder


def render_guardrail_message(path: str, explanation: str) -> None:
    css_class = path.replace("_", "-")
    text = explanation.replace(
        OFFICIAL_DOCS_URL,
        f'<a href="{OFFICIAL_DOCS_URL}" target="_blank" rel="noopener">Official docs</a>',
    )
    st.markdown(f'<div class="guardrail-box {css_class}">{text}</div>', unsafe_allow_html=True)


for idx, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        path = msg.get("path", "success")
        if path in ("invalid_intent", "no_results", "low_confidence"):
            render_guardrail_message(path, msg.get("explanation") or GUARDRAIL_RESPONSES.get(path, ""))
        else:
            if msg.get("explanation"):
                st.markdown(f'<div class="explanation-box">{msg["explanation"]}</div>', unsafe_allow_html=True)
            if msg.get("code"):
                st.code(msg["code"], language="python")
                render_copy_button(msg["code"], str(idx))

if user_query:
    user_query = user_query.strip()
    if not user_query:
        st.stop()
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.spinner("Searching docs and generating code..."):
        result = backend_query(user_query)
    st.session_state.messages.append({
        "role": "assistant",
        "path": result.get("path", "success"),
        "explanation": result.get("explanation"),
        "code": result.get("code"),
    })
    st.rerun()
