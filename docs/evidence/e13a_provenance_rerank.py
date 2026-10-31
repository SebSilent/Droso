"""E13a -- Class C: does provenance re-ranking make taught facts the top row, and does
that let any ask cross the floor? Read-only, zero brain builds, no organ change.

Class C (answer_formation_diagnosis.md section 3) is a book row outranking the taught
fact: `done about the same time as the bell` beat `the copper bell turns twice`.

THE STRUCTURAL POINT THIS PROBE EXISTS TO TEST, stated before running. The gate at
organs/neural_language.py:3469-3475 sorts candidates by coverage DESCENDING and takes
scored[0], so `best_cov` is already the MAXIMUM over all hits. A book row "outranks" the
taught fact precisely BECAUSE it has higher coverage. Re-ranking by provenance therefore
selects a row whose coverage is <= the current maximum -- it can lower best_cov, never
raise it. Provenance can only help if the taught row is absent from `hits` entirely, which
is candidate GENERATION, not ranking, and is out of scope here.

So the pre-registered expectation is: taught facts DO become top rows, coverage does NOT
rise, no ask crosses 0.6, and -- the part worth measuring -- the guarded scarf ask does NOT
flip, because its top row is already the taught fact `the scarf is wet`.

Usage:  python docs/evidence/e13a_provenance_rerank.py
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
OUT = ROOT / "docs" / "evidence" / "e13a_provenance_rerank.json"

FLOOR = 0.6
_WORD = re.compile(r"[a-z']+")


def toks(s):
    return _WORD.findall((s or "").lower())


def load_tells():
    """script name (both bare and sel- prefixed) -> list of tell token-sets.

    E11a lesson: the file says `count-frequency`, the journal says
    `sel-count-frequency`. Normalise both ways and fail LOUDLY on a miss.
    """
    raw = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    scripts = raw.get("scripts") if isinstance(raw, dict) else raw
    out = {}
    for sc in scripts:
        n = str(sc.get("name") or "")
        says = [t["say"] for t in (sc.get("turns") or [])
                if isinstance(t, dict) and isinstance(t.get("say"), str)]
        sets = [frozenset(toks(s)) for s in says if toks(s)]
        for k in (n, n.removeprefix("sel-"), "sel-" + n):
            out.setdefault(k, sets)
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


def coverage(must, row_toks, df, n_mem, stem):
    """The existing formula, verbatim: organs/neural_language.py:3464-3473."""
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

    tells = load_tells()
    df, n_mem = doc_freq()
    rows = [json.loads(l) for l in ASKS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"journal {len(rows)}  binder {n_mem}  scripts {len(tells)}")

    recs = []
    for r in rows:
        req, near = r.get("required"), r.get("nearest")
        if not req or not near:
            continue
        sc = r.get("script") or ""
        if sc not in tells:
            raise SystemExit(f"!! ABORT: unresolved script {sc!r} for {r.get('ask')!r}")
        tset = tells[sc]
        cands = []
        for row in near:
            txt = row if isinstance(row, str) else " ".join(row)
            rt = toks(txt)
            taught = frozenset(rt) in tset
            cands.append({"row": txt, "tokens": rt, "taught": taught,
                          "cov": round(coverage(req, rt, df, n_mem, stem), 6)})
        # existing gate: max coverage wins
        by_cov = sorted(cands, key=lambda c: -c["cov"])
        # Class C repair: provenance first, coverage as tie-break WITHIN each group
        by_prov = sorted(cands, key=lambda c: (not c["taught"], -c["cov"]))
        rec = {
            "ask": r.get("ask"), "script": sc, "stage": r.get("stage"),
            "cause": r.get("cause"), "pass": bool(r.get("pass")),
            "tier": r.get("tier"), "recorded_coverage": r.get("coverage"),
            "must": req,
            "n_cands": len(cands),
            "n_taught": sum(1 for c in cands if c["taught"]),
            "top_by_cov": by_cov[0]["row"], "top_by_cov_taught": by_cov[0]["taught"],
            "cov_by_cov": by_cov[0]["cov"],
            "top_by_prov": by_prov[0]["row"], "top_by_prov_taught": by_prov[0]["taught"],
            "cov_by_prov": by_prov[0]["cov"],
            "cands": [{k: c[k] for k in ("row", "taught", "cov")} for c in by_cov],
        }
        rec["rerank_changes_top"] = rec["top_by_cov"] != rec["top_by_prov"]
        rec["cov_delta"] = round(rec["cov_by_prov"] - rec["cov_by_cov"], 6)
        rec["crosses_floor_orig"] = rec["cov_by_cov"] >= FLOOR
        rec["crosses_floor_prov"] = rec["cov_by_prov"] >= FLOOR
        recs.append(rec)

    print(f"asks with candidates: {len(recs)}")

    print("\n=== does provenance re-ranking promote taught facts? ===")
    ch = [x for x in recs if x["rerank_changes_top"]]
    print(f"  asks whose top row CHANGES: {len(ch)}/{len(recs)}")
    for x in ch:
        print(f"  {x['ask'][:46]}")
        print(f"     cov-top  {x['cov_by_cov']:.4f} taught={x['top_by_cov_taught']} "
              f"{x['top_by_cov'][:44]!r}")
        print(f"     prov-top {x['cov_by_prov']:.4f} taught={x['top_by_prov_taught']} "
              f"{x['top_by_prov'][:44]!r}")
        print(f"     coverage delta {x['cov_delta']:+.4f}")
    promoted = [x for x in ch if x["top_by_prov_taught"] and not x["top_by_cov_taught"]]
    print(f"  asks where a TAUGHT fact becomes top: {len(promoted)}")

    print("\n=== coverage direction (the structural prediction) ===")
    up = [x for x in recs if x["cov_delta"] > 1e-9]
    dn = [x for x in recs if x["cov_delta"] < -1e-9]
    print(f"  coverage ROSE on {len(up)} asks, FELL on {len(dn)}, "
          f"unchanged on {len(recs)-len(up)-len(dn)}")
    print(f"  max rise {max((x['cov_delta'] for x in recs), default=0):+.4f}   "
          f"max fall {min((x['cov_delta'] for x in recs), default=0):+.4f}")

    print("\n=== floor crossings ===")
    gate = [x for x in recs if x["cause"] == "recall_gate"]
    print(f"  recall-gate asks: {len(gate)}")
    for x in sorted(gate, key=lambda x: -x["cov_by_prov"]):
        print(f"    {x['cov_by_cov']:.4f} -> {x['cov_by_prov']:.4f}  "
              f"{'CROSSES' if x['crosses_floor_prov'] else 'below'}  "
              f"taught_in_cands={x['n_taught']}/{x['n_cands']}  {x['ask'][:40]}")
    print(f"  crossing 0.6 after re-rank: "
          f"{sum(1 for x in gate if x['crosses_floor_prov'])}/{len(gate)}")

    print("\n=== the guarded scarf ask (B2) ===")
    scarf = [x for x in recs if "scarf" in (x["ask"] or "").lower()]
    if not scarf:
        print("  NOT PRESENT with candidates -- B2 untestable here")
    for x in scarf:
        print(f"  {x['ask']}  pass={x['pass']}")
        print(f"    top_by_cov  {x['cov_by_cov']:.4f} taught={x['top_by_cov_taught']} "
              f"{x['top_by_cov']!r}")
        print(f"    top_by_prov {x['cov_by_prov']:.4f} taught={x['top_by_prov_taught']} "
              f"{x['top_by_prov']!r}")
        print(f"    delta {x['cov_delta']:+.4f}   FLIPS TO PASSING: "
              f"{x['crosses_floor_prov']}")
    scarf_flip = any(x["crosses_floor_prov"] for x in scarf)
    gained = sum(1 for x in gate if x["crosses_floor_prov"])

    print("\n=== VERDICT ===")
    print(f"  taught facts promoted to top : {len(promoted)}")
    print(f"  recall-gate asks crossing 0.6: {gained}/{len(gate)}")
    print(f"  guarded scarf flips          : {scarf_flip}")
    if gained == 0:
        v = ("NEGATIVE -- provenance re-ranking gains nothing: best_cov is already the "
             "MAXIMUM over hits, so re-ranking can only lower it. No E13b.")
    elif scarf_flip:
        v = "ABORT -- gains asks but breaks the guarded invariant. No E13b."
    else:
        v = "POSITIVE -- gains asks without breaking the guard; specify E13b."
    print(f"  {v}")

    OUT.write_text(json.dumps({"floor": FLOOR, "n": len(recs), "promoted": len(promoted),
                               "recall_gate_crossing": gained, "recall_gate_n": len(gate),
                               "scarf_flips": scarf_flip, "verdict": v, "records": recs},
                              indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
