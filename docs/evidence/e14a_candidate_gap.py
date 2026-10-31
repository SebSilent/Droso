"""E14a -- zero-build test of the candidate-generation repair's guard risk.

E13a showed that for 5 of 9 recall-gate asks the taught fact is NOT among the
candidates at all (`taught_in_cands=0/3`), while for 4 asks it is already the top
row. So the gap is candidate GENERATION, not ranking.

The smallest repair is to guarantee session rows are candidates: admit every row
with `who != "book"` into `hits`, then let the EXISTING coverage gate score them.
The gate takes the MAXIMUM coverage over hits, so admitting more candidates can
only RAISE best_cov -- including for the guarded scarf ask. That is the risk, and
it is computable offline: the tells are known exactly from tools/scripts_heldout.json,
and the coverage formula is organs/neural_language.py:3464-3473.

So this probe computes, per ask, the coverage of EVERY tell in its own script and
takes the max -- an upper bound on what the repair could produce, since it admits
strictly more candidates than the repair would (the repair admits session rows, and
in a scratch session the tells ARE the session rows).

If the guarded scarf ask's max crosses 0.6, the repair breaks the invariant and
E14b must not be built.

ZERO brain builds. Read-only. No organ change.
"""
from __future__ import annotations

import collections
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ASKS = ROOT / "state" / "selection" / "generation_13_asks.jsonl"
META = ROOT / "state" / "language_state.json.cortex.meta.json"
SCRIPTS = ROOT / "tools" / "scripts_heldout.json"
OUT = ROOT / "docs" / "evidence" / "e14a_candidate_gap.json"
FLOOR = 0.6
_WORD = re.compile(r"[a-z']+")


def toks(s):
    return _WORD.findall((s or "").lower())


def load_scripts():
    raw = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    scripts = raw.get("scripts") if isinstance(raw, dict) else raw
    out = {}
    for sc in scripts:
        n = str(sc.get("name") or "")
        says = [t["say"] for t in (sc.get("turns") or [])
                if isinstance(t, dict) and isinstance(t.get("say"), str)]
        for k in (n, n.removeprefix("sel-"), "sel-" + n):
            out.setdefault(k, says)
    return out


def doc_freq():
    meta = json.loads(META.read_text(encoding="utf-8"))
    df = collections.Counter()
    for m in meta:
        t = m.get("tokens") or []
        if isinstance(t, str):
            t = t.split()
        for w in {str(x).lower() for x in t}:
            df[w] += 1
    return df, len(meta)


def cov(must, row_toks, df, n_mem, stem):
    if not must:
        return 0.0
    wq = {w: math.log(1.0 + n_mem / max(1.0, df.get(w, 0))) for w in must}
    tot = sum(wq.values())
    if tot <= 0:
        return 0.0
    hs = {stem(t) for t in row_toks}
    return sum(wq[w] for w in must if stem(w) in hs) / tot


def main():
    from organs.stemming import stem

    scripts = load_scripts()
    df, n_mem = doc_freq()
    rows = [json.loads(l) for l in ASKS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"journal {len(rows)}  binder {n_mem}  scripts {len(scripts)}")

    recs = []
    for r in rows:
        req, near = r.get("required"), r.get("nearest")
        if not req:
            continue
        sc = r.get("script") or ""
        if sc not in scripts:
            raise SystemExit(f"!! ABORT: unresolved script {sc!r}")
        tells = scripts[sc]
        scored = sorted(
            ((round(cov(req, toks(t), df, n_mem, stem), 6), t) for t in tells),
            key=lambda x: -x[0])
        near_rows = [x if isinstance(x, str) else " ".join(x) for x in (near or [])]
        taught_in_near = sum(1 for t in tells
                             if any(set(toks(t)) == set(toks(n)) for n in near_rows))
        rec = {
            "ask": r.get("ask"), "script": sc, "stage": r.get("stage"),
            "cause": r.get("cause"), "pass": bool(r.get("pass")), "tier": r.get("tier"),
            "recorded_coverage": r.get("coverage"),
            "must": req, "n_tells": len(tells),
            "taught_in_candidates": taught_in_near,
            "best_tell": scored[0][1] if scored else None,
            "best_tell_cov": scored[0][0] if scored else 0.0,
            "all_tell_cov": [[c, t] for c, t in scored[:4]],
        }
        rec["crosses_with_all_tells"] = rec["best_tell_cov"] >= FLOOR
        rec["gain_over_recorded"] = round(
            rec["best_tell_cov"] - float(r.get("coverage") or 0.0), 6)
        recs.append(rec)

    print(f"asks with a recorded `must`: {len(recs)}")

    print("\n=== candidate-generation gap ===")
    gap = [x for x in recs if x["taught_in_candidates"] == 0]
    have = [x for x in recs if x["taught_in_candidates"] > 0]
    print(f"  asks with NO taught row among candidates: {len(gap)}")
    print(f"  asks WITH a taught row among candidates : {len(have)}")

    print("\n=== recall-gate asks: what admitting all tells would do ===")
    gate = [x for x in recs if x["cause"] == "recall_gate"]
    for x in sorted(gate, key=lambda x: -x["best_tell_cov"]):
        print(f"  rec={x['recorded_coverage']}  best_tell={x['best_tell_cov']:.4f} "
              f"({'CROSSES' if x['crosses_with_all_tells'] else 'below'}) "
              f"taught_in_cands={x['taught_in_candidates']}  {x['ask'][:40]}")
        print(f"      best tell: {x['best_tell']!r}")
    print(f"  crossing 0.6: {sum(1 for x in gate if x['crosses_with_all_tells'])}"
          f"/{len(gate)}")

    print("\n=== GUARDED SCARF ASK (the abort test) ===")
    scarf = [x for x in recs if "scarf" in (x["ask"] or "").lower()]
    if not scarf:
        print("  not present with a recorded `must`")
    for x in scarf:
        print(f"  {x['ask']}  pass={x['pass']} tier={x['tier']}")
        print(f"    must={x['must']}")
        print(f"    recorded coverage      = {x['recorded_coverage']}")
        print(f"    best tell coverage     = {x['best_tell_cov']:.4f}  "
              f"({x['best_tell']!r})")
        print(f"    CROSSES 0.6 IF ALL TELLS ADMITTED: {x['crosses_with_all_tells']}")
        for c, t in x["all_tell_cov"]:
            print(f"      {c:.4f}  {t!r}")
    flip = any(x["crosses_with_all_tells"] for x in scarf)

    print("\n=== every ask that would cross 0.6 ===")
    for x in sorted(recs, key=lambda x: -x["best_tell_cov"]):
        if x["crosses_with_all_tells"]:
            print(f"  {x['best_tell_cov']:.4f}  pass={x['pass']} "
                  f"stage={x['stage'] or '-':14s} {x['ask'][:48]}")

    n_gate_cross = sum(1 for x in gate if x["crosses_with_all_tells"])
    print("\n=== VERDICT ===")
    print(f"  recall-gate asks crossing : {n_gate_cross}/{len(gate)}")
    print(f"  guarded scarf flips       : {flip}")
    if flip:
        v = ("ABORT E14 -- admitting session rows lifts the guarded scarf ask over the "
             "floor. Same failure as E12a, reached by candidate generation instead of "
             "by the numerator.")
    elif n_gate_cross == 0:
        v = ("NEGATIVE -- admitting session rows gains nothing: even with every tell as a "
             "candidate no recall-gate ask reaches 0.6. The cap is the coverage formula, "
             "not the candidate pool. No E14b.")
    else:
        v = ("POSITIVE -- gains recall-gate asks without flipping the guard; specify E14b.")
    print(f"  {v}")

    OUT.write_text(json.dumps({"floor": FLOOR, "n": len(recs), "gap": len(gap),
                               "have": len(have), "gate_crossing": n_gate_cross,
                               "gate_n": len(gate), "scarf_flips": flip,
                               "verdict": v, "records": recs}, indent=1),
                  encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
