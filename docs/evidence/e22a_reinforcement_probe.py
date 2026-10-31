"""E22a -- read-only teach-time reinforcement probe.

E19/E20/E21a closed every lever that operates on RETRIEVAL of an existing taught
row: eviction (0/19 failures), cue omission (the gate ranks the row first on 4 of
9 and still refuses), and cue dilution (de-framing recovers 0 of 4). What is left
that does not operate on retrieval is the row's own reinforcement -- its `count`.

This probe asks: does taught-row count predict retrieval rank, coverage, or
pass/fail? If it does, a flag-gated reinforcement experiment is worth proposing.
If it does not, the line closes.

It reads only existing journals and the live binder dump. No brain build, no
retrieval change, no score, no genome, no organ behaviour.

Usage:  python docs/evidence/e22a_reinforcement_probe.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
META = ROOT / "state" / "language_state.json.cortex.meta.json"
OUT = ROOT / "docs" / "evidence" / "e22a_reinforcement.json"


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 4) if xs else None


def main():
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    attr = [r for r in rows if (r.get("attribution") or {}).get("taught_count") is not None]

    out = {"journal": str(JOURNAL.relative_to(ROOT)), "asks_total": len(rows),
           "asks_with_taught_count": len(attr)}

    # ---- 1. the count distribution itself
    counts = Counter(r["attribution"]["taught_count"] for r in attr)
    out["count_distribution"] = {str(k): v for k, v in sorted(counts.items())}
    print("=== 1. taught-row count distribution across the battery ===")
    for k, v in sorted(counts.items()):
        print(f"  count={k}: {v} asks")
    print(f"  distinct count values: {len(counts)}")

    # ---- 2. count vs pass/fail
    print("\n=== 2. count vs pass/fail ===")
    by_count = defaultdict(list)
    for r in attr:
        by_count[r["attribution"]["taught_count"]].append(r)
    out["pass_by_count"] = {}
    for c in sorted(by_count):
        grp = by_count[c]
        npass = sum(1 for r in grp if r.get("pass"))
        rate = round(npass / len(grp), 4)
        out["pass_by_count"][str(c)] = {"n": len(grp), "pass": npass, "pass_rate": rate}
        print(f"  count={c}: {npass}/{len(grp)} pass  (rate {rate})")

    # ---- 3. count vs coverage (gate asks only -- coverage is a gate quantity)
    print("\n=== 3. count vs gate coverage ===")
    out["coverage_by_count"] = {}
    for c in sorted(by_count):
        gate = [r for r in by_count[c] if r.get("cause_all") == "recall_gate"]
        covs = [r.get("coverage") for r in gate if isinstance(r.get("coverage"), (int, float))]
        out["coverage_by_count"][str(c)] = {"n_gate": len(gate), "n_with_cov": len(covs),
                                            "mean_cov": mean(covs),
                                            "min": round(min(covs), 4) if covs else None,
                                            "max": round(max(covs), 4) if covs else None}
        print(f"  count={c}: gate asks {len(gate)}, coverage mean={mean(covs)} "
              f"range=[{min(covs) if covs else None}, {max(covs) if covs else None}]")

    # ---- 4. count vs retrieval rank (E19's independent probe rank)
    print("\n=== 4. count vs independent probe rank ===")
    out["rank_by_count"] = {}
    for c in sorted(by_count):
        ranks = [r["attribution"].get("taught_rank") for r in by_count[c]]
        have = [x for x in ranks if isinstance(x, int)]
        out["rank_by_count"][str(c)] = {"n": len(ranks), "n_ranked": len(have),
                                        "mean_rank": mean(have),
                                        "best": min(have) if have else None,
                                        "worst": max(have) if have else None}
        print(f"  count={c}: ranked {len(have)}/{len(ranks)}, mean rank {mean(have)}, "
              f"best {min(have) if have else None}, worst {max(have) if have else None}")

    # ---- 5. per-ask table, sorted by count then coverage
    print("\n=== 5. per-ask detail ===")
    out["asks"] = []
    for r in sorted(attr, key=lambda x: (-x["attribution"]["taught_count"],
                                         -(x.get("coverage") or 0))):
        a = r["attribution"]
        rec = {"ask": r.get("ask"), "script": r.get("script"), "pass": bool(r.get("pass")),
               "taught_count": a.get("taught_count"), "probe_rank": a.get("taught_rank"),
               "coverage": r.get("coverage"), "stage_all": r.get("stage_all"),
               "cause_all": r.get("cause_all"), "taught_row": a.get("taught_row")}
        out["asks"].append(rec)
        print(f"  count={rec['taught_count']} pass={str(rec['pass']):5} "
              f"cov={str(rec['coverage']):6} rank={str(rec['probe_rank']):5} "
              f"cause={str(rec['cause_all']):16} {str(rec['ask'])[:44]!r}")

    # ---- 6. the decisive within-count comparison
    print("\n=== 6. decisive comparison: same count, different outcome ===")
    hi = [r for r in attr if r["attribution"]["taught_count"] == max(counts)]
    hi_pass = [r for r in hi if r.get("pass")]
    hi_fail = [r for r in hi if not r.get("pass")]
    out["high_count_split"] = {"n": len(hi), "pass": len(hi_pass), "fail": len(hi_fail)}
    print(f"  count={max(counts)} group: {len(hi_pass)} pass, {len(hi_fail)} fail")
    for r in hi:
        print(f"    pass={str(bool(r.get('pass'))):5} cov={str(r.get('coverage')):6} "
              f"cause={str(r.get('cause_all')):16} {str(r.get('ask'))[:46]!r}")

    # ---- 7. live binder count distribution (context, not per-ask)
    if META.exists():
        try:
            meta = json.loads(META.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                meta = meta.get("meta") or meta.get("rows") or []
            cs = Counter(int(m.get("count", 1)) for m in meta if isinstance(m, dict))
            out["live_binder_counts"] = {"rows": len(meta),
                                         "distinct_counts": len(cs),
                                         "top": {str(k): v for k, v in cs.most_common(8)}}
            print("\n=== 7. live binder count distribution (context) ===")
            print(f"  rows {len(meta)}, distinct count values {len(cs)}")
            print(f"  top: {cs.most_common(8)}")
        except Exception as exc:
            out["live_binder_error"] = f"{type(exc).__name__}: {exc}"
            print(f"\n  binder dump unreadable: {type(exc).__name__}: {exc}")

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
