"""One-off: is the ov=4 on 'where is the box' a double-appended posting
(rebind appends the same row again) or something else?  Replay the
accumulation script, then inspect the row's posting entries and count."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from converse import build

session_dir = ROOT / "state" / "sessions" / f"diag_{time.strftime('%Y%m%d_%H%M%S')}"
agent = build(session_dir)
lang, binder = agent.language, agent.language.cortex.binder

for step in ("the box is heavy", "the box is red", "the box is on the shelf",
             "how is the box", "where is the box"):
    r = lang.respond(step, speaker="you")
    for _ in range(2):
        lang.tick(world_dt=2.0)

def inspect(tokens):
    key = tuple(str(t).strip().lower() for t in tokens)[:binder.max_roles]
    idx = binder._seen.get(key)
    if idx is None:
        print(f"{tokens}: not bound")
        return
    m = binder.meta[idx]
    print(f"prop {' '.join(tokens)!r}: row={idx} count={m.get('count')} "
          f"when={m.get('when')}")
    for w in set(key):
        raw = binder._postings.get(w, [])
        stm = binder._stem_postings.get(__import__('organs.stemming', fromlist=['stem']).stem(w), [])
        print(f"   {w!r}: raw postings x{raw.count(idx)}, "
              f"stem postings x{stm.count(idx)} (list len {len(raw)}/{len(stm)})")

print()
inspect(["where", "is", "the", "box"])
inspect(["droso", "says", "the", "box", "is", "heavy"])
inspect(["the", "box", "is", "heavy"])
inspect(["the", "box", "is", "on", "the", "shelf"])
inspect(["how", "is", "the", "box"])

hits = binder.recall(["is", "the", "box"], k=8)
print("\nrecall now:")
for h in hits:
    print(f"  ov={h['overlap']} {' '.join(str(t) for t in h['tokens'])}")