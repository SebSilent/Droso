"""E26 -- user-visible capability changes, gen 21 (control) vs gen 23 (v_frame)."""
import json
import sys
from pathlib import Path

SEL = Path(__file__).resolve().parents[2] / "state" / "selection"
TRT = sys.argv[1] if len(sys.argv) > 1 else "generation_23"


def load(p):
    return {(r["script"], r["ask"]): r
            for r in (json.loads(x) for x in
                      p.read_text(encoding="utf-8").splitlines() if x.strip())}


c = load(SEL / "generation_21_asks.jsonl")
t = load(SEL / f"{TRT}_asks.jsonl")

print(f"=== {TRT} vs generation_21 : USER-VISIBLE CHANGES ===")
print("\n-- NEWLY ANSWERED --")
n = 0
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b and not a.get("pass") and b.get("pass"):
        n += 1
        print(f"  {k[1]!r}")
        print(f"     before: {str(a.get('said'))[:64]!r}")
        print(f"     after : {str(b.get('said'))[:64]!r}")
print(f"  count: {n}")

print("\n-- NEWLY BROKEN --")
m = 0
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b and a.get("pass") and not b.get("pass"):
        m += 1
        print(f"  {k[1]!r}  stage {a.get('stage')} -> {b.get('stage')}")
print(f"  count: {m}")

print("\n-- STILL FAILING BUT STAGE MOVED (crossed a gate, died at the next) --")
d = 0
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b and not a.get("pass") and not b.get("pass") and a.get("stage") != b.get("stage"):
        d += 1
        print(f"  {k[1][:56]!r}  {a.get('stage')} -> {b.get('stage')}")
print(f"  count: {d}")

pc = sum(1 for r in c.values() if r.get("pass"))
pt = sum(1 for r in t.values() if r.get("pass"))
print(f"\nTOTAL ANSWERED: {pc}/42 -> {pt}/42   NET: {pt - pc:+d}")

print("\n-- STAGE MASS --")
for name, rows in (("ctl", c), ("trt", t)):
    dd = {}
    for r in rows.values():
        if not r.get("pass") and r.get("stage"):
            dd[r["stage"]] = dd.get(r["stage"], 0) + 1
    print(f"  {name} {dict(sorted(dd.items()))}")

# abort conditions from the published fitness block
g = json.loads((SEL / f"{TRT}.jsonl").read_text(encoding="utf-8"))
rt = g["fitness"]["regression"]
s = [k for k in t if k[1] == "where did i say the scarf is?"][0]
print("\n-- ABORT CONDITIONS --")
print(f"  B1 scarf still refuses : {t[s].get('pass') is True}")
print(f"  B4 coverage None       : {t[s].get('coverage') is None}")
print(f"  B4 reason unchanged    : {t[s]['reason'] == c[s]['reason']}")
print(f"  B2 guarded             : {rt['probe_guard_passed']}/{rt['probe_guard_asked']}")
print(f"  B3 frozen_lost_n       : {rt['frozen_lost_n']}  "
      f"capability {g['fitness']['capability']['passed']}/24")
print(f"  B5 answers subtracted  : {m}")
ok = (t[s].get("pass") is True and t[s].get("coverage") is None
      and t[s]["reason"] == c[s]["reason"]
      and rt["probe_guard_passed"] == rt["probe_guard_asked"] == 4
      and rt["frozen_lost_n"] == 0 and m == 0)
print(f"  --> E26 v_frame ACCEPTED: {ok}")
