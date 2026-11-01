"""C3 diagnosis: is the cohort gradient AGE, or FRAME COMPOSITION?

Reads the old-path longevity JSON and answers two separate questions:
  1. verdict by frame -- does one held-out frame account for all failures?
  2. verdict by fact across probes -- does any fact get WORSE in a later probe
     than it was in an earlier one? That is the interference/decay test, and it
     is the only test that can distinguish "age damaged this fact" from "this
     fact was never answerable by the old path".
"""
import collections
import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "docs" / "evidence" / \
    "electric_c3_longevity_oldpath.json"
d = json.loads(p.read_text(encoding="utf-8"))
facts = {f["n"]: f for f in d["facts"]}

print("--- 1. verdict by held-out FRAME (final probe, old path) ---")
by = collections.defaultdict(collections.Counter)
for r in d["cycles_out"][-1]["rows"]:
    if r["which"] == "H":
        by[r["frame"]][r["verdict"]] += 1
for k in sorted(by):
    print(f"  {k:<18} {dict(by[k])}")

print("\n--- 1b. how many facts drew each frame, per cohort ---")
mix = collections.defaultdict(collections.Counter)
for f in d["facts"]:
    mix[(f["n"] - 1) // 5 + 1][f["frame_H"].split("-")[0]] += 1
for c in sorted(mix):
    print(f"  cohort {c}: {dict(mix[c])}")

print("\n--- 2. per-fact H verdict at every probe (decay / interference) ---")
hist = collections.defaultdict(dict)
for c in d["cycles_out"]:
    for r in c["rows"]:
        if r["which"] == "H":
            hist[r["n"]][c["cycle"]] = r["verdict"]
rank = {"correct": 0, "refusal": 1, "other": 2, "confabulation": 3, "silence": 4}
changed = []
for n in sorted(hist):
    v = hist[n]
    seq = [v[c] for c in sorted(v)]
    worse = any(rank[seq[i + 1]] > rank[seq[i]] for i in range(len(seq) - 1))
    if worse:
        changed.append(n)
    print(f"  n{n:<2} c{(n - 1) // 5 + 1} {v.get('frame', facts[n]['frame_H'].split('-')[0]):<4}"
          f" {seq}")
print(f"\nfacts that got WORSE in a later probe: {len(changed)} {changed}")

print("\n--- 3. what the old path SAYS when it confabulates H2 ---")
for c in d["cycles_out"]:
    for r in c["rows"]:
        if r["which"] == "H" and r["verdict"] == "confabulation":
            print(f"  cycle {c['cycle']} n{r['n']} {r['frame']}")
            print(f"     tell : {facts[r['n']]['tell']}")
            print(f"     ask  : {r['ask']}")
            print(f"     said : {r['said']}")
            norm = lambda s: " ".join(w.strip("?.!,") for w in str(s).lower().split())
            print(f"     said == ask verbatim: {norm(r['said']) == norm(r['ask'])}")
