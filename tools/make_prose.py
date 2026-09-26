"""A book made of the prose that is already here.

The graded corpus bought volume and not breadth: 43,633 lines, 351 distinct words.
An individual raised on it cannot learn a word the books do not contain, so every
such life caps out near two hundred words however long it runs -- and vocabulary,
not line count, is what stands between him and English.

This extracts the prose that already exists in the project: docstrings and
comments, which are ordinary English sentences written to explain something. It is
a large lexicon, it is grammatical, and it is about what he is, which is not a
neutral choice -- an animal that learns to talk from its own documentation ends up
able to talk about itself, and that is a capability rather than a side effect.

Identifiers are split on underscores, so `learn_from_task` becomes three English
words instead of one token no sentence elsewhere contains. Sentences that are
mostly code are dropped: the point is language, and a line of API signatures
teaches nothing about word order.

Usage:
    python tools/make_prose.py                 # writes books/07_prose.txt
    python tools/make_prose.py --min-words 5
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ("organs", "world", "connectome", "server", "tools", "tests")
OUT = ROOT / "books" / "07_prose.txt"

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORDISH = re.compile(r"[a-z][a-z'\-]*")
_CODEY = re.compile(r"[(){}\[\]<>=/*|\\@~`^$%+;:]")


def _clean(text: str) -> str:
    """Prose out of a docstring or comment: identifiers split, markup dropped."""
    t = str(text or "")
    t = t.replace("`", " ").replace("*", " ").replace("::", ":")
    # `learn_from_task` and learn_from_task both become three words
    t = re.sub(r"\b([a-z]+(?:_[a-z0-9]+)+)\b", lambda m: m.group(1).replace("_", " "), t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _sentences(text: str, min_words: int, max_words: int) -> list:
    out = []
    for chunk in _SENT_SPLIT.split(text):
        c = chunk.strip().strip(":").strip()
        if not c or len(c) < 12:
            continue
        words = [w for w in c.split() if w]
        if not (min_words <= len(words) <= max_words):
            continue
        if _CODEY.search(c):
            # A sentence that is mostly punctuation and operators is a code
            # fragment with prose wrapped around it.
            codey = sum(1 for ch in c if _CODEY.match(ch))
            if codey > max(2, len(c) // 40):
                continue
        alpha = sum(1 for w in words if _WORDISH.fullmatch(w.lower()))
        if alpha < len(words) * 0.7:
            continue
        s = re.sub(r"\s+", " ", c).strip()
        if not s.endswith((".", "!", "?")):
            s += "."
        out.append(s)
    return out


def harvest(min_words: int = 4, max_words: int = 24) -> list:
    seen: set = set()
    rows: list = []

    def add(text: str):
        for s in _sentences(_clean(text), min_words, max_words):
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append(s)

    for folder in SCAN:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.as_posix():
                continue
            try:
                src = path.read_text(encoding="utf-8")
                tree = ast.parse(src)
            except (OSError, SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef, ast.Module)):
                    doc = ast.get_docstring(node)
                    if doc:
                        add(doc)
            # comments, which in this project carry most of the reasoning
            for line in src.splitlines():
                st = line.strip()
                if st.startswith("#") and not st.startswith("#!"):
                    add(st.lstrip("#").strip())
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-words", type=int, default=4)
    ap.add_argument("--max-words", type=int, default=24)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    rows = harvest(a.min_words, a.max_words)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    vocab = set()
    total = 0
    for s in rows:
        ws = [w for w in re.findall(r"[a-z']+", s.lower())]
        total += len(ws)
        vocab.update(ws)
    print(json.dumps({"book": str(out), "lines": len(rows), "words": total,
                      "distinct_words": len(vocab),
                      "words_per_line": round(total / max(1, len(rows)), 2)},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
