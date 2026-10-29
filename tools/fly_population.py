r"""A breeding population of Droso brains: shared substrate, per-fly genome.

WHY THIS FILE WAS REWRITTEN TWICE (2026-10-29). The first version could not
evolve and said so three ways: generation 1's best EQUALLED the base because the
base already sat at the ceiling; mutation was only ever observed as degradation
(0.0, 0.104 against a 1.0 base); and 8 of 10 mutants were invisible to fitness.
Its lineage was broken too -- control rows all parent None, A and B sharing ten
ids, and no lineage at all for generations.

THE SECOND REWRITE FAILED ITS OWN GATE, and is recorded because the failure is
the useful part: with genes head_index / prep_head / prep_scope, ten mutants
gave reach 5/10 -- exactly the 50% the gate refuses -- because prep_scope is
inert while prep_head is off, so a third of all mutations changed nothing any
component could see. A gene that only matters in a context the base is not in
is not a gene. Every gene below now bites from the base genome.

THE THREE FIXES, in the order they were made:

1. LINEAGE. Every individual is namespaced (A-*, B-*, g1-*, g2-*) and carries
   row id, genome id, parent genome id and generation. `phase_generations`
   asserts the population size holds, and prints a TRACE per generation that
   resolves the best back to its parent BY GENOME ID, stopping at the founder.

2. FITNESS WITH HEADROOM. Four components; each is 8 spans: 2 plain, 3 with a
   prepositional modifier, 3 with a relative clause. The incumbent passes the
   plain ones and fails BOTH harder flavours -- "the bell of the gate" has head
   `bell` and it says `gate`; "the bell the gate holds" has head `bell` and it
   says `holds`. That is the same span-head check made harder, the way the
   24-ask set was made harder to escape 32/32 -- not a fifth soft check. No
   component is 1.0 on the base, so none is dead weight. THE BREEDING GATE IS
   BASE COMPOSITE STRICTLY BELOW 1.0.

3. MUTATION REACH. Three genes, each decisive at the base: head_index (which
   word of the span is the head), cut_at (none | of | all -- does the fly stop
   the span at a preposition), rel_head (does a relative clause take its head
   as the first noun). A mutation always changes its gene. The FRACTION of
   mutants whose fitness differs from base is reported, not just the spread.

PROCESS MODEL, unchanged and forced by the cost model: one immutable substrate,
serial in process, a fly is a genome plus a dict of deltas, never a second
house (a second house measured +2426 MB duplicated, N=1).

  py -3.10 tools/fly_population.py --phase control --n 10 --seed 13
  py -3.10 tools/fly_population.py --phase generations --n 10 --gens 2
  py -3.10 tools/fly_population.py --phase trace
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
from organs.stemming import stem  # noqa: E402

STATE = ROOT / "state" / "fitness"

ARTICLES = ("the", "a", "some")
MODS = ("old", "copper", "heavy")
NOUNS = ("bell", "lantern", "latch", "crow", "sparrow", "box", "basket", "gate")
VERBS = ("turns", "bites", "holds", "follows", "shines", "keeps", "rings")
OF = ("of",)
PP = ("near", "under", "behind")
PREPS = OF + PP
TAILS = ("twice", "at noon", "again")
COMPONENTS = ("genitive_subject", "pp_subject", "genitive_object", "pp_object")
GENES = ("head_index", "cut_at", "rel_head")
CUTS = ("none", "of", "all")


# ------------------------------------------------------------------ genomes
def base_genome(seed: int = 13) -> dict:
    """The committed rule as a genome: last content word of the span, no
    prepositional handling, no relative-clause handling -- which is exactly the
    incumbent's behaviour and why it scores below 1.0 on the harder flavours."""
    return {"seed": int(seed), "head_index": -1, "cut_at": "none",
            "rel_head": False, "stem_verb": True}


def canon(g: dict) -> str:
    return json.dumps(g, sort_keys=True, separators=(",", ":"))


def gid(g: dict) -> str:
    return hashlib.sha256(canon(g).encode("utf-8")).hexdigest()[:12]


def mutate(genome: dict, rng: random.Random) -> dict:
    """One gene, always to a DIFFERENT value. A mutation that changes nothing
    is not a mutation, and that is what made half the mutants invisible."""
    g = json.loads(canon(genome))
    gene = rng.choice(GENES)
    if gene == "head_index":
        g["head_index"] = -1 if g["head_index"] == 0 else 0
    elif gene == "cut_at":
        g["cut_at"] = rng.choice([c for c in CUTS if c != g["cut_at"]])
    else:
        g["rel_head"] = not g["rel_head"]
    g["seed"] = rng.randrange(1 << 30)
    return g


# ------------------------------------------------------------------ material
def _np(rng, flavour):
    """A noun phrase, and the word that is really its head."""
    noun = rng.choice(NOUNS)
    toks = [rng.choice(ARTICLES)]
    mod = rng.choice((None,) + MODS)
    if mod:
        toks.append(mod)
    toks.append(noun)
    if flavour == "plain":
        return toks, noun, None
    if flavour == "prep":
        other = rng.choice([n for n in NOUNS if n != noun])
        return toks + [rng.choice(OF if True else PP), rng.choice(ARTICLES),
                       other], noun, None
    other = rng.choice([n for n in NOUNS if n != noun])
    v2 = rng.choice(VERBS)
    return toks + [rng.choice(ARTICLES), other, v2], noun, v2


def _pairs(comp, seed):
    rng = random.Random(seed)
    genitive = comp.startswith("genitive")
    flavours = ["plain", "plain", "prep", "prep", "prep",
                "rel", "rel", "rel"]
    out = []
    for flavour in flavours:
        verb = rng.choice(VERBS)
        tail = rng.choice(TAILS)
        if flavour == "prep" and not genitive:
            noun = rng.choice(NOUNS)
            toks = [rng.choice(ARTICLES)]
            mod = rng.choice((None,) + MODS)
            if mod:
                toks.append(mod)
            toks.append(noun)
            other = rng.choice([n for n in NOUNS if n != noun])
            np_toks = toks + [rng.choice(PP), rng.choice(ARTICLES), other]
            head = noun
        else:
            np_toks, head, v2 = _np(rng, flavour)
            if v2 is not None and v2 == verb:
                verb = rng.choice([v for v in VERBS if v != v2])
        if comp.endswith("subject"):
            toks = np_toks + [verb] + tail.split()
            shape = {"kind": "subject_unknown", "verb": verb,
                     "tail": tail.split()}
        else:
            toks = ["the", "frost", verb] + np_toks
            shape = {"kind": "object_unknown", "verb": verb,
                     "subject": ["frost"]}
        out.append({"comp": comp, "flavour": flavour, "tokens": toks,
                    "shape": shape, "head": head})
    return out


def build_pairs(seed: int = 0):
    pairs = []
    for i, comp in enumerate(COMPONENTS):
        pairs += _pairs(comp, seed=seed * 10 + i)
    return pairs


def load_pairs(agent=None, n: int = 48):
    """Kept for tools/fly_cost_model.py. The key is the construction, which is
    intrinsic -- it comes from how the sentence was built, not from any ask in
    either suite, so nothing here can be tuned toward the held-out set."""
    return build_pairs(), f"key = construction, {len(COMPONENTS)} components"


# ------------------------------------------------------------------ fitness
def _span(tokens, shape):
    toks = [str(t).strip().lower() for t in tokens if str(t).strip()]
    stems = [stem(t) for t in toks]
    vs = stem(shape["verb"])
    vi = next((i for i, s in enumerate(stems) if s == vs), None)
    if vi is None:
        return None
    return toks[:vi] if shape["kind"] == "subject_unknown" else toks[vi + 1:]


def fly_filler(tokens, shape, genome):
    """What this fly says the head of the span is."""
    span = _span(tokens, shape)
    if span is None:
        return None
    cut = genome.get("cut_at", "none")
    if cut != "none":
        scope = PREPS if cut == "all" else OF
        for i, t in enumerate(span):
            if t in scope:
                span = span[:i]
                break
    fn = frozenset(set(nl.NeuralLanguage.SHAPE_FUNCTION_WORDS)
                   | set(genome.get("extra_function") or ()))
    content = [t for t in span if t not in fn]
    if not content:
        return None
    if genome.get("rel_head"):
        # A relative clause's head is the first noun, i.e. the first content
        # word once leading modifiers and determiners are stripped.
        rest = list(content)
        while rest and rest[0] in MODS:
            rest = rest[1:]
        if rest:
            return rest[0]
    try:
        return content[int(genome.get("head_index", -1))]
    except IndexError:
        return None


def evaluate_components(genome, pairs):
    tot = {c: 0 for c in COMPONENTS}
    hit = {c: 0 for c in COMPONENTS}
    for p in pairs:
        f = fly_filler(p["tokens"], p["shape"], genome)
        tot[p["comp"]] += 1
        if f is not None and f == p["head"]:
            hit[p["comp"]] += 1
    comps = {c: round(hit[c] / tot[c], 6) if tot[c] else 0.0
             for c in COMPONENTS}
    return comps, round(sum(comps.values()) / len(comps), 6)


def fitness_shape_vs_binder(agent, genome, pairs) -> float:
    """Kept for the cost model. The name is historical: the binder key was
    replaced by the construction key after it answered 0/48 (it takes an int
    role and token ids; it was being called with names and strings)."""
    return evaluate_components(genome, pairs)[1]


# ------------------------------------------------------------------ lineage
def rows_for(pop, genomes, pairs, gen=1, parents=None):
    rows = []
    for i, g in enumerate(genomes):
        comps, val = evaluate_components(g, pairs)
        rows.append({"id": f"{pop}-{i}", "pop": pop, "gen": gen,
                     "genome": g, "genome_id": gid(g),
                     "parent": (parents[i] if parents else None),
                     "fitness": val, "components": comps})
    return rows


def trace(rows, row):
    """Resolve a row's ancestry by genome ID. Stops at a founder (parent None)
    or a self-parenting elite. No prose, no recollection."""
    chain = [{"row": row["id"], "genome_id": row["genome_id"],
              "fitness": row["fitness"], "parent": row["parent"]}]
    cur = row
    seen = {row["genome_id"]}
    while cur.get("parent"):
        if cur["parent"] in seen:
            break
        prev = [r for r in rows if r["genome_id"] == cur["parent"]]
        if not prev:
            chain.append({"row": None, "genome_id": cur["parent"],
                          "fitness": None, "parent": None, "founder": True})
            break
        prev = max(prev, key=lambda r: r["gen"])
        chain.append({"row": prev["id"], "genome_id": prev["genome_id"],
                      "fitness": prev["fitness"], "parent": prev["parent"]})
        seen.add(prev["genome_id"])
        cur = prev
    return chain


def _lineage_path(tag):
    return STATE / f"fly_lineage_{tag}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"


def write_lineage(rows, path):
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


# ------------------------------------------------------------------ phases
def phase_control(args):
    rng = random.Random(args.seed)
    base = base_genome(args.seed)
    pairs = build_pairs()
    clones = [json.loads(canon(base)) for _ in range(args.n)]
    a = rows_for("A", clones, pairs)
    muts = [mutate(base, rng) for _ in range(args.n)]
    b = rows_for("B", muts, pairs, parents=[gid(base)] * args.n)

    base_comps, base_val = evaluate_components(base, pairs)
    a_vals = sorted({r["fitness"] for r in a})
    b_vals = sorted({r["fitness"] for r in b})
    differing = sum(1 for r in b if r["fitness"] != base_val)

    print("BASE genome", gid(base), canon(base))
    for c in COMPONENTS:
        print(f"  {c:18s} {base_comps[c]:.6f}")
    print(f"  {'COMPOSITE':18s} {base_val:.6f}   <- breeding gate: must be < 1.0")
    print(f"A null  : 10 clones, zero mutation -> values={a_vals} "
          f"identical_ids={len({r['genome_id'] for r in a}) == 1} "
          f"null_spread={len(a_vals) - 1}")
    print(f"B mutant: 10 mutants, one base     -> values={b_vals} "
          f"mutant_spread={len(b_vals) - 1}")
    print(f"B reach : {differing}/{args.n} mutants differ from base fitness "
          f"({100.0 * differing / args.n:.0f}%)")
    verdict = []
    if len(a_vals) != 1:
        verdict.append("NULL NOT ZERO: fix the harness, evolution cannot start")
    if differing * 10 < args.n * 7:
        verdict.append(f"REACH TOO LOW: {differing}/{args.n} mutants moved")
    if base_val >= 1.0:
        verdict.append("NO HEADROOM: the base already maxes the fitness")
    print("verdict:", "; ".join(verdict) if verdict else
          "control passes: null zero, reach >=70%, headroom present")

    tag = time.strftime("%Y%m%d_%H%M%S")
    p = STATE / f"fly_control_{tag}.json"
    rows = a + b
    p.write_text(json.dumps({"stamp": tag, "base": base, "base_id": gid(base),
                             "base_components": base_comps,
                             "base_composite": base_val,
                             "null_spread": len(a_vals) - 1,
                             "mutant_spread": len(b_vals) - 1,
                             "differing_fraction": round(differing / args.n, 3),
                             "verdict": verdict, "rows": rows},
                            indent=2), encoding="utf-8")
    lp = _lineage_path("control")
    write_lineage(rows, lp)
    print("report:", p)
    print("lineage:", lp)
    return 0


def phase_generations(args):
    rng = random.Random(args.seed + 1)
    pairs = build_pairs()
    base = base_genome(args.seed)
    base_comps, base_val = evaluate_components(base, pairs)
    print(f"base composite {base_val:.6f}")
    pop = [{"genome": json.loads(canon(base)), "parent": None}]
    pop += [{"genome": mutate(base, rng), "parent": gid(base)}
            for _ in range(args.n - 1)]
    allrows, bests = [], []
    for gen in range(1, args.gens + 1):
        rows = rows_for(f"g{gen}", [p["genome"] for p in pop], pairs,
                        gen=gen, parents=[p["parent"] for p in pop])
        allrows += rows
        best = max(rows, key=lambda r: (r["fitness"], r["id"]))
        bests.append({"gen": gen, "best": best["fitness"],
                      "best_row": best["id"], "best_genome_id": best["genome_id"],
                      "distinct": len({r["fitness"] for r in rows}),
                      "components": best["components"]})
        print(f"gen {gen}: best={best['fitness']:.6f} ({best['id']}) "
              f"distinct={bests[-1]['distinct']} n={len(rows)}")
        ranked = sorted(rows, key=lambda r: (-r["fitness"], r["id"]))
        nxt = [{"genome": r["genome"], "parent": r["genome_id"]}
               for r in ranked[:args.elite]]
        while len(nxt) < len(rows):
            win = min(rng.sample(ranked, min(3, len(ranked))),
                      key=lambda r: (-r["fitness"], r["id"]))
            nxt.append({"genome": mutate(win["genome"], rng),
                        "parent": win["genome_id"]})
        assert len(nxt) == len(rows), "population size must hold"
        pop = nxt

    tag = time.strftime("%Y%m%d_%H%M%S")
    lp = _lineage_path("gens")
    write_lineage(allrows, lp)
    p = STATE / f"fly_gens_{tag}.json"
    p.write_text(json.dumps({"stamp": tag, "base_composite": base_val,
                             "bests": bests, "rows": allrows}, indent=2),
                 encoding="utf-8")
    print("report:", p)
    print("lineage:", lp)
    print("\nTRACE -- generation best back to its parent, by genome id:")
    for b in bests:
        row = next(r for r in allrows
                   if r["id"] == b["best_row"] and r["gen"] == b["gen"])
        for step in trace(allrows, row):
            if step.get("founder"):
                print(f"  gen {b['gen']}: {step['genome_id']} = FOUNDER (base)")
            else:
                print(f"  gen {b['gen']}: {step['row']} id={step['genome_id']} "
                      f"fit={step['fitness']:.6f} <- parent={step['parent']}")
    return 0


def phase_trace(args):
    lp = sorted(STATE.glob("fly_lineage_gens_*.jsonl"))[-1]
    rows = [json.loads(l) for l in lp.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print("lineage:", lp, "rows:", len(rows),
          "distinct ids:", len({r["id"] for r in rows}),
          "distinct genome ids:", len({r["genome_id"] for r in rows}))
    for gen in sorted({r["gen"] for r in rows}):
        best = max((r for r in rows if r["gen"] == gen),
                   key=lambda r: (r["fitness"], r["id"]))
        print(f"\ngen {gen} best {best['id']} fit={best['fitness']:.6f}")
        for step in trace(rows, best):
            if step.get("founder"):
                print(f"   -> {step['genome_id']} FOUNDER (base genome)")
            else:
                print(f"   -> {step['row']} id={step['genome_id']} "
                      f"fit={step['fitness']} parent={step['parent']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--phase", default="control",
                    choices=["control", "generations", "trace"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--gens", type=int, default=2)
    ap.add_argument("--elite", type=int, default=2)
    args = ap.parse_args()
    if args.phase == "control":
        return phase_control(args)
    if args.phase == "generations":
        return phase_generations(args)
    return phase_trace(args)


if __name__ == "__main__":
    sys.exit(main())