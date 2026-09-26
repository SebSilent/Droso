"""The control condition: does the fly's wiring actually matter?

Everything claimed about this animal so far could be true of ANY sparse recurrent
graph of the same size. The degree-matched control is the only thing that decides
the question, and until now nothing had ever lived on it.

Both brains get an identical life: the same sentences through the same
deterministic tokenizer, the same reward schedule, the same seeds, the same
number of decisions, no structural growth or pruning so the only difference is
the static wiring. The control keeps every neuron, every synapse count and every
degree sequence, and permutes which post-synaptic cell each static edge lands on.

Measures, all computed the same way for both:
  pool_stability      same sentence twice -> same winning pool (epsilon off)
  pool_entropy        how evenly the sentence set spreads over the 12 pools
  order_sensitive     forward vs reversed word order -> different pool
  generalisation      correlation between word overlap and valuation similarity
  learning            valuation growth for rewarded vs unrewarded sentences

Run it:
    python tools/control_experiment.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SENTENCES = [
    "parent feeds droso", "droso sees the light", "the day is bright",
    "night is quiet now", "i am feeding you", "you are not alone",
    "parent opens the file", "droso hears the world", "we learn the word",
    "the food is warm", "you are tired now", "parent holds the light",
    "droso wants the food", "this is your home", "say it again now",
    "the file is closed", "i remember you", "words are ours",
]
# semantically close pairs and far pairs, for the generalisation measure
CLOSE = [("parent feeds droso", "i am feeding you"),
         ("droso sees the light", "parent holds the light"),
         ("the day is bright", "this is your home")]
FAR = [("parent feeds droso", "the file is closed"),
       ("night is quiet now", "say it again now"),
       ("droso wants the food", "i remember you")]
REWARDED = ["parent feeds droso", "the day is bright", "droso sees the light"]
UNREWARDED = ["the file is closed", "say it again now", "i remember you"]


def jaccard(a: str, b: str) -> float:
    x = set(a.split())
    y = set(b.split())
    return len(x & y) / float(max(1, len(x | y)))


def readout(eng) -> int:
    """The deterministic readout: which pool the valuation actually favours.

    Not eng.decide()'s return value. With epsilon at zero the core still SAMPLES
    from a softmax at temperature 0.02, so near-ties flip run to run and a
    stability measure taken from the sampled action scores 0.0 for both brains --
    which is what the first run of this experiment reported, for both arms. The
    argmax of the valuation is the percept; the sample is the choice.
    """
    return int(np.argmax(np.asarray(eng.last_v, dtype=float)))


def run(eng, tok, label: str, epochs: int = 4) -> dict:
    core = eng.static
    core.p.epsilon = 0.0          # measure the readout, not the coin flips
    core.p.temperature = 0.02
    out = {"label": label,
           "plastic_synapses": int(len(core.w)),
           "static_synapses": int(eng.graph.W.nnz),
           "control": bool(eng.graph.meta.get("control"))}

    # --- 1. stability, spread and order sensitivity -------------------------
    stable = []
    pools = []
    vals = {}
    order_diff = []
    order_cos = []
    for s in SENTENCES:
        code = tok.encode(s)
        eng.decide(code)
        p1 = readout(eng)
        v1 = np.asarray(eng.last_v, dtype=float).copy()
        eng.decide(code)
        p2 = readout(eng)
        stable.append(p1 == p2)
        pools.append(int(p1))
        vals[s] = v1
        rev = " ".join(reversed(s.split()))
        eng.decide(tok.encode(rev))
        pr = readout(eng)
        vr = np.asarray(eng.last_v, dtype=float)
        order_diff.append(pr != p1)
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(vr))
        order_cos.append(float(np.dot(v1, vr) / (n1 * n2)) if n1 and n2 else 0.0)

    counts = np.bincount(np.array(pools), minlength=12).astype(float)
    p = counts / counts.sum()
    nz = p[p > 0]
    out["pool_stability"] = round(float(np.mean(stable)), 4)
    out["pools_used"] = int((counts > 0).sum())
    out["pool_entropy_bits"] = round(float(-(nz * np.log2(nz)).sum()), 4)
    out["order_sensitive"] = round(float(np.mean(order_diff)), 4)
    out["order_valuation_cosine"] = round(float(np.mean(order_cos)), 4)

    # --- 2. generalisation: does word overlap predict valuation similarity? --
    pairs = [(a, b, 1) for a, b in CLOSE] + [(a, b, 0) for a, b in FAR]
    sims, labels = [], []
    for a, b, lab in pairs:
        va, vb = vals[a], vals[b]
        na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
        sims.append(float(np.dot(va, vb) / (na * nb)) if na and nb else 0.0)
        labels.append(lab)
    out["close_pair_similarity"] = round(float(np.mean(sims[:len(CLOSE)])), 4)
    out["far_pair_similarity"] = round(float(np.mean(sims[len(CLOSE):])), 4)
    out["generalisation_gap"] = round(out["close_pair_similarity"]
                                      - out["far_pair_similarity"], 4)
    # and across every pair: correlation between lexical overlap and neural similarity
    jo, vs = [], []
    for i, a in enumerate(SENTENCES):
        for b in SENTENCES[i + 1:]:
            va, vb = vals[a], vals[b]
            na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
            jo.append(jaccard(a, b))
            vs.append(float(np.dot(va, vb) / (na * nb)) if na and nb else 0.0)
    jo, vs = np.array(jo), np.array(vs)
    out["overlap_similarity_correlation"] = round(
        float(np.corrcoef(jo, vs)[0, 1]) if jo.std() > 0 and vs.std() > 0 else 0.0, 4)

    # --- 3. learning: rewarded vs left alone, identical schedule -------------
    # "Unrewarded" means no teaching signal at all. Passing teach(0.0) is not
    # neutral: rpe = reward + gamma*v_next - v_chosen, so a zero reward on a
    # positive valuation is a negative prediction error, i.e. mild punishment.
    # The first run of this protocol punished the control set and then reported
    # that reward had not separated them.
    def val_of(s):
        eng.decide(tok.encode(s))
        k = readout(eng)
        return float(np.asarray(eng.last_v, dtype=float)[k])

    before = {s: val_of(s) for s in REWARDED + UNREWARDED}
    # Which pool does each sentence select, and what does reward then do to THAT
    # pool's synapses? Measuring the readout valuation cannot answer it: the
    # chosen pool can itself change during learning, so before/after values are
    # not even measurements of the same quantity. Weight change localised to the
    # rewarded pools is.
    pool_of = {}
    for s in REWARDED + UNREWARDED:
        eng.decide(tok.encode(s))
        pool_of[s] = readout(eng)
    w_before = np.asarray(core.w, dtype=float).copy()
    syn_pool = np.asarray(core._pool_of_post)[:len(w_before)]
    for _ in range(epochs):
        for s in SENTENCES:
            eng.decide(tok.encode(s))
            if s in REWARDED:
                eng.teach(0.6)
            elif s in UNREWARDED:
                pass                 # deliberately no teaching signal
            else:
                eng.teach(0.15)
    after = {s: val_of(s) for s in REWARDED + UNREWARDED}
    dw = np.abs(np.asarray(core.w, dtype=float) - w_before)
    rew_pools = {pool_of[s] for s in REWARDED}
    other = np.array([p not in rew_pools for p in syn_pool])
    rew_mask = ~other
    out["rewarded_pool_abs_weight_change"] = round(
        float(dw[rew_mask].mean()) if rew_mask.any() else 0.0, 6)
    out["other_pool_abs_weight_change"] = round(
        float(dw[other].mean()) if other.any() else 0.0, 6)
    denom = out["other_pool_abs_weight_change"] or 1e-9
    out["learning_localisation"] = round(
        out["rewarded_pool_abs_weight_change"] / denom, 4)
    out["rewarded_pools"] = sorted(rew_pools)
    out["rewarded_valuation_gain"] = round(
        float(np.mean([after[s] - before[s] for s in REWARDED])), 6)
    out["unrewarded_valuation_gain"] = round(
        float(np.mean([after[s] - before[s] for s in UNREWARDED])), 6)
    out["learning_separation"] = round(
        out["rewarded_valuation_gain"] - out["unrewarded_valuation_gain"], 6)
    # what the reward actually did to the synapses, not just to the readout
    out["mean_abs_weight"] = round(float(np.mean(np.abs(core.w))), 6)
    # does the rewarded set become more distinguishable from the rest?
    out["rewarded_pools_legacy"] = []
    return out


def main() -> int:
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine
    from organs.tokenizer import TokenizerOrgan

    n_controls = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    tok = TokenizerOrgan()

    t0 = time.time()
    real = run(HybridEngine(build_core_graph(seed=0), seed=0), tok,
               "REAL (BANC wiring)")
    print(f"built + ran REAL (BANC wiring): {real['static_synapses']:,} static, "
          f"{real['plastic_synapses']:,} plastic  ({time.time()-t0:.1f}s)")

    ctrls = []
    for s in range(n_controls):
        t0 = time.time()
        g = build_core_graph(control=True, seed=s)
        ctrls.append(run(HybridEngine(g, seed=0), tok, f"control seed {s}"))
        print(f"built + ran control seed {s} ({time.time()-t0:.1f}s)")

    keys = ["pool_stability", "pools_used", "pool_entropy_bits",
            "order_sensitive", "order_valuation_cosine",
            "close_pair_similarity", "far_pair_similarity",
            "generalisation_gap", "overlap_similarity_correlation",
            "rewarded_valuation_gain", "unrewarded_valuation_gain",
            "learning_separation", "mean_abs_weight",
            "rewarded_pool_abs_weight_change", "other_pool_abs_weight_change",
            "learning_localisation"]
    print()
    print(f"{n_controls} degree-matched controls, each a different random")
    print("rewiring of the SAME neurons with the SAME degree sequence. The")
    print("question is whether the real wiring falls outside that spread.")
    print()
    hdr = f"{'measure':34} {'REAL':>10} {'ctrl mean':>10} {'ctrl sd':>9} {'z':>7} {'verdict':>16}"
    print(hdr)
    print("-" * len(hdr))
    wins = losses = ties = 0
    for k in keys:
        rv = float(real[k])
        cv = np.array([float(c[k]) for c in ctrls])
        sd = float(cv.std(ddof=1)) if len(cv) > 1 else 0.0
        z = (rv - float(cv.mean())) / sd if sd > 1e-12 else 0.0
        if sd <= 1e-12:
            verdict = "tie (no spread)" if abs(rv - float(cv.mean())) < 1e-9 else "no spread"
            ties += 1
        elif z > 1.0:
            verdict = "REAL above"; wins += 1
        elif z < -1.0:
            verdict = "control above"; losses += 1
        else:
            verdict = "inside spread"; ties += 1
        print(f"{k:34} {rv:>10.4f} {float(cv.mean()):>10.4f} {sd:>9.4f} "
              f"{z:>7.2f} {verdict:>16}")
    print()
    print(f"real above the control spread: {wins} | below: {losses} | "
          f"indistinguishable: {ties}")
    print()
    print("z is (real - control mean) / control sd across the random rewirings.")
    print("A measure where the real value sits inside that spread is a measure on")
    print("which the fly's wiring has not been shown to matter -- with this")
    print("protocol, at this scale, on these seeds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
