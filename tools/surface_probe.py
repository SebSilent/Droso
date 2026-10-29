r"""Is the ceiling reachable at all? The whole genome space, enumerated.

WHY THIS EXISTS. Elite-only breeding with k=2 should compose two genes with
near-certainty if the composition scores well: eight mutants a generation, a
third of them flipping the missing gene, three generations. It improved on ZERO
of five seeds, and so did every tournament size. That kills "the pool is too
small" as an explanation before any inference about selection strength is made,
so the next question is the surface itself: is there a genome that scores 1.0,
and if the best possible score is 0.625, which pairs make 1.0 impossible?

Twelve genomes: head_index (-1, 0) x cut_at (none, of, all) x rel_head (bool).
Cheap enough to enumerate exhaustively, which is stronger than sampling.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.fly_population import (base_genome, build_pairs,  # noqa: E402
                                  evaluate_components, fly_filler)

PAIRS = build_pairs()
G0 = base_genome(13)
rows = []
for hi, ca, rh in itertools.product((-1, 0), ("none", "of", "all"),
                                    (False, True)):
    g = dict(G0)
    g.update(head_index=hi, cut_at=ca, rel_head=rh)
    comps, val = evaluate_components(g, PAIRS)
    rows.append((val, hi, ca, rh, comps))
rows.sort(reverse=True)

print(f"genome space: {len(rows)} genomes, {len(PAIRS)} pairs "
      f"({len(PAIRS) // 4} per component)")
for val, hi, ca, rh, comps in rows:
    print(f"  {val:.5f}  head={hi:2d} cut={ca:5s} rel={str(rh):5s}  "
          f"{','.join(f'{c}={v:.3f}' for c, v in comps.items())}")
print(f"MAX IN SPACE {rows[0][0]:.5f}")

val, hi, ca, rh, _ = rows[0]
g = dict(G0)
g.update(head_index=hi, cut_at=ca, rel_head=rh)
fails = [p for p in PAIRS
         if fly_filler(p["tokens"], p["shape"], g) != p["head"]]
print(f"\nbest genome fails {len(fails)} of {len(PAIRS)} pairs")
for p in fails[:8]:
    print(f"   {p['comp']:17s} {p['flavour']:5s} {' '.join(p['tokens'])}"
          f"  -> got {fly_filler(p['tokens'], p['shape'], g)!r}"
          f" want {p['head']!r}")