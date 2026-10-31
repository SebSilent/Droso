"""E24 phase 1 -- treatment verification. Read-only over the generation journals.

Checks the pre-registered success criterion (design section 1, section 4):
  1. score change is ZERO against the control
  2. the scarf ask still refuses
  3. its refusal is INVENTORY-LICENSED, not coverage-driven (abort A5)
  4. no ask gained an answer licence (phase 1 is refusal-only)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "state" / "selection"


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


ctl = load(SEL / "generation_20_asks.jsonl")   # flag OFF
trt = load(SEL / "generation_21_asks.jsonl")   # flag ON
kc = {(r["script"], r["ask"]): r for r in ctl}
kt = {(r["script"], r["ask"]): r for r in trt}

print("=== 1. SCORE CHANGE (pre-registered expectation: ZERO) ===")
pc = sum(1 for r in ctl if r.get("pass"))
pt = sum(1 for r in trt if r.get("pass"))
print(f"  control passes {pc}/{len(ctl)}   treatment passes {pt}/{len(trt)}")
diff = [k for k in kc if (kc[k].get("pass"), kc[k].get("stage"))
        != (kt[k].get("pass"), kt[k].get("stage"))]
print(f"  differing (pass,stage) keys: {len(diff)}")
for k in diff:
    print(f"    !! {k}  ctl={kc[k].get('pass')},{kc[k].get('stage')} "
          f"trt={kt[k].get('pass')},{kt[k].get('stage')}")

print("\n=== 2/3. THE GUARDED SCARF ASK ===")
scarf = [k for k in kt if "scarf" in k[1] and k[1].startswith("where")]
for k in scarf:
    c, t = kc[k], kt[k]
    print(f"  ask            : {k[1]!r}")
    print(f"  control        : pass={c.get('pass')} stage={c.get('stage')} "
          f"cause={c.get('cause_all')} coverage={c.get('coverage')}")
    print(f"  treatment      : pass={t.get('pass')} stage={t.get('stage')} "
          f"cause={t.get('cause_all')} coverage={t.get('coverage')}")
    print(f"  licensed_refusal (treatment): {t.get('licensed_refusal')}")
    print(f"  licensed_refusal (control)  : {c.get('licensed_refusal')}")
    print(f"  reason (treatment): {str(t.get('reason'))[:110]!r}")
    print(f"  reason (control)  : {str(c.get('reason'))[:110]!r}")
    print(f"  absence_relation  : {t.get('absence_relation')}")
    # `licensed_refusal` is NOT a persisted journal key -- the harness writes a
    # fixed row schema. The load-bearing evidence is the `reason` string plus the
    # ABSENCE of a coverage measurement: if the inventory pre-empted the gate, the
    # gate never ran, so coverage is None and the reason names the subject and the
    # missing relation rather than a percentage.
    tr = str(t.get("reason") or "")
    cr = str(c.get("reason") or "")
    inv_lic = ("was told but no" in tr) and (t.get("coverage") is None)
    cov_driven = "%" in cr and c.get("coverage") is not None
    still_refuses = bool(t.get("pass"))
    print(f"  control reason is coverage-driven : {cov_driven}")
    print(f"  treatment reason names the absence: {inv_lic}")
    print(f"  coverage gate reached (ctl/trt)   : "
          f"{c.get('coverage') is not None} / {t.get('coverage') is not None}")
    print(f"  --> still refuses        : {'YES' if still_refuses else 'NO'}")
    print(f"  --> inventory-licensed   : {'YES' if inv_lic else 'NO'}")
    print(f"  --> A5 (guard relocated) : {'SATISFIED' if inv_lic and still_refuses else 'FIRED'}")

print("\n=== 4. PHASE 1 IS REFUSAL-ONLY ===")
lic = [k for k in kt if "was told but no" in str(kt[k].get("reason") or "")]
print(f"  asks carrying a licensed_refusal: {len(lic)}")
for k in lic:
    print(f"    {k[1]!r}  pass={kt[k].get('pass')} rel={kt[k].get('absence_relation')}")
newly_silent = [k for k in lic if kc[k].get("pass") is False]
print(f"  licensed refusals on asks the control ANSWERED: {len(newly_silent)}")
for k in newly_silent:
    print(f"    !! REGRESSION {k[1]!r}")

print("\n=== VERDICT ===")
zero = (pc == pt) and not diff
g = scarf[0] if scarf else None
relocated = bool(g and "was told but no" in str(kt[g].get("reason") or "")
                 and kt[g].get("coverage") is None and kt[g].get("pass"))
print(f"  zero score change        : {'PASS' if zero else 'FAIL'}")
print(f"  guard relocated (A5)     : {'PASS' if relocated else 'FAIL'}")
print(f"  refusal-only, no regress : {'PASS' if not newly_silent else 'FAIL'}")
print(f"  PHASE 1 ACCEPTED         : {zero and relocated and not newly_silent}")
