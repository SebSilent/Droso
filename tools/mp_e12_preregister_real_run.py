"""B.6 item 4, step 1: register the accounting choice BEFORE the first real read.

This script reads NO value from the donor. It opens the address space with a throwaway journal purely to ask the
header for tensor shapes, computes the planned read arithmetic from those shapes and the pool rule, and writes
this artifact. The artifact's `registered_at_utc` is therefore an earlier fact than the first record in the
extraction journal, and that ordering is the proof that the accounting was chosen before the data existed rather
than after it was seen -- which is the whole difference between a registration and an R2 act.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.mp_e12_access_journal import AccessJournal  # noqa: E402
from tools.mp_e12_address_space import (  # noqa: E402
    ADDRESS_SPACE_VERSION, MAX_ROWS_PER_READ, DonorAddressSpace)

OUT = ROOT / "experiments/MP-E12/results/real_run_preregistration.json"
SCRATCH = ROOT / "_tmp/prereg_shape_query.jsonl"
LIST = ROOT / "experiments/MP-E12/results/probe_list_v1.json"

# ---- the pool rule, written down before it is used -----------------------------------------------
# Value-blind by construction: it consumes INTEGER token ids and nothing else. No weight value is consulted
# at any point in choosing a candidate, so the candidate pool cannot have been picked to produce a result.
SAMPLE_STRIDE_A = 7919          # odd, coprime with 50257: the map j -> r_j has no short cycle
SAMPLE_STRIDE_B = 104729
SAMPLE_N = 40                   # 23 other probes + 40 sampled rows = 63 <= MAX_ROWS_PER_READ, ONE call


def pool_for(token_id, other_ids, n_vocab):
    ids = [t for t in other_ids if t != token_id]
    for j in range(SAMPLE_N):
        r = (token_id * SAMPLE_STRIDE_A + j * SAMPLE_STRIDE_B + 1) % n_vocab
        if r != token_id and r not in ids:
            ids.append(r)
    return ids[:MAX_ROWS_PER_READ - 1]


def calls_for(rows):
    return -(-rows // MAX_ROWS_PER_READ)


probes = json.loads(LIST.read_text(encoding="utf-8"))["probes"]
ids = [p["token_id"] for p in probes]
N_VOCAB = 50257

sha = "248dfc3911869ec493c76e65bf2fcf7f615828b0254c12b473182f0f81d3a707"
planned = {}
with AccessJournal(str(SCRATCH), donor_sha256=sha, run_label="prereg_shape_query") as jr:
    with DonorAddressSpace(journal=jr) as ax:
        shapes = {t: ax.shape(t) for t in
                  ("wte.weight", "ln_f.weight", "ln_f.bias", "h.0.attn.c_attn.weight",
                   "h.0.attn.c_proj.weight", "h.0.mlp.c_fc.weight", "h.0.mlp.c_proj.weight")}
        recs = jr.read().__len__() if hasattr(jr, "read") else 0
        pool_sizes = [len(pool_for(t, ids, N_VOCAB)) for t in ids]

# ---- planned arithmetic per class, from shapes only -----------------------------------------------
c2_calls = calls_for(shapes["h.0.attn.c_attn.weight"][0]) * 4 + 2      # 4 head column slices + ln_f w/b
c3_calls = (calls_for(shapes["h.0.attn.c_proj.weight"][0]) * 4          # W_O slices
            + calls_for(shapes["h.0.mlp.c_fc.weight"][0]) * 12          # one c_fc per layer
            + 12)                                                       # neuron-value gathers, 5 rows each
c1_calls = 2                                                            # probe row + pool, one call each
planned = {
    "1_embedding_geometry": {
        "registered_ops": 2, "read_calls": c1_calls, "conservative_ops": 2 + c1_calls,
        "rows_touched": 1 + max(pool_sizes),
        "values_floats_max": (1 + max(pool_sizes)) * shapes["wte.weight"][1],
        "fits_the_registered_budget": 2 + c1_calls <= 24},
    "2_association_edges": {
        "registered_ops": 5, "read_calls": c2_calls, "conservative_ops": 5 + c2_calls,
        "rows_touched": 4 * shapes["h.0.attn.c_attn.weight"][0] + 2 * shapes["ln_f.weight"][0],
        "values_floats_max": 4 * shapes["h.0.attn.c_attn.weight"][0] * shapes["h.0.attn.c_attn.weight"][1],
        "fits_the_registered_budget": 5 + c2_calls <= 24},
    "3_circuit_motifs": {
        "registered_ops": 16, "read_calls": c3_calls, "conservative_ops": 16 + c3_calls,
        "rows_touched": (4 * shapes["h.0.attn.c_proj.weight"][0]
                         + 12 * shapes["h.0.mlp.c_fc.weight"][0]
                         + 12 * 5),
        "values_floats_max": (4 * shapes["h.0.attn.c_proj.weight"][0] * shapes["h.0.attn.c_proj.weight"][1]
                              + 12 * shapes["h.0.mlp.c_fc.weight"][0] * shapes["h.0.mlp.c_fc.weight"][1]),
        "fits_the_registered_budget": 16 + c3_calls <= 24},
}
three_class = {"registered_ops": sum(v["registered_ops"] for v in planned.values()),
               "read_calls": sum(v["read_calls"] for v in planned.values()),
               "conservative_ops": sum(v["conservative_ops"] for v in planned.values())}

doc = {
    "schema_version": "droso.real_run_preregistration.v1",
    "registered_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "purpose": "B.6 item 4: the three compile reads against the real donor. This file is the accounting "
               "registration, written before the first real read so that the choice cannot have been made "
               "after seeing what the reads return.",
    "the_registered_rule_as_written": ("one operation = one vector-by-donor-matrix multiply, or one "
                                       "similarity search against one donor matrix. A gather of already-read "
                                       "rows is NOT an operation, and element-wise work is not an operation. "
                                       "Per item, the budget is 24 operations (plan C3)."),
    "the_reading_this_run_uses": {
        "choice": "CONSERVATIVE",
        "definition": "conservative_ops = registered_ops + one charged operation for EVERY journaled read "
                      "call, however many values that call returns. A gather is charged, not free.",
        "relation_to_the_registered_rule": "STRICTER than the registered rule. The registered rule treats a "
                                           "gather of already-read rows as free; this run does not. The PI has "
                                           "not ruled on the loophole, and while it is open the person holding "
                                           "the reader is the one who should pay for it, not the one who has "
                                           "to argue about it afterwards.",
        "not_exploiting_it": "No extraction in this run earns its result by the free-gather reading. Where "
                             "the two readings differ in outcome, the conservative one decides, and both "
                             "tallies are emitted side by side so the ruling can be made with data.",
        "third_tally_also_emitted": "rows_touched: the count if a gather were charged per ROW rather than per "
                                    "call. It is reported, not run under, because it is a stricter reading "
                                    "still and the PI has not chosen it either."},
    "what_the_conservative_reading_does_to_the_battery": planned,
    "consequence_measured_before_any_read": (
        f"a full three-class item costs {three_class['registered_ops']} operations under the registered rule "
        f"and {three_class['conservative_ops']} under this one ({three_class['read_calls']} separate donor "
        f"reads). The registered budget is 24. So under conservative accounting the three-class item ABORTS as "
        f"a budget event and writes nothing, and only class 1 -- embedding geometry over a bounded candidate "
        f"pool -- fits. That is not a choice made after seeing the data: it is arithmetic on tensor shapes, "
        f"performed here, before the first value was read."),
    "classes_run_against_the_real_donor": ["1_embedding_geometry"],
    "classes_recorded_as_pre_flight_budget_events": ["2_association_edges", "3_circuit_motifs"],
    "why_a_pre_flight_event_rather_than_a_run_then_abort": (
        "C3 says an over-budget item writes nothing. Performing 254 reads and then discarding the row would "
        "still have put 254 records in the access journal and spent the bytes; the check is therefore made on "
        "the PLAN, from shapes, so an aborted class touches no value at all. The registered post-hoc check "
        "stays in place for the synthetic path, where it is the check that has always been there."),
    "candidate_pool_rule": {
        "formula": f"pool(T) = [other 23 probe ids, ascending] ++ [(T*{SAMPLE_STRIDE_A} + j*{SAMPLE_STRIDE_B} "
                   f"+ 1) mod {N_VOCAB} for j in 0..{SAMPLE_N - 1}], deduplicated in that order, T excluded, "
                   f"capped at {MAX_ROWS_PER_READ - 1}",
        "value_blind": "the formula consumes INTEGER token ids only. No weight value is consulted in choosing "
                       "a candidate, so the pool cannot have been picked to produce a neighbour.",
        "why_a_pool_at_all": "the registered budget does not admit a global search against the real donor: "
                             f"wte.weight has {N_VOCAB} rows, which at MAX_ROWS_PER_READ="
                             f"{MAX_ROWS_PER_READ} is {calls_for(N_VOCAB)} read calls for one item. A pool of "
                             "63 rows is one call.",
        "what_it_costs_in_claim_strength": "a neighbour found here is nearest AMONG THESE 63, not nearest "
                                           "among 50,257. The synthetic graph could make the global claim "
                                           "because it held the whole matrix in RAM and the rule charged that "
                                           "as zero operations. The real graph trades that reach for "
                                           "provenance, and the trade is stated in the artifact rather than "
                                           "left for a reader to discover.",
        "pool_sizes_measured": {"min": min(pool_sizes), "max": max(pool_sizes), "n_items": len(pool_sizes)}},
    "budget": {"registered_ops_per_item": 24, "enforcement": "pre-flight on the plan for the real source; "
                                                              "post-hoc per extraction for the synthetic "
                                                              "source (unchanged)",
               "if_exceeded": "STOP that item, report the count, write nothing. Raising a registered budget "
                              "after seeing the need is an R2 act and is not available to this run."},
    "caps_inherited_from_the_instrument": {"MAX_ROWS_PER_READ": MAX_ROWS_PER_READ,
                                           "address_space_version": ADDRESS_SPACE_VERSION},
    "mask_buffers": "excluded by the address space before byte arithmetic; no class in this run names an "
                    "h.<N>.attn.bias tensor, and the run's journal is checked for it afterwards rather than "
                    "trusted.",
    "what_the_coming_figures_are_NOT": {
        "latency_or_10x": "NOT a claim about the >=10x threshold. The threshold has never been re-based on the "
                          "real donor: reference_inference exists against the synthetic shapes only, and that "
                          "re-basing is a separate item. No wall-clock ratio is emitted by this run.",
        "MP-E12b": "NOT evidence about MP-E12b, which D-MPE12-04 bars.",
        "behaviour": "NOT a behavioural claim of any kind: no text was generated, no prompt was run, the donor "
                     "was never executed. R17 binds behavioural figures, so it does not bind these, and no "
                     "fresh-vs-fresh floor is needed for them. A later reader who wants to use a neighbour "
                     "cosine as evidence about model BEHAVIOUR is making a claim this artifact does not make.",
        "knowledge_localisation": "NOT a localisation of knowledge in a layer or head; a cosine between two "
                                  "embedding rows is a property of two vectors, not a place where a concept "
                                  "lives."},
    "provenance_of_this_file": "written by tools/mp_e12_preregister_real_run.py; the shape query that produced "
                              "the arithmetic opened the address space with a scratch journal and read no "
                              "value, so this artifact was registered at zero donor reads.",
}
OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {OUT.relative_to(ROOT)}")
print(f"  registered_at_utc {doc['registered_at_utc']}")
print(f"  three-class item: registered {three_class['registered_ops']} ops | conservative "
      f"{three_class['conservative_ops']} ops | {three_class['read_calls']} read calls")
for k, v in planned.items():
    print(f"  {k:24s} registered={v['registered_ops']:3d} calls={v['read_calls']:4d} "
          f"conservative={v['conservative_ops']:4d} fits_24={v['fits_the_registered_budget']}")
print(f"  pool sizes: {doc['candidate_pool_rule']['pool_sizes_measured']}")
print(f"  scratch journal records (must be 0): {sum(1 for _ in SCRATCH.open(encoding='utf-8')) if SCRATCH.exists() else 'file absent'}")
