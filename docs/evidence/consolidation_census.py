"""Before/after census of which rows consolidate() selects.

docs/open_learning_design.md section 7a requires this as proof (ii): the WITNESS_W
change moves what consolidation selects on the live brain, so the change in selection
has to be measured and not assumed.

It reports three nested sets, exactly as consolidate() builds them:
  scanned   the value-ranked top `scan_top` of rows with >= 2 tokens
  urgent    those whose weakest adjacent-pair weight is below `urgency_line`
  picked    urgent[:budget], the rows that would actually be replayed

The distribution is computed by a REPLICA of consolidate()'s selection, and the replica
is VALIDATED against the real function's own returned counters (rows_scanned,
rows_urgent, rows_replayed) in the same run. A replica that disagreed with the real
counts would be reporting on a function that does not exist; the agreement is printed
so the census is evidence rather than a model.

The real consolidate() is called with passes=0, which makes its replay loop
`for _ in range(0)` a no-op: it scans and selects and writes nothing. The house is a
sealed session anyway (converse.build), so live state is untouched either way, and the
guard is checked.

  py -3.10 docs/evidence/consolidation_census.py [--budget 200] [--scan-top 2000]
"""
import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]   # docs/evidence/ -> repo root
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
from tools.converse import build, guard_check, guard_live_files  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--budget", type=int, default=200)
ap.add_argument("--scan-top", type=int, default=2000)
ap.add_argument("--urgency-line", type=float, default=0.1)
ap.add_argument("--label", default="")
a = ap.parse_args()

guard = guard_live_files("consolidation_census")
sd = ROOT / "state" / "sessions" / "_consol_census"
if sd.exists():
    shutil.rmtree(sd)
agent = build(sd)
lang = agent.language
binder = lang.cortex.binder
meta = binder.meta

print(f"WITNESS_W = {json.dumps(lang.WITNESS_W, sort_keys=True)}")
print(f"'you' present: {'you' in lang.WITNESS_W}   default: "
      f"{lang.WITNESS_W.get('__missing__', 0.6)}")
print(f"binder rows {len(meta)}  who {json.dumps(dict(Counter(str(m.get('who') or '?') for m in meta)))}")


def value(m):
    """consolidate()'s own ranking, neural_language.py:501-504."""
    who = str(m.get("who", ""))
    return lang.WITNESS_W.get(who, 0.6) * float(np.log1p(int(m.get("count", 1))))


# ---- replica of the selection
cands = [m for m in meta if len(m.get("tokens", [])) >= 2]
cands.sort(key=value, reverse=True)
scanned = cands[:a.scan_top]
w = lang.san_w
fp = lang._fp_idx
urgent = []
for m in scanned:
    toks = [str(t) for t in m.get("tokens", [])]
    weakest = None
    for x, y in zip(toks, toks[1:]):
        ia, ib = fp(x), fp(y)
        if ia.size == 0 or ib.size == 0:
            continue
        wmax = float(w[np.ix_(ia, ib)].max())
        if weakest is None or wmax < weakest:
            weakest = wmax
    if weakest is not None and weakest < a.urgency_line:
        urgent.append((value(m), m, weakest))
urgent.sort(key=lambda t: t[0], reverse=True)
picked = urgent[:a.budget]


def dist(rows):
    who = Counter(str(m.get("who") or "?") for m in rows)
    cnt = Counter(int(m.get("count", 1)) for m in rows)
    return {"n": len(rows), "who": dict(who.most_common()),
            "count": {str(k): v for k, v in sorted(cnt.items())[:6]},
            "max_count": max(cnt) if cnt else None}


print(f"\nREPLICA  scanned {len(scanned)}  urgent {len(urgent)}  picked {len(picked)}")

# ---- the real function, with its replay loop disabled
real = lang.consolidate(budget=a.budget, passes=0, urgency_line=a.urgency_line,
                        scan_top=a.scan_top)
print(f"REAL     scanned {real['rows_scanned']}  urgent {real['rows_urgent']}  "
      f"replayed {real['rows_replayed']}  ({real['elapsed_s']}s)")
agree = (real["rows_scanned"] == len(scanned)
         and real["rows_urgent"] == len(urgent)
         and real["rows_replayed"] == len(picked))
print(f"replica agrees with the real counters: {agree}")
if not agree:
    print("  THE REPLICA IS WRONG -- the distribution below describes a function "
          "that does not exist")

print(f"\nPICKED (the {len(picked)} rows consolidation would replay)")
print(f"  {json.dumps(dist([m for _v, m, _w in picked]))}")
print(f"SCANNED window (top {len(scanned)} by value)")
print(f"  {json.dumps(dist(scanned))}")
print(f"  value range {value(scanned[-1]):.6f} .. {value(scanned[0]):.6f}")
tied = sum(1 for m in scanned if abs(value(m) - value(scanned[-1])) < 1e-12)
print(f"  rows tied at the window's cutoff value: {tied}"
      + ("   <- the window fills by stable sort, i.e. arrival order"
         if tied > len(scanned) // 2 else ""))

print("\nfirst 10 picked rows:")
for _v, m, wk in picked[:10]:
    print(f"  value={value(m):.4f} who={str(m.get('who')):7s} count={m.get('count'):5d} "
          f"weakest={wk:.4f}  {' '.join(str(t) for t in (m.get('tokens') or []))[:52]}")

you = [m for m in meta if str(m.get("who") or "") == "you"]
print(f"\nwho=='you' rows in this binder: {len(you)}")
if you:
    in_scan = sum(1 for m in you if m in scanned)
    in_pick = sum(1 for m in you if any(m is p for _v, p, _w in picked))
    print(f"  of those, in the scanned window: {in_scan}; picked for replay: {in_pick}")
    print(f"  a taught row's value: {value(you[0]):.6f}   "
          f"a book row at the same count: "
          f"{lang.WITNESS_W.get('book', 0.6) * float(np.log1p(int(you[0].get('count', 1)))):.6f}")

shutil.rmtree(sd, ignore_errors=True)
moved = guard_check(guard)
print(f"\nlive state untouched: {not moved} {moved[:6] if moved else ''}")
if a.label:
    print(f"label: {a.label}")
sys.exit(0 if agree and not moved else 1)
