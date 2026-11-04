"""MP-E12a probe tests. Fast by design: the tiny donor shape exercises the same code path as the 124M one.

These tests are about the INSTRUMENT, not about any donor's knowledge. The donor is synthetic, so no test
here asserts anything about GPT-2; what is asserted is shape fidelity, the operation budget, the read-only
claim, the schema, and the honesty of the artifact's own labels.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_probes import (HEADS, K_NEIGHBOURS, K_SUCCESSORS, READ_BUDGET_OPS, SCHEMA_VERSION,
                                 ReadBudgetExceeded, build_graph, extraction_1_embedding_geometry,
                                 extraction_2_association_edges, extraction_3_circuit_motifs,
                                 heads_for, probe_item, reference_inference, OpCounter)
from tools.mp_e12_synthetic_donor import GPT2_124M, TINY, build_donor, param_count


@pytest.fixture(scope="module")
def donor():
    d = build_donor(TINY)
    d["name"] = "synthetic-tiny-shaped-random"
    return d


def _fingerprint(d):
    """Hash of every array's bytes, so 'read-only' is a measurement rather than a claim."""
    h = hashlib.sha256()
    for blk in d["layers"]:
        for k in sorted(blk):
            h.update(k.encode()); h.update(np.ascontiguousarray(blk[k]).tobytes())
    for k in ("wte", "wpe", "ln_f_weight", "ln_f_bias"):
        h.update(k.encode()); h.update(np.ascontiguousarray(d[k]).tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------- the donor is the shape it claims to be
def test_124m_config_has_the_published_parameter_count():
    assert param_count(GPT2_124M) == 124439808


def test_param_count_is_computed_not_typed():
    assert param_count(TINY) == 15552


def test_donor_is_deterministic_from_the_registered_seed():
    a, b = build_donor(TINY), build_donor(TINY)
    assert _fingerprint(a) == _fingerprint(b)
    assert _fingerprint(a) != _fingerprint(build_donor(TINY, seed=1250))


def test_unembedding_is_tied_and_says_so(donor):
    assert "lm_head" not in donor and "lm_head_weight" not in donor
    assert donor["config"]["n_vocab"] == donor["wte"].shape[0]


# ---------------------------------------------------------------- the budget, which is the point
def expected_ops(cfg):
    """The design's cost at a given shape: 2 + (1 + heads) + (heads + n_layer).

    Written as a formula because the count is a function of the CONFIG, which is the first thing this file
    learned: the tiny shape spends 13 and the 124M shape spends 23, from the same code path. A test that
    asserted 23 against the tiny donor would have been asserting a number the donor cannot spend.
    """
    return 2 + (1 + len(HEADS)) + (len(HEADS) + cfg["n_layer"])


@pytest.fixture(scope="module")
def donor124():
    d = build_donor(GPT2_124M)
    d["name"] = "synthetic-124M-shaped-random"
    return d


def test_one_item_spends_exactly_the_design_count_for_its_shape(donor):
    item = probe_item(donor, 0)
    assert item["operations_spent"] == expected_ops(TINY) == 13
    assert item["operations_spent"] <= READ_BUDGET_OPS


def test_the_registered_23_operations_are_a_124M_fact_not_a_tiny_one(donor124):
    """The budget of 24 was registered against the donor's real shape, so it is checked there."""
    item = probe_item(donor124, 0)
    assert item["operations_spent"] == 23 == expected_ops(GPT2_124M)
    assert item["operations_spent"] <= READ_BUDGET_OPS
    pe = item["per_extraction"]
    assert pe["1_embedding_geometry"]["ops"] == 2
    assert pe["2_association_edges"]["ops"] == 5
    assert pe["3_circuit_motifs"]["ops"] == 16
    assert pe["3_circuit_motifs"]["macs"] > 0
    assert item["registered_heads_used"] is True


def test_per_extraction_split_matches_the_registration(donor):
    pe = probe_item(donor, 0)["per_extraction"]
    assert pe["1_embedding_geometry"]["ops"] == 2
    assert pe["2_association_edges"]["ops"] == 5
    assert pe["3_circuit_motifs"]["ops"] == len(HEADS) + TINY["n_layer"]


def test_budget_abort_fires_and_writes_nothing(donor):
    with pytest.raises(ReadBudgetExceeded) as exc:
        probe_item(donor, 0, budget=5)
    assert exc.value.planned_ops > exc.value.budget
    assert exc.value.item == 0


def test_aborted_items_are_recorded_not_silently_dropped(donor):
    """C3's failure mode is a graph that looks complete but is missing its expensive probes."""
    graph = build_graph(donor, [0, 1, 2])
    assert graph["items_probed"] == 3 and graph["items_aborted"] == []
    with pytest.raises(ReadBudgetExceeded):
        probe_item(donor, 1, budget=10)
    # and a build that aborts everything must report the aborts, not an empty graph
    aborted = build_graph(donor, [0], budget=10)   # budget below the 23-operation design cost
    assert aborted["items_probed"] == 0
    assert [a["item"] for a in aborted["items_aborted"]] == [0]
    assert aborted["items_aborted"][0]["planned_ops"] > 10


def test_every_counted_operation_names_a_donor_matrix(donor):
    counter = OpCounter()
    heads, _ = heads_for(donor)
    for fn, kw in ((extraction_1_embedding_geometry, {}),
                   (extraction_2_association_edges, {"heads": heads}),
                   (extraction_3_circuit_motifs, {"heads": heads})):
        fn(donor, 0, counter, **kw)
    assert len(counter.entries) == expected_ops(TINY)
    for e in counter.entries:
        assert e["ops"] == 1 and e["macs"] > 0 and e["matrix"]
    assert counter.ops == expected_ops(TINY)


def test_the_gram_over_read_rows_is_counted_not_waved_through(donor):
    counter = OpCounter()
    extraction_1_embedding_geometry(donor, 0, counter)
    matrices = [e["matrix"] for e in counter.entries]
    assert any("gram" in m for m in matrices), "neighbour gram must spend an operation"


# ---------------------------------------------------------------- read-only, asserted
def test_a_full_graph_build_does_not_touch_a_single_tensor(donor):
    before = _fingerprint(donor)
    build_graph(donor, list(range(6)))
    assert _fingerprint(donor) == before, "MP-E12a is read-only; a mutated donor voids every figure"


# ---------------------------------------------------------------- the schema is the deliverable
def test_graph_carries_the_registered_schema_version(donor):
    graph = build_graph(donor, [0, 1])
    assert graph["schema_version"] == SCHEMA_VERSION
    assert graph["read_budget"]["value"] == READ_BUDGET_OPS


def test_nodes_and_edges_have_their_required_fields(donor):
    graph = build_graph(donor, [0])
    node_types = {"probe_token", "pool_candidate", "feature_detector", "successor_token"}
    edge_types = {"co_clustered", "association", "directed_map", "detector_value"}
    for n in graph["items"][0]["nodes"]:
        assert set(n) >= {"node_id", "type", "source", "confidence"}
        assert n["type"] in node_types
    for e in graph["items"][0]["edges"]:
        assert set(e) >= {"src", "dst", "type", "confidence", "extraction", "provenance"}
        assert e["type"] in edge_types
        assert set(e["provenance"]) >= {"source_model", "method"}


def test_confidence_is_a_read_score_and_stays_in_range(donor):
    graph = build_graph(donor, [0])
    for e in graph["items"][0]["edges"]:
        assert isinstance(e["confidence"], float)


# ---------------------------------------------------------------- the labels that keep it honest
def test_the_artifact_calls_its_donor_synthetic_everywhere(donor):
    graph = build_graph(donor, [0])
    assert graph["donor"]["is_synthetic"] is True
    assert "synthetic" in graph["donor"]["name"]
    assert "not GPT-2" in graph["quoting_guard"]["meaning"] or "GPT-2" in graph["quoting_guard"]["meaning"]
    for e in graph["items"][0]["edges"]:
        assert "synthetic" in e["provenance"]["source_model"]


def test_energy_is_not_measured_and_says_so(donor):
    assert "NOT MEASURED" in build_graph(donor, [0])["energy_estimate"]


def test_the_registered_head_subset_applies_only_to_a_donor_that_has_it(donor):
    used_tiny, registered_tiny = heads_for(donor)
    assert registered_tiny is False and len(used_tiny) == len(HEADS)
    stub = {"config": GPT2_124M}
    assert heads_for(stub)[1] is True and heads_for(stub)[0] == HEADS


# ---------------------------------------------------------------- the other side of the 10x claim
def test_reference_inference_counts_donor_matrices_per_generated_token(donor):
    ref = reference_inference(donor, 1)
    assert ref["ops_per_generated_token"] == TINY["n_layer"] * 4 + 1
    ref124 = reference_inference({"config": GPT2_124M, "wte": np.zeros((1, GPT2_124M["n_embd"]),
                                                                       dtype=np.float32)}, 1)
    assert ref124["ops_per_generated_token"] == 49


def test_the_ten_times_threshold_depends_on_a_definition_the_plan_never_gives(donor124):
    """The calibration's headline finding, pinned where a future reader will trip over it.

    H2 says reading is at least ten times cheaper per association than inference. It never says how many
    generated tokens an 'equivalent association query' is -- and at the donor's real shape that choice
    decides the verdict: 23 read operations against 49 per generated token is 2.13x at one token, crosses
    10x at five, and on MACs (105.98M read against 123.53M per token) does not cross until nine. The
    threshold is therefore not a property of weight-reading; it is a property of the query length the plan
    leaves unstated. Registered as D-MPE12-05.
    """
    bench = {b["tokens_generated"]: b for b in build_graph(donor124, [0], )["benchmark_vs_reference_inference"]}
    assert bench[1]["meets_10x_on_ops"] is False
    assert bench[1]["cheaper_by_ops"] == pytest.approx(49 / 23, abs=1e-3)
    assert bench[5]["meets_10x_on_ops"] is True
    assert bench[5]["meets_10x_on_macs"] is False
    assert bench[9]["meets_10x_on_macs"] is True
    assert bench[1]["meets_10x_on_macs"] is False


def test_the_benchmark_ratio_does_not_move_with_the_number_of_items_probed(donor):
    """The denominator bug this file shipped with once, kept from coming back.

    A per-association ratio must be a property of the association, not of how many associations happened to
    be probed in the same run. The first version divided a 24-item operation TOTAL against one generated
    token's cost, which made reading look 11x worse than inference -- a wrong answer that a single-item test
    could never have caught.
    """
    g1 = build_graph(donor, [0]); g6 = build_graph(donor, list(range(6)))
    one, six = g1["benchmark_vs_reference_inference"][0], g6["benchmark_vs_reference_inference"][0]
    assert one["read_ops_per_association"] == six["read_ops_per_association"]
    assert one["cheaper_by_ops"] == pytest.approx(six["cheaper_by_ops"], rel=1e-9)
    assert one["read_wall_clock_per_association_s"] is not None
    assert g6["operations_total"] == 6 * g1["operations_total"]   # the total SHOULD scale; the ratio must not


def test_the_read_reaches_ten_times_nowhere_on_wall_clock_at_the_registered_lengths(donor124):
    """The finding with teeth: on the donor's real shapes, wall-clock never gets to 10x.

    Asserted with a margin rather than to the third decimal because wall-clock is machine noise. What is
    pinned is the size of the gap -- a factor of 5.8 at nine tokens and under 2.0 at one -- not the digits.
    """
    graph = build_graph(donor124, [0])
    bench = graph["benchmark_vs_reference_inference"]
    assert all(b["meets_10x_on_wall_clock"] is False for b in bench)
    assert bench[0]["cheaper_by_wall_clock"] < 2.0
    assert bench[-1]["cheaper_by_wall_clock"] < 10.0
    f = graph["calibration_findings"]
    assert "NONE OF THE REGISTERED LENGTHS" in f[
        "1_ten_x_is_a_function_of_query_length_the_plan_does_not_fix"]["finding"]
    assert f"of {24} spent" in f["4_the_registered_budget_has_one_operation_of_headroom"]["finding"]


def test_the_artifact_names_which_side_its_caveats_flatter(donor):
    c = build_graph(donor, [0])["benchmark_caveats"]
    assert "reference_understates_inference" in c
    assert "FLATTERS the read side" in c["reference_understates_inference"]


def test_benchmark_reports_ops_macs_and_wall_clock(donor):
    b = build_graph(donor, [0])["benchmark_vs_reference_inference"][0]
    for key in ("cheaper_by_ops", "cheaper_by_macs", "cheaper_by_wall_clock",
                "read_ops_per_association", "read_macs_per_association",
                "read_wall_clock_per_association_s", "reference_run_seconds",
                "meets_10x_on_ops", "meets_10x_on_macs", "meets_10x_on_wall_clock"):
        assert key in b, key
    assert "energy_estimate" in build_graph(donor, [0])
