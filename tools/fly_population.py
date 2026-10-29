r"""A breeding population of Droso brains: shared substrate, per-fly genome.

PROCESS MODEL (stated, because the measured RAM forces it).  One immutable
substrate -- the built house: corpus, band, embeddings, weights -- is loaded
ONCE per process and is shared read-only by every fly.  Flies run SERIALLY IN
PROCESS against that one substrate; a fly is a genome plus its own mutable layer
(a dict of deltas and knobs), never a second house.  Windows has no fork(), so
copy-on-write between processes is not available here, and the cost model
(tools/fly_cost_model.py) measures what a second loaded house would actually
cost.  Nothing in this file rebuilds from corpus, and nothing writes into the
shared substrate: the mutable layer is applied to a scratch copy of only the
array a knob touches, and that copy is freed before the next fly.

  A genome is seeded and deterministic: the same seed always names the same
  brain, and the canonical JSON of a genome is its identity.
  A fly never touches main's answer path: the shape policy is evaluated here,
  over pairs, and the shared organ is read-only.
  Saving and forking a fly is the eight-file surface already proved
  restart-identical, or smaller: a genome is one JSON line.

  py -3.10 tools/fly_population.py --phase control        (null vs mutant)
  py -3.10 tools/fly_population.py --phase generations --gens 3

FITNESS.  Cheap, intrinsic, deterministic, seconds not minutes: does the fly's
head rule name the same word the independent organ -- the cortex binder --
unbinds for that role.  The 24-ask held-out set is NEVER the selection
pressure; it is scored once afterward as an outside check and labelled as one.
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

# ------------------------------------------------------------------ genomes
ARTICLES = ("the", "a", "some", "two", "old", "copper", "heavy", "red")
NOUNS = ("bell", "lantern", "latch", "crow", "sparrow", "box", "basket", "gate")
VERBS = ("turns", "bites", "holds", "follows", "shines", "keeps", "rings")
TAILS = ("twice", "at noon", "in the pantry", "on the shelf", "again")

# A fly may only choose among these; none of them is a threshold moved toward
# an answer key -- they are positions in a span and membership of a closed
# function-word class.
HEAD_CHOICES = (0, -1, -2)
EXTRA_FUNCTION = ("twice", "again", "some", "old")


def base_genome(seed: int) -> dict:
    """The genome every population descends from: the committed rule."""
    return {"seed": int(seed), "head_index": -1, "extra_function": [],
            "stem_verb": True}


def canon(genome: dict) -> str:
    return json.dumps(genome, sort_keys=True, separators=(",", ":"))


def gid(genome: dict) -> str:
    return hashlib.sha256(canon(genome).encode("utf-8")).hexdigest()[:12]


def mutate(genome: dict, rng: random.Random) -> dict:
    """One fly's worth of change: a gene is picked by the rng, not by luck of
    dict order, so the same seed replays the same brain exactly."""
    g = json.loads(canon(genome))
    which = rng.randrange(3)
    if which == 0:
        g["head_index"] = rng.choice(HEAD_CHOICES)
    elif which == 1:
        pool = [w for w in EXTRA_FUNCTION if w not in g["extra_function"]]
        if pool:
            g["extra_function"] = sorted(g["extra_function"] + [rng.choice(pool)])
        else:
            g["extra_function"] = []
    else:
        g["stem_verb"] = not g["stem_verb"]
    g["seed"] = rng.randrange(1 << 30)
    return g


# ------------------------------------------------------------------ pairs
def synth_pairs(n: int = 48, seed: int = 7):
    """Propositions with a subject-unknown shape and the head the sentence
    itself puts in the answer slot.  Built from a closed word pool, so a fly
    can never be scored on held-out material it was tuned toward."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        mod = rng.choice([(), ("copper",), ("heavy",), ("old", "copper")])
        art = rng.choice(("the", "a", "some"))
        noun = rng.choice(NOUNS)
        verb = rng.choice(VERBS)
        tail = rng.choice(TAILS)
        toks = [art, *mod, noun, verb, *tail.split()]
        head = noun
        out.append({"tokens": toks, "head": head,
                    "shape": {"kind": "subject_unknown", "verb": verb,
                              "tail": tail.split()}})
    return out


_BINDER_ERR = [None]


def binder_key(agent, tokens):
    """What the OTHER organ says, or None.  The binder is the independent half
    of the fitness; if it cannot answer these pairs the fitness degrades to a
    structural agreement and says so -- it does not silently change meaning."""
    try:
        L = agent.language
        b = L.cortex.binder
        # role_of takes an INTEGER role (neural_language.py:2726
        # `role = self.role_for(inter[0])`) and a TOKEN LIST, not a string and
        # not a role name. Passing "agent" raised inside the binder and my
        # except swallowed it, which is how 0/48 pairs looked like a silent
        # binder instead of a broken call.
        role = L.role_for("what")
        if role is None:
            _BINDER_ERR[0] = "role_for('what') returned None"
            return None
        got = b.role_of(list(tokens), int(role), b.candidates())
        if isinstance(got, dict) and got.get("answer"):
            return str(got["answer"]).strip().lower()
        _BINDER_ERR[0] = f"no answer (score={got.get('score') if isinstance(got, dict) else got})"
    except Exception as e:
        _BINDER_ERR[0] = f"{type(e).__name__}: {e}"
    return None


def load_pairs(agent, n: int = 48):
    pairs = synth_pairs(n=n)
    keyed = 0
    for p in pairs:
        k = binder_key(agent, p["tokens"])
        p["key"] = k
        keyed += 1 if k else 0
    mode = "binder" if keyed >= max(2, n // 5) else "structural"
    note = (f"{keyed}/{n} pairs answered by the cortex binder; "
            f"fitness key = {mode}")
    return pairs, note


# ------------------------------------------------------------------ fitness
def fly_function_words(genome: dict):
    return frozenset(set(nl.NeuralLanguage.SHAPE_FUNCTION_WORDS)
                     | set(genome["extra_function"]))


def fly_filler(tokens, shape, genome):
    """The fly's own head rule, applied to the span the arbiter would fill.
    Mirrors _shape_matches' subject branch; the genome chooses which word of
    the span the fly believes is the head."""
    fn = fly_function_words(genome)
    toks = [str(t).strip().lower() for t in tokens if str(t).strip()]
    vs = stem(shape["verb"]) if genome["stem_verb"] else shape["verb"].lower()
    stems = [stem(t) for t in toks]
    vi = next((i for i, s in enumerate(stems) if s == vs), None)
    if vi is None:
        return None
    before = [t for t in toks[:vi] if t not in fn]
    if not before:
        return None
    try:
        return before[genome["head_index"]]
    except IndexError:
        return None


def fitness_shape_vs_binder(agent, genome, pairs) -> float:
    """Fraction of pairs where the fly names the word the key organ names.
    Deterministic: no clock, no rng, no live state, no shared-array writes."""
    hits = tot = 0
    for p in pairs:
        key = p["key"] or p["head"]
        f = fly_filler(p["tokens"], p["shape"], genome)
        if f is None:
            continue
        tot += 1
        hits += 1 if f == key else 0
    return round(hits / tot, 6) if tot else 0.0


# ------------------------------------------------------------------ lineage
def write_lineage(rows, path: Path):
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def spawn(base, n, rng):
    """Population B: n mutants from one base, same seed, mutation only."""
    return [mutate(base, rng) for _ in range(n)]


def evaluate(agent, genomes, pairs, gen=1, parent=None):
    rows = []
    for i, g in enumerate(genomes):
        rows.append({"id": f"g{gen}-{i}", "gen": gen,
                     "parent": parent if gen == 1 else (parent or "base"),
                     "genome": g, "genome_id": gid(g),
                     "fitness": fitness_shape_vs_binder(agent, g, pairs)})
    return rows


def select(rows, rng, elite=2, k=3):
    """Elitism plus tournament. The best `elite` survive unmutated; the rest of
    the next generation are drawn by tournament among survivors; losers are
    discarded, not kept as history."""
    ranked = sorted(rows, key=lambda r: (-r["fitness"], r["genome_id"]))
    keep = [r["genome"] for r in ranked[:elite]]
    while len(keep) < len(rows):
        contest = rng.sample(ranked, min(k, len(ranked)))
        win = min(contest, key=lambda r: (-r["fitness"], r["genome_id"]))
        keep.append(win["genome"])
    return [{"genome": g, "parent": None} for g in keep]


# ------------------------------------------------------------------ phases
def phase_control(agent, args, note):
    rng = random.Random(args.seed)
    base = base_genome(args.seed)
    clones = [json.loads(canon(base)) for _ in range(args.n)]
    a_rows = evaluate(agent, clones, None, gen=1)
    mutants = spawn(base, args.n, rng)
    b_rows = evaluate(agent, mutants, None, gen=1)

    def spread(rows):
        vals = sorted({r["fitness"] for r in rows})
        return vals

    a_vals, b_vals = spread(a_rows), spread(b_rows)
    a_ident = len({r["genome_id"] for r in a_rows}) == 1 and len(a_vals) == 1
    print(f"population A (null, {args.n} clones, zero mutation): "
          f"values={a_vals} identical={a_ident}")
    print(f"population B (mutant, {args.n} from one base):        "
          f"values={b_vals} distinct={len(b_vals)}")
    print(f"null spread={len(a_vals)-1}  mutant spread={len(b_vals)-1}")
    verdict = ("EVOLUTION MAY START" if (a_ident and len(b_vals) > len(a_vals))
               else "AXIS CLOSES: no heritable variance above the null")
    print("verdict:", verdict)
    out = {"stamp": time.strftime("%Y-%m-%d %H:%M:%S"), "n": args.n,
           "seed": args.seed, "base": base, "base_id": gid(base),
           "fitness_key_note": note,
           "A_null": a_rows, "B_mutant": b_rows,
           "null_spread": len(a_vals) - 1, "mutant_spread": len(b_vals) - 1,
           "clones_identical": a_ident, "verdict": verdict}
    p = STATE / f"fly_control_{time.strftime('%Y%m%d_%H%M%S')}.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    write_lineage(a_rows + b_rows,
                  STATE / f"fly_lineage_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
    print("report:", p)
    return out


def phase_generations(agent, args, note):
    rng = random.Random(args.seed + 1)
    pairs, _ = load_pairs(agent)
    pop = [base_genome(args.seed)] + spawn(base_genome(args.seed), args.n - 1, rng)
    bests = []
    rows = None
    for gen in range(1, args.gens + 1):
        rows = evaluate(agent, pop, pairs, gen=gen, parent=gid(base_genome(args.seed)))
        best = max(r["fitness"] for r in rows)
        bests.append({"gen": gen, "best": best,
                      "distinct": len({r["fitness"] for r in rows})})
        print(f"gen {gen}: best={best:.4f} distinct={bests[-1]['distinct']} "
              f"n={len(rows)}")
        parents = select(rows, rng, elite=args.elite)
        pop = [p["genome"] for p in parents] + \
              [mutate(rng.choice(parents)["genome"], rng)
               for _ in range(args.n - args.elite)]
    p = STATE / f"fly_gens_{time.strftime('%Y%m%d_%H%M%S')}.json"
    p.write_text(json.dumps({"seed": args.seed, "note": note,
                             "bests": bests}, indent=2), encoding="utf-8")
    print("report:", p)
    return bests


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--phase", default="control",
                    choices=["control", "generations"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--gens", type=int, default=3)
    ap.add_argument("--elite", type=int, default=2)
    ap.add_argument("--house", action="store_true",
                    help="load the real substrate so the binder can be the key")
    args = ap.parse_args()

    agent = None
    if args.house:
        from tools.converse import build
        d = ROOT / "state" / "sessions" / f"flypop_{time.strftime('%Y%m%d_%H%M%S')}"
        try:
            agent = build(d)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
    pairs, note = load_pairs(agent) if agent else (synth_pairs(), "no house")
    print("fitness key:", note)
    if _BINDER_ERR[0]:
        print("binder said:", _BINDER_ERR[0])

    # evaluate() needs the pairs bound once, so a fly never rebuilds anything.
    # Capture the real function BEFORE shadowing the module name: the first cut
    # of this assigned evaluate_b into globals()['evaluate'], and evaluate_b
    # then resolved `evaluate` to itself -- 995 frames of recursion.
    _orig = evaluate

    def evaluate_b(agent, genomes, _ignored, gen=1, parent=None):
        return _orig(agent, genomes, pairs, gen=gen, parent=parent)
    globals()["evaluate"] = evaluate_b

    if args.phase == "control":
        phase_control(agent, args, note)
    else:
        phase_generations(agent, args, note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
