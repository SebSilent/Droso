"""Reach pre-flight for ANSWER_COVERAGE_FLOOR: does the gene bite, and where?

Cited by docs/selection_design.md section 8 ("Reach, measured before the run rather
than after"). Reads the refusal reasons in a generation's ask journal -- answer()
puts the coverage percentage in the reason string it returns -- and reports which
coverages a candidate floor value would admit or newly refuse.

This is a REACH measurement of the kind tools/fly_population.py reports, not a
tuning input. It was run before generation 1 and sigma was not changed after seeing
it; the stall rule in section 8 forbids changing it after seeing the scores either.

  py -3.10 docs/evidence/coverage_floor_reach.py [--generation 0] [--floor 0.55]
"""
import argparse
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "state" / "selection"
PCT = re.compile(r"covers (\d+)%")

ap = argparse.ArgumentParser()
ap.add_argument("--generation", type=int, default=0)
ap.add_argument("--floor", type=float, default=None,
                help="a candidate floor to test; default reports every observed "
                     "coverage instead")
a = ap.parse_args()

p = SEL / f"generation_{a.generation}_asks.jsonl"
if not p.exists():
    print(f"no ask journal at {p}")
    sys.exit(1)
rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
line = sorted({r["line"] for r in rows})[0]
one = [r for r in rows if r["line"] == line]

print(f"{p.name}: {len(rows)} rows, reporting line {line} ({len(one)} asks)")
print("stage counts:", dict(Counter(r["stage"] for r in one if not r["pass"])))

print(f"\nrefusals carrying a coverage percentage, line {line}:")
obs = []
for r in one:
    m = PCT.search(str(r.get("reason") or ""))
    tag = f"{r['tier']}/{r['id'].split('::')[0]}"
    if m:
        obs.append((int(m.group(1)), r["ask"], tag, r["pass"]))
        print(f"  {int(m.group(1)):3d}%  pass={str(r['pass']):5s} {tag:34s} "
              f"{r['ask'][:46]}")
    elif r["stage"] == "recall":
        print(f"   --   pass={str(r['pass']):5s} {tag:34s} {r['ask'][:46]}"
              f"   [recall with no coverage: {str(r.get('reason'))[:40]}]")

print(f"\n{len(obs)} refusals carry a coverage; distinct values: "
      f"{sorted({o[0] for o in obs})}")

if a.floor is not None:
    # round() is not cosmetic: 0.55 * 100 is 55.00000000000001 in IEEE-754, so an
    # unrounded comparison puts a 55% refusal BELOW a 0.55 floor and reports the
    # gene as inert when it is not. The first version of this script had that bug.
    pct = round(a.floor * 100, 6)
    # And the coverage in the reason string is itself rounded to a whole percent by
    # answer(), so a floor landing exactly on a reported value is genuinely
    # ambiguous: "covers 55%" is any best_cov in [0.545, 0.555), and the organ
    # compares the unrounded one. Flagged rather than silently decided.
    edge = [o for o in obs if abs(o[0] - pct) < 1]
    admitted = [o for o in obs if o[0] >= pct and not o[3]]
    newly = [o for o in obs if o[0] >= pct and o[3]]
    print(f"\nat floor {a.floor}: a refusal at or above {pct:.0f}% would be admitted")
    for o in sorted(edge):
        print(f"  AMBIGUOUS {o[0]:3d}% is within a rounding step of the floor, so "
              f"the organ's unrounded best_cov decides: {o[1][:44]}")
    for o in sorted(admitted):
        print(f"  ADMITTED  {o[0]:3d}%  {o[2]:34s} {o[1][:46]}")
    if not admitted:
        print("  nothing admitted: the floor does not bite at this value")
    for o in sorted(newly):
        print(f"  and a PASS at {o[0]:3d}% still passes (it needed a refusal: "
              f"{o[2]}) {o[1][:40]}")
else:
    print("\nwhich floor values would admit something, and what:")
    for v in sorted({o[0] for o in obs}):
        got = [o for o in obs if o[0] >= v and not o[3]]
        risk = [o for o in obs if o[0] >= v and o[3]]
        print(f"  floor <= {v / 100:.2f}: admits {len(got)} refusal(s)"
              + (f", and puts {len(risk)} pass-by-refusal at risk" if risk else ""))
sys.exit(0)
