r"""Why half the mutations are silent: boundary distance, gene by gene.

THE CLAIM TO TEST. A gene only bites when a mutation crosses a decision
boundary. If the base sits a long way from every boundary, a small change to a
weight changes no argmax anywhere and the mutant is indistinguishable from the
base -- which is exactly the 2/10-5/10 reach measured last cut.

WHAT THIS PRINTS, per gene:
  distance up / down   the smallest change that moves the composite, found by
                       sweeping the weight in 0.01 steps from the base until
                       fitness differs. This is the boundary distance, measured,
                       not asserted.
  draws / crossed      among the ten mutation draws the control run makes, which
                       gene was picked, what the delta was, and whether the
                       composite moved at all.

The mutation distribution is untouched: same mutate(), same gaussian, same
stream. Only the base genome's position is a free parameter, and the point of
this file is to show that position is what reach is made of.

  py -3.10 tools/reach_probe.py
  py -3.10 tools/reach_probe.py --json state/fitness/reach.json
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

from tools.fly_v2 import (GENES, base_genome, build_pairs, canon, composite,  # noqa: E402
                          mutate)

C5 = 0.666667          # measured with a real house; constant w.r.t. these genes
PAIRS = build_pairs()


def score(genome):
    return composite(genome, PAIRS, C5)[1]


def boundary(genome, gene, step=0.01, limit=3.0):
    """Smallest |delta| in each direction that moves the composite."""
    base_val = score(genome)
    out = {}
    for sign in (+1, -1):
        d = step
        found = None
        while d <= limit + 1e-9:
            g = dict(genome)
            g[gene] = min(3.0, max(0.0, round(genome[gene] + sign * d, 6)))
            if g[gene] == genome[gene]:
                break
            if score(g) != base_val:
                found = round(d, 3)
                break
            d = round(d + step, 6)
        out["up" if sign > 0 else "down"] = found
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    base = base_genome(args.seed)
    base_val = score(base)
    print("BASE", canon(base), "composite", f"{base_val:.6f}")
    print("\nBOUNDARY DISTANCE (smallest change that moves the composite):")
    dist = {}
    for g in GENES:
        dist[g] = boundary(base, g)
        up, down = dist[g]["up"], dist[g]["down"]
        print(f"  {g:8s} value={base[g]:.2f}  up={up}  down={down}")

    rng = random.Random(args.seed)
    draws = []
    for i in range(args.n):
        child = mutate(base, rng)
        changed = [k for k in GENES if child[k] != base[k]]
        gene = changed[0] if changed else "none"
        delta = round(child[gene] - base[gene], 4)
        moved = score(child) != base_val
        draws.append({"draw": i, "gene": gene, "delta": delta, "moved": moved})
    print(f"\nTEN MUTATION DRAWS (stream = control seed {args.seed}):")
    per_gene = {g: [0, 0] for g in list(GENES) + ["none"]}
    for d in draws:
        per_gene[d["gene"]][0] += 1
        per_gene[d["gene"]][1] += 1 if d["moved"] else 0
        print(f"  draw {d['draw']:2d}  {d['gene']:8s} delta={d['delta']:+.3f} "
              f"{'CROSSED' if d['moved'] else 'silent'}")
    print("\nPER GENE:")
    for g in list(GENES) + ["none"]:
        n, c = per_gene[g]
        print(f"  {g:8s} draws={n} crossed={c}")
    crossed = sum(1 for d in draws if d["moved"])
    print(f"\nREACH {crossed}/{args.n} = {100.0 * crossed / args.n:.0f}%")

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"stamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                 "seed": args.seed, "base": base,
                                 "base_composite": base_val,
                                 "boundary": dist, "draws": draws,
                                 "per_gene": per_gene,
                                 "reach": crossed / args.n}, indent=2),
                     encoding="utf-8")
        print("report:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())