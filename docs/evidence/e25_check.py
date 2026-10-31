"""E25 -- abort conditions B1-B7 and the corrected prediction, read off the
published journals. Control = generation 21 (absence-inventory only),
treatment = generation 22 (absence-inventory + v_synt). Read-only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "state" / "selection"


def load(p):
    return {(r["script"], r["ask"]): r
            for r in (json.loads(x) for x in
                      p.read_text(encoding="utf-8").splitlines() if x.strip())}


kc = load(SEL / "generation_21_asks.jsonl")
kt = load(SEL / "generation_22_asks.jsonl")
gc = json.loads((SEL / "generation_21.jsonl").read_text(encoding="utf-8"))
gt = json.loads((SEL / "generation_22.jsonl").read_text(encoding="utf-8"))

print("=== ARMS DIFFER IN EXACTLY ONE FLAG ===")
fc = gc["provenance"]["code_flags"]
ft = gt["provenance"]["code_flags"]
print(f"  genome      : {gc['genome_id']} / {gt['genome_id']}")
# Gen 21 ran before the flag existed, so it has no `coverage_exclude_synt` key at
# all. Compare over the UNION of keys and treat a missing key as off -- which is
# exactly what the harness now stamps explicitly on both branches, so that a
# missing key can never again be confused with a deliberate off.
keys = sorted(set(fc) | set(ft))
differing = [k for k in keys if fc.get(k, False) != ft.get(k, False)]
print(f"  ctl flags   : {fc}")
print(f"  trt flags   : {ft}")
print(f"  differing   : {differing}")
print(f"  --> the arms differ in exactly one flag: "
      f"{differing == ['coverage_exclude_synt']}")
same_battery = set(kc) == set(kt)
print(f"  same battery: {same_battery}")


def score(rows, tier):
    sub = [r for r in rows.values() if r.get("tier") == tier]
    return sum(1 for r in sub if r.get("pass")), len(sub)


print("\n=== SCORES (corrected prediction: frozen 19/24, probes 2/14, guard 4/4) ===")
for name, rows in (("control  ", kc), ("treatment", kt)):
    f, p = score(rows, "frozen"), score(rows, "probe")
    tot = sum(1 for r in rows.values() if r.get("pass"))
    print(f"  {name} frozen {f[0]}/{f[1]}   probes {p[0]}/{p[1]}   total {tot}/{len(rows)}")

print("\n=== B1/B4: THE GUARDED SCARF ASK ===")
s = [k for k in kt if k[1] == "where did i say the scarf is?"][0]
c, t = kc[s], kt[s]
b1 = t.get("pass") is True
b4 = (t.get("coverage") is None) and (t["reason"] == c["reason"])
print(f"  B1 still refuses      : {b1}  (pass={t.get('pass')})")
print(f"  B4 coverage None      : {t.get('coverage') is None}  (ctl {c.get('coverage')})")
print(f"  B4 reason unchanged   : {t['reason'] == c['reason']}")
print(f"     reason: {t['reason']!r}")

print("\n=== B2/B3: FLOORS ===")
b3 = score(kt, "frozen")[0] >= 19
print(f"  B3 frozen >= 19/24    : {b3}  ({score(kt, 'frozen')[0]})")
# The 18 probe-tier rows are 14 paraphrase probes + 4 guarded probes. The
# harness's own "probes N/14" column counts only the paraphrase half, so guarded
# has to be read from the published fitness block, not re-derived by guessing at
# a `script` value -- the first version of this check did exactly that, printed
# 0/4, and then reported PASS anyway by reusing the frozen score. Authoritative
# source is the generation record.
for name, gj in (("control  ", gc), ("treatment", gt)):
    fit = gj["fitness"]
    reg = fit["regression"]
    print(f"  {name} frozen={fit['capability']['passed']}/"
          f"{fit['capability']['asked']}  "
          f"guarded={reg['probe_guard_passed']}/{reg['probe_guard_asked']}  "
          f"frozen_lost={reg['frozen_lost_n']}  "
          f"paraphrase={fit['generalisation']['passed']}/"
          f"{fit['generalisation']['asked']}  verdict={reg['verdict']}")
rt = gt["fitness"]["regression"]
b2 = rt["probe_guard_passed"] == rt["probe_guard_asked"] == 4
b3 = rt["frozen_lost_n"] == 0 and gt["fitness"]["capability"]["passed"] >= 19
print(f"  B2 guarded 4/4        : {b2}")
print(f"  B3 frozen >= 19, 0 lost: {b3}")

print("\n=== B5: NO ANSWER SUBTRACTED ===")
lost = [k for k in kc if kc[k].get("pass") and not kt[k].get("pass")]
print(f"  asks the control answered that now refuse: {len(lost)}")
for k in lost:
    print(f"    !! {k[1]!r}")
b5 = not lost

print("\n=== THE TWO PREDICTED GAINS ===")
for ask in ("how often does the bell turn?",
            "what is held by the thing the frost bites?"):
    k = [x for x in kt if x[1] == ask][0]
    print(f"  {ask!r}")
    print(f"     ctl pass={kc[k].get('pass')} stage={kc[k].get('stage')} "
          f"cov={kc[k].get('coverage')}")
    print(f"     trt pass={kt[k].get('pass')} stage={kt[k].get('stage')} "
          f"cov={kt[k].get('coverage')}")

print("\n=== EVERY ASK THAT CHANGED ===")
ch = [k for k in kc if (kc[k].get("pass"), kc[k].get("stage"))
      != (kt[k].get("pass"), kt[k].get("stage"))]
for k in sorted(ch, key=lambda x: x[1]):
    print(f"  {k[1][:52]!r}")
    print(f"     {kc[k].get('pass')},{kc[k].get('stage')} -> "
          f"{kt[k].get('pass')},{kt[k].get('stage')}")
print(f"  total changed: {len(ch)}")

print("\n=== STAGE MASS ===")
for name, rows in (("control  ", kc), ("treatment", kt)):
    d = {}
    for r in rows.values():
        if not r.get("pass") and r.get("stage"):
            d[r["stage"]] = d.get(r["stage"], 0) + 1
    print(f"  {name} {dict(sorted(d.items()))}")

print("\n=== VERDICT ===")
print(f"  B1 scarf still refuses   : {'PASS' if b1 else 'ABORT'}")
print(f"  B2 guarded 4/4           : {'PASS' if b2 else 'ABORT'}")
print(f"  B3 frozen >= 19/24       : {'PASS' if b3 else 'ABORT'}")
print(f"  B4 inventory pre-empts   : {'PASS' if b4 else 'ABORT'}")
print(f"  B5 no answer subtracted  : {'PASS' if b5 else 'ABORT'}")
ok = b1 and b2 and b3 and b4 and b5 and same_battery
print(f"  --> E25 v_synt ACCEPTED  : {ok}")
