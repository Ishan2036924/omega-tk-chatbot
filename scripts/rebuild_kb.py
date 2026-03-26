#!/usr/bin/env python3
"""
Omega TK Knowledge Base Rebuild Script
=======================================
Crawls the entire Omega TK documentation, converts all content to structured
Q&A-code triplets, and rebuilds the FAISS index from scratch.

Steps:
  1. Discover all /omegatk/ URLs by crawling from the index page
  2. Scrape each page with structure-aware extraction
  3. Extract Q&A pairs from data/raw/Omega_ChatBot_Prompts.html
  4. Convert existing training_prompts.json to triplet format (gold standard)
  5. Generate 2-3 questions per scraped unit via GPT-4o-mini
  6. Apply strict chunking rules
  7. Embed with text-embedding-3-small: "Question: {q}\nAnswer: {a}\nCode: {c}"
  8. Rebuild FAISS index, save chunks_metadata.json & omega_tk_triplets.json
  9. Update src/config.py TOP_K → 5
"""

import os
import sys
import re
import json
import time
import hashlib
import signal
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE        = Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

RAW_DIR       = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TRIPLETS_PATH  = RAW_DIR / "omega_tk_triplets.json"
TRAINING_PATH  = RAW_DIR / "training_prompts.json"
HTML_PATH      = RAW_DIR / "Omega_ChatBot_Prompts.html"
FAISS_PATH     = PROCESSED_DIR / "faiss.index"
CHUNKS_PATH    = PROCESSED_DIR / "chunks.json"          # legacy path (kept for compatibility)
META_PATH      = PROCESSED_DIR / "chunks_metadata.json"

EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_DIM       = 1536
TOP_K_NEW       = 5
RATE_LIMIT_S    = 1.0     # seconds between HTTP requests
PAGE_TIMEOUT    = 60      # seconds per page scrape

BASE_URL   = "https://docs.eyesopen.com/toolkits/python/omegatk/"
INDEX_URL  = BASE_URL + "index.html"
ALLOWED_PATH_PREFIX = "/toolkits/python/omegatk/"

# API-reference page patterns
API_REF_PATTERNS = [
    r"/OEConfGenClasses/",
    r"/OEConfGenConstants/",
    r"/OEConfGenFunctions/",
]
THEORY_KEYWORDS = ["theory", "overview", "background", "introduction", "sampling"]
EXAMPLE_KEYWORDS = ["example", "examples", "flipper", "torsion", "fragment", "macrocycle", "gpu"]

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Logging helper ─────────────────────────────────────────────────────────────

def log(msg: str):
    print(msg, flush=True)

# ── Timeout context ────────────────────────────────────────────────────────────

class TimeoutError(Exception):
    pass

def _timeout_handler(signum, frame):
    raise TimeoutError()

# ── HTTP helpers ───────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

def _get(url: str, timeout: int = 30) -> Optional[requests.Response]:
    """GET a URL; return None on any failure."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout)
        if r.status_code == 404:
            log(f"  ⚠  404 — skipping {url}")
            return None
        r.raise_for_status()
        return r
    except requests.RequestException as exc:
        log(f"  ✗  Request failed {url}: {exc}")
        return None

# ── Step 1: URL discovery ──────────────────────────────────────────────────────

def discover_urls() -> list[str]:
    """
    BFS crawl from the index page, collecting all /omegatk/ sub-URLs.
    Returns sorted, deduplicated list.
    """
    log("\n" + "=" * 60)
    log("STEP 1 — Discovering Omega TK URLs")
    log("=" * 60)

    visited: set[str] = set()
    queue: list[str] = [INDEX_URL]
    found: list[str] = []
    failed: list[str] = []

    while queue:
        url = queue.pop(0)
        # Normalise — drop fragment
        url = url.split("#")[0].rstrip("/")
        if not url.endswith(".html"):
            url_html = url + ".html" if not url.endswith("/") else url + "index.html"
        else:
            url_html = url

        if url_html in visited:
            continue
        visited.add(url_html)

        parsed = urlparse(url_html)
        # Only follow /omegatk/ pages on the same domain
        if ALLOWED_PATH_PREFIX not in parsed.path:
            continue

        log(f"  Scanning: {url_html}")
        time.sleep(RATE_LIMIT_S)

        resp = _get(url_html)
        if resp is None:
            failed.append(url_html)
            continue

        found.append(url_html)

        # Parse links
        soup = BeautifulSoup(resp.content, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            abs_url = urljoin(url_html, href).split("#")[0]
            parsed_link = urlparse(abs_url)
            if (
                parsed_link.netloc == "docs.eyesopen.com"
                and ALLOWED_PATH_PREFIX in parsed_link.path
                and abs_url not in visited
            ):
                queue.append(abs_url)

    log(f"\nDiscovered {len(found)} URLs ({len(failed)} failed/404)")
    log("\nAll discovered URLs:")
    for u in sorted(found):
        log(f"  {u}")

    return sorted(set(found))

# ── Step 2: Structure-aware scraping ──────────────────────────────────────────

def _classify_page(url: str) -> str:
    """Return 'api_ref', 'example', or 'theory'."""
    for pat in API_REF_PATTERNS:
        if re.search(pat, url):
            return "api_ref"
    slug = url.lower().split("/")[-1]
    if any(k in slug for k in EXAMPLE_KEYWORDS):
        return "example"
    if any(k in slug for k in THEORY_KEYWORDS):
        return "theory"
    return "theory"   # default for index/overview pages

def _clean_text(s: str) -> str:
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _extract_code_blocks(main: BeautifulSoup) -> list[str]:
    """Return a list of complete code block texts."""
    blocks = []
    for pre in main.find_all("pre"):
        code_tag = pre.find("code")
        text = (code_tag or pre).get_text()
        text = text.strip()
        if len(text) > 20:
            blocks.append(text)
    return blocks

def scrape_page(url: str) -> list[dict]:
    """
    Scrape one page and return a list of raw units:
      { url, page_title, section, prose, code, content_type }
    """
    page_type = _classify_page(url)

    resp = _get(url, timeout=PAGE_TIMEOUT)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.content, "html.parser")

    # Page title
    title_tag = soup.find("h1") or soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else url.split("/")[-1]

    # Main content area
    main = (
        soup.find("div", class_="document")
        or soup.find("div", role="main")
        or soup.find("main")
        or soup.find("article")
        or soup.body
    )
    if main is None:
        return []

    # Remove navigation / TOC sidebars
    for el in main.find_all(["script", "style", "nav", "footer",
                              "div", "section"],
                             class_=re.compile(r"sidebar|toc|nav|sphinxsidebar|relations")):
        el.decompose()

    units = []

    if page_type == "api_ref":
        units.extend(_scrape_api_ref(url, page_title, main))
    elif page_type == "example":
        units.extend(_scrape_examples(url, page_title, main))
    else:
        units.extend(_scrape_theory(url, page_title, main))

    return units


def _scrape_api_ref(url: str, page_title: str, main: BeautifulSoup) -> list[dict]:
    """Extract per-class / per-function sections from an API reference page."""
    units = []

    # Each documented entity is wrapped in a dl/dt/dd structure in Sphinx HTML
    for dl in main.find_all("dl", class_=re.compile(r"class|function|method|attribute")):
        # Class/function name from the <dt>
        dt = dl.find("dt")
        if dt is None:
            continue
        entity_name = dt.get_text(strip=True).split("(")[0].strip()

        # Description
        dd = dl.find("dd")
        prose = _clean_text(dd.get_text(separator=" ", strip=True)) if dd else ""

        # Code examples inside this section
        code_blocks = _extract_code_blocks(dl)

        if code_blocks:
            for cb in code_blocks:
                units.append({
                    "url": url,
                    "page_title": page_title,
                    "section": entity_name,
                    "prose": prose[:1200],
                    "code": cb,
                    "content_type": "api_ref",
                })
        else:
            if prose and len(prose.split()) > 10:
                units.append({
                    "url": url,
                    "page_title": page_title,
                    "section": entity_name,
                    "prose": prose[:1200],
                    "code": "",
                    "content_type": "api_ref",
                })

    # If no dl-based entities found, fall back to section-level extraction
    if not units:
        units.extend(_scrape_theory(url, page_title, main))

    return units


def _scrape_examples(url: str, page_title: str, main: BeautifulSoup) -> list[dict]:
    """
    For example pages: pair each code block with the prose that precedes it.
    Never truncate code.
    """
    units = []
    pending_prose: list[str] = []

    for el in main.children:
        if not hasattr(el, "name") or el.name is None:
            continue
        if el.name == "pre":
            code = el.get_text().strip()
            if len(code) > 20:
                prose = " ".join(pending_prose).strip()
                pending_prose = []
                units.append({
                    "url": url,
                    "page_title": page_title,
                    "section": page_title,
                    "prose": _clean_text(prose)[:800],
                    "code": code,
                    "content_type": "example",
                })
        elif el.name in ("p", "li"):
            t = el.get_text(" ", strip=True)
            if t:
                pending_prose.append(t)
        elif el.name in ("h2", "h3", "h4"):
            # New heading — flush pending prose as its own unit
            if pending_prose:
                prose_blob = _clean_text(" ".join(pending_prose))
                if len(prose_blob.split()) > 10:
                    units.append({
                        "url": url,
                        "page_title": page_title,
                        "section": el.get_text(strip=True),
                        "prose": prose_blob[:800],
                        "code": "",
                        "content_type": "example",
                    })
                pending_prose = []
        elif el.name in ("div", "section"):
            # Recurse into nested containers
            sub = el
            sub_units = _scrape_examples(url, page_title, sub)
            units.extend(sub_units)

    # Flush any trailing prose
    if pending_prose:
        prose_blob = _clean_text(" ".join(pending_prose))
        if len(prose_blob.split()) > 10:
            units.append({
                "url": url,
                "page_title": page_title,
                "section": page_title,
                "prose": prose_blob[:800],
                "code": "",
                "content_type": "example",
            })

    # Deduplicate by code hash
    seen: set[str] = set()
    deduped = []
    for u in units:
        key = hashlib.md5((u["code"] or u["prose"]).encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            deduped.append(u)

    return deduped


def _scrape_theory(url: str, page_title: str, main: BeautifulSoup) -> list[dict]:
    """
    For theory/overview pages: split on headings, keep each heading +
    following paragraphs as one unit (max 300 tokens ≈ 400 words).
    """
    MAX_WORDS = 400
    units = []
    current_section = page_title
    current_paras: list[str] = []
    current_code: str = ""

    def flush():
        nonlocal current_paras, current_code
        if current_paras or current_code:
            prose = _clean_text(" ".join(current_paras))
            # Split on sentence boundaries if too long
            if len(prose.split()) > MAX_WORDS:
                # sentence-split
                sentences = re.split(r"(?<=[.!?])\s+", prose)
                bucket: list[str] = []
                for sent in sentences:
                    bucket.append(sent)
                    if len(" ".join(bucket).split()) >= MAX_WORDS:
                        units.append({
                            "url": url,
                            "page_title": page_title,
                            "section": current_section,
                            "prose": " ".join(bucket).strip(),
                            "code": current_code,
                            "content_type": "theory",
                        })
                        bucket = []
                        current_code = ""
                if bucket:
                    units.append({
                        "url": url,
                        "page_title": page_title,
                        "section": current_section,
                        "prose": " ".join(bucket).strip(),
                        "code": current_code,
                        "content_type": "theory",
                    })
            else:
                if len(prose.split()) >= 8:   # skip micro-fragments
                    units.append({
                        "url": url,
                        "page_title": page_title,
                        "section": current_section,
                        "prose": prose,
                        "code": current_code,
                        "content_type": "theory",
                    })
            current_paras = []
            current_code = ""

    for el in main.descendants:
        if not hasattr(el, "name") or el.name is None:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            flush()
            current_section = el.get_text(strip=True)
        elif el.name in ("p", "li"):
            t = el.get_text(" ", strip=True)
            if t and el.parent and el.parent.name not in ("dd",):
                current_paras.append(t)
        elif el.name == "pre":
            code = el.get_text().strip()
            if len(code) > 20:
                flush()
                current_code = code

    flush()
    return units


# ── Step 3: Extract from Omega_ChatBot_Prompts.html ───────────────────────────

def extract_notebook_qa(html_path: Path) -> list[dict]:
    """
    Parse the Jupyter notebook HTML export.
    Markdown cells = question/answer text
    Code cells = Python code
    Returns list of {question, answer, code} dicts.
    """
    log("\n" + "=" * 60)
    log("STEP 3 — Extracting Q&A from Omega_ChatBot_Prompts.html")
    log("=" * 60)

    if not html_path.exists():
        log(f"  ⚠  Not found: {html_path}")
        return []

    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Jupyter notebook: cells are div.jp-Cell or div.cell
    cells = soup.find_all("div", class_=re.compile(r"(jp-Cell|cell)"))

    pairs = []
    last_markdown = ""
    current_question = ""
    current_answer_parts: list[str] = []

    for cell in cells:
        # Is it a markdown or code cell?
        cls = " ".join(cell.get("class", []))
        is_markdown = "Markdown" in cls or "text_cell" in cls
        is_code = "Code" in cls or "code_cell" in cls

        if is_markdown:
            text = cell.get_text(separator="\n", strip=True)
            # Clean up extra whitespace
            text = re.sub(r"\n{2,}", "\n", text).strip()
            last_markdown = text

            # Detect question pattern: lines ending with ? or starting with Q:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                line = line.strip()
                if line.endswith("?") and len(line) > 10:
                    if current_question and current_answer_parts:
                        pairs.append({
                            "question": current_question,
                            "answer": "\n".join(current_answer_parts).strip(),
                        })
                    current_question = line
                    current_answer_parts = lines[i+1:]
                    break
            else:
                # Continuation prose
                current_answer_parts.append(text)

        elif is_code:
            # Extract code from the input cell
            code_el = cell.find("div", class_=re.compile(r"(jp-CodeMirrorEditor|input_area|jp-Cell-inputArea)"))
            if not code_el:
                code_el = cell.find("div", class_=re.compile(r"highlight"))
            code = code_el.get_text("\n", strip=True) if code_el else ""
            code = code.strip()

            if code and len(code) > 10:
                if current_question:
                    pairs.append({
                        "question": current_question,
                        "answer": "\n".join(current_answer_parts).strip(),
                        "code": code,
                    })
                    current_question = ""
                    current_answer_parts = []
                else:
                    # Code without a preceding question — use last markdown as context
                    if last_markdown:
                        pairs.append({
                            "question": last_markdown[:200],
                            "answer": last_markdown,
                            "code": code,
                        })

    # Flush final pair
    if current_question and current_answer_parts:
        pairs.append({
            "question": current_question,
            "answer": "\n".join(current_answer_parts).strip(),
        })

    # Filter: must have non-trivial content
    pairs = [p for p in pairs if len(p.get("question", "")) > 5]
    log(f"  Extracted {len(pairs)} Q&A pairs from notebook HTML")
    return pairs


# ── Step 4: Convert training_prompts.json (gold standard) ────────────────────

def convert_training_prompts(path: Path) -> list[dict]:
    """Convert existing training_prompts.json to full triplet format."""
    log("\n" + "=" * 60)
    log("STEP 4 — Converting gold-standard training prompts")
    log("=" * 60)

    with open(path, "r") as f:
        raw = json.load(f)

    triplets = []
    for i, item in enumerate(raw):
        q = item.get("question", "").strip()
        code = item.get("code", "").strip()
        answer = item.get("answer", "").strip() or f"Here is how to {q.lower().rstrip('?')} using OpenEye Omega TK Python API."

        # Extract API component names from code
        api_components = re.findall(r"oe(?:omega|chem)\.\w+", code)
        api_components = list(dict.fromkeys(api_components))[:6]

        triplets.append({
            "question": q,
            "answer": answer,
            "code": code,
            "source_url": "https://docs.eyesopen.com/toolkits/python/omegatk/",
            "source_section": "Gold Standard Training Data",
            "api_components": api_components,
            "content_type": "example",
            "is_gold_standard": True,
        })

    log(f"  Converted {len(triplets)} gold-standard triplets")
    return triplets


# ── Step 5: Generate questions with GPT-4o-mini ───────────────────────────────

_QUESTION_GEN_SYSTEM = """\
You are building a RAG knowledge base for the OpenEye Omega Toolkit (Python API).
Given this documentation content, generate 2-3 natural language questions that an
engineer would ask that this content directly answers.

Rules:
- Be specific — include API class names (e.g. OEOmega, OEFlipperOptions) in questions
- Questions must be answerable ONLY from the given content (no hallucination)
- Return ONLY a JSON array of strings: ["question1", "question2"]
- No extra text before or after the JSON array
"""

def _gen_questions(unit: dict) -> list[str]:
    """Call GPT-4o-mini to generate 2-3 questions for a raw unit."""
    content_parts = []
    if unit.get("section") and unit["section"] != unit.get("page_title"):
        content_parts.append(f"Section: {unit['section']}")
    if unit.get("prose"):
        content_parts.append(f"Description: {unit['prose'][:600]}")
    if unit.get("code"):
        content_parts.append(f"Code:\n{unit['code'][:800]}")

    content = "\n\n".join(content_parts)
    if len(content.strip()) < 20:
        return []

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _QUESTION_GEN_SYSTEM},
                {"role": "user", "content": content},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        # Extract JSON array
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return []
    except Exception as e:
        log(f"    ⚠  Question gen failed: {e}")
        return []


def units_to_triplets(units: list[dict]) -> list[dict]:
    """
    Convert raw scraped units to full Q&A-code triplets.
    Generates questions via GPT-4o-mini (batched with 0.1s sleep to avoid rate limits).
    """
    log("\n" + "=" * 60)
    log(f"STEP 5 — Generating questions for {len(units)} scraped units")
    log("=" * 60)

    triplets = []
    for i, unit in enumerate(units):
        if i % 20 == 0 and i > 0:
            log(f"  Progress: {i}/{len(units)}")

        questions = _gen_questions(unit)
        time.sleep(0.1)   # light rate-limit for OpenAI

        # If GPT fails or returns nothing, use the section title as question
        if not questions:
            if unit.get("code"):
                questions = [f"How do I use {unit['section']} in Omega TK?"]
            else:
                questions = [f"What does {unit['section']} do in Omega TK?"]

        # Extract API components from code
        api_components = re.findall(r"oe(?:omega|chem)\.\w+", unit.get("code", ""))
        api_components = list(dict.fromkeys(api_components))[:6]

        # First question becomes the "canonical" question for this chunk
        for q in questions:
            triplets.append({
                "question": q.strip(),
                "answer": unit.get("prose", "").strip(),
                "code": unit.get("code", "").strip(),
                "source_url": unit.get("url", ""),
                "source_section": unit.get("section", unit.get("page_title", "")),
                "api_components": api_components,
                "content_type": unit.get("content_type", "theory"),
                "is_gold_standard": False,
            })

    log(f"  Generated {len(triplets)} triplets from scraped units")
    return triplets


# ── Flipper correction (Step 8) ───────────────────────────────────────────────

FLIPPER_CORRECTION = {
    "question": "How do I enumerate stereoisomers using OEFlipper?",
    "answer": (
        "OEFlipper is a generator FUNCTION, not a class. Do NOT call .Build() on it. "
        "Iterate over it directly with a for loop. Each iteration yields a stereo-enumerated "
        "copy of the input molecule. Use OEFlipperOptions to configure maximum stereocenters."
    ),
    "code": (
        "from openeye import oechem, oeomega\n"
        "from sys import argv\n\n"
        "ifs = oechem.oemolistream(argv[1])\n"
        "ofs = oechem.oemolostream(argv[2])\n\n"
        "opts = oeomega.OEFlipperOptions()\n"
        "opts.SetMaxCenters(5)\n\n"
        "for mol in ifs.GetOEMols():\n"
        "    for isomer in oeomega.OEFlipper(mol, opts):\n"
        "        oechem.OEWriteMolecule(ofs, isomer)\n\n"
        "ofs.close()"
    ),
    "source_url": "https://docs.eyesopen.com/toolkits/python/omegatk/",
    "source_section": "Flipper Examples",
    "api_components": ["oeomega.OEFlipper", "oeomega.OEFlipperOptions", "SetMaxCenters"],
    "content_type": "example",
    "is_gold_standard": True,
}


# ── Step 6: Apply chunking rules ───────────────────────────────────────────────

MIN_TOKENS  = 50    # ~37 words
MAX_TOKENS  = 1500  # hard cap per chunk

def _token_estimate(s: str) -> int:
    """Rough estimate: 1 token ≈ 0.75 words."""
    return int(len(s.split()) / 0.75)

def triplets_to_chunks(triplets: list[dict]) -> list[dict]:
    """
    Convert triplets to final FAISS chunks, applying strict rules.
    The embed_text field = "Question: {q}\nAnswer: {a}\nCode: {c}"
    """
    chunks = []
    seen_hashes: set[str] = set()

    for i, t in enumerate(triplets):
        q     = t.get("question", "").strip()
        a     = t.get("answer", "").strip()
        code  = t.get("code", "").strip()

        # Build embed text
        parts = [f"Question: {q}"]
        if a:
            parts.append(f"Answer: {a[:600]}")
        if code:
            parts.append(f"Code:\n{code[:1000]}")
        embed_text = "\n".join(parts)

        # Minimum size check
        if _token_estimate(embed_text) < MIN_TOKENS:
            continue

        # Deduplication by content hash
        h = hashlib.md5(embed_text.encode()).hexdigest()
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        # Boost score field for gold standard (used at retrieval time)
        chunk = {
            "id": f"triplet_{i:05d}",
            "text": embed_text,
            "question": q,
            "answer": a,
            "code": code,
            "source": t.get("source_section", ""),
            "source_url": t.get("source_url", ""),
            "content_type": t.get("content_type", "theory"),
            "api_components": t.get("api_components", []),
            "is_gold_standard": t.get("is_gold_standard", False),
            "type": "triplet",
        }
        chunks.append(chunk)

    return chunks


# ── Step 7: Embed ──────────────────────────────────────────────────────────────

def build_embeddings(texts: list[str]) -> np.ndarray:
    """Embed all texts in batches of 100."""
    log(f"\nEmbedding {len(texts)} chunks with {EMBEDDING_MODEL}...")
    BATCH = 100
    all_embs: list[list[float]] = []

    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        log(f"  Batch {i // BATCH + 1}/{(len(texts) + BATCH - 1) // BATCH} ({len(batch)} items)...")
        resp = _client.embeddings.create(input=batch, model=EMBEDDING_MODEL)
        all_embs.extend([item.embedding for item in resp.data])
        time.sleep(0.1)

    embs = np.array(all_embs, dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    embs = embs / norms
    log(f"  Embeddings shape: {embs.shape}")
    return embs


def build_faiss_index(embs: np.ndarray) -> faiss.IndexFlatIP:
    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(embs.astype(np.float32))
    log(f"  FAISS index: {index.ntotal} vectors")
    return index


# ── Step 8: Update src/config.py TOP_K ────────────────────────────────────────

def update_config_top_k():
    config_path = PROJECT_ROOT / "src" / "config.py"
    with open(config_path, "r") as f:
        content = f.read()
    new_content = re.sub(r"^TOP_K\s*=\s*\d+", f"TOP_K = {TOP_K_NEW}", content, flags=re.MULTILINE)
    with open(config_path, "w") as f:
        f.write(new_content)
    log(f"  Updated src/config.py: TOP_K = {TOP_K_NEW}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log("\n" + "=" * 60)
    log("Omega TK Knowledge Base Rebuild")
    log("=" * 60)

    stats = {
        "urls_scraped": 0,
        "urls_failed": [],
        "units_extracted": 0,
        "total_triplets": 0,
        "chunks_by_type": defaultdict(int),
        "old_chunk_count": 0,
        "new_chunk_count": 0,
    }

    # Record old count
    if CHUNKS_PATH.exists():
        with open(CHUNKS_PATH) as f:
            stats["old_chunk_count"] = len(json.load(f))

    # ── Step 1: Discover URLs ───────────────────────────────────────────────
    all_urls = discover_urls()
    stats["urls_scraped"] = len(all_urls)

    # ── Step 2: Scrape all pages ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log(f"STEP 2 — Scraping {len(all_urls)} pages")
    log("=" * 60)

    all_units: list[dict] = []
    failed_urls: list[str] = []

    for url in all_urls:
        log(f"  [{_classify_page(url)}] {url}")
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(PAGE_TIMEOUT)
        try:
            units = scrape_page(url)
            signal.alarm(0)
            all_units.extend(units)
            log(f"    → {len(units)} units")
        except TimeoutError:
            log(f"    ✗  Timed out after {PAGE_TIMEOUT}s")
            failed_urls.append(url)
        except Exception as exc:
            signal.alarm(0)
            log(f"    ✗  Error: {exc}")
            failed_urls.append(url)
        time.sleep(RATE_LIMIT_S)

    stats["units_extracted"] = len(all_units)
    stats["urls_failed"] = failed_urls
    log(f"\nTotal units extracted: {len(all_units)}")
    log(f"Failed pages: {len(failed_urls)}")

    # Save intermediate scraped units
    with open(RAW_DIR / "scraped_units.json", "w") as f:
        json.dump(all_units, f, indent=2)
    log(f"Saved scraped_units.json ({len(all_units)} units)")

    # ── Step 3: Extract from notebook HTML ─────────────────────────────────
    notebook_pairs = extract_notebook_qa(HTML_PATH)

    # ── Step 4: Gold standard triplets ─────────────────────────────────────
    gold_triplets = convert_training_prompts(TRAINING_PATH)

    # ── Step 5: Generate questions for scraped units ────────────────────────
    scraped_triplets = units_to_triplets(all_units)

    # Convert notebook pairs to triplets
    nb_triplets = []
    for p in notebook_pairs:
        nb_triplets.append({
            "question": p.get("question", "").strip(),
            "answer": p.get("answer", "").strip(),
            "code": p.get("code", "").strip(),
            "source_url": "data/raw/Omega_ChatBot_Prompts.html",
            "source_section": "Omega ChatBot Prompts Notebook",
            "api_components": re.findall(r"oe(?:omega|chem)\.\w+", p.get("code", "")),
            "content_type": "example",
            "is_gold_standard": True,
        })

    # ── Assemble & add Flipper correction ──────────────────────────────────
    all_triplets = [FLIPPER_CORRECTION] + gold_triplets + nb_triplets + scraped_triplets
    stats["total_triplets"] = len(all_triplets)

    # Save all triplets
    with open(TRIPLETS_PATH, "w") as f:
        json.dump(all_triplets, f, indent=2)
    log(f"\nSaved {len(all_triplets)} triplets → {TRIPLETS_PATH}")

    # Also update training_prompts.json with gold standard triplets merged
    updated_training = gold_triplets + nb_triplets + [FLIPPER_CORRECTION]
    with open(TRAINING_PATH, "w") as f:
        json.dump(updated_training, f, indent=2)
    log(f"Updated training_prompts.json ({len(updated_training)} entries)")

    # ── Step 6: Apply chunking rules ───────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 6 — Applying chunking rules")
    log("=" * 60)

    chunks = triplets_to_chunks(all_triplets)
    stats["new_chunk_count"] = len(chunks)

    for c in chunks:
        stats["chunks_by_type"][c["content_type"]] += 1

    log(f"  Final chunks after dedup + min-size filter: {len(chunks)}")
    for ct, n in sorted(stats["chunks_by_type"].items()):
        log(f"    {ct}: {n}")

    # ── Step 7: Embed & index ───────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 7 — Embedding & indexing")
    log("=" * 60)

    texts = [c["text"] for c in chunks]
    embs  = build_embeddings(texts)
    index = build_faiss_index(embs)

    # Save FAISS index
    faiss.write_index(index, str(FAISS_PATH))
    log(f"  Saved FAISS index → {FAISS_PATH}")

    # Save chunks_metadata.json (new rich format)
    with open(META_PATH, "w") as f:
        json.dump(chunks, f, indent=2)
    log(f"  Saved chunks_metadata.json → {META_PATH}")

    # Also overwrite legacy chunks.json so src/retriever.py keeps working
    with open(CHUNKS_PATH, "w") as f:
        json.dump(chunks, f, indent=2)
    log(f"  Updated legacy chunks.json → {CHUNKS_PATH}")

    # ── Step 8: Update config ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 8 — Updating src/config.py TOP_K")
    log("=" * 60)
    update_config_top_k()

    # ── Final report ─────────────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 9 — Final Report")
    log("=" * 60)
    log(f"  Total URLs scraped:          {stats['urls_scraped']}")
    log(f"  Total triplets generated:    {stats['total_triplets']}")
    log(f"  Total chunks in new index:   {stats['new_chunk_count']}")
    log(f"  Breakdown by content_type:")
    for ct, n in sorted(stats["chunks_by_type"].items()):
        log(f"    {ct:20s}: {n}")
    log(f"  Failed URLs ({len(stats['urls_failed'])}):")
    for u in stats["urls_failed"]:
        log(f"    ✗  {u}")
    log(f"  OLD vector count:            {stats['old_chunk_count']}")
    log(f"  NEW vector count:            {stats['new_chunk_count']}")
    log("\n  Done.")
    log("=" * 60)


if __name__ == "__main__":
    main()
