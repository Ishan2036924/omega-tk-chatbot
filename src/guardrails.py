"""Hybrid two-layer guardrails for the Omega TK Chatbot.

Layer 1: Intent Check - Fast pre-filter for valid requests
Layer 2: Retrieval Confidence - Score-based validation
"""

from enum import Enum


class IntentResult(Enum):
    """Result of intent classification."""
    VALID = "valid"
    INVALID = "invalid"


# Signals indicating user wants code/implementation help or explanation
VALID_INTENT_SIGNALS = {
    # Code generation
    "how to", "how do i", "how can i",
    "generate", "create", "build", "make",
    "example", "code", "script", "implement",
    "write", "show me", "give me",
    # Explanation (valid - will answer with explanation + code)
    "what is", "what are", "what does",
    "explain", "describe", "tell me about",
    "help with", "help me",
    # Usage
    "use", "using", "run", "execute",
    "configure", "setup", "set up",
    "convert", "read", "write", "parse",
    "load", "save", "output", "input",
}

# Signals indicating off-topic or invalid requests
INVALID_INTENT_SIGNALS = {
    # Entertainment
    "poem", "poetry", "joke", "story", "song",
    "funny", "humor", "laugh",
    # General info
    "weather", "news", "sports", "stock",
    "recipe", "food", "movie", "music",
    # Jailbreak attempts
    "ignore", "forget", "disregard",
    "pretend", "roleplay", "act as",
    "bypass", "override",
    # Other off-topic
    "translate", "summarize this article",
    "who is", "where is", "when did",
}


def check_intent(query: str) -> IntentResult:
    """
    Layer 1: Check if the query has valid intent for Omega TK assistance.

    Valid intents:
    - Code generation requests ("how to", "generate", "create", etc.)
    - Explanation requests ("what is", "explain", etc.)

    Invalid intents:
    - Empty or whitespace-only queries
    - Off-topic requests (poems, jokes, weather, etc.)
    - Jailbreak attempts (ignore instructions, etc.)

    Args:
        query: User's input query

    Returns:
        IntentResult.VALID or IntentResult.INVALID
    """
    # Handle empty or whitespace-only queries
    if not query or not query.strip():
        return IntentResult.INVALID

    query_lower = query.lower().strip()

    # First check for invalid signals (blocklist takes priority)
    for signal in INVALID_INTENT_SIGNALS:
        if signal in query_lower:
            return IntentResult.INVALID

    # Then check for valid signals
    for signal in VALID_INTENT_SIGNALS:
        if signal in query_lower:
            return IntentResult.VALID

    # If no clear signal, default to valid and let retrieval decide
    # This avoids false rejections for legitimate but unusually phrased queries
    return IntentResult.VALID


class RetrievalResult(Enum):
    """Result of retrieval confidence check."""
    CONFIDENT = "confident"
    LOW_CONFIDENCE = "low_confidence"
    NO_RESULTS = "no_results"


def check_retrieval_confidence(
    chunks: list,
    threshold: float = 0.35
) -> RetrievalResult:
    """
    Layer 2: Check retrieval confidence based on similarity scores.

    Args:
        chunks: List of retrieved chunks with 'score' field
        threshold: Minimum score threshold (default 0.35)

    Returns:
        RetrievalResult indicating confidence level
    """
    if not chunks:
        return RetrievalResult.NO_RESULTS

    # Get scores from chunks
    scores = [chunk.get("score", 0) for chunk in chunks]

    # Check if any score meets threshold
    if any(score >= threshold for score in scores):
        return RetrievalResult.CONFIDENT

    return RetrievalResult.LOW_CONFIDENCE
