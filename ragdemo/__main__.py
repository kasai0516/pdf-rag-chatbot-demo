"""CLI: python -m ragdemo {ask,serve,eval} [--docs samples]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .answer import answer
from .evaluate import evaluate
from .index import BM25Index, load_passages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ragdemo", description="Answer questions from your PDFs, with sources.")
    parser.add_argument("--docs", nargs="+", type=Path, default=[Path("samples")], help="PDF files or folders")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask", help="answer one question")
    ask.add_argument("question")
    sub.add_parser("serve", help="start the local web chat")
    ev = sub.add_parser("eval", help="run a question set")
    ev.add_argument("--questions", type=Path, default=Path("samples/questions.yaml"))
    args = parser.parse_args(argv)

    index = BM25Index(load_passages(args.docs))
    if args.cmd == "ask":
        result = answer(index, args.question)
        print(result.text)
        if result.mode == "claude" and result.sources:
            print("\nSources:")
            for i, p in enumerate(result.sources, start=1):
                print(f"  [{i}] {p.cite}")
        return 0
    if args.cmd == "serve":
        from .server import serve

        serve(index)
        return 0
    passed, total, lines = evaluate(index, args.questions)
    print("\n".join(lines))
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
