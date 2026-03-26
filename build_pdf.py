"""
Build a polished project-explanation PDF for the Omega TK Chatbot.
Run: python3 build_pdf.py
Output: ~/Desktop/OmegaTK_Chatbot_Explained.pdf
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus.flowables import HRFlowable
import os

OUTPUT = os.path.expanduser("~/Desktop/OmegaTK_Chatbot_Explained.pdf")

# ── Colour palette ────────────────────────────────────────────────────────────
DARK       = colors.HexColor("#1a1a2e")
ACCENT     = colors.HexColor("#4f46e5")   # indigo
ACCENT2    = colors.HexColor("#0ea5e9")   # sky blue
GREEN      = colors.HexColor("#16a34a")
AMBER      = colors.HexColor("#d97706")
RED        = colors.HexColor("#dc2626")
LIGHT_BG   = colors.HexColor("#f1f5f9")
MID_GREY   = colors.HexColor("#64748b")
BODY_TEXT  = colors.HexColor("#1e293b")
BOX_BORDER = colors.HexColor("#c7d2fe")   # light indigo

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    s = {}

    s["Title"] = ParagraphStyle(
        "Title", fontName="Helvetica-Bold", fontSize=28,
        leading=34, textColor=DARK, alignment=TA_LEFT, spaceAfter=4
    )
    s["Subtitle"] = ParagraphStyle(
        "Subtitle", fontName="Helvetica", fontSize=13,
        leading=18, textColor=MID_GREY, alignment=TA_LEFT, spaceAfter=2
    )
    s["Author"] = ParagraphStyle(
        "Author", fontName="Helvetica-Oblique", fontSize=10,
        leading=14, textColor=MID_GREY, alignment=TA_LEFT, spaceAfter=2
    )
    s["SectionNum"] = ParagraphStyle(
        "SectionNum", fontName="Helvetica-Bold", fontSize=11,
        leading=14, textColor=ACCENT, spaceBefore=18, spaceAfter=2
    )
    s["SectionTitle"] = ParagraphStyle(
        "SectionTitle", fontName="Helvetica-Bold", fontSize=16,
        leading=20, textColor=DARK, spaceBefore=2, spaceAfter=6
    )
    s["SubTitle"] = ParagraphStyle(
        "SubTitle", fontName="Helvetica-Bold", fontSize=12,
        leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=4
    )
    s["Body"] = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10.5,
        leading=16, textColor=BODY_TEXT, alignment=TA_JUSTIFY,
        spaceAfter=6
    )
    s["BodyB"] = ParagraphStyle(
        "BodyB", fontName="Helvetica-Bold", fontSize=10.5,
        leading=16, textColor=BODY_TEXT, spaceAfter=4
    )
    s["Mono"] = ParagraphStyle(
        "Mono", fontName="Courier", fontSize=9,
        leading=13, textColor=colors.HexColor("#334155"),
        backColor=colors.HexColor("#f8fafc"),
        leftIndent=12, rightIndent=12, spaceAfter=6,
        borderPad=6
    )
    s["TOC"] = ParagraphStyle(
        "TOC", fontName="Helvetica", fontSize=10.5,
        leading=18, textColor=BODY_TEXT, leftIndent=8
    )
    s["TOCBold"] = ParagraphStyle(
        "TOCBold", fontName="Helvetica-Bold", fontSize=11,
        leading=20, textColor=DARK, leftIndent=0
    )
    s["Tag"] = ParagraphStyle(
        "Tag", fontName="Helvetica-Bold", fontSize=8.5,
        leading=11, textColor=colors.white, alignment=TA_CENTER
    )
    s["Caption"] = ParagraphStyle(
        "Caption", fontName="Helvetica-Oblique", fontSize=9,
        leading=12, textColor=MID_GREY, alignment=TA_CENTER, spaceAfter=8
    )
    s["FooterNote"] = ParagraphStyle(
        "FooterNote", fontName="Helvetica-Oblique", fontSize=8.5,
        leading=12, textColor=MID_GREY, spaceAfter=4
    )
    return s

S = make_styles()


# ── Page footer ───────────────────────────────────────────────────────────────
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MID_GREY)
    w, _ = letter
    page = canvas.getPageNumber()
    canvas.drawString(inch, 0.5 * inch, "Omega TK Chatbot — Project Breakdown")
    canvas.drawRightString(w - inch, 0.5 * inch, f"Page {page}")
    canvas.restoreState()


# ── Helper: coloured badge ────────────────────────────────────────────────────
def badge_table(items_colors):
    """items_colors = [(label, bg_color), ...]  → horizontal tag row"""
    cells = []
    for label, bg in items_colors:
        cells.append(
            Table(
                [[Paragraph(label, S["Tag"])]],
                colWidths=[len(label) * 6.5 + 14],
                rowHeights=[16],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("ROUNDEDCORNERS", [4]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
        )
    wrapper = Table([cells], colWidths=None,
                    style=TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]))
    return wrapper


def info_box(paragraphs, bg=LIGHT_BG, border=BOX_BORDER):
    """Shaded box around a list of Paragraph objects."""
    inner = [[p] for p in paragraphs]
    t = Table(inner, colWidths=[6.3 * inch],
              style=TableStyle([
                  ("BACKGROUND", (0, 0), (-1, -1), bg),
                  ("BOX", (0, 0), (-1, -1), 0.75, border),
                  ("LEFTPADDING", (0, 0), (-1, -1), 12),
                  ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                  ("TOPPADDING", (0, 0), (-1, -1), 8),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                  ("ROWBACKGROUNDS", (0, 0), (-1, -1), [bg]),
              ]))
    return t


def flow_table(steps):
    """
    steps = [(label, description), ...]
    Renders a vertical numbered flow table.
    """
    rows = []
    for i, (label, desc) in enumerate(steps):
        num_cell = Paragraph(
            f'<font color="#ffffff"><b>{i+1}</b></font>',
            ParagraphStyle("N", fontName="Helvetica-Bold", fontSize=11,
                           textColor=colors.white, alignment=TA_CENTER, leading=14)
        )
        label_cell = Paragraph(f"<b>{label}</b>", S["Body"])
        desc_cell  = Paragraph(desc, S["Body"])
        rows.append([num_cell, label_cell, desc_cell])

    t = Table(rows, colWidths=[0.35*inch, 1.5*inch, 4.55*inch],
              style=TableStyle([
                  ("BACKGROUND", (0, 0), (0, -1), ACCENT),
                  ("BACKGROUND", (1, 0), (-1, -1), colors.white),
                  ("ROWBACKGROUNDS", (1, 0), (-1, -1),
                   [colors.HexColor("#f8fafc"), colors.white]),
                  ("BOX", (0, 0), (-1, -1), 0.5, BOX_BORDER),
                  ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                  ("VALIGN", (0, 0), (-1, -1), "TOP"),
                  ("LEFTPADDING", (0, 0), (-1, -1), 7),
                  ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                  ("TOPPADDING", (0, 0), (-1, -1), 7),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                  ("ALIGN", (0, 0), (0, -1), "CENTER"),
              ]))
    return t


def two_col(left_items, right_items, left_w=3.0*inch, right_w=3.4*inch):
    """Side-by-side two-column layout."""
    left_paras  = [[p] for p in left_items]
    right_paras = [[p] for p in right_items]
    left_t  = Table(left_paras,  colWidths=[left_w])
    right_t = Table(right_paras, colWidths=[right_w])
    wrapper = Table([[left_t, right_t]],
                    colWidths=[left_w + 0.1*inch, right_w + 0.1*inch],
                    style=TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]))
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD STORY
# ─────────────────────────────────────────────────────────────────────────────

story = []
SP = lambda n=1: Spacer(1, n * 0.12 * inch)
HR = lambda: HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"),
                         spaceAfter=6, spaceBefore=6)


# ══════════════════════════════════════════════════════════════════════════════
#  COVER PAGE
# ══════════════════════════════════════════════════════════════════════════════

cover_bar = Table(
    [[Paragraph("", S["Body"])]],
    colWidths=[6.5 * inch], rowHeights=[6],
    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)])
)
story.append(cover_bar)
story.append(SP(3))

story.append(Paragraph("Omega TK Chatbot", S["Title"]))
story.append(Paragraph("A Complete Technical Breakdown", S["Subtitle"]))
story.append(SP(1))
story.append(HR())
story.append(SP(1))

story.append(Paragraph(
    "This document explains how the Omega TK Chatbot works — from the moment a user "
    "types a question to the moment a validated Python code snippet appears on screen. "
    "It covers the backend pipeline, the three-layer safety system, the AI routing logic, "
    "the React frontend, and where the project can grow from here.",
    S["Body"]
))
story.append(SP(1))

tech_row = [
    ("FastAPI", ACCENT),
    ("OpenAI GPT-4o-mini", colors.HexColor("#7c3aed")),
    ("FAISS", colors.HexColor("#0369a1")),
    ("React + Vite", colors.HexColor("#0d9488")),
    ("Supabase", colors.HexColor("#166534")),
]
story.append(badge_table(tech_row))
story.append(SP(2))

story.append(Paragraph("What This Project Does", S["SubTitle"]))
story.append(Paragraph(
    "The Omega TK Chatbot is a domain-specific AI assistant built for the OpenEye Omega "
    "Toolkit — a Python library used in computational chemistry and drug discovery for "
    "generating 3D molecular conformers. Instead of a generic chatbot, this system knows "
    "exactly what it is supposed to do: answer questions, explain concepts, and write "
    "correct, validated Python code using the OpenEye API.",
    S["Body"]
))
story.append(Paragraph(
    "It is not simply a wrapper around ChatGPT. Every response passes through multiple "
    "safety layers that check intent, verify retrieval confidence, and validate generated "
    "code before it ever reaches the user. If the AI hallucinates a fake function name, "
    "the system catches it and retries automatically.",
    S["Body"]
))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  TABLE OF CONTENTS
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("Contents", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

toc = [
    ("1.", "System Architecture — The Big Picture"),
    ("2.", "How a Request Travels Through the Backend"),
    ("3.", "Layer 1 — Intent Guard (Is this even a valid question?)"),
    ("4.", "Layer 2 — FAISS Retrieval (Finding relevant documentation)"),
    ("5.", "LLM Intent Classifier (Routing to the right path)"),
    ("6.", "Path A — Concept Questions"),
    ("7.", "Path B — Code Generation with Layer 3 Validation"),
    ("8.", "Conversation Memory — History and Summarization"),
    ("9.", "Knowledge Base — User-Uploaded Context"),
    ("10.", "Supabase — Persistence and Analytics"),
    ("11.", "Frontend Architecture — The React Interface"),
    ("12.", "Testing Strategy — 59 Tests and Why They Matter"),
    ("13.", "Improvements and What Could Be Built Next"),
]
for num, title in toc:
    row = Table(
        [[Paragraph(num, S["TOCBold"]), Paragraph(title, S["TOC"])]],
        colWidths=[0.4*inch, 5.8*inch],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(row)

story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — ARCHITECTURE OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("01", S["SectionNum"]))
story.append(Paragraph("System Architecture — The Big Picture", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "Before diving into any code, it helps to see the whole system at once. The chatbot "
    "has three major parts that work together: a React frontend that the user talks to, "
    "a FastAPI backend that processes every message, and a set of external services "
    "(OpenAI for AI, FAISS for search, and Supabase for storage).",
    S["Body"]
))
story.append(SP(0.5))

# Architecture table
arch_data = [
    [
        Paragraph("<b>Layer</b>", S["BodyB"]),
        Paragraph("<b>Technology</b>", S["BodyB"]),
        Paragraph("<b>What It Does</b>", S["BodyB"]),
    ],
    [
        Paragraph("Frontend", S["Body"]),
        Paragraph("React 18 + Vite + Tailwind CDN", S["Body"]),
        Paragraph("The chat UI, welcome screen, analytics dashboard, and knowledge panel the user interacts with.", S["Body"]),
    ],
    [
        Paragraph("API Server", S["Body"]),
        Paragraph("FastAPI + Python 3.12", S["Body"]),
        Paragraph("Receives every message, runs it through the full pipeline, and returns a structured JSON response.", S["Body"]),
    ],
    [
        Paragraph("RAG Engine", S["Body"]),
        Paragraph("FAISS + text-embedding-3-small", S["Body"]),
        Paragraph("Converts the user's question into a vector and finds the most relevant chunks from the pre-built documentation index (131 vectors).", S["Body"]),
    ],
    [
        Paragraph("LLM", S["Body"]),
        Paragraph("GPT-4o-mini (OpenAI)", S["Body"]),
        Paragraph("Classifies intent, generates conversational responses, writes code, and summarizes long conversations.", S["Body"]),
    ],
    [
        Paragraph("Validator", S["Body"]),
        Paragraph("ast + regex (Python stdlib)", S["Body"]),
        Paragraph("Catches syntax errors, missing OpenEye patterns, and hallucinated API names in generated code — no LLM needed.", S["Body"]),
    ],
    [
        Paragraph("Database", S["Body"]),
        Paragraph("Supabase (PostgreSQL)", S["Body"]),
        Paragraph("Stores chat history, query analytics, thumbs up/down feedback, and user-uploaded knowledge chunks.", S["Body"]),
    ],
]

arch_t = Table(arch_data,
               colWidths=[1.1*inch, 1.85*inch, 3.45*inch],
               repeatRows=1,
               style=TableStyle([
                   ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                   ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.HexColor("#f8fafc"), colors.white]),
                   ("BOX", (0, 0), (-1, -1), 0.5, BOX_BORDER),
                   ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("LEFTPADDING", (0, 0), (-1, -1), 8),
                   ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                   ("TOPPADDING", (0, 0), (-1, -1), 7),
                   ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
               ]))
story.append(arch_t)
story.append(SP(1))

story.append(info_box([
    Paragraph(
        "<b>The key design decision:</b> the documentation was pre-processed offline. "
        "All the OpenEye Omega Toolkit docs were chunked into 131 text fragments and "
        "converted into embedding vectors using OpenAI's text-embedding-3-small model. "
        "These are stored in a FAISS index on disk. At query time, only the most relevant "
        "fragments are retrieved — the LLM never has to read the full docs.",
        S["Body"]
    )
]))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — REQUEST PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("02", S["SectionNum"]))
story.append(Paragraph("How a Request Travels Through the Backend", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "Every message the user sends follows the exact same journey. Here is that journey, "
    "step by step, from the moment the user hits Send to when they see a response.",
    S["Body"]
))
story.append(SP(0.5))

pipeline_steps = [
    ("User Sends Message",
     "The React frontend posts the message to POST /api/chat along with the conversation "
     "history (last 6 turns) and a session_id stored in the browser's localStorage."),
    ("Pre-Guardrail Check",
     "Before any LLM call, the server checks if the message is a greeting, a thank-you, "
     "or a capabilities question. If yes, a hardcoded response is returned instantly "
     "— zero latency, zero API cost."),
    ("Layer 1 — Intent Filter",
     "A keyword blocklist and allowlist checks whether the question is on-topic. "
     "Queries containing words like 'poem', 'weather', 'ignore your instructions' are "
     "rejected immediately with a polite fallback message."),
    ("LLM Intent Classifier",
     "GPT-4o-mini classifies the surviving query into one of four buckets: GREETING, "
     "CONVERSATION, CODE, or OFF_TOPIC. This call uses only 10 tokens and runs in "
     "roughly 300ms. It routes the request to the correct generation path."),
    ("FAISS Retrieval (Layer 2)",
     "The query is embedded and compared against the 131-vector FAISS index. The top "
     "matching documentation chunks are retrieved. If no chunk scores above the threshold "
     "(0.20 for concepts, 0.30 for code), the request is rejected with a 'not enough "
     "information' fallback."),
    ("Knowledge Base Merge",
     "If the user has uploaded any personal notes or files via the Knowledge Base panel, "
     "relevant chunks from their uploads are retrieved using cosine similarity in Python "
     "and merged into the context alongside the FAISS results."),
    ("Generation — Path A or B",
     "CONVERSATION intent: GPT-4o-mini generates a natural-language explanation using "
     "a system-message prompt. CODE intent: GPT-4o-mini generates code using a stricter "
     "prompt that demands the 5-step OpenEye pattern."),
    ("Layer 3 — Code Validation",
     "For code responses only, the generated code is validated: syntax check (ast.parse), "
     "pattern check (regex confirms the 5-step workflow), and API name check (allowlist "
     "catches hallucinated function names). If validation fails, the error is fed back "
     "to GPT as a retry hint — up to 5 attempts."),
    ("Supabase Logging",
     "The final response, intent, FAISS score, and latency are written to queries_log "
     "in Supabase. The chat turn is saved to chat_history. Both writes are fire-and-forget "
     "— they don't block the response."),
    ("Response to Client",
     "A JSON object is returned: { explanation, code, language, is_fallback, "
     "fallback_message, attempts }. The frontend renders the explanation as text and the "
     "code in a syntax-highlighted block with a Copy button."),
]

story.append(flow_table(pipeline_steps))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — LAYER 1
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("03", S["SectionNum"]))
story.append(Paragraph("Layer 1 — Intent Guard", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "The first line of defence is a pure Python keyword filter. It runs in microseconds "
    "and costs nothing because it makes no API calls. The logic is straightforward: if the "
    "query contains any word from the blocklist, reject it. If it contains any word from "
    "the allowlist, pass it through. If neither list matches, the request is allowed through "
    "anyway — to avoid false rejections for legitimate but unusually phrased questions.",
    S["Body"]
))
story.append(SP(0.5))

l1_data = [
    [Paragraph("<b>Blocklist (INVALID signals)</b>", S["BodyB"]),
     Paragraph("<b>Allowlist (VALID signals)</b>", S["BodyB"])],
    [Paragraph("poem, poetry, joke, story, song, weather, news, recipe,\nfood, movie, ignore, forget, pretend, roleplay, bypass", S["Body"]),
     Paragraph("how to, generate, create, explain, what is, code, script,\nconfigure, write, show me, example, implement, use", S["Body"])],
]
l1_t = Table(l1_data, colWidths=[3.1*inch, 3.3*inch],
             style=TableStyle([
                 ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                 ("BOX", (0, 0), (-1, -1), 0.5, BOX_BORDER),
                 ("INNERGRID", (0, 0), (-1, -1), 0.3, BOX_BORDER),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("LEFTPADDING", (0, 0), (-1, -1), 10),
                 ("TOPPADDING", (0, 0), (-1, -1), 8),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
             ]))
story.append(l1_t)
story.append(SP(0.8))

story.append(info_box([
    Paragraph(
        "<b>Real example:</b> A user types 'write a poem about molecules.' The word 'poem' "
        "is in the blocklist, so it is rejected before any LLM call is made. "
        "The user gets a polite message explaining the assistant only handles Omega TK topics. "
        "Total processing time: under 1ms.",
        S["Body"]
    )
], bg=colors.HexColor("#fef9c3"), border=colors.HexColor("#fde047")))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — FAISS RETRIEVAL
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("04", S["SectionNum"]))
story.append(Paragraph("Layer 2 — FAISS Retrieval", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "RAG stands for Retrieval-Augmented Generation. Instead of asking GPT to answer "
    "from memory (which leads to hallucinations), the system first finds relevant "
    "passages from the actual OpenEye documentation and includes them in the prompt. "
    "GPT then answers based on what it can read, not what it vaguely recalls.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("How the Index Was Built (Offline, Done Once)", S["SubTitle"]))
story.append(flow_table([
    ("Collect Docs", "The OpenEye Omega Toolkit documentation was gathered: API references, tutorials, code examples."),
    ("Chunk Text",   "Each document was split into overlapping chunks of roughly 400 characters with 50-character overlap so context is not lost at boundaries."),
    ("Embed",        "Each chunk was sent to OpenAI's text-embedding-3-small model, which returns a 1536-dimensional vector representing the meaning of that chunk."),
    ("Index",        "All vectors were loaded into a FAISS IndexFlatIP (inner product) index. The index was saved to disk as a .faiss file alongside a chunks.json metadata file."),
]))
story.append(SP(0.8))

story.append(Paragraph("How Retrieval Works at Query Time", S["SubTitle"]))
story.append(flow_table([
    ("Embed Query",   "The user's question is embedded using the same text-embedding-3-small model, producing a 1536-dim vector."),
    ("Search Index",  "FAISS computes the inner product between the query vector and all 131 stored vectors in milliseconds. The top-k highest scoring chunks are returned."),
    ("Apply Threshold", "Chunks below the similarity threshold are discarded. Concept queries use 0.20 (lower — because natural language scores lower against technical docs). Code queries use 0.30."),
    ("Format Context", "The surviving chunks are formatted into a readable context string and inserted into the LLM prompt."),
]))
story.append(SP(0.8))

story.append(info_box([
    Paragraph(
        "<b>Why two different thresholds?</b> When a user asks 'what is OEOmega?' (concept), "
        "the phrasing is general and the FAISS score will be lower even for highly relevant chunks. "
        "Concept queries use 0.20 so they don't get rejected unfairly. Code queries like "
        "'generate conformers for aspirin' are more technical and score higher — they use 0.30 "
        "for stricter relevance.",
        S["Body"]
    )
]))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — LLM CLASSIFIER
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("05", S["SectionNum"]))
story.append(Paragraph("LLM Intent Classifier — Smart Routing", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "After the keyword filter passes a request, a fast GPT-4o-mini call classifies the "
    "intent into exactly one of four categories. The model is given a system prompt that "
    "defines each category precisely, and it responds with a single word. The entire call "
    "uses about 10 output tokens — it is intentionally minimal.",
    S["Body"]
))
story.append(SP(0.5))

intent_data = [
    [Paragraph("<b>Intent</b>", S["BodyB"]),
     Paragraph("<b>Example Query</b>", S["BodyB"]),
     Paragraph("<b>What Happens</b>", S["BodyB"])],
    [Paragraph("GREETING", S["Body"]),
     Paragraph("'hello', 'thanks'", S["Body"]),
     Paragraph("Hardcoded instant response (already handled before this step in most cases)", S["Body"])],
    [Paragraph("CONVERSATION", S["Body"]),
     Paragraph("'what is OEOmega?', 'explain sampling modes'", S["Body"]),
     Paragraph("Path A: natural language response, no forced code block", S["Body"])],
    [Paragraph("CODE", S["Body"]),
     Paragraph("'write code to generate conformers', 'show me an example'", S["Body"]),
     Paragraph("Path B: code generation with Layer 3 validation and retry", S["Body"])],
    [Paragraph("OFF_TOPIC", S["Body"]),
     Paragraph("'capital of France', 'who is Elon Musk'", S["Body"]),
     Paragraph("Fallback response, no LLM generation", S["Body"])],
]
intent_t = Table(intent_data,
                 colWidths=[1.2*inch, 2.0*inch, 3.2*inch],
                 repeatRows=1,
                 style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                     ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                      [colors.HexColor("#f8fafc"), colors.white]),
                     ("BOX", (0, 0), (-1, -1), 0.5, BOX_BORDER),
                     ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("LEFTPADDING", (0, 0), (-1, -1), 8),
                     ("TOPPADDING", (0, 0), (-1, -1), 7),
                     ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                 ]))
story.append(intent_t)
story.append(SP(0.8))

story.append(Paragraph("The Fallback Classifier", S["SubTitle"]))
story.append(Paragraph(
    "If the OpenAI API call fails for any reason (network issue, timeout, rate limit), "
    "the system falls back to a keyword-based classifier. This ensures the chatbot never "
    "goes completely dark — it degrades gracefully rather than crashing.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Context-Aware Classification", S["SubTitle"]))
story.append(Paragraph(
    "The classifier receives the last two messages from conversation history alongside "
    "the current query. This means 'verify this code' is correctly classified as CONVERSATION "
    "because the classifier can see that 'this code' refers to something from the previous "
    "turn. Without history, it might wrongly route it toward code generation.",
    S["Body"]
))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — PATH A
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("06", S["SectionNum"]))
story.append(Paragraph("Path A — Answering Concept Questions", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "When the intent is CONVERSATION, the system takes the gentler path. The goal is "
    "a natural, helpful explanation — not a forced code dump. The system prompt is "
    "written like instructions to a knowledgeable colleague, not a code generator.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("What the Prompt Tells GPT", S["SubTitle"]))

prompt_rules = [
    ("Respond naturally", "Answer like a helpful colleague. No robotic structure."),
    ("No code unless asked", "Do not include a code block unless the user explicitly requests one."),
    ("Match response length", "Short factual questions get 3-5 sentences. Conceptual questions get 2-3 short paragraphs."),
    ("Name real APIs", "Always mention actual class names (OEOmegaOptions, OEFlipperOptions) with concrete parameter examples."),
    ("Yes/No questions", "Start with Yes or No, then explain in 2-4 sentences."),
    ("Verify code", "If the user asks to check code, analyse it step by step and give a direct verdict."),
]
story.append(flow_table(prompt_rules))
story.append(SP(0.8))

story.append(info_box([
    Paragraph(
        "<b>Temperature = 0.4</b> — slightly higher than the code path (0.2) to allow "
        "for more natural, varied phrasing. Max tokens: 800. The conversational prompt is "
        "injected as a system message so it persists across the full message history.",
        S["Body"]
    )
]))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — PATH B + LAYER 3
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("07", S["SectionNum"]))
story.append(Paragraph("Path B — Code Generation with Layer 3 Validation", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "Code generation is where things get interesting. GPT is good at writing Python, "
    "but it is also very capable of inventing function names that do not exist. In a "
    "domain-specific toolkit like OpenEye Omega, a hallucinated API call is worse than "
    "no code at all — a researcher could waste hours debugging something that simply "
    "does not exist. Layer 3 exists to catch exactly this.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("The 5-Step OpenEye Pattern", S["SubTitle"]))
story.append(Paragraph(
    "Every valid Omega Toolkit script follows the same structure. The Layer 3 validator "
    "checks that all five components are present before accepting the output.",
    S["Body"]
))
story.append(SP(0.3))

pattern_data = [
    [Paragraph("<b>Step</b>", S["BodyB"]), Paragraph("<b>What It Does</b>", S["BodyB"]), Paragraph("<b>Example</b>", S["BodyB"])],
    [Paragraph("1. Imports", S["Body"]),       Paragraph("Load the OpenEye modules", S["Body"]),       Paragraph("from openeye import oechem, oeomega", S["Mono"])],
    [Paragraph("2. Streams", S["Body"]),        Paragraph("Open input/output molecule files", S["Body"]),Paragraph("ifs = oechem.oemolistream('in.sdf')", S["Mono"])],
    [Paragraph("3. Options", S["Body"]),        Paragraph("Configure the Omega settings", S["Body"]),   Paragraph("opts = oeomega.OEOmegaOptions()", S["Mono"])],
    [Paragraph("4. Build", S["Body"]),          Paragraph("Generate the conformers", S["Body"]),        Paragraph("ret_code = omega.Build(mol)", S["Mono"])],
    [Paragraph("5. Error Check", S["Body"]),    Paragraph("Handle failure return codes", S["Body"]),    Paragraph("OEOmegaReturnCode_Success", S["Mono"])],
]
pattern_t = Table(pattern_data, colWidths=[0.9*inch, 2.0*inch, 3.5*inch],
                  repeatRows=1,
                  style=TableStyle([
                      ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                      ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                       [colors.HexColor("#f8fafc"), colors.white]),
                      ("BOX", (0, 0), (-1, -1), 0.5, BOX_BORDER),
                      ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                      ("VALIGN", (0, 0), (-1, -1), "TOP"),
                      ("LEFTPADDING", (0, 0), (-1, -1), 8),
                      ("TOPPADDING", (0, 0), (-1, -1), 7),
                      ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                  ]))
story.append(pattern_t)
story.append(SP(0.8))

story.append(Paragraph("The Three Validation Checks", S["SubTitle"]))

checks_data = [
    [Paragraph("<b>Check</b>", S["BodyB"]), Paragraph("<b>How It Works</b>", S["BodyB"]), Paragraph("<b>Catches</b>", S["BodyB"])],
    [Paragraph("Syntax Check", S["Body"]),
     Paragraph("ast.parse() — Python's own parser", S["Body"]),
     Paragraph("Unclosed parentheses, missing colons, indentation errors", S["Body"])],
    [Paragraph("Pattern Check", S["Body"]),
     Paragraph("Regex against 5 patterns — passes if 3 or more match", S["Body"]),
     Paragraph("Code that has no OpenEye imports, no Build() call, no error handling", S["Body"])],
    [Paragraph("API Name Check", S["Body"]),
     Paragraph("Every oeomega.X and oechem.X is checked against a curated allowlist", S["Body"]),
     Paragraph("Hallucinated names like oeomega.OEFakeConformerBuilder()", S["Body"])],
]
checks_t = Table(checks_data, colWidths=[1.3*inch, 2.5*inch, 2.6*inch],
                 repeatRows=1,
                 style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dc2626")),
                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                     ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                      [colors.HexColor("#fff5f5"), colors.white]),
                     ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
                     ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#fca5a5")),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("LEFTPADDING", (0, 0), (-1, -1), 8),
                     ("TOPPADDING", (0, 0), (-1, -1), 7),
                     ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                 ]))
story.append(checks_t)
story.append(SP(0.8))

story.append(Paragraph("The Retry Loop", S["SubTitle"]))
story.append(Paragraph(
    "If a check fails, the failure reason is converted into a clear, actionable instruction "
    "and appended to the next generation attempt. For example: 'Your previous code used "
    "unknown API names that may be hallucinated: OEFakeHallucinatedCall. Use only documented "
    "OpenEye Omega Toolkit APIs.' GPT receives this alongside the original question and "
    "generates again. The loop runs up to 5 times. In practice, almost all queries pass "
    "on the first or second attempt.",
    S["Body"]
))
story.append(SP(0.5))

story.append(info_box([
    Paragraph(
        "<b>Temperature = 0.2</b> for code generation — low enough to keep responses "
        "deterministic and correct, but not zero (which can cause repetitive failures on retries). "
        "Max tokens: 2048 to allow for complete code blocks.",
        S["Body"]
    )
]))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — CONVERSATION MEMORY
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("08", S["SectionNum"]))
story.append(Paragraph("Conversation Memory — History and Summarization", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "A chatbot that forgets what was said two messages ago is frustrating. This system "
    "handles memory in two ways: a sliding window for recent turns, and automatic "
    "summarization for older turns that would otherwise be lost.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Sliding Window (Last 6 Turns)", S["SubTitle"]))
story.append(Paragraph(
    "Every API call includes the last 6 messages from the conversation. The frontend "
    "sends the full history in each request, and the backend slices the most recent "
    "6 turns before constructing the LLM message array. This keeps the context window "
    "manageable and costs predictable.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Automatic Summarization (Older Turns)", S["SubTitle"]))
story.append(Paragraph(
    "When the conversation grows beyond 6 turns, the older messages don't simply vanish. "
    "They are summarized into 2-3 sentences by a separate GPT call. The summary captures "
    "what the user was working on, what code was generated, and any decisions made. "
    "This summary is prepended to the LLM context as a system message, so the assistant "
    "always knows the broader story of the conversation.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Summary Caching", S["SubTitle"]))
story.append(Paragraph(
    "Generating a summary costs tokens. The system caches summaries in memory using "
    "an MD5 hash of the message content as the key. If the same slice of history "
    "appears again (because no new old messages were added), the cached summary is "
    "returned instantly. The cache holds up to 200 entries before evicting the oldest.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Follow-Up Query Enrichment", S["SubTitle"]))
story.append(Paragraph(
    "Short follow-up queries like 'now use dense sampling instead' score poorly against "
    "the FAISS index because they contain almost no domain-specific terms. The system "
    "detects follow-up signals ('now', 'also', 'change it', 'same', 'this') and enriches "
    "the FAISS query by appending all prior user messages as context. This improved "
    "retrieval scores from 0.26 to 0.61 in testing.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Persistent History via Supabase", S["SubTitle"]))
story.append(Paragraph(
    "Beyond the in-memory sliding window, every chat turn is written to the chat_history "
    "table in Supabase. When a user reloads the page, their session_id (stored in "
    "localStorage) is used to fetch previous turns from GET /api/history/:session_id. "
    "The frontend reconstructs the message objects — including code blocks — and displays "
    "them with a 'History restored' toast notification.",
    S["Body"]
))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("09", S["SectionNum"]))
story.append(Paragraph("Knowledge Base — User-Uploaded Context", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "The built-in FAISS index covers the official OpenEye documentation. But researchers "
    "often have their own notes, internal protocols, or custom code patterns. The Knowledge "
    "Base feature lets users upload their own context that the assistant will use alongside "
    "the official docs.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Adding Knowledge", S["SubTitle"]))
story.append(Paragraph(
    "Users can paste text directly (with a source name for reference) or upload files. "
    "Supported file types include PDF (text extracted using pypdf), plain text files, "
    "Markdown files, and images. Images are processed through GPT-4o vision to extract "
    "any visible text or describe diagrams technically.",
    S["Body"]
))
story.append(SP(0.5))

kb_steps = [
    ("Text Input",    "User pastes text and gives it a source name in the Knowledge Base panel."),
    ("Chunking",      "The text is split into overlapping chunks of 400 characters using a recursive splitter that respects paragraph and sentence boundaries."),
    ("Embedding",     "Each chunk is embedded using text-embedding-3-small (same model as the FAISS index) to produce a 1536-dim vector."),
    ("Storage",       "Chunks are stored in Supabase's knowledge_chunks table with the session_id, source name, text, and embedding vector (as JSONB, not pgvector)."),
    ("Retrieval",     "At query time, _retrieve_knowledge() fetches all chunks for the session, embeds the query, computes cosine similarity in Python using numpy, and returns the top 3 chunks above a 0.25 threshold."),
    ("Merge",         "Retrieved knowledge chunks are prepended to the prompt context under a [User Knowledge Base] section, above the [Retrieved Documentation] from FAISS."),
]
story.append(flow_table(kb_steps))
story.append(SP(0.8))

story.append(info_box([
    Paragraph(
        "<b>Why JSONB instead of pgvector?</b> Supabase supports pgvector for vector "
        "similarity search in SQL, but that requires a specific database extension and "
        "schema setup. Since the similarity computation happens in Python anyway (using "
        "numpy), storing the embedding as a plain JSONB array is simpler and requires no "
        "additional database configuration. For small numbers of chunks per session, "
        "the performance difference is negligible.",
        S["Body"]
    )
]))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — SUPABASE
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("10", S["SectionNum"]))
story.append(Paragraph("Supabase — Persistence and Analytics", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "Supabase is the persistence layer. It runs as a managed PostgreSQL database in the "
    "cloud. The system uses four tables. All database writes are fire-and-forget — they "
    "don't block the response to the user, so database slowness never affects chat latency.",
    S["Body"]
))
story.append(SP(0.5))

db_data = [
    [Paragraph("<b>Table</b>", S["BodyB"]),
     Paragraph("<b>Key Columns</b>", S["BodyB"]),
     Paragraph("<b>Purpose</b>", S["BodyB"])],
    [Paragraph("chat_history", S["Body"]),
     Paragraph("session_id, role, content, created_at", S["Body"]),
     Paragraph("Stores every user and assistant message so chat can be restored on page reload.", S["Body"])],
    [Paragraph("queries_log", S["Body"]),
     Paragraph("session_id, message, intent, is_fallback, has_code, attempts, faiss_score, latency_ms", S["Body"]),
     Paragraph("Analytics data for every query. Powers the Analytics dashboard.", S["Body"])],
    [Paragraph("feedback", S["Body"]),
     Paragraph("session_id, message_id, feedback ('up'/'down')", S["Body"]),
     Paragraph("Thumbs up/down ratings from users. Shown in Analytics as helpful rate.", S["Body"])],
    [Paragraph("knowledge_chunks", S["Body"]),
     Paragraph("session_id, source, text, embedding (JSONB)", S["Body"]),
     Paragraph("User-uploaded knowledge chunks with their embedding vectors for cosine similarity search.", S["Body"])],
]
db_t = Table(db_data, colWidths=[1.4*inch, 2.1*inch, 2.9*inch],
             repeatRows=1,
             style=TableStyle([
                 ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#166534")),
                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                  [colors.HexColor("#f0fdf4"), colors.white]),
                 ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
                 ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#86efac")),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("LEFTPADDING", (0, 0), (-1, -1), 8),
                 ("TOPPADDING", (0, 0), (-1, -1), 7),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
             ]))
story.append(db_t)
story.append(SP(0.8))

story.append(Paragraph("Graceful Degradation", S["SubTitle"]))
story.append(Paragraph(
    "The system is designed to work even without Supabase configured. If SUPABASE_URL "
    "or SUPABASE_KEY are missing from the environment, every database function returns "
    "silently: chat history returns an empty list, analytics returns zero counts, "
    "feedback writes return {ok: false}. The core chat functionality always works. "
    "This makes local development easy — only the OpenAI key is required.",
    S["Body"]
))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 11 — FRONTEND
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("11", S["SectionNum"]))
story.append(Paragraph("Frontend Architecture — The React Interface", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "The frontend is a single-page React application built with Vite. It uses Tailwind "
    "CSS (loaded via CDN — no build step needed for styles), framer-motion for animations, "
    "lucide-react for icons, and highlight.js for code syntax highlighting. The final "
    "bundle is 324 kB.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Component Structure", S["SubTitle"]))

comp_data = [
    [Paragraph("<b>Component</b>", S["BodyB"]), Paragraph("<b>What It Renders</b>", S["BodyB"])],
    [Paragraph("App.jsx", S["Body"]),            Paragraph("Global state (session, messages, view), session init on mount, history restoration, toast notifications.", S["Body"])],
    [Paragraph("LeftPanel.jsx", S["Body"]),       Paragraph("Sidebar with session list, New Chat button, and nav items for Chat / Analytics / Knowledge Base.", S["Body"])],
    [Paragraph("MiddlePanel.jsx", S["Body"]),     Paragraph("Routes between ChatScreen, AnalyticsDashboard, and KnowledgePanel based on active view.", S["Body"])],
    [Paragraph("ChatScreen.jsx", S["Body"]),      Paragraph("Header with Export button, MessageList, and sticky InputBar at the bottom.", S["Body"])],
    [Paragraph("MessageList.jsx", S["Body"]),     Paragraph("Renders user messages, bot messages (with attempts badge), fallback boxes, and the ThinkingIndicator.", S["Body"])],
    [Paragraph("CodeBlock.jsx", S["Body"]),       Paragraph("Syntax-highlighted code using highlight.js + a Copy button.", S["Body"])],
    [Paragraph("InputBar.jsx", S["Body"]),        Paragraph("Auto-growing textarea, Paperclip and Mic icons (with 'Coming soon' tooltips), Send button.", S["Body"])],
    [Paragraph("AnalyticsDashboard.jsx", S["Body"]), Paragraph("Total Queries, Code Requests, Guardrail Blocks, Avg Latency, Response Quality (helpful rate), recent queries table.", S["Body"])],
    [Paragraph("KnowledgePanel.jsx", S["Body"]), Paragraph("Text paste area, drag-and-drop file upload, list of uploaded sources with delete buttons.", S["Body"])],
    [Paragraph("WelcomeScreen.jsx", S["Body"]),  Paragraph("Shown before first message: branding, tagline, 2x2 suggestion cards.", S["Body"])],
    [Paragraph("TextShimmer.jsx", S["Body"]),    Paragraph("Animated gradient sweep on the ThinkingIndicator text using framer-motion.", S["Body"])],
]
comp_t = Table(comp_data, colWidths=[1.7*inch, 4.7*inch],
               repeatRows=1,
               style=TableStyle([
                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d9488")),
                   ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.HexColor("#f0fdfa"), colors.white]),
                   ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#99f6e4")),
                   ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#99f6e4")),
                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("LEFTPADDING", (0, 0), (-1, -1), 8),
                   ("TOPPADDING", (0, 0), (-1, -1), 7),
                   ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
               ]))
story.append(comp_t)
story.append(SP(0.8))

story.append(Paragraph("Session Persistence", S["SubTitle"]))
story.append(Paragraph(
    "When the app loads, it checks localStorage for a key called omega_session_id. "
    "If found, it reuses that session and fetches the chat history from Supabase. "
    "If not found, it generates a new UUID session_id, saves it to localStorage, and "
    "creates a placeholder session entry. When the user clicks New Chat, a brand new "
    "UUID is generated and saved — the old session history stays in the database.",
    S["Body"]
))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 12 — TESTING
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("12", S["SectionNum"]))
story.append(Paragraph("Testing Strategy — 59 Tests, All Passing", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "The project has a full automated test suite that runs with pytest. All 59 tests "
    "pass consistently. Tests are split into three files, each targeting a different "
    "part of the system.",
    S["Body"]
))
story.append(SP(0.5))

test_data = [
    [Paragraph("<b>File</b>", S["BodyB"]),
     Paragraph("<b>Tests</b>", S["BodyB"]),
     Paragraph("<b>What's Covered</b>", S["BodyB"])],
    [Paragraph("test_guardrails.py", S["Body"]),
     Paragraph("29 tests", S["Body"]),
     Paragraph("Layer 1 intent check (VALID/INVALID for 12 query types), Layer 2 retrieval confidence (custom thresholds), Layer 3 syntax/pattern/API name checks.", S["Body"])],
    [Paragraph("test_chat.py", S["Body"]),
     Paragraph("28 tests", S["Body"]),
     Paragraph("parse_llm_response, build_retrieval_query, _handle_conversational shortcuts, HTTP endpoint tests (with and without OPENAI_API_KEY), live pipeline tests for off-topic/concept/code/attempts.", S["Body"])],
    [Paragraph("test_health.py", S["Body"]),
     Paragraph("2 tests", S["Body"]),
     Paragraph("Health endpoint returns 200 with {status: ok}.", S["Body"])],
]
test_t = Table(test_data, colWidths=[1.6*inch, 0.9*inch, 3.9*inch],
               repeatRows=1,
               style=TableStyle([
                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c3aed")),
                   ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.HexColor("#faf5ff"), colors.white]),
                   ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8b4fe")),
                   ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8b4fe")),
                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("LEFTPADDING", (0, 0), (-1, -1), 8),
                   ("TOPPADDING", (0, 0), (-1, -1), 7),
                   ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
               ]))
story.append(test_t)
story.append(SP(0.8))

story.append(info_box([
    Paragraph(
        "<b>Live tests vs. mocked tests:</b> Tests that require an OpenAI API key are "
        "automatically skipped if the key is not present. This lets the test suite run "
        "in CI environments without secrets. Tests that don't need the key (guardrail "
        "checks, response parsing, hardcoded conversational handlers) always run.",
        S["Body"]
    )
]))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 13 — IMPROVEMENTS
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("13", S["SectionNum"]))
story.append(Paragraph("Improvements and What Could Be Built Next", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph(
    "The system works well, but there are clear directions where it could grow. "
    "Some are small quality-of-life improvements. Others would be significant "
    "architectural additions.",
    S["Body"]
))
story.append(SP(0.5))

story.append(Paragraph("Near-Term Improvements", S["SubTitle"]))

near_term = [
    ("Voice Input",
     "The InputBar has a Mic button that shows 'Coming soon'. The backend already has "
     "POST /api/transcribe which accepts audio via Whisper. Wiring the frontend to "
     "record and send audio would complete this feature with minimal backend work."),
    ("File Attachments in Chat",
     "The Paperclip icon exists in the InputBar. The backend handles file uploads in the "
     "Knowledge Base panel. Allowing files to be attached directly in the chat input "
     "(processed inline as context for that single message) would make the workflow faster."),
    ("pgvector for Knowledge Base",
     "Currently, cosine similarity for knowledge retrieval is computed in Python by "
     "loading all session chunks into memory. Using Supabase's pgvector extension would "
     "push this computation to the database — faster, scalable to thousands of chunks."),
    ("Streaming Responses",
     "Currently, GPT generates the full response before anything appears in the chat. "
     "Using the OpenAI streaming API and Server-Sent Events would show tokens as they "
     "arrive, making the interface feel dramatically faster."),
    ("Code Execution Sandbox",
     "The generated code currently shows in a read-only block. Adding a sandboxed Python "
     "executor (using a service like Pyodide in the browser, or a Docker container on the "
     "server) would let users run the generated code directly and see its output."),
    ("Better Analytics Joins",
     "The feedback table uses session_id + message_id, but queries_log doesn't store "
     "message_id. This makes per-message feedback breakdown impossible without a schema "
     "change. Adding message_id to queries_log would unlock per-response quality metrics."),
]
story.append(flow_table(near_term))
story.append(SP(0.8))

story.append(Paragraph("Larger Architectural Ideas", S["SubTitle"]))

big_ideas = [
    ("Multi-Toolkit Support",
     "The RAG index currently contains only Omega Toolkit docs. The same architecture "
     "would work for OEDocking, OESpruce, or any other OpenEye toolkit by building "
     "separate FAISS indices and routing queries to the right one."),
    ("Fine-Tuned Model",
     "Instead of relying on few-shot prompting and retrieval, a fine-tuned version of "
     "GPT-4o-mini trained on curated Omega Toolkit Q&A pairs would reduce hallucinations "
     "further and potentially eliminate the need for Layer 3 retries."),
    ("Active Learning from Feedback",
     "Thumbs up/down feedback is collected but currently only displayed. A pipeline that "
     "automatically flags low-rated responses for human review and uses them to improve "
     "the prompt or fine-tune the model would close the feedback loop."),
    ("Multi-User Authentication",
     "Currently, any user can access any session by guessing a session_id (UUIDs make "
     "this hard but not impossible). Proper user authentication (OAuth, Supabase Auth) "
     "would isolate sessions and knowledge bases per authenticated user."),
]
story.append(flow_table(big_ideas))
story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
#  FINAL PAGE — QUICK REFERENCE
# ══════════════════════════════════════════════════════════════════════════════

story.append(Paragraph("Quick Reference", S["SectionTitle"]))
story.append(HR())
story.append(SP(0.5))

story.append(Paragraph("All API Endpoints", S["SubTitle"]))

ep_data = [
    [Paragraph("<b>Method</b>", S["BodyB"]), Paragraph("<b>Endpoint</b>", S["BodyB"]), Paragraph("<b>What It Does</b>", S["BodyB"])],
    [Paragraph("GET",    S["Body"]), Paragraph("/api/health",              S["Mono"]), Paragraph("Server health check",                              S["Body"])],
    [Paragraph("POST",   S["Body"]), Paragraph("/api/chat",                S["Mono"]), Paragraph("Main chat endpoint — full pipeline",               S["Body"])],
    [Paragraph("GET",    S["Body"]), Paragraph("/api/history/:session_id", S["Mono"]), Paragraph("Fetch past messages for a session",                S["Body"])],
    [Paragraph("GET",    S["Body"]), Paragraph("/api/analytics",           S["Mono"]), Paragraph("Query stats for last 24 hours",                    S["Body"])],
    [Paragraph("POST",   S["Body"]), Paragraph("/api/feedback",            S["Mono"]), Paragraph("Record thumbs up or down for a response",          S["Body"])],
    [Paragraph("POST",   S["Body"]), Paragraph("/api/knowledge",           S["Mono"]), Paragraph("Add pasted text to the knowledge base",            S["Body"])],
    [Paragraph("POST",   S["Body"]), Paragraph("/api/knowledge-file",      S["Mono"]), Paragraph("Upload a PDF, text, or image file",               S["Body"])],
    [Paragraph("GET",    S["Body"]), Paragraph("/api/knowledge/:session",  S["Mono"]), Paragraph("List knowledge sources for a session",             S["Body"])],
    [Paragraph("DELETE", S["Body"]), Paragraph("/api/knowledge/:chunk_id", S["Mono"]), Paragraph("Delete a knowledge source (all its chunks)",       S["Body"])],
    [Paragraph("POST",   S["Body"]), Paragraph("/api/transcribe",          S["Mono"]), Paragraph("Transcribe audio using Whisper",                   S["Body"])],
]
ep_t = Table(ep_data, colWidths=[0.65*inch, 2.1*inch, 3.65*inch],
             repeatRows=1,
             style=TableStyle([
                 ("BACKGROUND", (0, 0), (-1, 0), DARK),
                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                  [colors.HexColor("#f8fafc"), colors.white]),
                 ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                 ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("LEFTPADDING", (0, 0), (-1, -1), 8),
                 ("TOPPADDING", (0, 0), (-1, -1), 6),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
             ]))
story.append(ep_t)
story.append(SP(0.8))

story.append(Paragraph("Key Numbers", S["SubTitle"]))

nums_data = [
    ["131", "Documentation chunks in the FAISS index"],
    ["1,536", "Embedding dimensions (text-embedding-3-small)"],
    ["5", "Maximum Layer 3 retry attempts per code query"],
    ["6", "Message window injected into every LLM call"],
    ["0.20 / 0.30", "FAISS similarity thresholds (concept / code)"],
    ["0.25", "Knowledge base cosine similarity threshold"],
    ["59", "Automated tests (all passing)"],
    ["200", "In-memory summary cache capacity"],
    ["324 kB", "Frontend bundle size (gzipped)"],
]
nums_t = Table(
    [[Paragraph(f"<b>{n}</b>", ParagraphStyle("Num", fontName="Helvetica-Bold",
                fontSize=14, textColor=ACCENT, leading=16)),
      Paragraph(d, S["Body"])] for n, d in nums_data],
    colWidths=[1.2*inch, 5.2*inch],
    style=TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),
        ("BOX", (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])
)
story.append(nums_t)
story.append(SP(1))

story.append(info_box([
    Paragraph(
        "<b>How to run locally:</b>  "
        "/opt/anaconda3/envs/omega-tk-web/bin/python3 server/app.py "
        "then open http://localhost:8000  —  only OPENAI_API_KEY is required.",
        S["Body"]
    )
], bg=colors.HexColor("#fefce8"), border=colors.HexColor("#fde68a")))


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD
# ─────────────────────────────────────────────────────────────────────────────

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=letter,
    rightMargin=inch,
    leftMargin=inch,
    topMargin=0.9 * inch,
    bottomMargin=0.9 * inch,
)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(f"PDF saved to: {OUTPUT}")
