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
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536

# Text splitting settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Retrieval settings
TOP_K = 5
SIMILARITY_THRESHOLD = 0.3

# LLM settings
OPENAI_MODEL = "gpt-4o-mini"

# Documentation URLs to scrape
DOC_URLS = [
    "https://docs.eyesopen.com/toolkits/python/omegatk/index.html",
    # Class references (corrected: OEConfGenClasses, not OEOmegaClasses)
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEConfGenClasses/OEOmega.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEConfGenClasses/OEOmegaOptions.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEConfGenClasses/OEFlipperOptions.html",
    # Constants pages — sampling modes and return codes
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEConfGenConstants/OEOmegaReturnCode.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/OEConfGenConstants/OEOmegaSampling.html",
    "https://docs.eyesopen.com/toolkits/python/omegatk/omegaexamples.html",
]
