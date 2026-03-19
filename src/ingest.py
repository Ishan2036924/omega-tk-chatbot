"""Ingest pipeline for building the FAISS index from training data and scraped docs."""

import os
import json
import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
import faiss
import numpy as np
from dotenv import load_dotenv

load_dotenv()

from config import (
    TRAINING_PROMPTS_PATH,
    DOC_URLS,
    DOCS_DIR,
    FAISS_INDEX_PATH,
    CHUNKS_PATH,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)

_openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def load_training_prompts() -> list[dict]:
    """Load training prompts from JSON file."""
    print(f"Loading training prompts from {TRAINING_PROMPTS_PATH}...")
    with open(TRAINING_PROMPTS_PATH, "r") as f:
        prompts = json.load(f)
    print(f"Loaded {len(prompts)} training prompts")
    return prompts


def scrape_url(url: str) -> str:
    """Scrape text content from a URL."""
    print(f"Scraping: {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get main content - try common content selectors
        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="document")
        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        return text.strip()
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""


def scrape_documentation() -> list[str]:
    """Scrape all documentation URLs."""
    print("\nScraping documentation...")
    docs = []
    for url in DOC_URLS:
        content = scrape_url(url)
        if content:
            docs.append(content)
            # Save to docs directory
            filename = url.split("/")[-1].replace(".html", ".txt")
            if not filename or filename == "":
                filename = "index.txt"
            filepath = DOCS_DIR / filename
            with open(filepath, "w") as f:
                f.write(content)
            print(f"  Saved to {filepath} ({len(content)} chars)")
    print(f"Scraped {len(docs)} documentation pages")
    return docs


def create_chunks(training_prompts: list[dict], doc_texts: list[str]) -> list[dict]:
    """Create chunks from training prompts and documentation."""
    chunks = []

    # Training prompts: keep each Q&A as ONE chunk (don't split)
    print("\nProcessing training prompts as single chunks...")
    for i, prompt in enumerate(training_prompts):
        chunk_text = f"Question: {prompt['question']}\n\nCode:\n```python\n{prompt['code']}\n```"
        chunks.append({
            "id": f"training_{i}",
            "text": chunk_text,
            "source": "training_prompts",
            "type": "qa_pair"
        })
    print(f"Created {len(training_prompts)} training prompt chunks")

    # Documentation: split into smaller chunks
    print("\nChunking documentation...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    doc_chunk_count = 0
    for doc_idx, doc_text in enumerate(doc_texts):
        doc_chunks = splitter.split_text(doc_text)
        for chunk_idx, chunk_text in enumerate(doc_chunks):
            if chunk_text.strip():
                chunks.append({
                    "id": f"doc_{doc_idx}_{chunk_idx}",
                    "text": chunk_text.strip(),
                    "source": f"doc_{doc_idx}",
                    "type": "documentation"
                })
                doc_chunk_count += 1
    print(f"Created {doc_chunk_count} documentation chunks")

    print(f"\nTotal chunks: {len(chunks)}")
    return chunks


def build_embeddings(chunks: list[dict]) -> np.ndarray:
    """Generate embeddings for all chunks using OpenAI API (batched)."""
    print("\nGenerating embeddings with OpenAI...")
    texts = [chunk["text"] for chunk in chunks]

    BATCH_SIZE = 100  # OpenAI allows up to 2048 inputs per request
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        print(f"  Embedding batch {i // BATCH_SIZE + 1}/{(len(texts) + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)} chunks)...")
        response = _openai_client.embeddings.create(
            input=batch,
            model=EMBEDDING_MODEL,
        )
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    embeddings = np.array(all_embeddings, dtype=np.float32)
    # Normalize for cosine similarity (IndexFlatIP)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    print(f"Generated {len(embeddings)} embeddings of dimension {embeddings.shape[1]}")
    return embeddings


def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build FAISS index using inner product (cosine similarity with normalized vectors)."""
    print("\nBuilding FAISS index...")
    index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
    index.add(embeddings.astype(np.float32))
    print(f"FAISS index built with {index.ntotal} vectors")
    return index


def save_index_and_chunks(index: faiss.IndexFlatIP, chunks: list[dict]):
    """Save FAISS index and chunks to disk."""
    print("\nSaving to disk...")
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"Saved FAISS index to {FAISS_INDEX_PATH}")

    with open(CHUNKS_PATH, "w") as f:
        json.dump(chunks, f, indent=2)
    print(f"Saved chunks to {CHUNKS_PATH}")


def main():
    """Run the full ingestion pipeline."""
    print("=" * 60)
    print("Omega TK RAG Chatbot - Ingestion Pipeline")
    print("=" * 60)

    # Load training prompts
    training_prompts = load_training_prompts()

    # Scrape documentation
    doc_texts = scrape_documentation()

    # Create chunks
    chunks = create_chunks(training_prompts, doc_texts)

    # Build embeddings
    print(f"\nUsing OpenAI embedding model: {EMBEDDING_MODEL}")
    embeddings = build_embeddings(chunks)

    # Build FAISS index
    index = build_faiss_index(embeddings)

    # Save everything
    save_index_and_chunks(index, chunks)

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
