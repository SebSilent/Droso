"""A/B inertness instrument: does a flag-OFF run reproduce the pre-treatment artifact ROW FOR ROW?

WHY THIS EXISTS. The A/B has two halves and they are not the same claim. "Flag ON moved the number"
is a treatment effect; "flag OFF left every row where it was" is what makes the first claim
controlled rather than an observation on one arm. Without the second half, any difference between
the ON artifact and the pre-treatment artifact could be the run rather than the flag -- G0-prime
measured 11 rows of 3,672 moving between three IDENTICAL clones, so the instrument is not stable
enough to be assumed.

COUNTS ARE NOT ENOUGH. Two artifacts can agree on every tally -- 36 arbiter-tell rows, 24 guarded
absences, 16 asserted -- while different rows hold those places. So the comparison is keyed by the
row's position (arm, depth, phase, item, shape) and its identity (ask, said, src, cls), and every
difference NAMES itself.

THE REGISTERED TOLERANCE, APPLIED IN ADVANCE. organs/neural_language.py:946-948 gates a spoken row
on 2.0 s of wall clock, and G0-prime measured the resulting movement into exactly two cells,
learn/1/reasked and learn/1/restarted, which R13 excluded from the noise-floor claim. Differences
inside those two cells are counted and reported, never assumed away: more movement than the
registered 11 rows is a finding about the instrument, not a licence to widen the tolerance.
Differences anywhere else are a hard failure with no exception path.

  py tools/ab_reproduction.py --candidate experiments/MP-E9/results/ab_flag_off.json \
      --out experiments/MP-E9/results/ab_flag_off_reproduction.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R13_TIME_DEPENDENT_CELLS = ("learn/1/reasked", "learn/1/restarted")
R13_REGISTERED_ROWS = 11


def sha256_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def keyed(doc: dict) -> dict:
    """(arm, depth, phase, item, shape) -> row identity. Position is the key; identity is the value."""
    out = {}
    for arm, res in (doc.get("arms") or {}).items():
        for depth, ph in (res.get("probes") or {}).items():
            for phase, rows in ph.items():
                for r in rows:
                    out[(arm, str(depth), phase, str(r.get("item")), str(r.get("shape")))] = (
                        str(r.get("ask")), str(r.get("said")), str(r.get("src")),
                        str(r.get("cls")))
    return out


def cell_of(k) -> str:
    return f"{k[0]}/{k[1]}/{k[2]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--reference", default="docs/evidence/electric_learn_bench.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    cand_p = Path(a.candidate) if Path(a.candidate).is_absolute() else ROOT / a.candidate
    ref_p = Path(a.reference) if Path(a.reference).is_absolute() else ROOT / a.reference
    cand = json.loads(cand_p.read_text(encoding="utf-8"))
    ref = json.loads(ref_p.read_text(encoding="utf-8"))

    b, o = keyed(ref), keyed(cand)
    gained = {k: v for k, v in o.items() if k not in b}
    lost = {k: v for k, v in b.items() if k not in o}
    moved = {k: {"before": b[k], "after": o[k]} for k in b if k in o and b[k] != o[k]}
    all_d = {"gained": gained, "lost": lost, "moved": moved}
    total = sum(len(v) for v in all_d.values())

    in_r13 = {n: {str(k): v for k, v in d.items() if cell_of(k) in R13_TIME_DEPENDENT_CELLS}
              for n, d in all_d.items()}
    outside = {n: {str(k): v for k, v in d.items() if cell_of(k) not in R13_TIME_DEPENDENT_CELLS}
               for n, d in all_d.items()}
    n_in = sum(len(v) for v in in_r13.values())
    n_out = sum(len(v) for v in outside.values())
    cells = {}
    for d in all_d.values():
        for k in d:
            cells[cell_of(k)] = cells.get(cell_of(k), 0) + 1

    flags = (cand.get("provenance") or {}).get("electric_flags") or {}
    art = {
        "schema": "droso.ab_reproduction.v1",
        "label": a.label,
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reference": {"path": str(ref_p.relative_to(ROOT)).replace("\\", "/"),
                      "sha256_lf": sha256_lf(ref_p), "rows": len(b)},
        "candidate": {"path": str(cand_p.relative_to(ROOT)).replace("\\", "/"),
                      "sha256_lf": sha256_lf(cand_p), "rows": len(o),
                      "electric_flags": flags},
        "counts": {"rows_keyed_both": len(set(b) & set(o)), "gained": len(gained),
                   "lost": len(lost), "moved": len(moved), "total_differences": total,
                   "inside_r13_cells": n_in, "outside_r13_cells": n_out},
        "by_cell": dict(sorted(cells.items(), key=lambda x: (-x[1], x[0]))),
        "tolerance": {
            "cells": list(R13_TIME_DEPENDENT_CELLS),
            "registered_rows": R13_REGISTERED_ROWS,
            "basis": ("G0-prime noise floor: 11 rows of 3,672 moved across three identical clones, "
                      "all in these two cells, because the speech-act row is gated on 2.0 s of wall "
                      "clock. R13 excluded these cells from the noise-floor claim; this instrument "
                      "excludes them from the inertness FAILURE and still counts them."),
        },
        "verdict": {
            "inert_outside_registered_tolerance": n_out == 0,
            "movement_within_registered_rows": n_in <= R13_REGISTERED_ROWS,
            "row_for_row_identical": total == 0,
        },
        # Tuple keys are not JSON. Every difference is stringified as "arm|depth|phase|item|shape"
        # so a reader can locate the row in the artifact without a second pass through keyed().
        "differences": {n: {f"{k[0]}|{k[1]}|{k[2]}|{k[3]}|{k[4]}": v for k, v in d.items()}
                        for n, d in all_d.items() if d},
        "provenance_note": ("An artifact identifies its own arm through provenance.electric_flags; "
                           "this instrument reads that field rather than trusting the filename, "
                           "because a flag-OFF reproduction of a run that secretly had a treatment "
                           "on would prove nothing."),
    }
    v = art["verdict"]
    print(f"rows keyed: reference={len(b)} candidate={len(o)}")
    print(f"differences: gained={len(gained)} lost={len(lost)} moved={len(moved)} total={total}")
    print(f"  inside R13 cells: {n_in} (registered floor {R13_REGISTERED_ROWS})")
    print(f"  OUTSIDE R13 cells: {n_out}")
    print(f"  inert_outside_tolerance={v['inert_outside_registered_tolerance']} "
          f"row_for_row_identical={v['row_for_row_identical']}")
    if a.out:
        op = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(art, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        print(f"wrote {op.relative_to(ROOT)}")
    return 0 if (v["inert_outside_registered_tolerance"]
                 and v["movement_within_registered_rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
