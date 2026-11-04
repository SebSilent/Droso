"""MP-E12a: the three weight-reading extractions, under a hard per-item read budget.

READ-ONLY, AND THAT IS THE WHOLE CLAIM. Nothing here mutates a tensor, nothing here runs the donor: there
is no forward pass, no attention over a sequence, no sampling, no generated text. Each extraction multiplies
a probe vector by a donor parameter matrix and reads the result. `tests/test_mp_e12_probes.py` asserts the
donor is bit-identical after a full graph build, because "read-only" is a claim the code has to keep.

THE BUDGET IS IN THE READ PATH, NOT IN THE REPORT. `ReadBudgetExceeded` fires when an item would spend more
than the registered 24 matrix operations, and it fires BEFORE the item is written, so an over-budget probe
cannot contribute a row to a graph that then looks complete. That is the plan's C3 condition, and the
failure mode it prevents is a silent truncation.

THE DONOR IS SYNTHETIC and the artifact says so in every field group. Operation counts, matrix shapes and
MAC totals are properties of the code path and the shapes, so they are valid measurements here. Neighbours,
successors, motifs and confidences are not: random matrices hold no associations, and a figure of that kind
appearing in a sentence about GPT-2 is a reporting error this file cannot prevent but does name.

WHY A REFERENCE INFERENCE SIDE EXISTS AT ALL. H2's threshold is a comparison: reading at least ten times
cheaper per association than autoregressive inference. The read side is this file. The inference side is
`reference_inference`, which spends the donor-matrix operations a real generation loop would spend per
generated token, under the same registered counting rule. Without it the threshold is an assertion with one
side measured.
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_synthetic_donor import GPT2_124M, TINY, build_donor, shape_manifest

REGISTRATION = "experiments/MP-E12/registration.json"
READ_BUDGET_OPS = 24                      # registered NUMBER; an item above it aborts (plan C3)
SCHEMA_VERSION = "droso.association_graph.v1"
K_NEIGHBOURS, K_SUCCESSORS, K_NEURONS = 10, 5, 5
HEADS = [(0, 0), (3, 5), (7, 2), (11, 11)]   # registered (layer, head) subset


class ReadBudgetExceeded(Exception):
    def __init__(self, item, planned_ops, budget):
        super().__init__(f"item {item} would spend {planned_ops} operations against a budget of {budget}")
        self.item, self.planned_ops, self.budget = item, planned_ops, budget


class OpCounter:
    """Counts donor-matrix touches as registered: one op = one vector-by-donor-matrix multiply, or one
    similarity search against one donor matrix. Element-wise work and gathers of already-read rows are not
    ops, and attention between activation vectors touches no donor parameter so it is not an op either."""

    def __init__(self):
        self.entries = []                 # (extraction, matrix, ops, macs)

    def spend(self, extraction, matrix, ops, macs):
        self.entries.append({"extraction": extraction, "matrix": matrix, "ops": int(ops),
                             "macs": int(macs)})

    @property
    def ops(self):
        return sum(e["ops"] for e in self.entries)

    @property
    def macs(self):
        return sum(e["macs"] for e in self.entries)

    def per_extraction(self):
        out = {}
        for e in self.entries:
            d = out.setdefault(e["extraction"], {"ops": 0, "macs": 0, "matrices": []})
            d["ops"] += e["ops"]; d["macs"] += e["macs"]
            if e["matrix"] not in d["matrices"]:
                d["matrices"].append(e["matrix"])
        return out


def _normed(a):
    n = float(np.linalg.norm(a))
    return a / n if n > 0 else a


def extraction_1_embedding_geometry(donor, token_id, counter, k=K_NEIGHBOURS):
    """Nearest-neighbour structure of the token-embedding matrix, clustered into candidate feature pools.

    One similarity search against wte. The clustering is mutual-nearest-neighbour linking over the ids
    already read, which touches no donor matrix and therefore spends no operation -- a consequence of the
    registered counting rule, stated here rather than left for a reader to infer.
    """
    wte = donor["wte"]
    probe = wte[token_id]
    sims = wte @ _normed(probe) / max(float(np.linalg.norm(probe)), 1e-12)
    counter.spend("1_embedding_geometry", "wte", 1, wte.shape[0] * wte.shape[1])
    order = np.argsort(-sims)
    nbrs = [int(t) for t in order if int(t) != token_id][:k]
    # Mutual-nearest-neighbour linking needs a gram over the k neighbour rows. Those rows are already read,
    # but the gram is still a multiply by a matrix assembled from donor rows, so it is COUNTED as one
    # operation rather than waved through as "element-wise". A budget that only counts what the author
    # remembered is not a budget.
    rows = wte[nbrs]
    gram = rows @ rows.T
    counter.spend("1_embedding_geometry", "wte[nbrs] gram (k rows of a donor matrix)", 1,
                  len(nbrs) * len(nbrs) * wte.shape[1])
    gmax = np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-12)
    cos = gram / (gmax * gmax.T)
    nbr_sets = {t: set(int(y) for y in np.argsort(-cos[i])[:k] if int(y) != i and int(y) < len(nbrs))
                for i, t in enumerate(nbrs)}
    nbr_sets = {t: {nbrs[j] for j in s} for t, s in nbr_sets.items()}
    pool, seen = [], set()
    for t in nbrs:
        if t in seen:
            continue
        comp, stack = set(), [t]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.add(x); stack.extend(nbr_sets.get(x, ()))
        pool.append(sorted(comp))
    nodes = [{"node_id": f"probe:{token_id}", "type": "probe_token",
              "source": "wte", "confidence": 1.0}]
    nodes += [{"node_id": f"succ:{t}", "type": "successor_token", "source": "wte",
               "confidence": round(float(sims[t]), 6)} for t in nbrs]
    edges = [{"src": f"probe:{token_id}", "dst": f"succ:{t}", "type": "co_clustered",
              "confidence": round(float(sims[t]), 6), "extraction": "1_embedding_geometry",
              "provenance": {"source_model": donor.get("name", "synthetic"), "method": "embedding_geometry"}}
             for t in nbrs]
    return nodes, edges, {"pool_clusters": pool, "neighbours": nbrs}


def extraction_2_association_edges(donor, token_id, counter, heads=HEADS, k=K_SUCCESSORS):
    """Top-k associative successors read from the tied unembedding, plus each registered head's value read.

    Five operations: one multiply by wte (which IS the unembedding -- the tie is registered as a failure
    mode, because extraction 1 and this one read the same matrix and an agreement between them is partly
    arithmetic), and one per registered head's W_V slice.
    """
    cfg = donor["config"]; n = cfg["n_embd"]; dh = cfg["d_head"]
    probe = donor["wte"][token_id]
    ln, bias = donor["ln_f_weight"], donor["ln_f_bias"]   # the pre-unembedding norm, element-wise: no op
    scaled = (probe - probe.mean()) / (probe.std() + 1e-6) * ln + bias     # element-wise: no op spent
    logits = donor["wte"] @ scaled
    counter.spend("2_association_edges", "wte (tied unembedding)", 1,
                  donor["wte"].shape[0] * n)
    order = np.argsort(-logits)
    succ = [int(t) for t in order[:k]]
    nodes, edges = [], []
    for t in succ:
        nodes.append({"node_id": f"succ:{t}", "type": "successor_token", "source": "wte",
                      "confidence": round(float(logits[t]), 6)})
        edges.append({"src": f"probe:{token_id}", "dst": f"succ:{t}", "type": "association",
                      "confidence": round(float(logits[t]), 6), "extraction": "2_association_edges",
                      "provenance": {"source_model": donor.get("name", "synthetic"),
                                     "method": "unembedding_read"}})
    head_reads = {}
    for (layer, head) in heads:
        W = donor["layers"][layer]["c_attn_weight"][:, head * dh:(head + 1) * dh]
        v = W.T @ probe
        counter.spend("2_association_edges", f"h{layer}.{head}.W_V", 1, n * dh)
        head_reads[f"h{layer}.{head}"] = {"value_direction_norm": round(float(np.linalg.norm(v)), 6)}
    return nodes, edges, {"successors": succ, "head_value_reads": head_reads,
                          "donor_is_weight_tied": True}


def extraction_3_circuit_motifs(donor, token_id, counter, heads=HEADS, k=K_NEURONS):
    """Heads as directed association maps, MLP neurons as key-value feature detectors.

    Sixteen operations: one W_O slice per registered head, one c_fc per layer. The detector VALUES are rows
    gathered out of mlp_c_proj for the neurons that responded -- a gather of already-read rows, so it spends
    no operation under the registered rule, and the artifact says which is which rather than leaving a
    reader to guess whether the value read was counted.
    """
    cfg = donor["config"]; n = cfg["n_embd"]; dh = cfg["d_head"]
    probe = donor["wte"][token_id]
    nodes, edges, motifs = [], [], {"heads": {}, "neurons": {}}
    for (layer, head) in heads:
        # The head's output matrix maps its own d_head subspace into the residual stream. Reading that
        # slice against the probe is ONE multiply by ONE donor matrix, which is what keeps this extraction
        # inside the registered budget. An earlier draft also asked which token that direction is nearest
        # to -- a second read of wte per head, four uncounted operations, so it is dropped rather than
        # silently absorbed: a directed map is recorded as a direction, not as a word.
        W_O = donor["layers"][layer]["attn_c_proj_weight"][:, head * dh:(head + 1) * dh]
        direction = W_O.T @ probe
        counter.spend("3_circuit_motifs", f"h{layer}.{head}.W_O", 1, dh * n)
        key = f"h{layer}.{head}"
        motifs["heads"][key] = {"writes_direction_norm": round(float(np.linalg.norm(direction)), 6),
                                "written_in": "the head's own output subspace (d_head), not vocabulary space"}
        nodes.append({"node_id": f"map:{key}", "type": "feature_detector", "source": f"h{layer}.{head}.W_O",
                      "confidence": round(float(np.linalg.norm(direction)), 6)})
        edges.append({"src": f"probe:{token_id}", "dst": f"map:{key}", "type": "directed_map",
                      "confidence": round(float(np.linalg.norm(direction)), 6),
                      "extraction": "3_circuit_motifs",
                      "provenance": {"source_model": donor.get("name", "synthetic"), "method": "head_map"}})
    responded = {}
    for layer, blk in enumerate(donor["layers"]):
        pre = blk["mlp_c_fc_weight"].T @ probe + blk["mlp_c_fc_bias"]
        counter.spend("3_circuit_motifs", f"L{layer}.c_fc", 1, n * cfg["mlp_inner"])
        top = [int(t) for t in np.argsort(-pre)[:k]]
        responded[f"L{layer}"] = top
        vals = blk["mlp_c_proj_weight"][top, :].mean(axis=0)      # gather: no operation spent
        motifs["neurons"][f"L{layer}"] = {"top_neurons": top,
                                          "responses": [round(float(pre[t]), 6) for t in top],
                                          "mean_value_direction_norm": round(float(np.linalg.norm(vals)), 6)}
    return nodes, edges, motifs


def heads_for(donor, requested=HEADS):
    """The registered (layer, head) subset when the donor has one; the first valid pairs when it does not.

    The substitution exists so the tiny unit-test shape can run the same code path, and it is REPORTED in
    the item rather than hidden: an artifact built on a substituted subset says which.
    """
    cfg = donor["config"]
    if all(layer < cfg["n_layer"] and head < cfg["n_head"] for layer, head in requested):
        return list(requested), True
    valid = [(l, h) for l in range(cfg["n_layer"]) for h in range(cfg["n_head"])]
    return valid[:len(requested)], False


def probe_item(donor, token_id, budget=READ_BUDGET_OPS):
    """One probed association. Aborts before writing anything if it would exceed the budget."""
    counter = OpCounter()
    heads, registered = heads_for(donor)
    nodes, edges, detail = [], [], {}
    for fn, kw in ((extraction_1_embedding_geometry, {}),
                   (extraction_2_association_edges, {"heads": heads}),
                   (extraction_3_circuit_motifs, {"heads": heads})):
        n, e, d = fn(donor, token_id, counter, **kw)
        nodes += n; edges += e; detail.update(d)
        if counter.ops > budget:                                  # C3: abort, write nothing
            raise ReadBudgetExceeded(token_id, counter.ops, budget)
    return {"item": int(token_id), "nodes": nodes, "edges": edges, "detail": detail,
            "registered_heads_used": registered, "head_subset": [list(h) for h in heads],
            "operations_spent": counter.ops, "macs_spent": counter.macs,
            "per_extraction": counter.per_extraction(), "budget": budget,
            "aborted": False}


def reference_inference_run(donor, tokens_generated):
    """Spend, sequentially, the donor-matrix operations one autoregressive generation of k tokens pays.

    This is NOT a language model and does not produce text: no sampling, no attention between activations,
    no KV cache. It exists so H2's wall-clock side is a measurement on these shapes rather than a scaling of
    an op count, which would be the same number twice. Because it omits the activation-side work a real
    generation loop pays, it UNDERSTATES inference cost and therefore FLATTERS the read side; the artifact
    carries that caveat rather than burying the favourable direction.
    """
    cfg = donor["config"]; n = cfg["n_embd"]
    t0 = time.perf_counter()
    h = donor["wte"][0].astype(np.float32).copy()
    for _ in range(tokens_generated):
        for blk in donor["layers"]:
            qkv = blk["c_attn_weight"].T @ h                       # 1 donor matrix
            att = blk["attn_c_proj_weight"] @ qkv[:n]              # 1
            m = np.maximum(blk["mlp_c_fc_weight"].T @ att, 0.0)    # 1
            h = m @ blk["mlp_c_proj_weight"]                       # 1: (3072,) by (3072, 768)
            h = (h - h.mean()) / (h.std() + 1e-6)
        logits = donor["wte"] @ h                                   # 1: the tied unembedding
        h = donor["wte"][int(np.argmax(logits))].astype(np.float32).copy()
    return {"seconds": round(time.perf_counter() - t0, 6),
            "ops": (cfg["n_layer"] * 4 + 1) * tokens_generated}


def reference_inference(donor, tokens_generated):
    """The other side of H2's comparison: donor-matrix operations a generation loop spends per token."""
    cfg = donor["config"]; n = cfg["n_embd"]
    ops_per_token = cfg["n_layer"] * 4 + 1          # c_attn, attn c_proj, mlp c_fc, mlp c_proj, unembed
    macs_per_token = cfg["n_layer"] * (n * 3 * n + n * n + n * cfg["mlp_inner"] + cfg["mlp_inner"] * n) \
        + donor["wte"].shape[0] * n
    return {"tokens_generated": tokens_generated, "ops_per_generated_token": ops_per_token,
            "macs_per_generated_token": int(macs_per_token),
            "ops_for_this_association": ops_per_token * tokens_generated,
            "macs_for_this_association": int(macs_per_token) * tokens_generated,
            "counting_note": "attention between activation vectors touches no donor parameter matrix, so "
                             "under the registered counting rule it is not an operation on either side"}


def calibration_findings(bench, donor, items):
    """What the synthetic run taught, DERIVED from the rows above rather than typed in beside them."""
    cfg = donor["config"]; n = cfg["n_embd"]

    def crossing(key):
        hits = [b["tokens_generated"] for b in bench if b[key]]
        return min(hits) if hits else None

    read_macs = bench[0]["read_macs_per_association"] if bench else 0
    vocab_macs = 2 * donor["wte"].shape[0] * n           # the embedding search and the tied unembedding
    jac = []
    for it in items:
        nbrs = set(it["detail"].get("neighbours", []))
        succ = set(it["detail"].get("successors", []))
        if nbrs or succ:
            jac.append(len(nbrs & succ) / max(len(nbrs | succ), 1))
    return {
        "1_ten_x_is_a_function_of_query_length_the_plan_does_not_fix": {
            "finding": f"the pre-registered 10x threshold is crossed at {crossing('meets_10x_on_ops')} generated "
                       f"tokens on operation count, {crossing('meets_10x_on_macs')} on MACs, and "
                       f"{crossing('meets_10x_on_wall_clock') or 'NONE OF THE REGISTERED LENGTHS'} on wall-clock",
            "consequence": "H2 cannot be scored until 'equivalent association query' has a token length. It is "
                           "registered as D-MPE12-05, and the plan's own wording does not settle it.",
            "note_on_none": "a null crossing is the finding, not a missing measurement"},
        "2_the_read_is_slower_than_generating_one_token": {
            "finding": f"at k=1 the read costs {bench[0]['cheaper_by_wall_clock']}x the reference generation -- "
                       f"below 1.0 means SLOWER",
            "why": "the read pays two full vocabulary-sized multiplies (the embedding search and the tied "
                   "unembedding) in one shot, while a one-token generation pays one of them plus smaller "
                   "per-layer work that numpy runs faster than the sort and node-building the read does.",
            "both_sides_have_unpriced_work_in_opposite_directions":
                "the read side INCLUDES ranking 50,257 logits twice and constructing every node and edge; the "
                "reference side OMITS attention between activations, softmax and the KV cache, which a real "
                "generation pays. So this ratio is not favourable to the read by construction, and it is not "
                "unfavourable either -- it is two different amounts of work, and the honest statement is that "
                "neither side here is a full cost model."},
        "3_the_vocabulary_is_where_the_budget_goes": {
            "finding": f"{round(100 * vocab_macs / max(read_macs, 1), 1)}% of the read's MACs are the two wte "
                       f"multiplies; the twelve MLP reads and eight head reads together are the rest",
            "consequence": "any attempt to widen the probe battery (more heads, more layers, motifs across "
                           "more of the model) is nearly free in operations and expensive in MACs. The budget "
                           "counts operations, so it does not see this -- a registered limitation of the "
                           "counting rule, not of this run."},
        "4_the_registered_budget_has_one_operation_of_headroom": {
            "finding": f"{bench[0]['read_ops_per_association'] if bench else 'n/a'} of {READ_BUDGET_OPS} spent",
            "consequence": "the extraction that would have asked which token each head map is nearest to was "
                           "dropped during implementation because it costs 4 more operations, which would abort "
                           "every item. That is the budget doing its job, and it is also the budget binding "
                           "before the science does.",
            "what_would_have_been_missed_if_the_budget_were_looser": "nothing -- the cost of a looser budget is "
                     "paid by H2, which is the comparison this file exists to make"},
        "5_weight_tying_is_visible_as_a_shape_not_a_claim": {
            "finding": "extraction 1 and extraction 2 both read wte; on this donor their top-k sets overlap with "
                       f"mean Jaccard {round(float(np.mean(jac)), 4) if jac else 'n/a'}",
            "caveat": "on random weights that number describes geometry, not knowledge. It is here because the "
                      "instrument should be seen reporting the quantity the plan's superposition risk names, "
                      "not because this donor has a superposition to report."},
    }


def build_graph(donor, item_ids, budget=READ_BUDGET_OPS, association_tokens=(1, 3, 5, 9)):
    items, aborted = [], []
    t_read = time.perf_counter()
    for tid in item_ids:
        try:
            items.append(probe_item(donor, tid, budget))
        except ReadBudgetExceeded as exc:
            aborted.append({"item": exc.item, "planned_ops": exc.planned_ops, "budget": exc.budget})
    read_seconds = time.perf_counter() - t_read
    ops = sum(i["operations_spent"] for i in items)
    macs = sum(i["macs_spent"] for i in items)
    n_items = max(len(items), 1)
    # PER ASSOCIATION, not per graph. The first version of this line divided the whole battery's total
    # against one association's inference cost, which made a 24-item read look 11x WORSE than a 1-token
    # generation -- an artefact of the denominator, not a measurement. The sealed run caught it because the
    # printed ratio changed with the item count, which it must not.
    read_ops_per_assoc = ops / n_items
    read_macs_per_assoc = macs / n_items
    read_s_per_assoc = (read_seconds / n_items) if read_seconds > 0 else None
    bench = []
    for k in association_tokens:
        ref = reference_inference(donor, k)
        run = reference_inference_run(donor, k)
        co = ref["ops_for_this_association"] / max(read_ops_per_assoc, 1e-12)
        cm = ref["macs_for_this_association"] / max(read_macs_per_assoc, 1e-12)
        cw = (run["seconds"] / read_s_per_assoc) if read_s_per_assoc else None
        bench.append({**ref, "reference_run_seconds": run["seconds"],
                      "read_ops_per_association": round(read_ops_per_assoc, 4),
                      "read_macs_per_association": int(read_macs_per_assoc),
                      "read_wall_clock_per_association_s": round(read_s_per_assoc, 6) if read_s_per_assoc else None,
                      "cheaper_by_ops": round(co, 4), "cheaper_by_macs": round(cm, 4),
                      "cheaper_by_wall_clock": round(cw, 4) if cw is not None else None,
                      "meets_10x_on_ops": co >= 10.0, "meets_10x_on_macs": cm >= 10.0,
                      "meets_10x_on_wall_clock": (cw >= 10.0) if cw is not None else None})
    return {"schema_version": SCHEMA_VERSION,
            "donor": {"name": "synthetic-124M-shaped-random", "is_synthetic": True,
                      "param_count": donor["param_count"], "config": donor["config"],
                      "unembedding_tied_to_wte": True,
                      "shapes": shape_manifest(donor)["tensors"]},
            "read_budget": {"value": budget, "unit": "matrix operations per probed association",
                            "enforcement": "plan C3: an item above budget aborts and writes nothing"},
            "items": items, "items_probed": len(items), "items_aborted": aborted,
            "operations_total": ops, "macs_total": macs,
            "operations_per_item_mean": round(ops / max(len(items), 1), 4),
            "wall_clock_read_s": round(read_seconds, 4),
            "benchmark_vs_reference_inference": bench,
            "calibration_findings": calibration_findings(bench, donor, items),
            "benchmark_caveats": {
                "comparison_is_per_association": "read cost is the battery total divided by items probed, so "
                    "the ratio does not move when the item count changes. It moved when the first version "
                    "divided by the wrong denominator, and that is how the bug was seen.",
                "reference_understates_inference": "the reference loop spends the donor-matrix operations a "
                    "generation pays and omits attention between activations, softmax and the KV cache. "
                    "Every ratio here therefore FLATTERS the read side; a real inference cost would make "
                    "reading look better, not worse.",
                "wall_clock_is_shape_valid_content_free": "these shapes and this code path give a real "
                    "seconds-per-association, but on a synthetic donor the associations being compared are "
                    "not GPT-2's, so the figure bounds the machinery and not the finding.",
                "energy": "not estimated at all (D-MPE12-02)"},
            "energy_estimate": "NOT MEASURED -- no energy instrument in this repository (D-MPE12-02)",
            "quoting_guard": {
                "meaning": "The donor is synthetic. No association, neighbour, motif or confidence figure in "
                           "this artifact is evidence about GPT-2, because this donor is not GPT-2 and holds "
                           "no library. Operation counts, shapes and MAC totals ARE valid measurements here: "
                           "they are properties of the code path and the registered shapes.",
                "rule_source": REGISTRATION,
                "blocking_external_fact": "GPT-2 124M public weights are not on this machine (named blocker "
                                          "in the registration). Until they arrive, B.6 item 1 against the "
                                          "real donor cannot run."}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiny", action="store_true", help="the small test shape instead of 124M")
    ap.add_argument("--items", type=int, default=24, help="how many token ids to probe")
    ap.add_argument("--out", default="", help="write the association graph here")
    a = ap.parse_args(argv)
    cfg = TINY if a.tiny else GPT2_124M
    donor = build_donor(cfg)
    donor["name"] = "synthetic-124M-shaped-random" if not a.tiny else "synthetic-tiny-shaped-random"
    ids = list(range(min(a.items, cfg["n_vocab"])))
    graph = build_graph(donor, ids)
    if a.out:
        p = Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"items={graph['items_probed']} aborted={len(graph['items_aborted'])} "
          f"ops_per_item={graph['operations_per_item_mean']} total_ops={graph['operations_total']} "
          f"wall={graph['wall_clock_read_s']}s")
    for b in graph["benchmark_vs_reference_inference"]:
        print(f"  k={b['tokens_generated']} token(s): read {b['read_ops_per_association']} ops "
              f"({b['read_wall_clock_per_association_s']}s) vs infer {b['ops_for_this_association']} ops "
              f"({b['reference_run_seconds']}s) -> cheaper by ops {b['cheaper_by_ops']}x, "
              f"macs {b['cheaper_by_macs']}x, wall {b['cheaper_by_wall_clock']}x "
              f"| 10x on ops: {b['meets_10x_on_ops']}")
    print(f"wrote {a.out or '(not written)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
