"""Census the live binder: who owns the 60,000 rows, and how old are they.

The open-learning design turns on one fact: the binder is a fixed-capacity FIFO
(higher_cortex.py:46 MAX_PROPOSITIONS = 60000) that evicts with np.roll (:399-403)
and is already at capacity. So teaching is not additive, it is displacement -- and
WHAT gets displaced depends on who owns the rows. The figure in
docs/cross_session_design.md (book 59515 / droso 466 / parent 19 / you 0) was
measured 2026-10-25; this re-measures it rather than quoting it.

Read-only: opens the live cortex store directly, builds no house.
"""
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]   # docs/evidence/ -> repo root
sys.path.insert(0, str(ROOT))

meta_p = ROOT / "state" / "language_state.json.cortex.meta.json"
if not meta_p.exists():
    print(f"no cortex meta at {meta_p}")
    sys.exit(1)

meta = json.loads(meta_p.read_text(encoding="utf-8"))
print(f"{meta_p.name}: {len(meta)} rows")

who = collections.Counter(str(m.get("who") or "?") for m in meta)
print("\nrows by who:")
for k, v in who.most_common():
    print(f"  {k:10s} {v:7d}  {v / len(meta):6.2%}")

cnt = collections.Counter(int(m.get("count", 1)) for m in meta)
print("\nrows by count (how often rehearsed):")
for k in sorted(cnt)[:8]:
    print(f"  count {k:3d}  {cnt[k]:7d}")
print(f"  ... {len(cnt)} distinct counts, max {max(cnt)}")
print(f"  rows with count == 1: {cnt.get(1, 0)} ({cnt.get(1, 0) / len(meta):.2%})")

whens = [float(m.get("when") or 0.0) for m in meta if m.get("when")]
if whens:
    now = time.time()
    ages = sorted((now - w) / 86400.0 for w in whens)
    print(f"\nrow ages in days (n={len(ages)}):")
    for q in (0, 10, 50, 90, 100):
        i = min(len(ages) - 1, int(len(ages) * q / 100))
        print(f"  p{q:<3d} {ages[i]:10.2f}")

# The number that decides whether teaching can accumulate: how many rows are
# user-taught and still present, against how many rows one teaching session adds.
you = [m for m in meta if str(m.get("who") or "") == "you"]
print(f"\nwho == 'you' rows: {len(you)}")
for m in you[:12]:
    print(f"   {' '.join(str(t) for t in (m.get('tokens') or []))[:64]:64s} "
          f"count={m.get('count')} age={(time.time() - float(m.get('when') or 0)) / 86400:.2f}d")

toklen = collections.Counter(len(m.get("tokens") or []) for m in meta)
print("\nrows by token length:", dict(sorted(toklen.items())[:10]))
