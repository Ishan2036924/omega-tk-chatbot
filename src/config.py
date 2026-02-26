"""Configuration settings for Omega TK RAG Chatbot."""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DOCS_DIR = RAW_DIR / "docs"

# Ensure directories exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Training data path
TRAINING_PROMPTS_PATH = RAW_DIR / "training_prompts.json"

# Processed data paths
FAISS_INDEX_PATH = PROCESSED_DIR / "faiss.index"
CHUNKS_PATH = PROCESSED_DIR / "chunks.json"

# Embedding model settings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Text splitting settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Retrieval settings
TOP_K = 3
SIMILARITY_THRESHOLD = 0.3

# LLM settings
OPENAI_MODEL = "gpt-4o-mini"

# Documentation URLs to scrape
DOC_URLS = [
    "https://docs.eyesopen.com/toolkits/python/omegatk/index.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEOmegaClasses/OEOmega.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEOmegaClasses/OEOmegaOptions.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEOmegaClasses/OEFlipperOptions.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/omegaexamples.html",
]
