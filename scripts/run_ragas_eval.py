"""
Omega TK RAG Pipeline — RAGAS + RAG Triad Evaluation
=====================================================
Evaluates the production pipeline against all gold-standard Q&A pairs from
data/raw/training_prompts.json using:
  • RAGAS  : Faithfulness, AnswerRelevancy, ContextPrecisionWithReference, ContextRecall
  • RAG Triad (manual GPT-4o-mini judge): Context Relevance, Groundedness, Answer Relevance

Outputs to data/eval/:
  ragas_report.json     — per-question RAGAS scores
  rag_triad_report.json — per-question RAG Triad scores
  eval_summary.json     — combined averaged summary

Run from project root:
  conda activate omega-tk-web
  python scripts/run_ragas_eval.py
"""

import sys
import os

# Fix duplicate OpenMP runtime conflict between OpenEye and FAISS/RAGAS libraries.
# Without this the process aborts when RAGAS imports its ML dependencies after
# the OpenEye toolkit has already loaded its own copy of libomp.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json
import time
import logging
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Path setup ────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))    # retriever, generator, config
sys.path.insert(0, str(_PROJECT_ROOT / "server")) # validator

from dotenv import load_dotenv
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── OpenAI + project imports ──────────────────────────────────────────────────
import numpy as np
from openai import OpenAI

from config import TOP_K, EMBEDDING_MODEL
from retriever import get_retriever

# ── Constants ─────────────────────────────────────────────────────────────────
EVAL_DIR       = _PROJECT_ROOT / "data" / "eval"
PROMPTS_PATH   = _PROJECT_ROOT / "data" / "raw" / "training_prompts.json"
FAISS_THRESHOLD = 0.20          # low threshold so eval isn't gated by retrieval score
GOLD_BOOST     = 0.10           # same boost as production
CANDIDATE_K    = max(TOP_K * 3, 15)
RATE_LIMIT_S   = 0.5            # seconds between questions to avoid 429s
SAVE_EVERY     = 10             # checkpoint frequency (questions)
JUDGE_MODEL    = "gpt-4o-mini"  # model for generation + RAG Triad judge
RAGAS_MODEL    = "gpt-4o-mini"  # model for RAGAS scoring

# ── Production code prompt (mirrors server/app.py _CODE_PROMPT exactly) ──────
_CODE_PROMPT = """\
You are an expert Python developer specialising in the OpenEye Omega Toolkit \
for molecular conformer generation.

Use the retrieved documentation below to answer the user's question.

## Retrieved Documentation
{context}

## User Question
{question}

## Instructions
Before the code block, write a structured explanation with these four parts \
(each 1-3 sentences, no headings needed — just flowing prose):

1. **Purpose** — what the code accomplishes and why this approach is used.
2. **Key classes & options** — name every significant class (OEOmega, OEOmegaOptions, \
OEFlipperOptions, OEMacrocycleOmega, etc.) and explain what each one controls, \
including any important parameter values (e.g. OEOmegaSampling_Classic vs Dense, \
SetMaxConfs(), SetDielectricConst()).
3. **5-step pattern** — briefly confirm how the code follows the standard OpenEye pattern: \
molecule streams → options → Build() → return code check.
4. **Output & caveats** — what the output file contains, any edge cases or \
things the user should watch out for (e.g. stereochemistry, macrocycle detection, \
file format requirements).

Then provide the complete, working Python code block.

Always follow the 5-step OpenEye Omega pattern:
1. **Molecule Streams** — oemolistream / oemolostream
2. **Constants** — OEOmegaSampling_Classic / Dense / Pose / ROCS / FastROCS
3. **Options** — OEOmegaOptions(mode), OEMacrocycleOmegaOptions, OEFlipperOptions
4. **Execute** — omega.Build(mol)
5. **Error handling** — OEOmegaReturnCode_Success, OEGetOmegaError(ret_code)

Required import: `from openeye import oechem, oeomega`

## Response
Write the explanation (4 parts, flowing prose), then a ```python ... ``` code block:"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper: load gold standard pairs
# ─────────────────────────────────────────────────────────────────────────────

def load_gold_standard() -> list[dict]:
    with open(PROMPTS_PATH) as f:
        data = json.load(f)
    gs = [d for d in data if d.get("is_gold_standard")]
    print(f"Loaded {len(gs)} gold-standard pairs from {PROMPTS_PATH.name}")
    return gs


# ─────────────────────────────────────────────────────────────────────────────
# Helper: retrieve chunks (same logic as server/app.py _retrieve())
# ─────────────────────────────────────────────────────────────────────────────

def retrieve_chunks(question: str, retriever, threshold: float = FAISS_THRESHOLD) -> list[dict]:
    """
    Mirror of server/app.py _retrieve():
    - Embeds as "Question: {query}"
    - Gold-standard boost +0.10
    - Sorted by boosted score, capped at TOP_K
    """
    embed_query = f"Question: {question}"
    emb = retriever.embed_query(embed_query)
    scores, indices = retriever.index.search(emb, CANDIDATE_K)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        raw = float(score)
        if raw < threshold:
            continue
        chunk = retriever.chunks[idx].copy()
        if chunk.get("is_gold_standard"):
            raw = min(1.0, raw + GOLD_BOOST)
        chunk["score"] = raw
        results.append(chunk)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:TOP_K]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: generate answer using production prompt
# ─────────────────────────────────────────────────────────────────────────────

def generate_answer(question: str, chunks: list[dict], client: OpenAI) -> str:
    """Generate a response using the production _CODE_PROMPT template."""
    if not chunks:
        context_text = "(no documentation retrieved)"
    else:
        context_parts = []
        for i, c in enumerate(chunks, 1):
            text = c.get("text") or c.get("content") or ""
            src  = c.get("source", "")
            context_parts.append(f"[{i}] Source: {src}\n{text[:800]}")
        context_text = "\n\n---\n\n".join(context_parts)

    prompt = _CODE_PROMPT.format(context=context_text, question=question)

    completion = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1200,
    )
    return completion.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: RAG Triad judge
# ─────────────────────────────────────────────────────────────────────────────

_TRIAD_SYSTEM = (
    "You are a strict evaluator of RAG (Retrieval-Augmented Generation) pipelines. "
    "Return ONLY valid JSON with exactly the keys shown in the prompt."
)


def _judge(prompt: str, client: OpenAI) -> dict:
    """Call GPT-4o-mini and parse JSON response. Returns {score, reason} or defaults."""
    try:
        resp = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": _TRIAD_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.warning("RAG Triad judge call failed: %s", exc)
        return {"score": 0.0, "reason": f"judge error: {exc}"}


def rag_triad_score(question: str, answer: str, contexts: list[str], client: OpenAI) -> dict:
    """Run all 3 RAG Triad legs and return {context_relevance, groundedness, answer_relevance}."""
    ctx_text = "\n\n".join(f"[{i+1}] {c[:600]}" for i, c in enumerate(contexts))

    ctx_rel_prompt = (
        f"Question: {question}\n\n"
        f"Retrieved chunks:\n{ctx_text}\n\n"
        "On a scale of 0.0 to 1.0, how relevant are these retrieved chunks to answering "
        "this question? A score of 1.0 means the chunks directly answer the question; "
        "0.0 means completely irrelevant.\n"
        'Return JSON: {"score": <float 0-1>, "reason": "<one sentence>"}'
    )

    grounded_prompt = (
        f"Question: {question}\n\n"
        f"Context:\n{ctx_text}\n\n"
        f"Answer:\n{answer[:1000]}\n\n"
        "On a scale of 0.0 to 1.0, is every factual claim in the answer supported by "
        "the provided context? 1.0 = fully grounded; 0.0 = entirely hallucinated.\n"
        'Return JSON: {"score": <float 0-1>, "reason": "<one sentence>"}'
    )

    ans_rel_prompt = (
        f"Question: {question}\n\n"
        f"Answer:\n{answer[:1000]}\n\n"
        "On a scale of 0.0 to 1.0, does this answer fully and directly address the question "
        "asked? 1.0 = complete and on-target; 0.0 = entirely off-topic or missing.\n"
        'Return JSON: {"score": <float 0-1>, "reason": "<one sentence>"}'
    )

    ctx_rel  = _judge(ctx_rel_prompt,  client)
    grounded = _judge(grounded_prompt, client)
    ans_rel  = _judge(ans_rel_prompt,  client)

    return {
        "context_relevance": {
            "score":  float(ctx_rel.get("score",  0.0)),
            "reason": ctx_rel.get("reason", ""),
        },
        "groundedness": {
            "score":  float(grounded.get("score", 0.0)),
            "reason": grounded.get("reason", ""),
        },
        "answer_relevance": {
            "score":  float(ans_rel.get("score",  0.0)),
            "reason": ans_rel.get("reason", ""),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helper: save checkpoint
# ─────────────────────────────────────────────────────────────────────────────

def save_checkpoint(rows: list[dict], triad_rows: list[dict]) -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / "_checkpoint_pipeline.json").write_text(
        json.dumps({"pipeline": rows, "triad": triad_rows}, indent=2)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main evaluation loop
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline_eval(gold: list[dict], retriever, client: OpenAI) -> tuple[list[dict], list[dict]]:
    """
    For every gold-standard pair:
      1. Retrieve top-5 chunks
      2. Generate answer via production prompt
      3. Score with RAG Triad (3 GPT-4o-mini calls)

    Returns (pipeline_rows, triad_rows) for RAGAS and RAG Triad reporting.
    """
    pipeline_rows: list[dict] = []
    triad_rows:    list[dict] = []
    errors = 0

    total = len(gold)
    for i, entry in enumerate(gold, 1):
        question    = entry["question"]
        ground_truth_text = entry.get("answer", "")
        ground_truth_code = entry.get("code", "")
        # Combine answer + code as the full ground truth for RAGAS
        if ground_truth_code:
            ground_truth = f"{ground_truth_text}\n\n```python\n{ground_truth_code}\n```"
        else:
            ground_truth = ground_truth_text

        print(f"  [{i:>3}/{total}] {question[:70]}", end="", flush=True)

        try:
            # ── Step 1: retrieve ──────────────────────────────────────────────
            chunks   = retrieve_chunks(question, retriever)
            contexts = [c.get("text") or c.get("content") or "" for c in chunks]

            # ── Step 2: generate ──────────────────────────────────────────────
            answer = generate_answer(question, chunks, client)

            # ── Step 3: RAG Triad ─────────────────────────────────────────────
            triad = rag_triad_score(question, answer, contexts, client)

            # ── Accumulate ────────────────────────────────────────────────────
            pipeline_rows.append({
                "question":     question,
                "answer":       answer,
                "contexts":     contexts,
                "ground_truth": ground_truth,
                "n_chunks":     len(chunks),
                "top_score":    round(chunks[0]["score"], 4) if chunks else 0.0,
            })
            triad_rows.append({
                "question":         question,
                "context_relevance": triad["context_relevance"]["score"],
                "groundedness":      triad["groundedness"]["score"],
                "answer_relevance":  triad["answer_relevance"]["score"],
                "triad_avg":         round(
                    (triad["context_relevance"]["score"] +
                     triad["groundedness"]["score"] +
                     triad["answer_relevance"]["score"]) / 3, 4
                ),
                "reasons": {
                    "context_relevance": triad["context_relevance"]["reason"],
                    "groundedness":      triad["groundedness"]["reason"],
                    "answer_relevance":  triad["answer_relevance"]["reason"],
                },
            })

            print(f"  ✓  triad={triad_rows[-1]['triad_avg']:.2f}  chunks={len(chunks)}")

        except Exception as exc:
            errors += 1
            print(f"  ✗  ERROR: {exc}")
            logger.error("Question %d failed: %s — %s", i, question[:60], exc)

        # Checkpoint every SAVE_EVERY questions
        if i % SAVE_EVERY == 0:
            save_checkpoint(pipeline_rows, triad_rows)
            print(f"  └─ checkpoint saved ({i}/{total} done, {errors} errors so far)")

        time.sleep(RATE_LIMIT_S)

    # Final checkpoint
    save_checkpoint(pipeline_rows, triad_rows)
    print(f"\nPipeline loop done. {len(pipeline_rows)}/{total} succeeded, {errors} failed.")
    return pipeline_rows, triad_rows


# ─────────────────────────────────────────────────────────────────────────────
# RAGAS scoring
# ─────────────────────────────────────────────────────────────────────────────

def run_ragas(pipeline_rows: list[dict], client: OpenAI):
    """
    Run RAGAS evaluation and return an EvaluationResult.

    Uses the legacy singleton metrics from ragas.metrics._* (not the new
    ragas.metrics.collections classes) because ragas 0.4.x evaluate() validates
    metrics against the old Metric base class — the new collections classes
    inherit from BaseMetric which is a different hierarchy and fails the check.
    """
    from datasets import Dataset
    from ragas import evaluate
    # Legacy singleton metrics — these ARE instances of ragas.metrics.base.Metric
    from ragas.metrics._faithfulness import faithfulness
    from ragas.metrics._answer_relevance import answer_relevancy
    from ragas.metrics._context_precision import context_precision
    from ragas.metrics._context_recall import context_recall
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings as LCOpenAIEmbeddings

    llm_wrap = LangchainLLMWrapper(ChatOpenAI(model=RAGAS_MODEL, temperature=0))
    emb_wrap = LangchainEmbeddingsWrapper(LCOpenAIEmbeddings(model=EMBEDDING_MODEL))

    # Configure each singleton in-place
    faithfulness.llm      = llm_wrap
    answer_relevancy.llm  = llm_wrap
    answer_relevancy.embeddings = emb_wrap
    context_precision.llm = llm_wrap
    context_recall.llm    = llm_wrap

    ds = Dataset.from_dict({
        "question":     [r["question"]     for r in pipeline_rows],
        "answer":       [r["answer"]       for r in pipeline_rows],
        "contexts":     [r["contexts"]     for r in pipeline_rows],
        "ground_truth": [r["ground_truth"] for r in pipeline_rows],
    })

    print("\nRunning RAGAS evaluation (this may take a few minutes)...")
    result = evaluate(
        dataset=ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        raise_exceptions=False,
        show_progress=True,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Report generation + pretty-print
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(v) -> float:
    """Convert score to float, treating NaN as 0.0."""
    try:
        f = float(v)
        return 0.0 if f != f else f  # NaN check
    except Exception:
        return 0.0


def build_and_save_reports(
    pipeline_rows: list[dict],
    triad_rows:    list[dict],
    ragas_result,
) -> dict:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # ── RAGAS report ──────────────────────────────────────────────────────────
    ragas_scores_df = ragas_result.to_pandas()
    ragas_per_question = ragas_scores_df.to_dict(orient="records")

    ragas_avg = {
        "faithfulness":           _safe_float(ragas_scores_df.get("faithfulness",           [0]).mean() if hasattr(ragas_scores_df.get("faithfulness", [0]), "mean") else ragas_scores_df["faithfulness"].mean()),
        "answer_relevancy":       _safe_float(ragas_scores_df["answer_relevancy"].mean()       if "answer_relevancy"       in ragas_scores_df.columns else 0),
        "context_precision":      _safe_float(ragas_scores_df["context_precision"].mean()      if "context_precision"      in ragas_scores_df.columns else 0),
        "context_recall":         _safe_float(ragas_scores_df["context_recall"].mean()         if "context_recall"         in ragas_scores_df.columns else 0),
    }
    ragas_avg["ragas_average"] = round(
        sum(ragas_avg.values()) / len(ragas_avg), 4
    )

    ragas_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "n_questions":  len(pipeline_rows),
        "averages":     ragas_avg,
        "per_question": ragas_per_question,
    }
    (EVAL_DIR / "ragas_report.json").write_text(json.dumps(ragas_report, indent=2))

    # ── RAG Triad report ──────────────────────────────────────────────────────
    def col_avg(key: str) -> float:
        vals = [r[key] for r in triad_rows if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    triad_avg = {
        "context_relevance": col_avg("context_relevance"),
        "groundedness":      col_avg("groundedness"),
        "answer_relevance":  col_avg("answer_relevance"),
    }
    triad_avg["triad_average"] = round(
        sum(triad_avg.values()) / len(triad_avg), 4
    )

    triad_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "n_questions":  len(triad_rows),
        "averages":     triad_avg,
        "per_question": triad_rows,
    }
    (EVAL_DIR / "rag_triad_report.json").write_text(json.dumps(triad_report, indent=2))

    # ── Per-question combined scores (for bottom-5) ───────────────────────────
    # Attach RAGAS row scores to pipeline rows where possible
    combined_per_q: list[dict] = []
    ragas_cols = [c for c in ragas_scores_df.columns if c != "question"]

    for i, row in enumerate(pipeline_rows):
        ragas_row_scores = {}
        if i < len(ragas_scores_df):
            for col in ragas_cols:
                ragas_row_scores[col] = _safe_float(ragas_scores_df.iloc[i][col])

        triad_row = triad_rows[i] if i < len(triad_rows) else {}
        triad_row_scores = {
            "context_relevance": triad_row.get("context_relevance", 0.0),
            "groundedness":      triad_row.get("groundedness",      0.0),
            "answer_relevance":  triad_row.get("answer_relevance",  0.0),
        }

        all_scores = list(ragas_row_scores.values()) + list(triad_row_scores.values())
        combined_score = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0

        combined_per_q.append({
            "question":      row["question"],
            "combined_score": combined_score,
            "ragas":         ragas_row_scores,
            "triad":         triad_row_scores,
        })

    combined_per_q.sort(key=lambda x: x["combined_score"])
    bottom_5 = combined_per_q[:5]

    # ── Overall score ─────────────────────────────────────────────────────────
    overall = round(
        (ragas_avg["ragas_average"] + triad_avg["triad_average"]) / 2, 4
    )

    # ── Summary JSON ─────────────────────────────────────────────────────────
    summary = {
        "generated_at":   datetime.utcnow().isoformat() + "Z",
        "n_evaluated":    len(pipeline_rows),
        "overall_score":  overall,
        "ragas": {
            "faithfulness":      ragas_avg["faithfulness"],
            "answer_relevancy":  ragas_avg["answer_relevancy"],
            "context_precision": ragas_avg["context_precision"],
            "context_recall":    ragas_avg["context_recall"],
            "average":           ragas_avg["ragas_average"],
        },
        "rag_triad": {
            "context_relevance": triad_avg["context_relevance"],
            "groundedness":      triad_avg["groundedness"],
            "answer_relevance":  triad_avg["answer_relevance"],
            "average":           triad_avg["triad_average"],
        },
        "bottom_5_questions": [
            {"rank": j+1, "question": b["question"], "score": b["combined_score"]}
            for j, b in enumerate(bottom_5)
        ],
    }
    (EVAL_DIR / "eval_summary.json").write_text(json.dumps(summary, indent=2))

    return summary


def print_report(summary: dict) -> None:
    W = 52
    sep = "=" * W
    sub = "-" * W

    print(f"\n{sep}")
    print(f"  Omega TK RAG Pipeline — Evaluation Report")
    print(sep)

    print(f"\n  RAGAS Metrics")
    print(sub)
    r = summary["ragas"]
    print(f"  {'Faithfulness':<28} {r['faithfulness']:.2f}")
    print(f"  {'Answer Relevancy':<28} {r['answer_relevancy']:.2f}")
    print(f"  {'Context Precision':<28} {r['context_precision']:.2f}")
    print(f"  {'Context Recall':<28} {r['context_recall']:.2f}")
    print(f"  {'RAGAS Average':<28} {r['average']:.2f}")

    print(f"\n  RAG Triad Metrics")
    print(sub)
    t = summary["rag_triad"]
    print(f"  {'Context Relevance':<28} {t['context_relevance']:.2f}")
    print(f"  {'Groundedness':<28} {t['groundedness']:.2f}")
    print(f"  {'Answer Relevance':<28} {t['answer_relevance']:.2f}")
    print(f"  {'Triad Average':<28} {t['average']:.2f}")

    print(f"\n  {'Overall Pipeline Score':<28} {summary['overall_score']:.2f}")
    print(sep)
    print(f"  Evaluated on {summary['n_evaluated']} gold standard pairs")
    print(f"\n  Bottom 5 Questions (lowest combined scores):")
    for item in summary["bottom_5_questions"]:
        q = item["question"]
        q_disp = (q[:55] + "...") if len(q) > 58 else q
        print(f"  {item['rank']}. {q_disp} — score: {item['score']:.2f}")
    print(sep + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  Omega TK RAG Eval — starting")
    print("=" * 52)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # Load gold standard
    gold = load_gold_standard()

    print("Initialising OpenAI client...")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ── Resume from checkpoint if it already covers all questions ────────────
    checkpoint_path = EVAL_DIR / "_checkpoint_pipeline.json"
    pipeline_rows: list[dict] = []
    triad_rows:    list[dict] = []

    if checkpoint_path.exists():
        try:
            cp = json.loads(checkpoint_path.read_text())
            if len(cp.get("pipeline", [])) >= len(gold):
                pipeline_rows = cp["pipeline"]
                triad_rows    = cp["triad"]
                print(
                    f"Resuming from checkpoint — {len(pipeline_rows)} rows already evaluated. "
                    "Skipping pipeline loop, running RAGAS only."
                )
        except Exception as exc:
            print(f"Could not load checkpoint ({exc}), re-running pipeline.")

    if not pipeline_rows:
        # ── Pipeline loop: retrieve + generate + RAG Triad ────────────────────
        print("Loading retriever...")
        retriever = get_retriever()
        print(f"\nRunning pipeline eval on {len(gold)} questions...\n")
        pipeline_rows, triad_rows = run_pipeline_eval(gold, retriever, client)

    if not pipeline_rows:
        print("ERROR: No questions succeeded. Aborting.")
        sys.exit(1)

    # ── RAGAS ─────────────────────────────────────────────────────────────────
    ragas_result = run_ragas(pipeline_rows, client)

    # ── Build reports ─────────────────────────────────────────────────────────
    print("\nSaving reports to data/eval/...")
    summary = build_and_save_reports(pipeline_rows, triad_rows, ragas_result)

    # ── Print terminal summary ────────────────────────────────────────────────
    print_report(summary)

    print(f"  Reports saved to: {EVAL_DIR}/")
    print(f"    ragas_report.json")
    print(f"    rag_triad_report.json")
    print(f"    eval_summary.json\n")


if __name__ == "__main__":
    main()
