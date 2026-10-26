"""Pre-run check: every word in tools/scripts.json must be one Droso owns.

A script word he does not own cannot be bound, cannot be answered with, and
cannot be scored -- the script would measure nothing.  This check runs
before the benchmark and fails loudly if any word is missing.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.converse import build  # noqa: E402

agent = build(ROOT / "state" / "sessions" / "wordcheck")
lang = agent.language
vocab = set(lang.word_patterns)

scripts = json.loads((ROOT / "tools" / "scripts.json").read_text(
    encoding="utf-8"))["scripts"]

missing = {}
for s in scripts:
    words = set()
    for t in s["turns"]:
        for key in ("say", "ask"):
            if key in t:
                words |= set(re.findall(r"[a-z']+", t[key].lower()))
        e = t.get("expect") or {}
        for k in ("any_of", "must_contain", "must_not_contain"):
            words |= set(e.get(k) or [])
    miss = sorted(w for w in words if w not in vocab)
    if miss:
        missing[s["name"]] = miss

if missing:
    for name, miss in missing.items():
        print(f"MISSING in {name}: {miss}")
    raise SystemExit(1)
print("all script words owned by Droso")
print(f"scripts: {[s['name'] for s in scripts]}")
print(f"turn counts: {[len(s['turns']) for s in scripts]}")