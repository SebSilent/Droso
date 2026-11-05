"""Register the clustering finding as an instrument limitation, with the cost of each way out.

No donor read in this file. The measured part comes from the sealed class-1 graph; the cost part is arithmetic
on the registered caps. That separation matters: the question the PI has to answer is which pool size and which
k to register, and the honest answer cannot come from a pilot, because choosing them by measurement would be an
extraction run for the purpose of tuning the instrument -- which is the same act as raising a cap after seeing
the need, only earlier.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                       # noqa: BLE001 -- a console that cannot be set is not a failure
    pass

from tools.mp_e12_pool_rule import POOL_CAP              # noqa: E402
from tools.mp_e12_probes import K_NEIGHBOURS, READ_BUDGET_OPS  # noqa: E402
from tools.mp_e12_address_space import MAX_READS_PER_PROBE, MAX_ROWS_PER_READ  # noqa: E402

G = json.loads((ROOT / "experiments/MP-E12/results/association_graph_real_class1.json").read_text(
    encoding="utf-8"))
SYN = json.loads((ROOT / "experiments/MP-E12/results/probes_synthetic_calibration.json").read_text(
    encoding="utf-8"))
OUT = ROOT / "experiments/MP-E12/results/clustering_limitation_v1.json"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ITEMS = 24


def calls_for(rows):
    return -(-int(rows) // MAX_ROWS_PER_READ)


def cost(pool, items=ITEMS):
    calls_per_item = 1 + calls_for(pool)                 # probe row, then the pool in bounded gathers
    reg_per_item = 2                                    # one similarity search, one neighbour gram
    return {"pool_rows": pool,
            "read_calls_per_item": calls_per_item,
            "registered_ops_per_item": reg_per_item, "registered_ops_run": reg_per_item * items,
            "conservative_ops_per_item": reg_per_item + calls_per_item,
            "conservative_ops_run": (reg_per_item + calls_per_item) * items,
            "per_row_ops_per_item": reg_per_item + 1 + pool,
            "per_row_ops_run": (reg_per_item + 1 + pool) * items,
            "fits_24_registered": reg_per_item <= READ_BUDGET_OPS,
            "fits_24_conservative": reg_per_item + calls_per_item <= READ_BUDGET_OPS,
            "fits_24_per_row": reg_per_item + 1 + pool <= READ_BUDGET_OPS,
            "gather_cap_binds": calls_per_item > MAX_READS_PER_PROBE}


# ------------------------------------------------------------------ the measurement, from the sealed graph
def cluster_shape(graph):
    shapes = []
    for it in graph["items"]:
        for cl in it["detail"].get("pool_clusters", []):
            shapes.append(len(cl))
    return Counter(shapes), len(graph["items"])


real_counts, n_items = cluster_shape(G)
syn_counts, n_syn = cluster_shape(SYN)
per_item_components = Counter(len(it["detail"].get("pool_clusters", [])) for it in G["items"])
print(f"class-1 run: {n_items} items, components per item: {dict(per_item_components)}, "
      f"cluster sizes: {dict(real_counts)}")
print(f"synthetic calibration: {n_syn} items, cluster sizes: {dict(syn_counts)}")

pools = [POOL_CAP, 255, 511, 1023, 2047, 50257]
table = {str(p): cost(p) for p in pools}
for p in pools:
    c = table[str(p)]
    print(f"  pool {p:6d}: calls/item={c['read_calls_per_item']:4d} conservative/item="
          f"{c['conservative_ops_per_item']:4d} fits24(cons)={c['fits_24_conservative']} "
          f"fits24(per-row)={c['fits_24_per_row']}")

doc = {
    "registered_at_utc": NOW,
    "schema": "droso.instrument_limitation.v1",
    "status": "LIMITATION REGISTERED WITH A PROPOSAL. Nothing here is applied: the pool rule and K_NEIGHBOURS "
              "stand as registered, the sealed class-1 graph is untouched, and no extraction was run to tune "
              "any of it.",
    "the_finding_as_measured": {
        "what": "the mutual-nearest-neighbour feature-pool step returned exactly ONE component for every item, "
                "and that component had exactly K_NEIGHBOURS members",
        "components_per_item": {str(k): v for k, v in per_item_components.items()},
        "cluster_size_histogram": {str(k): v for k, v in real_counts.items()},
        "n_items": n_items,
        "also_true_of_the_synthetic_calibration": {"cluster_size_histogram": {str(k): v for k, v in
                                                                              syn_counts.items()},
                                                  "n_items": n_syn,
                                                  "meaning": "the degeneracy is not a property of the real "
                                                             "donor. It appeared on random matrices too, which "
                                                             "is how it was known to be about the instrument "
                                                             "before this step had any real result to blame."},
        "why_it_happens": "clustering runs over the k neighbours already read, so with k=10 the graph has 10 "
                          "nodes and mutual linking over a 63-row pool connects them densely enough that they "
                          "land in one component every time. A step that can only return one component at every "
                          "item is not measuring structure; it is echoing k.",
        "consequence_for_the_sealed_graph": "the pool_clusters field in the sealed class-1 artifact carries no "
                                            "information beyond k. The edges and cosines are unaffected -- they "
                                            "come from the similarity search, not from the linking -- so the "
                                            "sealed figures stand and only this one derived field is empty of "
                                            "content."},
    "the_two_ways_it_could_be_made_meaningful": {
        "A_pool_large_enough_for_k_to_bind": {
            "proposal": "raise the candidate pool so that 10 neighbours are sparse in it and mutual linking can "
                        "actually separate",
            "what_it_costs": {str(p): table[str(p)] for p in (255, 511, 1023, 2047, 50257)},
            "the_wall": "a global search over all 50,257 rows is 787 read calls per item: 789 conservative "
                        "operations against a budget of 24, and 16,384 rows is where the instrument's own "
                        "MAX_READS_PER_PROBE cap binds first",
            "what_it_would_change": "the pool-relative caveat in every sealed artifact would loosen, and the "
                                    "17 deferred words would still be deferred",
            "risk": "a bigger pool makes the neighbour claim stronger and the clustering claim weaker at the "
                    "same time: with more candidates, one component of 10 stops being evidence of a pool and "
                    "starts being evidence of nothing in particular unless k also moves"},
        "B_k_as_a_fraction_of_the_pool": {
            "proposal": "set k = max(2, round(pool / f)) for a registered fraction f, so the neighbour count "
                        "scales with the pool instead of being an absolute constant",
            "what_it_costs": "no extra reads at all -- the pool is unchanged, so the conservative cost stays at "
                             "4 operations per item and 96 for the run. The cost is in the graph: fewer edges "
                             "per item, and every sealed edge count changes meaning",
            "the_problem_this_one_has": "f cannot be chosen by measurement without running an extraction to see "
                                        "which f separates. That is tuning the instrument on results, which is "
                                        "the same act as raising a cap after seeing the need, only earlier in "
                                        "the chain. f has to be fixed by argument before the next read.",
            "and_the_other_problem": "k=10 is registered in the plan's instrument description and appears in "
                                     "the sealed calibration's schema. Changing it makes new graphs "
                                     "non-comparable with the sealed ones unless the change is versioned, "
                                     "which is why this is a proposal and not an edit."}},
    "cost_of_the_current_registration": table[str(POOL_CAP)],
    "cost_table_across_pool_sizes": table,
    "what_may_not_happen": {
        "no_choice_after_a_result": "neither A nor B may be picked by looking at what a pilot run returns. The "
                                    "PI chooses on the argument, or the program runs a registered pilot whose "
                                    "purpose and cost are written down first -- and that pilot is an extraction, "
                                    "so it needs authorising.",
        "no_cap_raised_here": "MAX_ROWS_PER_READ, MAX_READS_PER_PROBE, READ_BUDGET_OPS and POOL_CAP are "
                              "unchanged by this file. Nothing in the cost table was obtained by editing them.",
        "no_sealed_artifact_rewritten": "the class-1 graph keeps its pool_clusters field exactly as it was "
                                        "emitted, empty of information or not"},
    "proposal_to_the_pi": {
        "single_question": "is the feature-pool claim worth buying? It is the only claim in MP-E12a that the "
                           "current budget cannot support against the real donor, and it is the one the plan's "
                           "superposition risk names.",
        "if_yes": "option A at pool 1,023 fits the conservative reading at 19 of 24 operations per item and is "
                  "the cheapest version that could plausibly separate; it costs 456 conservative operations for "
                  "a 24-item run and 24,576 rows under the per-row reading",
        "if_no": "the clustering step should be reported as retired rather than left in artifacts that look "
                 "like results, and the pool-relative limitation stays as the honest ceiling on the neighbour "
                 "claim",
        "what_i_will_not_do": "pick one. Choosing the parameter that makes the instrument produce a "
                              "story is the failure this whole ledger exists to prevent."},
    "no_reads_in_this_step": {"donor_bytes_read_by_this_tool": 0,
                              "sources": ["the sealed class-1 artifact", "the sealed synthetic calibration",
                                          "the registered caps in the instrument"]},
}
OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"\nwrote {OUT.relative_to(ROOT)}")
print(f"  current registration (pool {POOL_CAP}): {doc['cost_of_the_current_registration']}")
print(f"  donor bytes read by this tool: 0")
