"""Cross-generation stability: does one genome give one per-ask result?

Cited by docs/selection_design.md section 8 ("zero differences across all seven
lines ... 294 ask evaluations") and by the generation-1 table in docs/STATE.md.

Compares every line of every published generation against the first line of
generation 0 on (pass, stage) per ask. Lines carrying the parent genome that differ
are INSTRUMENT NOISE, and the noise floor has to be known before a mutant's
difference can be attributed to its gene -- which is why this is a separate check
from verify_generation1.py rather than a line inside it.

  py -3.10 docs/evidence/cross_generation_stability.py
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "state" / "selection"

gens = sorted(p for p in SEL.glob("generation_*_asks.jsonl"))
if not gens:
    print(f"no ask journals under {SEL}")
    sys.exit(1)

allrows = []
for p in gens:
    allrows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip()]
    print(f"loaded {p.name}")

# genome_id per line, so a clone line and a mutant line are not confused: a
# difference on a line carrying the SAME genome is noise, on a different genome it
# is either the gene or noise, and only the first kind is interpretable on its own.
genome_of = {}
for p in sorted(SEL.glob("generation_*.jsonl")):
    if p.name.endswith("_asks.jsonl") or p.name.endswith("_asrun.jsonl") \
            or "_prev_" in p.name:
        continue
    for l in p.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            genome_of[r["line"]] = (r["genome_id"], r.get("mutation"))


def key(line):
    return {r["id"]: (r["pass"], r["stage"]) for r in allrows if r["line"] == line}


lines = sorted(genome_of, key=lambda x: (x.split("-")[0], x))
ref_line = lines[0]
ref = key(ref_line)
ref_genome = genome_of[ref_line][0]
print(f"\nreference {ref_line} ({ref_genome}): "
      f"{sum(1 for v in ref.values() if v[0])} passes of {len(ref)} asks\n")

total = 0
noise = 0
for ln in lines:
    k = key(ln)
    d = [i for i in ref if ref[i] != k.get(i)]
    total += len(d)
    gid, mut = genome_of[ln]
    same = gid == ref_genome
    if same:
        noise += len(d)
    tag = "same genome" if same else f"mutant {mut['value']}" if mut else "?"
    print(f"{ln:7s} {gid:13s} {tag:18s} {len(d):3d} asks differ   "
          f"{sum(1 for v in k.values() if v[0])}/{len(k)} pass")
    for i in d[:8]:
        print(f"        {i[:56]:56s} {ref[i]} -> {k.get(i)}")
    if set(ref) ^ set(k):
        print(f"        ask sets differ by {len(set(ref) ^ set(k))}")

n_evals = len(lines) * len(ref)
print(f"\nlines {len(lines)}  ask evaluations {n_evals}")
print(f"total per-ask differences: {total}")
print(f"differences on lines carrying the SAME genome as the reference: {noise}"
      f"   <- the instrument's noise floor")
print("\nstage distribution per line:")
for ln in lines:
    c = Counter(r["stage"] for r in allrows if r["line"] == ln and not r["pass"])
    print(f"  {ln:7s} {dict(sorted(c.items(), key=lambda kv: -kv[1]))}")
sys.exit(1 if noise else 0)
