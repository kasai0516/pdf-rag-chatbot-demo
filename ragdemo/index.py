"""Load PDFs, split them into passages that remember their page, and search them with BM25."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

STOPWORDS = set(
    """a an and are as at be by can could do does for from had has have how i if in is it its
    me much my no not of on or our so than that the their them then there these they this to
    was we what when where which who why will with you your
    please give tell short brief briefly quick quickly answer explain know want need would like help""".split()
)
HEADING = re.compile(r"^\d+\.\s")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
# Don't split after "U.S.", "e.g.", "Inc." and similar.
ABBREVIATION = re.compile(r"(?:\b[A-Za-z]\.|\b(?:e\.g|i\.e|etc|vs|Mr|Mrs|Ms|Dr|Inc|Ltd|Co|No|Fig|approx)\.)$")


def _split(paragraph: str) -> list[str]:
    sentences, start = [], 0
    for m in SENTENCE_END.finditer(paragraph):
        if ABBREVIATION.search(paragraph[start : m.start()]):
            continue
        sentences.append(paragraph[start : m.start()].strip())
        start = m.end()
    sentences.append(paragraph[start:].strip())
    return [s for s in sentences if s]


def stem(word: str) -> str:
    """A deliberately small stemmer: enough to match 'refunded'/'refundable' with 'refund'."""
    for suffix, min_len in (("able", 7), ("ing", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if word.endswith(suffix) and len(word) >= min_len and not word.endswith("ss"):
            return word[: -len(suffix)]
    return word


def terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS]


@dataclass
class Passage:
    file: str
    page: int  # 1-based
    text: str

    @property
    def cite(self) -> str:
        return f"{self.file} p.{self.page}"


def split_sentences(page_text: str) -> list[str]:
    """Rebuild paragraphs from wrapped PDF lines, then split them into sentences.

    Section headings ("2. Refunds") are kept as their own units so they never
    get glued onto a sentence.
    """
    units: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            units.extend(_split(" ".join(buffer)))
            buffer.clear()

    for line in page_text.splitlines():
        line = line.strip()
        if not line:
            flush()
        elif HEADING.match(line):
            flush()
            units.append(line)
        else:
            buffer.append(line)
    flush()
    return units


def load_passages(paths: list[Path], window: int = 4, step: int = 2) -> list[Passage]:
    """Split each page into overlapping windows of sentences so a passage keeps its context."""
    passages: list[Passage] = []
    pdfs: list[Path] = []
    for p in paths:
        pdfs.extend(sorted(p.glob("*.pdf")) if p.is_dir() else [p])
    for pdf in pdfs:
        for page_no, page in enumerate(PdfReader(str(pdf)).pages, start=1):
            sentences = split_sentences(page.extract_text() or "")
            if not sentences:
                continue
            starts = list(range(0, max(len(sentences) - window, 0) + 1, step))
            if starts[-1] + window < len(sentences):
                starts.append(len(sentences) - window)
            for start in starts:
                passages.append(Passage(pdf.name, page_no, "\n".join(sentences[start : start + window])))
    return passages


class BM25Index:
    def __init__(self, passages: list[Passage], k1: float = 1.5, b: float = 0.75):
        self.passages = passages
        self.docs = [Counter(terms(p.text)) for p in passages]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        self.k1, self.b = k1, b
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[float, Passage]]:
        q = terms(query)
        scored = []
        for doc, length, passage in zip(self.docs, self.lengths, self.passages):
            score = 0.0
            for t in q:
                if t in doc:
                    tf = doc[t]
                    denom = tf + self.k1 * (1 - self.b + self.b * length / self.avg_len)
                    score += self.idf.get(t, 0.0) * tf * (self.k1 + 1) / denom
            if score > 0:
                scored.append((score, passage))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    @staticmethod
    def coverage(query: str, passage: Passage) -> float:
        """Share of the question's content words that appear in the passage."""
        q = set(terms(query))
        if not q:
            return 0.0
        return len(q & set(terms(passage.text))) / len(q)
