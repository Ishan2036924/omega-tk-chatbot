"""Fallback responses for the Omega TK Chatbot."""

# Layer 1: Intent check failures
INVALID_INTENT_MSG = (
    "I'm designed to help with OpenEye Omega Toolkit code and questions. "
    "I can help you generate conformers, enumerate stereoisomers, and write "
    "Omega TK code. What would you like to build?"
)

# Layer 2: Retrieval confidence failures
LOW_CONFIDENCE_MSG = (
    "I'm not confident I have accurate information about this specific topic. "
    "Try rephrasing your question, or check the official docs: "
    "https://docs.eyesopen.com/toolkits/python/omegatk/"
)

NO_RESULTS_MSG = (
    "I don't have information about this in my knowledge base. "
    "This might be outside the scope of the Omega Toolkit, or try rephrasing. "
    "Official docs: https://docs.eyesopen.com/toolkits/python/omegatk/"
)

# Legacy (kept for compatibility)
UNSAFE_QUERY_MSG = "I can only help with Omega TK code generation questions."
