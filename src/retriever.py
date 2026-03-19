"""Retriever module for finding relevant chunks from the FAISS index."""

import os
import json
import faiss
import numpy as np
from openai import OpenAI

from config import (
    FAISS_INDEX_PATH,
    CHUNKS_PATH,
    EMBEDDING_MODEL,
    TOP_K,
    SIMILARITY_THRESHOLD,
)


class Retriever:
    """Retrieves relevant chunks from the FAISS index."""

    def __init__(self):
        """Initialize the retriever by loading index and chunks."""
        print("Loading retriever...")

        # Load FAISS index
        if not FAISS_INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {FAISS_INDEX_PATH}. "
                "Run 'python src/ingest.py' first to build the index."
            )
        self.index = faiss.read_index(str(FAISS_INDEX_PATH))
        print(f"  Loaded FAISS index with {self.index.ntotal} vectors")

        # Load chunks
        if not CHUNKS_PATH.exists():
            raise FileNotFoundError(
                f"Chunks file not found at {CHUNKS_PATH}. "
                "Run 'python src/ingest.py' first to build the index."
            )
        with open(CHUNKS_PATH, "r") as f:
            self.chunks = json.load(f)
        print(f"  Loaded {len(self.chunks)} chunks")

        # OpenAI client for embeddings
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        print(f"  Using OpenAI embedding model: {EMBEDDING_MODEL}")
        print("Retriever ready!")

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a query string using OpenAI embeddings."""
        response = self.client.embeddings.create(
            input=[query],
            model=EMBEDDING_MODEL,
        )
        embedding = np.array([response.data[0].embedding], dtype=np.float32)
        # Normalize for cosine similarity (IndexFlatIP)
        embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
        return embedding

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """
        Retrieve the most relevant chunks for a query.

        Args:
            query: The user's question
            top_k: Number of results to return

        Returns:
            List of chunk dictionaries with added 'score' field,
            filtered by similarity threshold. Returns empty list if
            no chunks meet the threshold.
        """
        query_embedding = self.embed_query(query)

        scores, indices = self.index.search(query_embedding, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty slots
                continue
            if score >= SIMILARITY_THRESHOLD:
                chunk = self.chunks[idx].copy()
                chunk["score"] = float(score)
                results.append(chunk)

        return results

    def format_context(self, chunks: list[dict]) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        if not chunks:
            return "No relevant context found."

        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("type", "unknown")
            score = chunk.get("score", 0)
            context_parts.append(
                f"### Context {i} (source: {source}, relevance: {score:.2f})\n{chunk['text']}"
            )

        return "\n\n".join(context_parts)


# Singleton instance for reuse
_retriever = None


def get_retriever() -> Retriever:
    """Get or create the singleton retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
