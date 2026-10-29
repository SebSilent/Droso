r"""Prove a saved genome is enough: load it, re-derive its composite, no evolution.

The defect: `--phase generations` printed the winner and wrote nothing, so the
outside check had to replay an entire run to recover a genome -- and a replay is
only trustworthy because it is deterministic, which is a fragile thing to depend
on. With the winner written to state/fitness/fly_best_seed<seed>.json, this file
does the opposite of a replay: it reads one JSON, one genome, and recomputes the
composite from it.

If the recomputed value differs from the stored one, either the genome was not
saved completely (a missing weight defaults differently) or the fitness is not a
function of the genome -- both are defects, so this asserts rather than prints.

  py -3.10 tools/verify_saved.py --seed 29
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.fly_v2 as fv  # noqa: E402
from tools.converse import build  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seed", type=int, default=29)
    args = ap.parse_args()

    f = ROOT / "state" / "fitness" / f"fly_best_seed{args.seed}.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    print("loaded:", f)
    print("gen", rec["gen"], "row", rec["row"], "genome_id", rec["genome_id"],
          "stored fitness", rec["fitness"])
    print("genome:", json.dumps(rec["genome"], sort_keys=True))

    # C5 is gene-aware, so it needs a real house -- the same one the run used.
    d = ROOT / "state" / "sessions" / "verify_saved"
    try:
        fv.AGENT = build(d)
        c5 = fv.c5_for(rec["genome"])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    comps, val = fv.composite(rec["genome"], fv.build_pairs())
    print("recomputed component by component:",
          json.dumps(comps, sort_keys=True))
    print("stored                           :",
          json.dumps(rec["components"], sort_keys=True))
    print(f"stored {rec['fitness']:.6f}  recomputed {val:.6f}  C5 {c5}")
    ok = abs(val - rec["fitness"]) < 1e-9 and comps == rec["components"]
    print("MATCH" if ok else "MISMATCH -- saved genome does not redrive the fitness")
    if not ok:
        return 1
    print("PROOF: one JSON file, no evolution, same composite")
    return 0


if __name__ == "__main__":
    sys.exit(main())