r"""Recover the best fly's genome, prove it is the SAME fly, and save it.

WHY THIS FILE EXISTS, AND WHY IT IS NOT A NEW RUN. The generation runs were
printed but never persisted: `tools/fly_v2.py --phase generations` writes no
report, so there is no saved genome to hand the shim. That is a defect in the
harness, recorded in docs/speech_log.md, not a number to be fudged.

The reply is deterministic: the same seed and the same code produce the same
population, so the best genome is a function of (seed, gens, n, code version).
This file replays it, then PROVES it recovered the same fly rather than a lucky
one:

  1. the replayed gen-5 best fitness must equal the printed 0.900000 exactly;
  2. the replay is run TWICE from independent RNG instances and the two best
     genome ids must be identical -- determinism, not a draw.

Only if both hold is the genome written to state/fitness/best_genome.json.
It is dereferencing a value that should have been saved, and it is labelled as
such wherever the number is reported.

  py -3.10 tools/score_best.py --seed 29 --gens 5 --expect 0.9
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.fly_v2 as fv  # noqa: E402
from tools.fly_v2 import (base_genome, build_pairs, canon, gid,  # noqa: E402
                          mutate, rows_for)


def replay(seed, gens, n=10, c5=None):
    rng = random.Random(seed + 1)
    pairs = build_pairs()
    base = base_genome(seed)
    pop = [{"genome": json.loads(canon(base)), "parent": None}]
    pop += [{"genome": mutate(base, rng), "parent": gid(base)}
            for _ in range(n - 1)]
    best_by_gen = []
    last_rows, last_genome = None, None
    for gen in range(1, gens + 1):
        rows = rows_for(f"g{gen}", [p["genome"] for p in pop], pairs,
                        c5, gen=gen, parents=[p["parent"] for p in pop])
        best = max(rows, key=lambda r: (r["fitness"], r["id"]))
        best_by_gen.append(best["fitness"])
        last_rows, last_genome = rows, best
        ranked = sorted(rows, key=lambda r: (-r["fitness"], r["id"]))
        nxt = [{"genome": r["genome"], "parent": r["genome_id"]}
               for r in ranked[:2]]
        while len(nxt) < len(rows):
            win = min(rng.sample(ranked, min(3, len(ranked))),
                      key=lambda r: (-r["fitness"], r["id"]))
            nxt.append({"genome": mutate(win["genome"], rng),
                        "parent": win["genome_id"]})
        pop = nxt
    return best_by_gen, last_genome


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seed", type=int, default=29)
    ap.add_argument("--gens", type=int, default=5)
    ap.add_argument("--expect", type=float, default=0.9)
    ap.add_argument("--house", action="store_true",
                    help="build one house so C5 is gene-aware, as in the run")
    args = ap.parse_args()

    # The reported run used --house, so C5 was gene-aware (0.666667 base,
    # 1.000000 with the parser gene). Without the house the replay scores
    # every fly against C5 = 0 and selects a DIFFERENT trajectory -- measured:
    # it returns 0.700, not 0.900, and the mismatch check refused to save.
    if args.house:
        import shutil
        from tools.converse import build
        d = fv.STATE / "sessions" / "score_best"
        try:
            fv.AGENT = build(d)
            print("house built for C5:", fv.c5_for({"w_count": 0.0}))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    a_bests, a_best = replay(args.seed, args.gens)
    b_bests, b_best = replay(args.seed, args.gens)
    print("replay A", a_bests, a_best["id"], a_best["genome_id"], a_best["fitness"])
    print("replay B", b_bests, b_best["id"], b_best["genome_id"], b_best["fitness"])
    same = (a_best["genome_id"] == b_best["genome_id"]
            and a_bests == b_bests)
    print("deterministic across two replays:", same)
    print("matches the printed best:", abs(a_best["fitness"] - args.expect) < 1e-9)
    if not same or abs(a_best["fitness"] - args.expect) > 1e-9:
        print("REFUSING to save: this is not the fly that was reported")
        return 1
    out = {"recovered_by": "deterministic replay (genome was never persisted)",
           "seed": args.seed, "gens": args.gens,
           "gen": a_best["gen"], "row": a_best["id"],
           "genome_id": a_best["genome_id"], "fitness": a_best["fitness"],
           "genome": a_best["genome"], "components": a_best["components"],
           "replay_a": a_bests, "replay_b": b_bests,
           "deterministic": same}
    p = ROOT / "state" / "fitness" / "best_genome.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("saved:", p, canon(a_best["genome"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())