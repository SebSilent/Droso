"""E23 pre-test -- read-only. Can excluding closed-class question syntax from the
coverage denominator be done without breaking a guarded invariant?

E12a tested a close relative (`COVERAGE_ANSWERABLE_TERMS`, restricting `must` via the
organ's own parser word sets) and it lifted the guarded scarf ask from 0.5797 to
0.6676, over the 0.6 floor. E12a checked ONE ask. This pre-test checks the whole
battery, under three exclusion variants, so the guard analysis is measured rather
than argued.

Recomputes coverage with the gate's own formula (organs/neural_language.py:3464-3473):
    wq[w] = log(1 + n_mem / max(1, df(w)))
    cov   = sum(wq[w] for w in must if stem(w) in row_stems) / sum(wq.values())
and compares four denominators per ask:
    orig      -- `required` as recorded
    v_synt    -- minus closed-class function words only (did/is/by/of/the/...)
    v_frame   -- minus function words AND question verbs (say/tell/mention/...)
    v_all     -- minus everything that is not a content noun/verb/adjective

Read-only over the generation-19 journal and the live binder dump. No brain build,
no organ change, no score, no genome.

Usage:  python docs/evidence/e23_pretest.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from organs.stemming import stem  # noqa: E402

JOURNAL = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
META = ROOT / "state" / "language_state.json.cortex.meta.json"
OUT = ROOT / "docs" / "evidence" / "e23_pretest.json"
FLOOR = 0.6

# Closed grammatical classes only -- no content vocabulary. E16a's D4 and E10's
# Finding 1 both forbid a hand-written content-word list; these are function words,
# auxiliaries, interrogatives and question verbs.
FUNCTION = {"the", "a", "an", "of", "by", "in", "on", "at", "to", "for", "and", "or",
            "but", "not", "no", "is", "are", "was", "were", "be", "been", "being",
            "do", "does", "did", "done", "it", "that", "this", "there", "i", "you",
            "me", "my", "your", "we", "they", "he", "she", "him", "her", "as", "than"}
INTERROG = {"what", "which", "who", "whom", "whose", "where", "when", "why", "how"}
QVERB = {"say", "said", "tell", "told", "mention", "mentioned", "name", "repeat"}
QMOD = {"often", "many", "much", "times", "time", "number", "about", "before",
        "after", "earlier", "last", "first", "true", "any", "ever", "left", "both",
        "all", "one", "thing", "things"}

VARIANTS = {
    "orig": set(),
    "v_synt": FUNCTION | INTERROG,
    "v_frame": FUNCTION | INTERROG | QVERB,
    "v_all": FUNCTION | INTERROG | QVERB | QMOD,
}


def doc_freq():
    raw = json.loads(META.read_text(encoding="utf-8"))
    meta = raw if isinstance(raw, list) else (raw.get("meta") or raw.get("rows") or [])
    df = Counter()
    for m in meta:
        if not isinstance(m, dict):
            continue
        t = m.get("tokens") or []
        if isinstance(t, str):
            t = t.split()
        for w in {str(x).lower() for x in t}:
            df[w] += 1
    return df, len(meta)


def coverage(must, row_text, df, n_mem):
    if not must:
        return None
    wq = {w: math.log(1.0 + n_mem / max(1.0, df.get(w, 0))) for w in must}
    tot = sum(wq.values())
    if tot <= 0:
        return None
    hs = {stem(w) for w in str(row_text or "").lower().split()}
    return sum(wq[w] for w in must if stem(w) in hs) / tot


def main():
    df, n_mem = doc_freq()
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"journal {len(rows)} asks; binder {n_mem} rows; floor {FLOOR}")

    # Only asks where the gate ran have a `required` cue and a `nearest` candidate.
    gate = [r for r in rows if r.get("required") and r.get("nearest")]
    print(f"asks where the recall gate ran (have required + nearest): {len(gate)}")

    recs = []
    for r in gate:
        req = [str(x) for x in r["required"]]
        top = str(r["nearest"][0])
        rec = {"ask": r.get("ask"), "pass": bool(r.get("pass")),
               "cause_all": r.get("cause_all"), "recorded_coverage": r.get("coverage"),
               "top_row": top, "required": req}
        for name, drop in VARIANTS.items():
            must = [w for w in req if w not in drop] if drop else list(req)
            c = coverage(must, top, df, n_mem)
            rec[name] = round(c, 6) if c is not None else None
            rec[f"{name}_must"] = must
            rec[f"{name}_crosses"] = (c is not None and c >= FLOOR)
        recs.append(rec)

    # ---- the guard analysis: which PASSING asks start crossing the floor?
    print("\n=== GUARD ANALYSIS: passing asks that would start crossing the floor ===")
    guard_report = {}
    for name in VARIANTS:
        if name == "orig":
            continue
        newly = [x for x in recs if x["pass"] and x[f"{name}_crosses"]
                 and not x["orig_crosses"]]
        guard_report[name] = [x["ask"] for x in newly]
        print(f"  {name:9s}: {len(newly)} passing ask(s) newly cross")
        for x in newly:
            print(f"      !! {x['ask']!r}  {x['orig']} -> {x[name]}  top={x['top_row']!r}")

    # ---- the gain analysis: which FAILING asks start crossing?
    print("\n=== GAIN ANALYSIS: failing asks that would start crossing the floor ===")
    gain_report = {}
    for name in VARIANTS:
        if name == "orig":
            continue
        gained = [x for x in recs if not x["pass"] and x[f"{name}_crosses"]
                  and not x["orig_crosses"]]
        gain_report[name] = [x["ask"] for x in gained]
        print(f"  {name:9s}: {len(gained)} failing ask(s) newly cross")
        for x in gained:
            print(f"      +  {x['ask']!r}  {x['orig']} -> {x[name]}")

    # ---- per-ask table
    print("\n=== per-ask coverage under each denominator ===")
    for x in sorted(recs, key=lambda x: (x["pass"], -(x["v_all"] or 0))):
        print(f"  {'PASS' if x['pass'] else 'fail'} {str(x['cause_all']):14s} "
              f"orig={x['orig']} v_synt={x['v_synt']} v_frame={x['v_frame']} "
              f"v_all={x['v_all']}  {str(x['ask'])[:40]!r}")

    # ---- verdict
    print("\n=== VERDICT ===")
    safe = [n for n, g in guard_report.items() if not g]
    useful = [n for n, g in gain_report.items() if g]
    viable = [n for n in useful if n in safe]
    print(f"  variants that break no passing ask : {safe or 'none'}")
    print(f"  variants that gain a failing ask   : {useful or 'none'}")
    print(f"  VIABLE (gain and guard-safe)       : {viable or 'none'}")
    if not viable:
        print("\n  No exclusion variant both gains an ask and preserves every passing")
        print("  ask. The denominator lever is closed on this battery, and E23 should")
        print("  not be implemented -- the guard analysis is measured, not argued.")

    OUT.write_text(json.dumps({
        "floor": FLOOR, "gate_asks": len(gate), "variants": list(VARIANTS),
        "guard_breaks": guard_report, "gains": gain_report, "viable": viable,
        "records": recs}, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
