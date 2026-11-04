"""MP-E10 checklist step 2: BOTH native routing variants, flag-gated, neither one chosen.

D-MPE10-03 asks the PI to confirm which variant is primary. It is still open, and this file does not answer
it. What it does is build both and measure both, because building two variants is not selecting one and the
plan already registered the case where the choice would otherwise be made by a result: C5 says a variant
that wins only while the other is disabled is recorded as an ABLATION RESULT, not as a win. The gate's own
failure branch says the routing ablation data decides the next attempt -- so the data has to exist before
the PI's choice is informed rather than after it is manufactured.

THE TWO VARIANTS, IN THE ENGINE'S OWN TERMS. `connectome/engine.py:decide` already takes two parameters,
and each variant is a way of filling one of them:
  variant_i   -> `extra_drive`: amplitude pairs from the spread of the decayed state, i.e. the target organ
                 injecting alongside the words ("how a scent, a body state or a voice enters ... through the
                 fly's own wiring rather than around it", engine.py's own words).
  variant_ii  -> `allowed_pools`: a subset mask over the MBON pools, derived from which pools the trace
                 currently resonates with. This is the reasoning loop's existing legality structure.
Neither variant invents a mechanism. Both are reads of the working-memory state through a parameter the
carve already accepts, which is what the registration means by "native".

WHAT THIS FILE IS NOT. It does not boot the house, does not call the carve, and does not touch
`speak_sentence`. The selection rules here run on the same labelled stand-in geometry the k-sweep used, so
what they measure is the two rules' behaviour on a candidate set, not the fly's decisions. The house-side
wiring is a separate step, recorded as named-missing in the registration, because it edits a live organ and
that deserves its own design step rather than a quiet import.

THE FLAG. MP_E10_ROUTING=off|variant_i|variant_ii|both, default `off`, which leaves the legacy unigram path
runnable for comparison exactly as the registration's ablation list requires. `off` is not a neutral setting:
it is the third condition of the ablation.
"""
from __future__ import annotations

import json, os, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e10_working_memory import DecayedTrace, unigram_context

N_POOLS = 12                      # the MBON pool count engine.decide's `allowed` argument restricts over
FLAG_ENV = "MP_E10_ROUTING"
VARIANTS = ("off", "variant_i", "variant_ii", "both")
DEFAULT_K = 8                     # the registered sweep's mid-grid; a routing run may pass any k
POOL_FLOOR = 3                    # variant_ii keeps at least this many pools legal, or it is a veto


def routing_flag(override: str | None = None) -> str:
    v = (override if override is not None else os.environ.get(FLAG_ENV, "off")).strip().lower()
    if v not in VARIANTS:
        raise ValueError(f"{FLAG_ENV}={v!r} is not one of {VARIANTS}")
    return v


def project(word: str, dim: int = 64) -> np.ndarray:
    """The same deterministic hash projection the k-sweep used -- a stand-in, and labelled as one here too."""
    rng = np.random.default_rng(abs(hash(("mp-e10-routing", word))) % (2 ** 32))
    return rng.standard_normal(dim).astype(np.float32)


def pool_vector(pool_index: int, dim: int = 64) -> np.ndarray:
    rng = np.random.default_rng(1000 + pool_index)
    return rng.standard_normal(dim).astype(np.float32)


# ------------------------------------------------------------------ the two variants
def variant_i_drive(trace: DecayedTrace, pool_vecs: list[np.ndarray] | None = None) -> list[tuple[int, float]]:
    """extra_drive pairs: spread of the decayed state, normalised, one amplitude per pool.

    'Spread' is what the registration's own word for it: the trace state's alignment with each pool, put on
    a common scale and floored so a pool the state has nothing to do with is not injected at a small
    positive amplitude that a reader would take for a weak preference. It is a drive, not a veto: every pool
    stays legal.
    """
    pool_vecs = pool_vecs or [pool_vector(i) for i in range(N_POOLS)]
    s = trace.state()
    raw = np.array([float(np.dot(s, p) / (np.linalg.norm(s) * np.linalg.norm(p) + 1e-12)) for p in pool_vecs])
    spread = raw - raw.mean()
    scale = float(np.abs(spread).max()) or 1.0
    drive = (spread / scale) * np.maximum(trace.weights()[-1], 1e-6)   # a fresh token's amplitude bounds it
    return [(i, round(float(a), 6)) for i, a in enumerate(drive) if abs(a) > 1e-9]


def variant_ii_mask(trace: DecayedTrace, pool_vecs: list[np.ndarray] | None = None,
                    keep: int = POOL_FLOOR) -> list[int]:
    """allowed_pools: the pools the trace currently resonates with; the rest are illegal this step.

    A mask is a different kind of claim from a drive -- it removes options rather than weighting them -- so
    it is floored at `keep` pools. Without the floor a near-empty state would leave one legal pool and the
    carve would have a decision with no alternatives, which is not a routing result but an absence of one.
    """
    pool_vecs = pool_vecs or [pool_vector(i) for i in range(N_POOLS)]
    s = trace.state()
    raw = np.array([float(np.dot(s, p) / (np.linalg.norm(s) * np.linalg.norm(p) + 1e-12)) for p in pool_vecs])
    order = list(np.argsort(-raw))
    return sorted(int(i) for i in order[:max(keep, 1)])


def score_candidates(cands: list[str], trace: DecayedTrace, *, flag: str,
                     pool_vecs: list[np.ndarray] | None = None,
                     candidate_pools: list[int] | None = None,
                     context_vecs: list[np.ndarray] | None = None) -> dict:
    """Rank candidates under the given flag. `off` is the legacy unigram path, kept runnable.

    `off` scores against the unigram context OF THE SEQUENCE, not of the candidate list -- scoring
    candidates against their own mean would be circular and would flatter the baseline. This is the thing
    step 2 exists to replace ("replace unigram context with a native, contextual sequence organ"), so it is
    the comparison arm by definition rather than by choice.
    """
    pool_vecs = pool_vecs or [pool_vector(i) for i in range(N_POOLS)]
    cand_vecs = [project(c) for c in cands]
    if flag == "off":
        ctx = unigram_context(context_vecs) if context_vecs else trace.state()
        scores = [float(np.dot(ctx, v)) for v in cand_vecs]
        legal = list(range(len(cands)))
        mechanism = "legacy unigram context over the sequence (kept runnable for comparison)"
    else:
        drive = variant_i_drive(trace, pool_vecs) if flag in ("variant_i", "both") else []
        mask = variant_ii_mask(trace, pool_vecs) if flag in ("variant_ii", "both") else None
        dmap = dict(drive)
        cand_pools = candidate_pools or [i % N_POOLS for i in range(len(cands))]
        scores, legal = [], []
        for i, (v, cp) in enumerate(zip(cand_vecs, cand_pools)):
            if mask is not None and cp not in mask:
                scores.append(float("-inf")); continue            # illegal: not suppressed, excluded
            base = float(np.dot(trace.state(), v))
            if drive:
                base += dmap.get(cp, 0.0)                          # injection acts through the pool it sits in
            scores.append(base); legal.append(i)
        mechanism = ("extra_drive from trace spread" if flag == "variant_i" else
                     "allowed_pools mask from trace resonance" if flag == "variant_ii" else
                     "both: drive AND mask (the C5 condition)")
    ranked = sorted(range(len(cands)), key=lambda i: (-scores[i] if scores[i] != float("-inf") else 1, i))
    return {"flag": flag, "mechanism": mechanism,
            "ranking": [cands[i] for i in ranked if scores[i] != float("-inf")],
            "excluded": [cands[i] for i in range(len(cands)) if scores[i] == float("-inf")],
            "scores": {cands[i]: (None if scores[i] == float("-inf") else round(scores[i], 6))
                       for i in range(len(cands))},
            "pools_legal": (len(legal)), "n_candidates": len(cands)}


# ------------------------------------------------------------------ the ablation
def ablation(sequence: list[str], cands: list[str], *, k: int = DEFAULT_K,
             candidate_pools: list[int] | None = None) -> dict:
    """Run all four flags over one sequence. No flag is privileged and none is dropped.

    'both' is the condition C5 is about: if a variant wins only while the other is excluded, that is an
    ablation result and the artifact says so in the same object that reports the winner.
    """
    trace = DecayedTrace(k=k, dim=64)
    seq_vecs = [project(w) for w in sequence]
    for v in seq_vecs:
        trace.push(v)
    rows = {flag: score_candidates(cands, trace, flag=flag, candidate_pools=candidate_pools,
                                   context_vecs=seq_vecs)
            for flag in VARIANTS}
    winners = {f: (rows[f]["ranking"][0] if rows[f]["ranking"] else None) for f in VARIANTS}
    agree = len(set(v for v in winners.values() if v is not None)) == 1
    c5 = {
        "condition": "a variant wins only with the other disabled",
        "i_wins_only_against_off": winners["variant_i"] == winners["off"] and winners["variant_i"] != winners["variant_ii"],
        "ii_wins_only_against_off": winners["variant_ii"] == winners["off"] and winners["variant_ii"] != winners["variant_i"],
        "variants_disagree": winners["variant_i"] != winners["variant_ii"],
        "both_flag_winner_matches_primary_alone": winners["both"] == winners["variant_ii"],
        "verdict_if_any_of_these_is_true": "record as an ABLATION RESULT, not a win (C5)",
    }
    return {"sequence": sequence, "k": k, "candidates": cands,
            "candidate_pools": list(candidate_pools or [i % N_POOLS for i in range(len(cands))]),
            "per_flag": rows, "winners": winners, "all_flags_agree": agree,
            "c5_ablation_test": c5,
            "trace_fingerprint_after_run": trace.fingerprint()}


# A GEOMETRY PROBE, not a language battery: a fixed alphabet and fixed sequences, so the two selection rules
# are compared on identical input and a reader can re-run the whole thing from this file. Naming words here
# would borrow meaning the measurement does not have.
ALPHABET = [f"w{i:02d}" for i in range(12)]
PROBE_BATTERY = [("w00",), ("w01", "w02"), ("w00", "w00", "w05"),
                 ("w03", "w07", "w11", "w02"), ("w06",) * 5,
                 tuple(ALPHABET[:8])]


def run_battery(k: int = DEFAULT_K) -> dict:
    probes = [{"probe": list(seq), "result": ablation(list(seq), ALPHABET, k=k)}
              for seq in PROBE_BATTERY]
    disagree = [p["probe"] for p in probes if p["result"]["winners"]["variant_i"]
                != p["result"]["winners"]["variant_ii"]]
    c5_hits = [p["probe"] for p in probes
               if p["result"]["c5_ablation_test"]["i_wins_only_against_off"]
               or p["result"]["c5_ablation_test"]["ii_wins_only_against_off"]]
    return {"schema": "mp_e10.routing_ablation.v1", "k": k, "n_probes": len(probes),
            "flags_run": list(VARIANTS), "probes": probes,
            "summary": {
                "probes_where_variants_disagree_on_the_winner": len(disagree),
                "probes_where_a_variant_won_only_against_off": len(c5_hits),
                "probes_where_all_four_flags_agree": sum(1 for p in probes
                                                        if p["result"]["all_flags_agree"])},
            "quoting_guard": {
                "meaning": "This is an instrument-level ablation of two selection rules over a labelled "
                           "stand-in geometry. It is not a scored MP-E10 run, not an H1 or H2 figure, and not "
                           "a decision about which variant is primary. No verdict sentence about G3 may quote "
                           "it while D-MPE10-02 and D-MPE10-03 remain open.",
                "what_it_does_measure": "that both registered variants exist, are flag-gated, run over the "
                                        "same input, and differ or agree in the ways C5 asks about",
                "what_it_does_not_measure": "anything about the live carve, the house's pools, spoken output, "
                                            "retention or the guard batteries -- the house-side wiring is a "
                                            "separate step (named-missing in the registration)",
                "rule_source": "experiments/MP-E10/registration.json"}}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    art = run_battery(k=a.k)
    if a.out:
        p = Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    s = art["summary"]
    print(f"k={art['k']} probes={art['n_probes']} flags={art['flags_run']}")
    print(f"  variants disagree on winner: {s['probes_where_variants_disagree_on_the_winner']}"
          f" | a variant won only against off: {s['probes_where_a_variant_won_only_against_off']}"
          f" | all four agree: {s['probes_where_all_four_flags_agree']}")
    print(f"wrote {a.out or '(not written)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
