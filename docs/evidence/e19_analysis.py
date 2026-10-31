"""E19: classify each failing ask as eviction or retrieval.

Reads the generation-19 journal, the first run carrying read-only binder
attribution, and separates the two causes that `passing_ask_analysis.md` showed
were being conflated under one label:

  * **eviction**   -- `taught_resident` is False. The expected taught row is gone
                      from the binder by the time the ask runs. No threshold or
                      ranking repair can reach it.
  * **retrieval**  -- `taught_resident` is True but `taught_rank` is None or outside
                      the nearest window the gate actually consults. The row is in
                      the binder and the query does not surface it.
  * **neither**    -- resident AND ranked inside the window. The row reached the
                      candidate set and the ask still failed, so the defect is
                      downstream of retrieval (score, arbitration, mouth).

The window is the gate's own `nearest` list length, read per ask from the journal
rather than assumed, so the inside/outside call is made against what the run
actually consulted.

Also reports the passing side, which is the control: if passing asks show the same
residency profile as failing ones, residency is not the discriminator and E19's
hypotheses are both wrong.

Read-only. No brain builds.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
OUT = Path(__file__).with_suffix(".json")


def classify(row):
    a = row.get("attribution") or {}
    if not a.get("ok"):
        return "attribution_failed", a.get("why")
    res = a.get("taught_resident")
    if res is False:
        return "eviction", "not_resident"
    if res is None:
        return "unknown", a.get("why")
    rank = a.get("taught_rank")
    window = len(row.get("nearest") or [])
    if rank is None:
        return "retrieval", "resident_not_ranked"
    if window and rank > window:
        return "retrieval", f"rank {rank} outside window {window}"
    return "neither", f"rank {rank} inside window {window}"


def main():
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    passing = [r for r in rows if r.get("pass")]
    failing = [r for r in rows if not r.get("pass")]

    out = {"journal": str(JOURNAL.relative_to(ROOT)), "total": len(rows),
           "passing": [], "failing": [], "tally": {}}

    for label, group in (("passing", passing), ("failing", failing)):
        tally = Counter()
        for r in group:
            cls, why = classify(r)
            tally[cls] += 1
            a = r.get("attribution") or {}
            out[label].append({
                "ask": r.get("ask"),
                "class": cls,
                "why": why,
                "stage_all": r.get("stage_all"),
                "cause_all": r.get("cause_all"),
                "coverage": r.get("coverage"),
                "coverage_present": r.get("coverage_present"),
                "taught_resident": a.get("taught_resident"),
                "taught_count": a.get("taught_count"),
                "taught_rank": a.get("taught_rank"),
                "taught_row": a.get("taught_row"),
                "taught_rank_cue": a.get("taught_rank_cue"),
                "expected_tell": a.get("expected_tell"),
                "nearest": r.get("nearest"),
                "window": len(r.get("nearest") or []),
            })
        out["tally"][label] = dict(tally.most_common())

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    for label in ("failing", "passing"):
        print(f"\n=== {label.upper()} (n={len(out[label])}) ===")
        print(f"  tally: {out['tally'][label]}")
        for rec in out[label]:
            if label == "passing" and rec["class"] == "neither":
                continue  # printed in aggregate below
            print(f"  [{rec['class']:>9}] {rec['ask']!r}")
            print(f"             resident={rec['taught_resident']} "
                  f"count={rec['taught_count']} rank={rec['taught_rank']} "
                  f"window={rec['window']} stage={rec['stage_all']} "
                  f"cause={rec['cause_all']} cov={rec['coverage']}")
            print(f"             row={rec['taught_row']!r} why={rec['why']}")
        if label == "passing":
            n_neither = out["tally"]["passing"].get("neither", 0)
            print(f"  (+ {n_neither} passing asks classified 'neither', "
                  f"resident and ranked inside the window)")

    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
