r"""The additive redesign: continuous gene weights, and one component off the real path.

WHY. The previous surface peaked one mutation from the base (max 0.625 over all
12 genomes = what generation 1 already held), because `cut_at` and `rel_head`
competed for the same decision. Here every gene is a WEIGHT on a feature, all
features are summed into one argmax, so a fly can hold all of them at once --
the decisions are additive by construction, not by luck. Values are continuous,
so the genome space is uncountable and a stall cannot mean "the space was 12".

FIVE COMPONENTS, FOUR SYNTHETIC AND ONE REAL:
  C1-C4  span head on 2 plain / 3 prepositional / 3 relative spans per component
  C5     ARBITER COVERAGE read off the organ's own `_question_shape` and
         `role_for` on deterministic question forms. Not scored against any
         ask's key, never consults the held-out set. The incumbent fails the
         `how many` forms, so the composite's ceiling is below 1.0 and a fly
         cannot max this exam while still failing the real parser.

FEATURES (per content word in the span, all summed, highest wins):
  w_pos    later in the span is better            (base 1.0  -> last word)
  w_prep   its next token is a preposition        (base 0.9  -> below w_pos, so
  w_first  earlier in the span is better           the base still names the last
  w_len    longer words are better                 word and still fails prep/rel)
The base weights sit just below the cliff on w_prep and w_first, so a mutation
usually crosses a boundary and moves a component -- a gene that only matters far
from where the base stands is not a gene (the prep_scope lesson).

  py -3.10 tools/fly_v2.py --phase control --seeds 13 7 17 23 29
  py -3.10 tools/fly_v2.py --phase generations --seeds 13 7 17 23 29 --gens 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
from organs.stemming import stem  # noqa: E402

STATE = ROOT / "state" / "fitness"
AGENT = None          # set by --house: one built house, shared by every fly
ARTICLES = ("the", "a", "some")
MODS = ("old", "copper", "heavy")
NOUNS = ("bell", "lantern", "latch", "crow", "sparrow", "box", "basket", "gate")
VERBS = ("turns", "bites", "holds", "follows", "shines", "keeps", "rings")
OF = ("of",)
PP = ("near", "under", "behind")
PREPS = OF + PP
TAILS = ("twice", "at noon", "again")
COMPONENTS = ("genitive_subject", "pp_subject", "genitive_object", "pp_object")
GENES = ("w_pos", "w_prep", "w_first", "w_len")
QUESTIONS = ("what turns twice?", "what does the frost bite?",
             "who follows the sparrow?", "where is the box kept?",
             "how many times does the bell turn?",
             "how many eggs are left in the basket?")


# ------------------------------------------------------------------ genomes
def base_genome(seed: int = 13) -> dict:
    """The committed rule expressed as weights, sitting just below the cliff on
    the two features that would fix the harder spans."""
    return {"seed": int(seed), "w_pos": 1.0, "w_prep": 0.9,
            "w_first": 0.9, "w_len": 0.0}


def canon(g: dict) -> str:
    return json.dumps(g, sort_keys=True, separators=(",", ":"))


def gid(g: dict) -> str:
    return hashlib.sha256(canon(g).encode("utf-8")).hexdigest()[:12]


def mutate(genome: dict, rng: random.Random) -> dict:
    g = json.loads(canon(genome))
    gene = rng.choice(GENES)
    g[gene] = min(3.0, max(0.0, round(g[gene] + rng.gauss(0.0, 0.6), 6)))
    g["seed"] = rng.randrange(1 << 30)
    return g


# ------------------------------------------------------------------ material
def _span_np(rng, flavour):
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
        prep = rng.choice(OF if True else PP)
        return toks + [prep, rng.choice(ARTICLES), other], noun, None
    other = rng.choice([n for n in NOUNS if n != noun])
    return toks + [rng.choice(ARTICLES), other, rng.choice(VERBS)], noun, None


def _pairs(comp, seed):
    rng = random.Random(seed)
    genitive = comp.startswith("genitive")
    flavours = ["plain", "plain", "prep", "prep", "prep", "rel", "rel", "rel"]
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
            np_toks, head, v2 = _span_np(rng, flavour)
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


# ------------------------------------------------------------------ the rule
def _content(tokens, shape):
    toks = [str(t).strip().lower() for t in tokens if str(t).strip()]
    stems = [stem(t) for t in toks]
    vs = stem(shape["verb"])
    vi = next((i for i, s in enumerate(stems) if s == vs), None)
    if vi is None:
        return None, None
    span = toks[:vi] if shape["kind"] == "subject_unknown" else toks[vi + 1:]
    fn = set(nl.NeuralLanguage.SHAPE_FUNCTION_WORDS) | set(MODS)
    content = [(i, t) for i, t in enumerate(span) if t not in fn]
    return content, span


def fly_head(tokens, shape, genome):
    """Every gene is a weight; every weight is summed; the highest wins. Adding
    a capability never takes another away -- that is what additive means here."""
    content, span = _content(tokens, shape)
    if not content:
        return None
    n = max(1, len(content) - 1)
    best, best_score = None, -1e9
    for rank, (i, word) in enumerate(content):
        nxt = span[i + 1] if i + 1 < len(span) else ""
        score = (genome["w_pos"] * (rank / n)
                 + genome["w_prep"] * (1.0 if nxt in PREPS else 0.0)
                 + genome["w_first"] * (1.0 - rank / n)
                 + genome["w_len"] * min(1.0, len(word) / 6.0))
        if score >= best_score:
            best, best_score = word, score
    return best


def arbiter_coverage():
    """C5: the organ's own parser and role resolution on deterministic question
    forms. The incumbent yields no checkable shape for `how many`, so its score
    is below 1.0 -- and no gene below can lift it, which is the point: the
    composite's ceiling stays out of reach."""
    # A hollow instance answers "no role" for EVERY form, which caps the
    # composite without measuring anything. With a built house the parser and
    # role resolution are the real ones, so the component reads the real path.
    lang = AGENT.language if AGENT is not None else nl.NeuralLanguage.__new__(nl.NeuralLanguage)
    hits = 0
    detail = {}
    for q in QUESTIONS:
        toks = [t for t in q.lower().replace("?", "").split() if t]
        try:
            shape = lang._question_shape(toks)
        except Exception as e:
            shape = None
            detail[q] = f"error:{type(e).__name__}"
        ok = shape is not None
        if ok:
            try:
                role = lang.role_for(toks[0])
                ok = role is not None
            except Exception:
                ok = False
        detail[q] = ("shape+role" if ok else
                     ("no shape" if shape is None else "no role"))
        hits += 1 if ok else 0
    return round(hits / len(QUESTIONS), 6), detail


def evaluate(genome, pairs):
    tot = {c: 0 for c in COMPONENTS}
    hit = {c: 0 for c in COMPONENTS}
    for p in pairs:
        f = fly_head(p["tokens"], p["shape"], genome)
        tot[p["comp"]] += 1
        if f is not None and f == p["head"]:
            hit[p["comp"]] += 1
    comps = {c: round(hit[c] / tot[c], 6) for c in COMPONENTS}
    return comps, round(sum(comps.values()) / len(comps), 6)


def composite(genome, pairs, c5):
    comps, c14 = evaluate(genome, pairs)
    comps["arbiter_coverage"] = c5
    return comps, round((c14 * 4 + c5) / 5, 6)


# ------------------------------------------------------------------ runs
def rows_for(pop, genomes, pairs, c5, gen=1, parents=None):
    out = []
    for i, g in enumerate(genomes):
        comps, val = composite(g, pairs, c5)
        out.append({"id": f"{pop}-{i}", "pop": pop, "gen": gen, "genome": g,
                    "genome_id": gid(g), "parent": parents[i] if parents else None,
                    "fitness": val, "components": comps})
    return out


def phase_control(args):
    pairs = build_pairs()
    base = base_genome(args.seeds[0])
    c5, detail = arbiter_coverage()
    base_comps, base_val = composite(base, pairs, c5)
    print("BASE", gid(base), canon(base))
    for k, v in base_comps.items():
        print(f"  {k:18s} {v:.6f}")
    print(f"  {'COMPOSITE':18s} {base_val:.6f}   <- gate: must be < 1.0")
    print("  C5 detail:", json.dumps(detail))
    for seed in args.seeds:
        rng = random.Random(seed)
        clones = [json.loads(canon(base_genome(seed))) for _ in range(args.n)]
        a = rows_for("A", clones, pairs, c5)
        muts = [mutate(base_genome(seed), rng) for _ in range(args.n)]
        b = rows_for("B", muts, pairs, c5, parents=[gid(base_genome(seed))] * args.n)
        av = sorted({r["fitness"] for r in a})
        bv = sorted({r["fitness"] for r in b})
        _, bval = composite(base_genome(seed), pairs, c5)
        diff = sum(1 for r in b if r["fitness"] != bval)
        print(f"seed {seed:3d}: null {av} (spread {len(av)-1}, "
              f"identical_ids={len({r['id'] for r in a}) and len({r['genome_id'] for r in a})==1}) "
              f"| mutant {len(bv)} distinct spread {len(bv)-1} "
              f"| differing {diff}/{args.n}")
        if len(av) != 1:
            print("  NULL NOT ZERO -- evolution cannot start")
    return 0


def phase_generations(args):
    pairs = build_pairs()
    c5, _ = arbiter_coverage()
    print(f"C5 arbiter coverage {c5:.6f}")
    for seed in args.seeds:
        rng = random.Random(seed + 1)
        base = base_genome(seed)
        _, base_val = composite(base, pairs, c5)
        pop = [{"genome": json.loads(canon(base)), "parent": None}]
        pop += [{"genome": mutate(base, rng), "parent": gid(base)}
                for _ in range(args.n - 1)]
        allrows, bests = [], []
        for gen in range(1, args.gens + 1):
            rows = rows_for(f"g{gen}", [p["genome"] for p in pop], pairs, c5,
                            gen=gen, parents=[p["parent"] for p in pop])
            allrows += rows
            best = max(rows, key=lambda r: (r["fitness"], r["id"]))
            bests.append({"gen": gen, "best": best["fitness"], "row": best["id"],
                          "genome_id": best["genome_id"],
                          "components": best["components"]})
            ranked = sorted(rows, key=lambda r: (-r["fitness"], r["id"]))
            nxt = [{"genome": r["genome"], "parent": r["genome_id"]}
                   for r in ranked[:2]]
            while len(nxt) < len(rows):
                win = min(rng.sample(ranked, min(3, len(ranked))),
                          key=lambda r: (-r["fitness"], r["id"]))
                nxt.append({"genome": mutate(win["genome"], rng),
                            "parent": win["genome_id"]})
            pop = nxt
        b = [x["best"] for x in bests]
        improved = (b[1] > b[0]) or (b[2] > b[0])
        print(f"seed {seed:3d}: base {base_val:.5f} -> "
              f"{' '.join(f'{x:.5f}' for x in b)}  {'IMPROVED' if improved else 'stalled'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--phase", default="control",
                    choices=["control", "generations"])
    ap.add_argument("--seeds", nargs="*", type=int, default=[13, 7, 17, 23, 29])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--gens", type=int, default=3)
    ap.add_argument("--house", action="store_true",
                    help="build one real house so C5 reads the real parser")
    args = ap.parse_args()
    global AGENT
    if args.house:
        import shutil
        from tools.converse import build
        d = STATE / "sessions" / f"flyv2_{time.strftime('%Y%m%d_%H%M%S')}"
        try:
            AGENT = build(d)
            print("house built for C5")
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return phase_control(args) if args.phase == "control" else phase_generations(args)


if __name__ == "__main__":
    sys.exit(main())