"""Paraphrase-gap diagnosis -- read-only, ZERO brain builds.

E17a found the one mechanism that is neither closed nor in need of a new primitive: a failing ask
with a PASSING TWIN on identical taught evidence. `how many eggs are left in the basket?` passes;
`what number of eggs is left in the basket?` fails at the recall gate.

This probe finds every such pair in the 42-ask battery and traces the minimal difference:
candidate generation, coverage terms, answer path, final stage.

Usage:  python docs/evidence/paraphrase_gap_probe.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

JOURNAL = ROOT / "state" / "selection" / "generation_13_asks.jsonl"
OUT = ROOT / "docs" / "evidence" / "paraphrase_gap_result.json"

_W = re.compile(r"[a-z']+")


def toks(s):
    return _W.findall((s or "").lower())


def load_scripts():
    """ask -> (script, expect). Both batteries, so a twin in either is found."""
    out = {}
    for name in ("scripts_heldout.json", "scripts_selection.json"):
        p = ROOT / "tools" / name
        if not p.exists():
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        for s in (raw.get("scripts") if isinstance(raw, dict) else raw):
            sn = str(s.get("name") or "")
            for t in (s.get("turns") or []):
                if isinstance(t, dict) and isinstance(t.get("ask"), str):
                    out[t["ask"]] = (sn, t.get("expect") or {})
    return out


def main():
    rows = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    scripts = load_scripts()
    print(f"journal rows {len(rows)}   script asks {len(scripts)}")

    for r in rows:
        sn, exp = scripts.get(r["ask"], ("?", {}))
        r["script"] = sn
        r["answer"] = [str(a).lower() for a in (exp.get("answer") or [])]
        r["forbid"] = [str(a).lower() for a in (exp.get("forbid") or [])]
        r["refusal"] = bool(exp.get("require_refusal")) or (not r["answer"] and not r["forbid"])

    # ------------------------------------------------- group into propositions
    # Two asks are twins when they are in the same script and want the same answer.
    # Same taught evidence, different surface form -- the paraphrase relation.
    groups = {}
    for r in rows:
        if r["refusal"]:
            continue                      # a guarded ask has no "correct answer" twin
        key = (r["script"], tuple(sorted(r["answer"])))
        groups.setdefault(key, []).append(r)

    pairs = {k: v for k, v in groups.items() if len(v) >= 2
             and any(x["pass"] for x in v) and any(not x["pass"] for x in v)}
    print(f"propositions with both a passing and a failing ask: {len(pairs)}")

    findings = []
    for (script, answer), grp in sorted(pairs.items()):
        passing = [x for x in grp if x["pass"]]
        failing = [x for x in grp if not x["pass"]]
        print(f"\n{'='*78}\nSCRIPT {script}   answer={list(answer)}")
        for x in passing:
            print(f"  PASS  {x['ask']}")
        for x in failing:
            print(f"  FAIL  {x['ask']}   stage={x.get('stage')} cause={x.get('cause')}")

        for f in failing:
            for p in passing:
                fr, pr = set(f.get("required") or []), set(p.get("required") or [])
                only_f, only_p = sorted(fr - pr), sorted(pr - fr)
                # nearest[0] is the top retrieved row: same row => retrieval agrees
                fn = (f.get("nearest") or [None])[0]
                pn = (p.get("nearest") or [None])[0]
                same_top = fn is not None and fn == pn
                rec = {
                    "script": script, "answer": list(answer),
                    "failing": f["ask"], "passing": p["ask"],
                    "fail_stage": f.get("stage"), "fail_cause": f.get("cause"),
                    "fail_cov": f.get("coverage"), "pass_cov": p.get("coverage"),
                    "fail_required": sorted(fr), "pass_required": sorted(pr),
                    "terms_only_in_failing": only_f,
                    "terms_only_in_passing": only_p,
                    "same_top_row": same_top,
                    "fail_top_row": fn, "pass_top_row": pn,
                }
                findings.append(rec)

                print(f"\n  --- {f['ask']!r}\n      vs {p['ask']!r}")
                print(f"      coverage   fail={rec['fail_cov']}  pass={rec['pass_cov']}")
                print(f"      required   fail={rec['fail_required']}")
                print(f"                 pass={rec['pass_required']}")
                print(f"      ONLY in failing: {only_f}")
                print(f"      ONLY in passing: {only_p}")
                print(f"      top row identical: {same_top}")
                print(f"        fail top: {str(fn)[:70]!r}")
                print(f"        pass top: {str(pn)[:70]!r}")
                print(f"        pass form bypasses the recall gate: "
                      f"{rec['pass_cov'] is None and not rec['pass_required']}")
                print(f"      stage/cause: {rec['fail_stage']} / {rec['fail_cause']}")

    # ------------------------------------------------------- classify
    print(f"\n{'='*78}\nCLASSIFICATION of the minimal difference")
    classes = {}
    for r in findings:
        if not r["same_top_row"]:
            c = "RETRIEVAL: the twin pulls a different top row"
        elif r["terms_only_in_failing"]:
            c = "TERMS: the failing form adds question-syntax terms to the numerator"
        elif r["fail_cov"] is not None and r["pass_cov"] is not None and r["fail_cov"] < r["pass_cov"]:
            c = "COVERAGE: same row, same terms, lower score"
        else:
            c = "OTHER"
        classes.setdefault(c, []).append(r)
    for c, rs in sorted(classes.items()):
        print(f"  {c}: {len(rs)}")
        for r in rs:
            print(f"      {r['failing'][:56]}")
            if r["terms_only_in_failing"]:
                print(f"        extra terms {r['terms_only_in_failing']}")

    OUT.write_text(json.dumps({"n_pairs": len(pairs), "findings": findings,
                               "classes": {k: len(v) for k, v in classes.items()}},
                              indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
