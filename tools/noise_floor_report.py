"""Per-arm noise-floor report -- the question section 6.2 actually asks.

G0-prime's criterion (B.1 step 3) is that three clones of ONE configuration produce identical outcomes
row for row. The plan defines N as "three clones of **arm A's** configuration", and arm A is Droso in
ELECTRIC-learn mode. The clone run cloned the full shipped three-arm configuration, which is a
superset -- so "were the runs identical" is not yet the answer. The answer has to be per arm, because
arm A is the arm every downstream hypothesis is scored on, and a difference confined to the control
arm says something different from a difference in the arm under test.

It also separates the two kinds of difference, which is what makes a registered tolerance possible:

  graded-field differences   cls / said / src / item / shape / mech / taught / own / answered
  reason-string differences  the organ's own explanation, e.g. a coverage percentage

Only the first kind can change a result. The second is the organism talking about itself, and it is
where the measured jitter lives.

Run:  .venv/Scripts/python.exe tools/noise_floor_report.py
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import tools.bench_noise_floor as nf        # noqa: E402

D = HERE / "experiments" / "G0-prime" / "results" / "noise_floor"
# arm A of MP-E8 is the learn configuration; the bench's own arms are control/teach/learn.
ARM_A = "learn"
GRADED_FIELDS = tuple(f for f in nf.GRADED if f != "reason")


def arm_of(coord: str) -> str:
    return coord.split("/", 1)[0]


def field_of(diff: str):
    if "]." not in diff:
        return "rowcount"
    return diff.split("].", 1)[1].split(":")[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(D))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    d = pathlib.Path(a.dir)

    files = sorted(d.glob("clone_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    if len(files) < 3:
        print(f"[report] need three clones, found {len(files)}: {[f.name for f in files]}")
        return 1

    docs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    flats = [nf.flat(x) for x in docs]
    rows = len(flats[0])

    per_arm = defaultdict(Counter)
    pairs = {}
    samples = {}
    all_diffs = []
    for i in range(len(flats)):
        for j in range(i + 1, len(flats)):
            ds = nf.diff(flats[i], flats[j])
            pairs[f"clone{i + 1}vs{j + 1}"] = {"rows_compared": min(len(flats[i]), len(flats[j])),
                                               "differences": len(ds), "first": ds[:10]}
            samples[f"clone{i + 1}vs{j + 1}"] = ds[:8]
            all_diffs += ds
            for x in ds:
                per_arm[arm_of(x)][field_of(x)] += 1

    # Where the differences live. An instability confined to one arm, one depth and the two phases
    # that recur after a question has already been asked is a diagnosis; a uniform scatter across the
    # matrix would be something much worse, because it would mean no registered cell is trustworthy.
    concentration = {"by_arm": Counter(), "by_depth": Counter(), "by_phase": Counter(),
                     "by_field": Counter(), "coordinates": set()}
    # coordinates is built from the FULL difference list, never from the capped `samples` preview.
    # Reading the preview instead reported "8 distinct rows" when 11 rows actually moved -- a number
    # that looked like a measurement and was really an artefact of a display limit.
    for x in all_diffs:
        if "]." not in x:
            continue
        coord, rest = x.split("].", 1)
        arm, depth, phase = coord[:coord.rindex("[")].split("/")
        concentration["by_arm"][arm] += 1
        concentration["by_depth"][depth] += 1
        concentration["by_phase"][phase] += 1
        concentration["by_field"][rest.split(":")[0]] += 1
        concentration["coordinates"].add(coord + "]")
    graded_coords = sorted({x.split("].", 1)[0] + "]" for x in all_diffs if "]." in x
                            and x.split("].", 1)[1].split(":")[0] in GRADED_FIELDS})
    concentration["coordinates"] = sorted(concentration["coordinates"])
    concentration["distinct_rows_touched"] = len(concentration["coordinates"])
    concentration["distinct_rows_with_graded_field_difference"] = len(graded_coords)
    concentration["graded_coordinates"] = graded_coords
    concentration = {k: (dict(sorted(v.items())) if isinstance(v, Counter) else v)
                     for k, v in concentration.items()}

    graded_by_arm = {arm: sum(c for f, c in counts.items() if f in GRADED_FIELDS)
                     for arm, counts in per_arm.items()}
    reason_by_arm = {arm: sum(c for f, c in counts.items() if f == "reason")
                     for arm, counts in per_arm.items()}

    arm_a_graded = graded_by_arm.get(ARM_A, 0)
    all_graded = sum(graded_by_arm.values())
    all_reason = sum(reason_by_arm.values())

    out = {
        "schema": "droso.noise_floor_report.v1",
        "clones": [f.name for f in files],
        "rows_per_clone": rows,
        "criterion_as_written": "three clones of one configuration identical row for row "
                                "(B.1 step 3); N is defined as clones of ARM A's configuration "
                                "(section 6.2)",
        "arm_a_is": ARM_A,
        "pairs": pairs,
        "differences_by_arm_and_field": {arm: dict(sorted(c.items()))
                                         for arm, c in sorted(per_arm.items())},
        "concentration": concentration,
        "graded_field_differences_by_arm": dict(sorted(graded_by_arm.items())),
        "reason_string_differences_by_arm": dict(sorted(reason_by_arm.items())),
        "arm_A_graded_field_differences": arm_a_graded,
        "arm_A_identical_row_for_row": arm_a_graded == 0,
        "total_graded_field_differences": all_graded,
        "total_reason_string_differences": all_reason,
        "verdict": {
            "strict_identity_all_arms": all_graded + all_reason == 0,
            "graded_identity_all_arms": all_graded == 0,
            "arm_A_graded_identity": arm_a_graded == 0,
        },
        "samples": samples,
        "interpretation": (
            "A difference in cls/said/src/item/shape/mech/taught/own/answered can change a result and "
            "must be treated as a treatment effect or as a real reproducibility failure. A difference "
            "confined to `reason` is the organ's own coverage commentary moving by a percentage point; "
            "it cannot change a class, but it does mean the runs are not byte-identical, which is what "
            "B.1 step 3 literally asks for."
        ),
    }
    dest = pathlib.Path(a.out) if a.out else (d / "per_arm_breakdown.json")
    dest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print(f"[report] clones: {[f.name for f in files]}  rows/clone: {rows}")
    for k, v in sorted(pairs.items()):
        print(f"   {k}: {v['differences']} differences")
    print("\n   arm            graded-field diffs   reason-only diffs")
    for arm in sorted(set(list(graded_by_arm) + list(reason_by_arm))):
        print(f"   {arm:14s} {graded_by_arm.get(arm, 0):>18}   {reason_by_arm.get(arm, 0):>16}")
    print("\nwhere they live (summed over clone pairs):")
    print("   arm     :", concentration["by_arm"])
    print("   depth   :", concentration["by_depth"])
    print("   phase   :", concentration["by_phase"])
    print("   field   :", concentration["by_field"])
    print(f"   distinct rows touched: {len(concentration['coordinates'])}")

    v = out["verdict"]
    print(f"\n[report] ARM A ({ARM_A}) row-for-row identical in graded fields: "
          f"{v['arm_A_graded_identity']} ({arm_a_graded} differences)")
    print(f"[report] all arms identical, strict (incl. reason strings): "
          f"{v['strict_identity_all_arms']}")
    print(f"[report] all arms identical in GRADED fields only: {v['graded_identity_all_arms']}")
    print(f"[report] -> {dest.relative_to(HERE).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
