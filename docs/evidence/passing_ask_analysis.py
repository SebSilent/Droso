"""Compare passing and failing asks on the fields the instrument now records for
both.

Reads the generation-15 journal, which is the first run carrying `stage_all`,
`cause_all` and `coverage_present` on every ask rather than only on failures.
That is what makes a passing-vs-failing comparison possible at all: before this
run one side of every pair was absent from the instrument, which is why
`paraphrase_gap_diagnosis.md` could only reason from the failing side and had to
retract an inference about the passing side.

Groups asks by outcome and reports, for each group:
  * coverage distribution, and how many have `coverage_present` at all -- a None
    coverage with `coverage_present` False means the recall gate never ran, which
    is a different fact from a gate that ran and returned None;
  * required terms, and which of them are answerable content words;
  * nearest rows, split taught vs book -- the E14a finding was that failing asks
    retrieve book rows, so the passing side is the control for that claim;
  * stage_all and cause_all, which for a passing ask say *which path answered*
    rather than which refused.

Then it looks for the minimal difference: asks that fail only at the coverage
threshold while retrieving the correct taught row and ranking it top, which is
the candidate defect the failing-side data pointed at but could not confirm.

Read-only. No brain builds.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.heldout_eval import _said_content  # noqa: E402

# Probe-local, same set E17a used: content words an answer can legitimately carry.
# Not imported because it does not live in tools/ -- it was defined per-probe there
# too. Kept identical so the two probes' "answerable required term" counts agree.
ANSWERABLE = {
    "lantern", "kettle", "scarf", "coat", "moon", "bell", "eggs", "water", "hook",
    "copper", "wool", "blue", "red", "wet", "dry", "heavy", "light", "cold", "warm",
    "first", "last", "twice", "once", "three", "two", "one", "four", "five",
    "turn", "turns", "boil", "boiling", "hang", "hanging", "shine", "shining",
    "sooner", "before", "after", "often", "many", "much", "both", "which", "what",
}

JOURNAL = ROOT / "state" / "selection" / "generation_15_asks.jsonl"
OUT = Path(__file__).with_suffix(".json")

def expect_of(row):
    """The journal row carries the step's expect; no need to re-import the battery."""
    return row.get("expect") or {}


def load():
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows


def cov_of(row):
    return row.get("coverage")


def nearest_taught(row):
    return [r for r in (row.get("nearest") or []) if r.startswith("droso:")]


def nearest_book(row):
    return [r for r in (row.get("nearest") or []) if r.startswith("book:")]


def summarise(rows, label):
    covs = [cov_of(r) for r in rows if isinstance(cov_of(r), (int, float))]
    present = sum(1 for r in rows if r.get("coverage_present"))
    return {
        "label": label,
        "n": len(rows),
        "coverage_present": present,
        "coverage_absent": len(rows) - present,
        "coverage_n": len(covs),
        "coverage_min": round(min(covs), 6) if covs else None,
        "coverage_max": round(max(covs), 6) if covs else None,
        "coverage_mean": round(sum(covs) / len(covs), 6) if covs else None,
        "stage_all": dict(Counter(r.get("stage_all") for r in rows).most_common()),
        "cause_all": dict(Counter(r.get("cause_all") for r in rows).most_common()),
        "with_required": sum(1 for r in rows if r.get("required")),
        "with_nearest": sum(1 for r in rows if r.get("nearest")),
        "nearest_has_taught": sum(1 for r in rows if nearest_taught(r)),
        "nearest_all_book": sum(1 for r in rows
                                if (r.get("nearest") or []) and not nearest_taught(r)),
    }


def main():
    rows = load()
    passing = [r for r in rows if r.get("pass")]
    failing = [r for r in rows if not r.get("pass")]

    out = {
        "journal": str(JOURNAL.relative_to(ROOT)),
        "total": len(rows),
        "passing": summarise(passing, "passing"),
        "failing": summarise(failing, "failing"),
        "per_ask": [],
        "candidates": [],
    }

    for r in rows:
        said = _said_content(r.get("words") or [])
        req = r.get("required") or []
        ans_req = [w for w in req if w in ANSWERABLE]
        near = r.get("nearest") or []
        rec = {
            "ask": r.get("ask"),
            "pass": bool(r.get("pass")),
            "expect": expect_of(r),
            "stage": r.get("stage"),
            "stage_all": r.get("stage_all"),
            "cause": r.get("cause"),
            "cause_all": r.get("cause_all"),
            "coverage_present": r.get("coverage_present"),
            "coverage": cov_of(r),
            "required": req,
            "required_answerable": ans_req,
            "said": said,
            "nearest": near,
            "nearest_taught": nearest_taught(r),
            "nearest_book": nearest_book(r),
            "why": (r.get("why") or "")[:160],
        }
        out["per_ask"].append(rec)

        # The candidate defect: fails at the recall gate, the correct taught row
        # IS retrieved and ranked top, and the only thing blocking is the score.
        # Rank-keyed rather than score-keyed, so it is not the mechanism E12a
        # (restrict must), E14a (admit all tells) or gen 2/6 (move the floor) closed.
        if (not rec["pass"] and rec["stage_all"] == "recall"
                and rec["cause_all"] == "recall_gate"
                and rec["nearest_taught"]
                and near and near[0].startswith("droso:")):
            out["candidates"].append({
                "ask": rec["ask"],
                "coverage": rec["coverage"],
                "top_row": near[0],
                "required": req,
                "required_answerable": ans_req,
                "said": said,
            })

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    for grp in ("passing", "failing"):
        g = out[grp]
        print(f"\n=== {grp.upper()} (n={g['n']}) ===")
        print(f"  coverage_present={g['coverage_present']} absent={g['coverage_absent']} "
              f"numeric={g['coverage_n']}")
        if g["coverage_n"]:
            print(f"  coverage min={g['coverage_min']} max={g['coverage_max']} "
                  f"mean={g['coverage_mean']}")
        print(f"  stage_all={g['stage_all']}")
        print(f"  cause_all={g['cause_all']}")
        print(f"  required={g['with_required']} nearest={g['with_nearest']} "
              f"nearest_has_taught={g['nearest_has_taught']} "
              f"nearest_all_book={g['nearest_all_book']}")

    print(f"\n=== CANDIDATES: taught row retrieved AND ranked top, still refused "
          f"(n={len(out['candidates'])}) ===")
    for c in out["candidates"]:
        print(f"  {c['ask']!r}")
        print(f"    coverage={c['coverage']} top={c['top_row']!r}")
        print(f"    required={c['required']} answerable={c['required_answerable']} "
              f"said={c['said']}")

    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
