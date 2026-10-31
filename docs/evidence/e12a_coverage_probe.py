"""E12a -- read-only recomputation of coverage over ANSWERABLE terms.

ZERO brain builds. No organ change. Recomputes, from the recorded generation-13
journal plus the binder's document frequencies, what coverage WOULD be if `must`
were restricted to terms that could appear in an answer.

Mirrors organs/neural_language.py:3463-3473 exactly:

    wq[w] = log(1 + n_mem / max(1, df(w)))
    tot   = sum(wq[w] for w in must)
    cov   = sum(wq[w] for w in must if stem(w) in {stem(t) for t in row}) / tot

The only change is the set `must`. Two are computed per ask:
  must_orig      -- the recorded `required`, verbatim
  must_answerable-- `required` minus the organ's OWN question-shape parser word sets
                    (organs/neural_language.py:2112), which are already maintained
                    there and are deliberately not stemming.STOPWORDS

Pre-registered question (answer_formation_diagnosis.md section 5): does the guarded
scarf ask flip to >= 0.6? If it does, E12 is refuted at zero cost and the floor and
the guarded invariant are jointly unsatisfiable with this coverage formula.

Usage:  python docs/evidence/e12a_coverage_probe.py
"""
from __future__ import annotations

import collections
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASKS = ROOT / "state" / "selection" / "generation_13_asks.jsonl"
META = ROOT / "state" / "language_state.json.cortex.meta.json"
OUT = ROOT / "docs" / "evidence" / "e12a_coverage_probe.json"

FLOOR = 0.6
_WORD = re.compile(r"[a-z']+")


def question_frame_words() -> set:
    """The organ's own parser vocabulary -- read, not retyped."""
    import organs.neural_language as nl

    out = set()
    for attr in dir(nl.NeuralLanguage):
        if not attr.startswith("SHAPE_"):
            continue
        v = getattr(nl.NeuralLanguage, attr, None)
        if isinstance(v, (frozenset, set, tuple, list)):
            out |= {str(w).lower() for w in v}
    return out


def document_frequencies() -> tuple:
    meta = json.loads(META.read_text(encoding="utf-8"))
    df = collections.Counter()
    for m in meta:
        toks = m.get("tokens") or []
        if isinstance(toks, str):
            toks = toks.split()
        for w in {str(t).lower() for t in toks}:
            df[w] += 1
    return df, len(meta)


def coverage(must, row_tokens, df, n_mem, stem) -> float:
    if not must:
        return 0.0
    wq = {w: math.log(1.0 + n_mem / max(1.0, df.get(w, 0))) for w in must}
    tot = sum(wq.values())
    if tot <= 0:
        return 0.0
    hs = {stem(t) for t in row_tokens}
    return sum(wq[w] for w in must if stem(w) in hs) / tot


def main() -> int:
    import sys
    sys.path.insert(0, str(ROOT))
    from organs.stemming import stem

    frame = question_frame_words()
    df, n_mem = document_frequencies()
    rows = [json.loads(l) for l in ASKS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"journal rows {len(rows)}   binder rows {n_mem}   "
          f"parser frame words {len(frame)}")

    recs = []
    for r in rows:
        req = r.get("required")
        near = r.get("nearest")
        if not req or not near:
            continue
        row0 = near[0] if isinstance(near[0], str) else " ".join(near[0])
        toks = _WORD.findall(row0.lower())
        ans = [w for w in req if w not in frame]
        dropped = [w for w in req if w in frame]
        c_orig = coverage(req, toks, df, n_mem, stem)
        c_ans = coverage(ans, toks, df, n_mem, stem) if ans else 0.0
        recs.append({
            "ask": r.get("ask"), "stage": r.get("stage"), "cause": r.get("cause"),
            "pass": bool(r.get("pass")), "tier": r.get("tier"),
            "probe": r.get("probe"), "script": r.get("script"),
            "recorded_coverage": r.get("coverage"),
            "recomputed_orig": round(c_orig, 6),
            "recomputed_answerable": round(c_ans, 6),
            "must_orig": req, "must_answerable": ans, "dropped": dropped,
            "best_row": row0,
            "orig_passes_floor": c_orig >= FLOOR,
            "answerable_passes_floor": c_ans >= FLOOR,
            "flips": (c_orig < FLOOR) != (c_ans < FLOOR),
        })

    print(f"asks with a recorded candidate row: {len(recs)}")

    # sanity: does the recomputation reproduce the recorded coverage?
    both = [x for x in recs if x["recorded_coverage"] is not None]
    if both:
        d = [abs(x["recomputed_orig"] - float(x["recorded_coverage"])) for x in both]
        print(f"\n=== fidelity check: recomputed_orig vs recorded coverage ===")
        print(f"  n={len(both)}  max abs delta={max(d):.4f}  mean={sum(d)/len(d):.4f}")
        worst = max(both, key=lambda x: abs(x["recomputed_orig"]
                                            - float(x["recorded_coverage"])))
        print(f"  worst: {worst['ask'][:46]!r} recorded={worst['recorded_coverage']} "
              f"recomputed={worst['recomputed_orig']}")
        print(f"  NOTE: `nearest[0]` is the diagnostic nearest row and may not be the")
        print(f"        row the gate scored, so a delta here is expected and bounded.")

    print(f"\n=== the guarded scarf ask ===")
    scarf = [x for x in recs if "scarf" in (x["ask"] or "").lower()]
    if not scarf:
        print("  NOT PRESENT in the journal with a candidate row -- cannot test B2")
    for x in scarf:
        print(f"  {x['ask']}")
        print(f"    tier={x['tier']} probe={x['probe']} pass={x['pass']} "
              f"stage={x['stage']}")
        print(f"    must_orig      = {x['must_orig']}")
        print(f"    must_answerable= {x['must_answerable']}  dropped={x['dropped']}")
        print(f"    best_row       = {x['best_row']!r}")
        print(f"    coverage orig={x['recomputed_orig']:.4f} -> "
              f"answerable={x['recomputed_answerable']:.4f}   floor={FLOOR}")
        print(f"    FLIPS TO PASSING: {x['answerable_passes_floor']}")

    print(f"\n=== the recall-gate asks ===")
    gate = [x for x in recs if x["cause"] == "recall_gate"]
    for x in sorted(gate, key=lambda x: -x["recomputed_answerable"]):
        print(f"  {x['recomputed_orig']:.4f} -> {x['recomputed_answerable']:.4f}  "
              f"{'CROSSES' if x['answerable_passes_floor'] else 'still below'}  "
              f"{x['ask'][:46]}")
        print(f"      dropped {x['dropped']}")
    n_cross = sum(1 for x in gate if x["answerable_passes_floor"])
    print(f"  recall-gate asks crossing 0.6: {n_cross}/{len(gate)}")

    print(f"\n=== every ask that flips ===")
    flips = [x for x in recs if x["flips"]]
    for x in flips:
        print(f"  {'PASS' if x['pass'] else 'fail'} {x['stage'] or '-':14s} "
              f"{x['recomputed_orig']:.4f} -> {x['recomputed_answerable']:.4f}  "
              f"{x['ask'][:50]}")
    print(f"  total flips: {len(flips)}")

    # B5: did the parser sets remove a CONTENT term?
    CONTENT = {"kettle", "frost", "eggs", "bell", "coat", "scarf", "basket",
               "lantern", "copper", "latch", "door", "moon"}
    bad = sorted({w for x in recs for w in x["dropped"]} & CONTENT)
    print(f"\n=== B5: content terms wrongly dropped by the parser sets ===")
    print(f"  {bad or 'none'}")

    scarf_flip = any(x["answerable_passes_floor"] for x in scarf)
    verdict = ("ABORT E12 -- guarded scarf ask reaches the floor"
               if scarf_flip else
               "E12a does NOT refute E12 -- proceed to specify E12b")
    print(f"\nVERDICT: {verdict}")

    OUT.write_text(json.dumps({
        "floor": FLOOR, "n_recs": len(recs), "n_flips": len(flips),
        "scarf_present": bool(scarf), "scarf_flips": scarf_flip,
        "recall_gate_crossing": n_cross, "recall_gate_n": len(gate),
        "b5_content_dropped": bad, "verdict": verdict, "records": recs,
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
