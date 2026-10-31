"""E11a -- offline discriminability probe for session-provenanced term support.

ZERO brain builds. No organ change. Read-only.

Computes, as a STANDALONE function here and not in the organ:

    support(q) = max over rows r with r.who != "book"
                 of |terms(q) & terms(r)| / |terms(q)|

and asks the one question that can kill the design (design doc section 8, item 6):

    does ANY single threshold separate the 4 `mouth` failures from the 10 `recall`
    failures WITHOUT also admitting the recall-gate failures?

PROVENANCE OF THE SESSION ROWS -- a correction to the design doc, found while writing
this script. The doc said everything needed is already on disk, naming the live binder.
That is wrong in a way that matters: each ask is built fresh in SCRATCH and the tells are
replayed into that scratch session, so the session rows DO NOT EXIST in the live binder
(`who == "you"` census is 0 of 60,000). Computing support against the live binder alone
would measure pre-existing non-book memory and systematically understate the signal --
it would test the wrong rows and could have "refuted" a working design.

The fix costs no builds: the tells are known exactly from `tools/scripts_heldout.json`.
A binder row created by a tell contains that tell's tokens, so the session rows are
synthesised from the script and combined with the live non-book rows (droso 466 +
parent 19), which is what the organ would actually see mid-ask.

Usage:  python docs/evidence/e11a_support_probe.py
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASKS = ROOT / "state" / "selection" / "generation_13_asks.jsonl"
SCRIPTS = ROOT / "tools" / "scripts_heldout.json"
META = ROOT / "state" / "language_state.json.cortex.meta.json"
OUT = ROOT / "docs" / "evidence" / "e11a_support_probe.json"

_WORD = re.compile(r"[a-z']+")


def terms(text: str) -> set:
    """Lowercased alphabetic tokens. Deliberately NO content/function filtering:
    design doc constraint 3 -- E10 Finding 1 is that we do not have a reliable
    content/function distinction, so the signal must not need one."""
    return set(_WORD.findall((text or "").lower()))


# ---------------------------------------------------------------- tells per script
def load_scripts() -> dict:
    """script name -> ordered list of turns.

    CORRECTION FOUND WHILE RUNNING: the file names scripts `count-frequency` while the
    journal records `sel-count-frequency`. The first version of this probe keyed on the
    file name, so EVERY lookup missed and all 42 asks silently fell back to live-only
    rows -- support was then measured against droso's 466 prior rows, not the taught
    facts, and A2/item6 "failed" for that reason alone. Names are normalised here and
    the fallback is made LOUD rather than silent.
    """
    raw = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    scripts = raw.get("scripts") if isinstance(raw, dict) else raw
    out = {}
    items = (scripts.items() if isinstance(scripts, dict)
             else [(s.get("name") or f"#{i}", s) for i, s in enumerate(scripts)])
    for name, sc in items:
        n = str(name)
        turns = sc.get("turns") or sc.get("says") or sc.get("lines") or []
        for key in (n, n.removeprefix("sel-"), "sel-" + n):
            out.setdefault(key, turns)
    return out


def tells_before(turns: list, ask: str) -> list:
    """The `say` turns replayed BEFORE this ask -- not the whole script."""
    says = []
    for t in turns:
        if isinstance(t, str):
            says.append(t)
        elif isinstance(t, dict):
            v = t.get("say") or t.get("tell") or t.get("text")
            if isinstance(v, str) and v.strip():
                says.append(v)
            elif isinstance(t.get("ask"), str) and t["ask"].strip() == (ask or "").strip():
                break
    return says


# ------------------------------------------------------- the signal under test
def session_support(q_terms: set, rows: list) -> tuple:
    """(support, best_row_terms, best_overlap). Read-only; rows are token sets."""
    if not q_terms:
        return 0.0, set(), set()
    best, best_row, best_ov = 0.0, set(), set()
    for r in rows:
        ov = q_terms & r
        s = len(ov) / len(q_terms)
        if s > best:
            best, best_row, best_ov = s, r, ov
    return best, best_row, best_ov


def main() -> int:
    asks = [json.loads(l) for l in ASKS.read_text(encoding="utf-8").splitlines() if l.strip()]
    scripts = load_scripts()
    print(f"asks {len(asks)}   script names resolved {len(scripts)}")
    missing = sorted({a.get("script") for a in asks} - set(scripts))
    if missing:
        raise SystemExit(f"!! ABORT: asks whose script is unresolved: {missing}\n"
                         f"   support would be measured against the wrong rows.")

    # live non-book rows, for fidelity with what the organ sees mid-ask
    live = []
    if META.exists():
        meta = json.loads(META.read_text(encoding="utf-8"))
        who = collections.Counter(str(m.get("who") or "?") for m in meta)
        print(f"live binder {len(meta)} rows  by who {dict(who)}")
        for m in meta:
            if str(m.get("who") or "") != "book":
                t = terms(" ".join(str(x) for x in (m.get("tokens") or [])))
                if t:
                    live.append(t)
    print(f"live non-book rows usable: {len(live)}")

    recs = []
    n_tells_tot = 0
    for a in asks:
        sc = a.get("script") or ""
        ask_txt = a.get("ask") or ""
        says = tells_before(scripts[sc], ask_txt)
        n_tells_tot += len(says)
        if not says:
            raise SystemExit(f"!! ABORT: no tells precede {ask_txt!r} in {sc!r}")
        rows = [terms(t) for t in says if terms(t)] + live
        qt = terms(ask_txt)
        s, brow, bov = session_support(qt, rows)
        recs.append({
            "ask": a.get("ask"), "script": sc, "stage": a.get("stage"),
            "cause": a.get("cause"), "coverage": a.get("coverage"),
            "pass": bool(a.get("pass")), "spoken": bool(a.get("spoken")),
            "q_terms": len(qt), "support": round(s, 4),
            "overlap": sorted(bov), "n_tells": len(says), "tells": says,
        })
    print(f"tells resolved across the battery: {n_tells_tot}")

    # ---- A1: ask-independence. Resonance failed this; support must not.
    vals = [r["support"] for r in recs]
    rng = max(vals) - min(vals)
    print(f"\n=== A1 ask-dependence ===")
    print(f"support range across {len(vals)} asks: {min(vals):.4f} .. {max(vals):.4f}"
          f"  range={rng:.4f}  distinct={len(set(vals))}")
    a1 = "PASS" if rng >= 0.10 else "FAIL -> abort A1"
    print(f"A1 (range >= 0.10): {a1}")

    # ---- group summaries
    print(f"\n=== support by stage ===")
    by = collections.defaultdict(list)
    for r in recs:
        by[r["stage"] or "pass"].append(r["support"])
    for k in sorted(by, key=lambda k: -max(by[k])):
        v = by[k]
        print(f"  {k:14s} n={len(v):2d}  min={min(v):.4f} max={max(v):.4f} "
              f"mean={sum(v)/len(v):.4f}")

    mouth = [r for r in recs if r["stage"] == "mouth"]
    recall = [r for r in recs if r["stage"] == "recall"]
    gate = [r for r in recall if r["cause"] == "recall_gate"]
    comp = [r for r in recall if r["cause"] == "comprehension"]

    print(f"\n=== the 4 mouth asks ===")
    for r in sorted(mouth, key=lambda r: -r["support"]):
        print(f"  {r['support']:.4f}  {r['ask'][:52]:52s} ov={r['overlap']}")
    print(f"\n=== the {len(recall)} recall asks ({len(gate)} recall_gate, {len(comp)} comprehension) ===")
    for r in sorted(recall, key=lambda r: -r["support"]):
        print(f"  {r['support']:.4f}  [{r['cause']:13s}] {r['ask'][:46]:46s} ov={r['overlap']}")

    # ---- A2 + item 6: does ANY single threshold work?
    print(f"\n=== A2 / item 6: single-threshold separation ===")
    if not mouth or not recall:
        print("cannot test: empty group")
        a2 = item6 = "UNTESTABLE"
        thr = None
    else:
        lo_mouth = min(r["support"] for r in mouth)
        hi_recall = max(r["support"] for r in recall)
        hi_gate = max((r["support"] for r in gate), default=0.0)
        print(f"  min(mouth)          = {lo_mouth:.4f}")
        print(f"  max(recall)         = {hi_recall:.4f}")
        print(f"  max(recall_gate)    = {hi_gate:.4f}")
        sep = lo_mouth - hi_recall
        print(f"  margin mouth-recall = {sep:+.4f}")
        a2 = "PASS" if sep > 0 else "FAIL -> abort A2"
        print(f"  A2 (mouth separates from recall): {a2}")
        # item 6: threshold must admit ALL mouth and NO recall_gate
        cands = sorted({round(v, 4) for v in vals})
        ok = [t for t in cands
              if all(r["support"] >= t for r in mouth)
              and all(r["support"] < t for r in gate)]
        thr = ok[0] if ok else None
        print(f"  thresholds admitting all 4 mouth and no recall_gate: {len(ok)}"
              + (f"  e.g. {thr}" if ok else ""))
        item6 = "PASS" if ok else "FAIL -> design killed, do not run E11b"
        print(f"  item 6: {item6}")

    # ---- test #5 frequency-independence, test #6 the-bias, on real asks
    print(f"\n=== secondary checks ===")
    num = [r for r in recs if "numbered" in " ".join(r["overlap"]) or "sold" in " ".join(r["overlap"])]
    print(f"  asks whose best row overlaps a known corpus attractor (numbered/sold): {len(num)}")
    the_q = [r["support"] for r in recs if "the" in terms(r["ask"] or "")]
    nothe = [r["support"] for r in recs if "the" not in terms(r["ask"] or "")]
    if the_q and nothe:
        print(f"  'the'-bias: mean support with 'the' {sum(the_q)/len(the_q):.4f} (n={len(the_q)})"
              f"  without {sum(nothe)/len(nothe):.4f} (n={len(nothe)})"
              f"  delta {sum(the_q)/len(the_q) - sum(nothe)/len(nothe):+.4f}")

    OUT.write_text(json.dumps({
        "A1_range": round(rng, 4), "A1": a1, "A2": a2, "item6": item6,
        "threshold": thr, "n_asks": len(recs), "records": recs,
    }, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"\nVERDICT  A1={a1}  A2={a2}  item6={item6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
