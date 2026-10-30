"""Classify every harness ask from its own journal, using the raw recall fields.

Reads state/selection/generation_7_asks.jsonl -- the first journal recorded with
`coverage`, `required` and `nearest` in it -- and assigns each ask to one of four
classes. The point is that the classification now comes from the harness's own
scored run rather than from a separate probe reconstructing the context, which is
the exact defect that falsified E6's P2: a coverage value measured outside the
harness did not transfer, and no value measured inside it has yet been shown to
fail.

The four classes, and the rule that separates them:

  ABSENT        stage=recall, `required` empty AND `nearest` empty.
                The cue reached no binder posting at all. There is nothing to
                recall and no threshold is relevant. This is the class E5's shape
                repairs could not touch, because informativeness had no words to
                work on.

  UNREACHABLE   stage=recall, `nearest` NON-empty but `required` empty, or
                `coverage` == 0 with postings present.
                Memories exist and the organ found neighbours, but the cue could
                not bind to them -- the posting is there and the question cannot
                address it. Distinct from ABSENT (nothing there) and from GATE
                (something there, scored, and refused).

  GATE          stage=recall, `required` non-empty AND `coverage` is not None.
                A posting was found, scored, and refused because best_cov < the
                floor. This is the only class a threshold can move, and E6 showed
                moving the threshold buys nothing measurable.

  DOWNSTREAM    stage in (shape_arbiter, mouth, gating), or the ask was spoken
                and still failed grading.
                The recall gate is not where it died. The shape arbiter vetoed,
                the mouth could not render it, the response gate held it, or the
                organ answered and the content did not match `expect`.

Read-only. Writes docs/evidence/harness_coverage_diagnosis.json.
"""

from __future__ import annotations

import io
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

JOURNAL = os.path.join(ROOT, "state", "selection", "generation_7_asks.jsonl")
OUT = os.path.join(ROOT, "docs", "evidence", "harness_coverage_diagnosis.json")

RECALL_STAGES = {"recall"}
DOWNSTREAM_STAGES = {"shape_arbiter", "mouth", "gating", "engine_error",
                     "genome_refused"}


def classify(rec: dict) -> tuple[str, str]:
    """(class, why) for one journal row. `why` is the rule that fired."""
    stage = rec.get("stage")
    passed = bool(rec.get("pass"))
    cov = rec.get("coverage")
    req = rec.get("required") or []
    near = rec.get("nearest") or []

    if passed:
        # A pass is recorded too, with its coverage, because the coverage of the
        # asks that WORK is the only in-harness evidence of where the gate sits.
        return "PASS", f"passed; coverage={cov}"

    if stage in RECALL_STAGES:
        if not req and not near:
            return "ABSENT", "required empty and nearest empty: no posting"
        if not near:
            return "UNREACHABLE", "required set but nearest empty"
        if not req:
            return "UNREACHABLE", (
                f"nearest has {len(near)} posting(s) but required is empty: "
                "the cue found neighbours it could not bind")
        if cov is None:
            return "UNREACHABLE", "required and nearest present, coverage unset"
        if float(cov) <= 0.0:
            return "UNREACHABLE", f"coverage 0 with {len(near)} posting(s)"
        return "GATE", f"coverage={cov} < floor, required={req}"

    if stage in DOWNSTREAM_STAGES:
        return "DOWNSTREAM", f"stage={stage}"

    if rec.get("spoken"):
        return "DOWNSTREAM", "spoken but content did not match expect"

    return "DOWNSTREAM", f"stage={stage or 'unset'}"


def main() -> int:
    if not os.path.exists(JOURNAL):
        print(f"missing journal {JOURNAL}")
        return 2
    rows = [json.loads(l) for l in io.open(JOURNAL, encoding="utf-8") if l.strip()]
    if not rows:
        print("journal is empty")
        return 2

    genomes = sorted({r.get("genome_id") for r in rows if r.get("genome_id")})
    print(f"journal rows: {len(rows)}   genomes: {genomes}")

    tally = Counter()
    by_class = defaultdict(list)
    stage_tally = Counter()
    pass_cov = []
    gate_cov = []

    for r in rows:
        cls, why = classify(r)
        tally[cls] += 1
        by_class[cls].append({
            "tier": r.get("tier"), "script": r.get("script"),
            "id": r.get("id"), "ask": r.get("ask"),
            "stage": r.get("stage"), "class": cls, "why": why,
            "coverage": r.get("coverage"),
            "required": r.get("required"),
            "nearest": r.get("nearest"),
            "said": (r.get("said") or "")[:120],
            "spoken": r.get("spoken"),
            "probe": r.get("probe"), "rewords": r.get("rewords"),
            "guard": r.get("guard"),
        })
        if r.get("stage"):
            stage_tally[r["stage"]] += 1
        if r.get("coverage") is not None:
            (pass_cov if r.get("pass") else gate_cov).append(float(r["coverage"]))

    n_pass = tally["PASS"]
    n_fail = len(rows) - n_pass
    print(f"\npassed {n_pass}/{len(rows)}   failed {n_fail}")
    print(f"stage tally (failures only): {dict(stage_tally)}")

    print("\n=== CLASS TALLY ===")
    for k in ("ABSENT", "UNREACHABLE", "GATE", "DOWNSTREAM"):
        print(f"  {k:<12} {tally[k]}")

    if pass_cov:
        print(f"\ncoverage of PASSING asks: n={len(pass_cov)} "
              f"min={min(pass_cov):.4f} max={max(pass_cov):.4f}")
    if gate_cov:
        print(f"coverage of failed recall asks: n={len(gate_cov)} "
              f"min={min(gate_cov):.4f} max={max(gate_cov):.4f}")

    for k in ("ABSENT", "UNREACHABLE", "GATE", "DOWNSTREAM"):
        print(f"\n=== {k} ({tally[k]}) ===")
        for e in by_class[k]:
            cov = e["coverage"]
            covs = "-" if cov is None else f"{float(cov):.4f}"
            print(f"  [{e['tier']}] {e['ask'][:46]:<46} stage={str(e['stage']):<14}"
                  f" cov={covs:<8} req={len(e['required'] or [])} "
                  f"near={len(e['nearest'] or [])}")
            print(f"        why: {e['why'][:110]}")
            if e["said"]:
                print(f"        said: {e['said'][:90]}")

    out = {
        "journal": os.path.relpath(JOURNAL, ROOT).replace("\\", "/"),
        "rows": len(rows),
        "genomes": genomes,
        "passed": n_pass,
        "failed": n_fail,
        "stage_tally": dict(stage_tally),
        "class_tally": {k: tally[k] for k in
                        ("ABSENT", "UNREACHABLE", "GATE", "DOWNSTREAM")},
        "pass_coverage": {"n": len(pass_cov),
                          "min": min(pass_cov) if pass_cov else None,
                          "max": max(pass_cov) if pass_cov else None,
                          "values": sorted(pass_cov)},
        "failed_recall_coverage": {"n": len(gate_cov),
                                   "min": min(gate_cov) if gate_cov else None,
                                   "max": max(gate_cov) if gate_cov else None,
                                   "values": sorted(gate_cov)},
        "asks": by_class,
    }
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
