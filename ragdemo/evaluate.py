"""Run the question set and report retrieval hits and correct refusals."""
from __future__ import annotations

from pathlib import Path

import yaml

from .answer import answer
from .index import BM25Index


def evaluate(index: BM25Index, questions_file: Path, k: int = 3) -> tuple[int, int, list[str]]:
    items = yaml.safe_load(questions_file.read_text(encoding="utf-8"))
    passed, lines = 0, []
    for item in items:
        q, expect = item["question"], item["expect"]
        result = answer(index, q, k=k)
        if expect == "refuse":
            ok = result.refused
            got = "declined" if result.refused else "answered (should decline)"
        else:
            hits = [p for _, p in index.search(q, k=k)]
            found = any(p.file == expect["file"] and p.page == expect["page"] for p in hits)
            ok = found and not result.refused
            got = "source found" if ok else ("declined (should answer)" if result.refused else "source missed")
        passed += ok
        lines.append(f"{'PASS' if ok else 'FAIL'}  {q}  ->  {got}")
    return passed, len(items), lines
