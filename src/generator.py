"""Generator module for calling OpenAI LLM to generate responses."""

import os
from dotenv import load_dotenv
from openai import OpenAI

from config import OPENAI_MODEL
from prompts import build_prompt

# Load environment variables
load_dotenv()


class Generator:
    """Generates responses using OpenAI LLM."""

    def __init__(self):
        """Initialize the generator with OpenAI API."""
        print("Initializing generator...")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Create a .env file with your API key."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = OPENAI_MODEL
        print(f"  Using model: {self.model}")
        print("Generator ready!")

    def generate(self, context: str, question: str) -> str:
        """
        Generate a response using the LLM.

        Args:
            context: Retrieved context chunks formatted as string
            question: User's question

        Returns:
            Generated response from the LLM
        """
        # Build the full prompt
        prompt = build_prompt(context=context, question=question)

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2048,
        )

        return response.choices[0].message.content


# Singleton instance for reuse
_generator = None


def get_generator() -> Generator:
    """Get or create the singleton generator instance."""
    global _generator
    if _generator is None:
        _generator = Generator()
    return _generator
