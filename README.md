# Omega TK RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that helps developers write Python code for the **OpenEye Omega Toolkit**—a molecular modeling library for conformer generation and stereochemistry enumeration.

## What Problem Does This Solve?

The OpenEye Omega Toolkit has a steep learning curve. Developers often need to:
- Search through extensive documentation
- Understand the 5-step pattern (streams → options → engine → build → error handling)
- Find working code examples for specific use cases

This chatbot **retrieves relevant documentation** and **generates working Python code** on demand, reducing the time from question to working code from minutes to seconds.

**Built for:** Computational chemists, cheminformatics developers, and researchers using OpenEye toolkits.

---

## Features

- [x] **Code Generation** — Generates complete, working Python scripts for Omega TK
- [x] **Semantic Search** — Finds relevant documentation using vector similarity
- [x] **Guardrail System** — Two-layer protection against hallucination and off-topic queries
- [x] **32 Curated Examples** — Pre-loaded Q&A pairs covering common use cases
- [x] **CLI Interface** — Simple command-line chat loop
- [x] **Zero Infrastructure** — No external databases or paid vector services

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RUNTIME FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User Query: "Generate conformers for a molecule"                          │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────┐                                                       │
│   │  LAYER 1        │  ✗ "What's the weather?" → REJECTED                   │
│   │  Intent Check   │  ✗ "Write a poem" → REJECTED                          │
│   │  (guardrails)   │  ✓ "Generate conformers" → PASS                       │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────┐      ┌────────────────┐                               │
│   │  retriever.py   │─────►│  FAISS Index   │                               │
│   │  (embed query)  │◄─────│  (91 vectors)  │                               │
│   └────────┬────────┘      └────────────────┘                               │
│            │ top-3 chunks + similarity scores                               │
│            ▼                                                                │
│   ┌─────────────────┐                                                       │
│   │  LAYER 2        │  ✗ score < 0.35 → "I'm not confident..."              │
│   │  Confidence     │  ✗ no results → "I don't have info..."                │
│   │  Check          │  ✓ score ≥ 0.35 → PASS                                │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────┐      ┌────────────────┐                               │
│   │  generator.py   │─────►│  OpenAI API    │                               │
│   │  (build prompt) │◄─────│  (GPT-4o-mini) │                               │
│   └────────┬────────┘      └────────────────┘                               │
│            │                                                                │
│            ▼                                                                │
│   Python Code Output with explanation                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Overview

| Component | File | Purpose |
|-----------|------|---------|
| **Chat Interface** | `chat.py` | CLI loop, orchestrates the full pipeline |
| **Guardrails** | `guardrails.py` | Intent check + confidence validation |
| **Retriever** | `retriever.py` | Embeds queries, searches FAISS, returns chunks |
| **Generator** | `generator.py` | Builds prompts, calls OpenAI API |
| **Ingestion** | `ingest.py` | Scrapes docs, builds embeddings, creates index |

---

## Tech Stack & Design Choices

| Technology | Purpose | Why This Choice |
|------------|---------|-----------------|
| **FAISS** | Vector search | Free, runs locally, no API costs. Pinecone/Weaviate require paid tiers for production. |
| **GPT-4o-mini** | Code generation | Best cost/quality ratio ($0.15/1M tokens). |
| **all-MiniLM-L6-v2** | Embeddings | Fast (384 dims), free, runs on CPU. OpenAI embeddings cost $0.02/1M tokens. |
| **LangChain TextSplitter** | Chunking | Recursive splitting preserves context better than naive splitting. |
| **Python + CLI** | Interface | Simple PoC. No frontend framework overhead. |

**Zero-Budget Constraint:** This project was designed to run entirely on free tiers and local compute. No paid vector databases, no GPU requirements, minimal API costs (~$0.01 per conversation).

---

## Project Structure

```
omega-tk-chatbot/
├── src/
│   ├── chat.py               # Main entry point, CLI interface
│   ├── guardrails.py         # Two-layer guardrail system
│   ├── fallback_responses.py # Predefined rejection messages
│   ├── retriever.py          # FAISS search + query embedding
│   ├── generator.py          # OpenAI LLM integration
│   ├── ingest.py             # Build index from docs + training data
│   ├── prompts.py            # System prompt with 5-step pattern
│   ├── config.py             # All settings (paths, models, thresholds)
│   └── test_guardrails.py    # Unit tests for guardrails
├── data/
│   ├── raw/
│   │   ├── training_prompts.json   # 32 curated Q&A pairs
│   │   └── docs/                   # Scraped OpenEye documentation
│   └── processed/
│       ├── faiss.index             # Vector index (91 vectors)
│       └── chunks.json             # Text chunks with metadata
├── .env                      # API keys (not in repo)
├── .env.example              # Template for .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

### Step 1: Clone and Setup Environment

```bash
git clone <repository-url>
cd omega-tk-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure API Key

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-api-key-here
```

### Step 3: Build the Index (One Time)

```bash
python src/ingest.py
```

This will:
1. Load 32 training Q&A pairs from `training_prompts.json`
2. Scrape OpenEye documentation (5 pages)
3. Chunk text into 500-character segments
4. Generate embeddings with `all-MiniLM-L6-v2`
5. Build FAISS index and save to `data/processed/`

### Step 4: Run the Chatbot

```bash
python src/chat.py
```

---

## Usage

### Running the Chatbot

```bash
cd omega-tk-chatbot
source venv/bin/activate
python src/chat.py
```

### Example Queries

| Query Type | Example |
|------------|---------|
| Single molecule | "Generate conformers for one molecule from an input file" |
| Database processing | "Generate conformers for a database of molecules" |
| Stereochemistry | "Enumerate stereoisomers with Flipper" |
| Configuration | "Set Omega options for Dense sampling" |
| Error handling | "How do I handle Omega return codes?" |

---

## Guardrail System

The chatbot uses a **two-layer guardrail system** to prevent hallucination and reject off-topic queries.

### Why Two Layers?

| Layer | Purpose | Speed | What It Catches |
|-------|---------|-------|-----------------|
| **Layer 1: Intent** | Fast pre-filter | ~0ms | Off-topic queries, jailbreak attempts |
| **Layer 2: Confidence** | Accuracy gate | ~50ms | Questions outside knowledge base |

### Layer 1: Intent Check

Examines query text for signal words:

```python
# VALID signals (pass through)
"how to", "generate", "create", "what is", "explain", "example", "code"

# INVALID signals (rejected immediately)
"poem", "joke", "weather", "news", "ignore", "pretend", "bypass"
```

- Blocklist is checked first (catches "ignore instructions and generate code")
- Ambiguous queries default to valid (let Layer 2 decide)

### Layer 2: Retrieval Confidence

After retrieval, checks similarity scores:

| Condition | Response |
|-----------|----------|
| No chunks retrieved | "I don't have information about this..." |
| Max score < 0.35 | "I'm not confident I have accurate information..." |
| Max score ≥ 0.35 | Proceed to code generation |

### Examples

| Query | Layer 1 | Layer 2 | Result |
|-------|---------|---------|--------|
| "What's the weather?" | REJECTED | — | Invalid intent message |
| "Write a poem about molecules" | REJECTED | — | Invalid intent message |
| "Generate conformers" | PASS | PASS | Generated code |
| "Explain OEOmega options" | PASS | PASS | Explanation + code |

---

## Example Outputs

### Query 1: Single Molecule Conformer Generation

**User:** "Generate conformers for one molecule from an input file and write output."

**Response:**

This code reads a single molecule from an input file, generates conformers using the OpenEye Omega Toolkit, and writes the resulting conformers to an output file.

```python
from openeye import oechem, oeomega
import argparse

parser = argparse.ArgumentParser(description='Generate conformers for a single molecule.')
parser.add_argument('input', help='Input molecule file')
parser.add_argument('output', help='Output conformer file')
args = parser.parse_args()

ifs = oechem.oemolistream(args.input)
ofs = oechem.oemolostream(args.output)

mol = oechem.OEMol()
oechem.OEReadMolecule(ifs, mol)

opts = oeomega.OEOmegaOptions(oeomega.OEOmegaSampling_Classic)
omega = oeomega.OEOmega(opts)

ret_code = omega.Build(mol)
if ret_code == oeomega.OEOmegaReturnCode_Success:
    oechem.OEWriteMolecule(ofs, mol)
else:
    print(oeomega.OEGetOmegaError(ret_code))

ofs.close()
```

---

### Query 2: Stereoisomer Enumeration

**User:** "Enumerate unspecified stereochemistry (Flipper) and write isomers."

**Response:**

This code enumerates unspecified stereochemistry for molecules using OEFlipper and writes the generated isomers to an output file.

```python
from openeye import oechem, oeomega
from sys import argv

ifs = oechem.oemolistream(argv[1])
ofs = oechem.oemolostream(argv[2])

opts = oeomega.OEFlipperOptions()

for mol in ifs.GetOEMols():
    for isomer in oeomega.OEFlipper(mol, opts):
        oechem.OEWriteMolecule(ofs, isomer)

ofs.close()
```

---

### Query 3: Guardrail Rejection

**User:** "What's the weather?"

**Response:**

I'm designed to help with OpenEye Omega Toolkit code and questions. I can help you generate conformers, enumerate stereoisomers, and write Omega TK code. What would you like to build?

---

## Limitations & Future Improvements

### Current Limitations

| Limitation | Impact |
|------------|--------|
| **CLI only** | No web interface or API endpoint |
| **English only** | No multilingual support |
| **Limited docs** | Only 5 OpenEye pages scraped (some returned 404) |
| **No conversation memory** | Each query is independent |
| **No code execution** | Cannot test generated code |

### Future Improvements

| Improvement | Benefit |
|-------------|---------|
| **Web UI** | Streamlit or Gradio interface for easier access |
| **More documentation** | Scrape full OpenEye toolkit docs |
| **Better embeddings** | Use OpenAI `text-embedding-3-small` for higher quality |
| **Conversation memory** | Track context across multiple queries |
| **Code validation** | Syntax check generated code before returning |
| **Fine-tuned model** | Train on OpenEye-specific code patterns |
| **Multi-toolkit support** | Extend to OEChem, GraphSim, other OpenEye tools |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "FAISS index not found" | Run `python src/ingest.py` first |
| "OPENAI_API_KEY not set" | Create `.env` file with your API key |
| Slow first query | Embedding model loads on first use; subsequent queries are faster |
| "I'm not confident..." | Rephrase question to be more specific about Omega TK |

---

## License

MIT License

---

## Acknowledgments

- **OpenEye Scientific Software** — For the Omega Toolkit and documentation
- **OpenAI** — GPT-4o-mini for code generation
- **Hugging Face** — sentence-transformers for embeddings
- **Meta AI** — FAISS for vector search

---

## Academic Context

This project was developed as a proof-of-concept for **AAI 6670 - Conversational AI** to demonstrate:

1. RAG architecture for domain-specific code generation
2. Guardrail systems for LLM safety
3. Cost-effective design with zero-budget constraints
4. Integration of semantic search with generative AI

