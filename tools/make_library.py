"""Give him books that were not written for him.

The whole generated corpus -- 45,359 lines across seven books -- contains 2,549
distinct words. He knows 3,050. That is not a coincidence and it is not a ceiling he
can read past: a word no book contains cannot be learned, so goal A was capped by the
library rather than by the animal. Everything built so far raises how well he reads;
none of it raises what there is to read.

So this fetches public-domain English from Project Gutenberg and lays it out the way
his reader expects: one sentence per line, sentences between three and thirty words,
mostly alphabetic, duplicates dropped. Real prose, with the vocabulary and the clause
structure that come with it -- which is also the honest difficulty. Generated
caregiver speech has consistent roles and short sentences; Dickens has neither, and
that is what English is.

The books are graded loosely by how hard they are to read, and the shelf is ordered so
a life starts with the simple ones. Nothing here is required to be finished: he is
persistent and the reading rate is the limit, not the session.

Files land in books/gutenberg_*.txt, which is gitignored -- tens of megabytes of
somebody else's prose does not belong in a repository when a URL and a script
reproduce it exactly.

Usage:
    python tools/make_library.py                  # the graded default set
    python tools/make_library.py --ids 11,74,84   # specific Gutenberg ids
    python tools/make_library.py --max-lines 4000 # cap each book
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "books"

# id -> (name, difficulty). Ordered roughly easy to hard; the shelf is walked
# alphabetically, so the numeric prefix sets the reading order.
DEFAULT_SET = [
    (2591, "grimms_fairy_tales", 1),
    (11, "alice_in_wonderland", 1),
    (244, "a_study_in_scarlet", 2),
    (120, "treasure_island", 2),
    (74, "tom_sawyer", 2),
    (158, "emma", 3),
    (84, "frankenstein", 3),
    (36, "war_of_the_worlds", 3),
    (1661, "sherlock_holmes", 3),
    (98, "a_tale_of_two_cities", 4),
    (1342, "pride_and_prejudice", 4),
    (1400, "great_expectations", 4),
    (2701, "moby_dick", 5),
    (1260, "jane_eyre", 4),
    (5200, "metamorphosis", 4),
    (2600, "war_and_peace", 5),
]

_START = re.compile(r"\*\*\*\s*START OF TH(E|IS) PROJECT GUTENBERG EBOOK", re.I)
_END = re.compile(r"\*\*\*\s*END OF TH(E|IS) PROJECT GUTENBERG EBOOK", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z][a-z'\-]*")
_JUNK = re.compile(r"[^A-Za-z' ,.;:!?\-\n]")


def _body(raw: str) -> str:
    """Strip the Gutenberg licence header and trailer."""
    lines = raw.splitlines()
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and _START.search(ln):
            start = i + 1
        if _END.search(ln):
            end = i
            break
    if start is None:
        start = 0
    if end is None:
        end = len(lines)
    return "\n".join(lines[start:end])


def _sentences(text: str, min_words: int, max_words: int,
               max_lines: int) -> list:
    text = _JUNK.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    seen: set = set()
    out: list = []
    for chunk in _SENT.split(text):
        c = chunk.strip()
        if len(c) < 12:
            continue
        words = [w for w in c.split() if w]
        if not (min_words <= len(words) <= max_words):
            continue
        alpha = sum(1 for w in words if _WORD.fullmatch(w.lower()))
        if alpha < len(words) * 0.85:
            continue
        s = re.sub(r"\s+", " ", c).strip()
        if not s.endswith((".", "!", "?")):
            s += "."
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_lines:
            break
    return out


def fetch(gid: int, timeout: float = 60.0) -> str | None:
    for url in (f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
                f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
                f"https://www.gutenberg.org/files/{gid}/{gid}.txt"):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "droso-reader/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            for enc in ("utf-8", "latin-1"):
                try:
                    return data.decode(enc)
                except UnicodeDecodeError:
                    continue
        except Exception:
            continue
    return None


def build(ids=None, max_lines: int = 6000, min_words: int = 3,
          max_words: int = 30) -> dict:
    BOOKS.mkdir(parents=True, exist_ok=True)
    chosen = DEFAULT_SET if not ids else [
        (int(i), f"gutenberg_{i}", 3) for i in ids]
    report = []
    vocab_before: set = set()
    for p in BOOKS.glob("*.txt"):
        if p.name.startswith("gutenberg_"):
            continue
        vocab_before.update(re.findall(r"[a-z']+",
                                       p.read_text(encoding="utf-8",
                                                   errors="replace").lower()))
    for gid, name, level in chosen:
        t0 = time.time()
        raw = fetch(gid)
        if raw is None:
            report.append({"id": gid, "name": name, "fetched": False})
            continue
        body = _body(raw)
        rows = _sentences(body, min_words, max_words, max_lines)
        out = BOOKS / f"gutenberg_{level}_{name}.txt"
        out.write_text("\n".join(rows) + "\n", encoding="utf-8")
        words = re.findall(r"[a-z']+", " ".join(rows).lower())
        new = set(words) - vocab_before
        vocab_before |= new
        report.append({"id": gid, "name": name, "fetched": True,
                       "level": level, "lines": len(rows),
                       "words": len(words),
                       "distinct": len(set(words)),
                       "new_distinct_words": len(new),
                       "bytes_down": len(raw),
                       "seconds": round(time.time() - t0, 1),
                       "file": out.name})
        print("  %-24s %6d lines %7d words %+6d new"
              % (name, len(rows), len(words), len(new)))
    total_lines = sum(r.get("lines", 0) for r in report)
    return {"books": len([r for r in report if r.get("fetched")]),
            "failed": [r["id"] for r in report if not r.get("fetched")],
            "lines_added": total_lines,
            "distinct_words_now": len(vocab_before),
            "report": report}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="",
                    help="comma-separated Gutenberg ids instead of the default set")
    ap.add_argument("--max-lines", type=int, default=6000)
    ap.add_argument("--min-words", type=int, default=3)
    ap.add_argument("--max-words", type=int, default=30)
    a = ap.parse_args()
    ids = [int(x) for x in a.ids.split(",") if x.strip()] or None
    out = build(ids, a.max_lines, a.min_words, a.max_words)
    print(json.dumps({k: v for k, v in out.items() if k != "report"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
