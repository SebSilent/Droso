r"""The selection lever, tested one condition at a time.

PRE-REGISTERED BEFORE THIS RAN (docs/speech_log.md): gen-2 stalls at 0.625
because a three-way tournament in a ten-fly pool breeds from the 0.625 carriers
too rarely to compose them. Fitness, mutation, population (10) and material are
untouched; the ONLY variable is how parents are chosen. Every condition starts
from the same population for a given seed, so a difference is attributable to
breeding and not to a luckier draw.

Conditions, in order, each attributable on its own:
  elite       top k reproduce, everyone else discarded     k = 2, then 4
  tournament  k-way tournament among all survivors         k = 5, then 7

Pass: on 3 of 5 seeds or more, gen-2 best > gen-1 best OR gen-3 best >
gen-1 best within a condition. A stall everywhere is a result: the ceiling is
not reachable by selection strength, and the next question is whether the
composite surface is too sparse -- not whether the pool is too small.

  py -3.10 tools/selection_lever.py
  py -3.10 tools/selection_lever.py --conditions elite:2 --gens 3
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.fly_population import (STATE, base_genome, build_pairs, canon,  # noqa: E402
                                  gid, mutate, rows_for)

SEEDS = (13, 7, 17, 23, 29)
CONDITIONS = (("elite", 2), ("elite", 4), ("tournament", 5), ("tournament", 7))
ELITE = 2          # unmutated survivors carried in tournament mode
GENES = ("head_index", "cut_at", "rel_head")


def breed(rows, mode, k, n, rng):
    """One change, one variable: who is allowed to reproduce."""
    ranked = sorted(rows, key=lambda r: (-r["fitness"], r["id"]))
    if mode == "elite":
        parents = ranked[:max(1, min(k, len(ranked)))]
        nxt = [{"genome": p["genome"], "parent": p["genome_id"]} for p in parents]
        while len(nxt) < n:
            p = rng.choice(parents)
            nxt.append({"genome": mutate(p["genome"], rng),
                        "parent": p["genome_id"]})
        return nxt
    nxt = [{"genome": r["genome"], "parent": r["genome_id"]}
           for r in ranked[:ELITE]]
    while len(nxt) < n:
        win = min(rng.sample(ranked, min(k, len(ranked))),
                  key=lambda r: (-r["fitness"], r["id"]))
        nxt.append({"genome": mutate(win["genome"], rng),
                    "parent": win["genome_id"]})
    return nxt


def run(seed, mode, k, gens=3, n=10):
    # Same stream as tools/fly_population.py phase_generations, so every
    # condition begins from an identical population for this seed.
    rng = random.Random(seed + 1)
    pairs = build_pairs()
    base = base_genome(seed)
    pop = [{"genome": json.loads(canon(base)), "parent": None}]
    pop += [{"genome": mutate(base, rng), "parent": gid(base)}
            for _ in range(n - 1)]
    allrows, bests = [], []
    for gen in range(1, gens + 1):
        rows = rows_for(f"g{gen}", [p["genome"] for p in pop], pairs, gen=gen,
                        parents=[p["parent"] for p in pop])
        allrows += rows
        best = max(rows, key=lambda r: (r["fitness"], r["id"]))
        bests.append({"gen": gen, "best": best["fitness"], "row": best["id"],
                      "genome_id": best["genome_id"], "genome": best["genome"]})
        pop = breed(rows, mode, k, n, rng)
    return bests, allrows


def chain(rows, row):
    """Ancestry by genome id, with the genes visible at each step."""
    out = [row]
    cur, seen = row, {row["genome_id"]}
    while cur.get("parent") and cur["parent"] not in seen:
        prev = [r for r in rows if r["genome_id"] == cur["parent"]]
        if not prev:
            out.append({"id": None, "genome_id": cur["parent"], "fitness": None,
                        "genome": None, "founder": True})
            break
        prev = max(prev, key=lambda r: r["gen"])
        out.append(prev)
        seen.add(prev["genome_id"])
        cur = prev
    return out


def genes(genome):
    if not genome:
        return "(founder = base genome)"
    return " ".join(f"{g}={genome.get(g)}" for g in GENES)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--conditions", nargs="*", default=None,
                    help="e.g. elite:2 tournament:5; default runs all four")
    ap.add_argument("--gens", type=int, default=3)
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    conds = CONDITIONS
    if args.conditions:
        conds = tuple((c.split(":")[0], int(c.split(":")[1]))
                      for c in args.conditions)

    out = {"stamp": time.strftime("%Y-%m-%d %H:%M:%S"), "seeds": list(SEEDS),
           "gens": args.gens, "n": args.n, "conditions": []}
    majority = (len(SEEDS) // 2) + 1
    for mode, k in conds:
        label = f"{mode}:{k}"
        per_seed = []
        for seed in SEEDS:
            bests, allrows = run(seed, mode, k, args.gens, args.n)
            b = {x["gen"]: x["best"] for x in bests}
            improved = (b.get(2, 0) > b[1]) or (b.get(3, 0) > b[1])
            per_seed.append({"seed": seed, "bests": b,
                             "rows": [{"gen": x["gen"], "row": x["row"],
                                       "genome_id": x["genome_id"],
                                       "genome": x["genome"]} for x in bests],
                             "improved": improved,
                             "trace": None})
            if improved:
                target = max((x for x in bests if x["gen"] > 1),
                             key=lambda x: x["best"])
                row = next(r for r in allrows
                           if r["id"] == target["row"] and r["gen"] == target["gen"])
                per_seed[-1]["trace"] = [
                    {"row": s.get("id"), "genome_id": s["genome_id"],
                     "fitness": s["fitness"], "genes": genes(s.get("genome")),
                     "founder": bool(s.get("founder"))}
                    for s in chain(allrows, row)]
        wins = sum(1 for s in per_seed if s["improved"])
        print(f"\n== {label}  improving seeds {wins}/{len(SEEDS)} "
              f"({'PASS' if wins >= majority else 'FAIL'})")
        print("  seed | gen-1  | gen-2  | gen-3")
        for s in per_seed:
            b = s["bests"]
            print(f"  {s['seed']:4d} | {b[1]:.5f} | {b.get(2, float('nan')):.5f} "
                  f"| {b.get(3, float('nan')):.5f}")
        for s in per_seed:
            if s["trace"]:
                print(f"  composition path, seed {s['seed']}:")
                for step in s["trace"]:
                    if step["founder"]:
                        print(f"    <- {step['genome_id']} FOUNDER")
                    else:
                        print(f"    {step['row']:6s} id={step['genome_id']} "
                              f"fit={step['fitness']:.5f}  {step['genes']}")
        out["conditions"].append({"label": label, "mode": mode, "k": k,
                                  "wins": wins, "pass": wins >= majority,
                                  "seeds": per_seed})

    p = STATE / f"selection_lever_{time.strftime('%Y%m%d_%H%M%S')}.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nreport:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())