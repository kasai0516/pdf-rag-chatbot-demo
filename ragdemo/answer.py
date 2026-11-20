"""Answer a question from the indexed PDFs, with sources, or decline.

Two modes:
- extractive (default, offline): returns the best-matching sentences, quoted with their page.
- claude (optional): if the `anthropic` package is installed and RAGDEMO_USE_CLAUDE=1,
  Claude writes the answer using only the retrieved passages and cites them.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .index import BM25Index, Passage, terms

NOT_FOUND = "I couldn't find this in the documents."
MIN_COVERAGE = 0.6  # share of question words that must appear in the best passage
HEADING = re.compile(r"^\d+\.\s")


@dataclass
class Answer:
    text: str
    refused: bool
    sources: list[Passage] = field(default_factory=list)
    mode: str = "extractive"


def _best_sentences(
    question: str, passages: list[Passage], idf: dict[str, float], n: int = 2
) -> list[tuple[str, Passage]]:
    """Rank sentences by the rarity-weighted question words they contain.

    Rare words ("monthly", "annual") weigh more than common ones ("plan"), so a
    sentence about the right subject beats one that merely shares generic words.
    """
    q = set(terms(question))
    lines = []
    for rank, p in enumerate(passages):
        for line in p.text.splitlines():
            if HEADING.match(line) or not line.rstrip().endswith("."):
                continue  # skip section headings and fragments; quote full sentences only
            lines.append((rank, line, p, terms(line)))

    # Subjects the question asks about, e.g. ("monthly", "plan") from "Monthly plans ...".
    asked = {(lt[0], lt[1]) for _, _, _, lt in lines if len(lt) > 1 and lt[0] in q}

    candidates = []
    for rank, line, p, lt in lines:
        overlap = sum(idf.get(t, 0.0) for t in q & set(lt))
        if not overlap:
            continue
        # A sentence about a *different* subject of the same kind ("Annual plans ..." when the
        # question is about monthly plans) ranks below every sentence without that conflict.
        conflict = bool(lt) and lt[0] not in q and len(lt) > 1 and any(s == lt[1] for _, s in asked)
        if lt and lt[0] in q:
            overlap += idf.get(lt[0], 0.0)  # the sentence is about what the question names
        candidates.append((not conflict, overlap, -rank, line, p))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]), reverse=True)
    picked, seen = [], set()
    for _, _, _, line, p in candidates:
        if line not in seen:
            picked.append((line, p))
            seen.add(line)
        if len(picked) == n:
            break
    return picked


def _ask_claude(question: str, passages: list[Passage]) -> str:
    import anthropic  # optional dependency

    numbered = "\n\n".join(f"[{i}] ({p.cite})\n{p.text}" for i, p in enumerate(passages, start=1))
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY or an `ant auth login` profile
    response = client.beta.messages.create(
        model=os.environ.get("RAGDEMO_MODEL", "claude-opus-5-5"),
        max_tokens=16000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=(
            "Answer the user's question using only the numbered passages. "
            "Cite the passages you used like [1]. Keep the answer to one to three sentences. "
            "If the passages do not contain the answer, reply with exactly: NOT_IN_DOCUMENTS"
        ),
        messages=[{"role": "user", "content": f"Passages:\n{numbered}\n\nQuestion: {question}"}],
    )
    if response.stop_reason == "refusal":
        return "NOT_IN_DOCUMENTS"
    return "".join(block.text for block in response.content if block.type == "text").strip()


def answer(index: BM25Index, question: str, k: int = 3) -> Answer:
    hits = index.search(question, k=k)
    if not hits or index.coverage(question, hits[0][1]) < MIN_COVERAGE:
        return Answer(NOT_FOUND, refused=True)
    passages = [p for _, p in hits]

    if os.environ.get("RAGDEMO_USE_CLAUDE") == "1":
        text = _ask_claude(question, passages)
        if text == "NOT_IN_DOCUMENTS" or not text:
            return Answer(NOT_FOUND, refused=True, mode="claude")
        return Answer(text, refused=False, sources=passages, mode="claude")

    picked = _best_sentences(question, passages, index.idf)
    if not picked:
        return Answer(NOT_FOUND, refused=True)
    text = " ".join(f"{line} [{p.cite}]" for line, p in picked)
    sources = list({p.cite: p for _, p in picked}.values())
    return Answer(text, refused=False, sources=sources)
