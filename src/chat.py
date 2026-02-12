"""Chat module for the Omega TK RAG Chatbot with hybrid guardrails."""

import logging

from retriever import get_retriever
from generator import get_generator
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Chat:
    """Main chat interface with hybrid two-layer guardrails."""

    def __init__(self):
        """Initialize chat with retriever and generator."""
        self.retriever = get_retriever()
        self.generator = get_generator()

    def respond(self, query: str) -> str:
        """
        Process a user query through the two-layer guardrail system.

        Layer 1: Intent check (fast pre-filter)
        Layer 2: Retrieval confidence (score-based validation)

        Args:
            query: User's question

        Returns:
            Response string (generated code or fallback message)
        """
        # Layer 1: Intent Check
        intent_result = check_intent(query)
        if intent_result == IntentResult.INVALID:
            logger.info("Path: invalid_intent - Query rejected by intent check")
            return INVALID_INTENT_MSG

        # Layer 2: Retrieval + Confidence Check
        chunks = self.retriever.retrieve(query)
        retrieval_result = check_retrieval_confidence(chunks)

        if retrieval_result == RetrievalResult.NO_RESULTS:
            logger.info("Path: no_results - No chunks retrieved")
            return NO_RESULTS_MSG

        if retrieval_result == RetrievalResult.LOW_CONFIDENCE:
            logger.info("Path: low_confidence - Retrieval scores below threshold")
            return LOW_CONFIDENCE_MSG

        # Both layers passed - generate response
        logger.info("Path: success - Generating response")
        context = self.retriever.format_context(chunks)
        response = self.generator.generate(context=context, question=query)

        return response


# Singleton instance
_chat = None


def get_chat() -> Chat:
    """Get or create the singleton chat instance."""
    global _chat
    if _chat is None:
        _chat = Chat()
    return _chat


def main():
    """Simple REPL for testing the chatbot."""
    print("=" * 60)
    print("Omega TK RAG Chatbot")
    print("Type 'quit' to exit")
    print("=" * 60)

    chat = get_chat()

    while True:
        try:
            query = input("\nYou: ").strip()
            if query.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if not query:
                print("Please enter a question about Omega TK.")
                continue

            response = chat.respond(query)
            print(f"\nAssistant: {response}")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
