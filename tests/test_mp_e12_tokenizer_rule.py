"""Tests for the tokenizer landing, the BPE probe rule, and the clustering limitation.

Three claims hold this step together, and each is checked rather than asserted in prose: the tokenizer bytes are
the bytes the provenance says they are; probe list v1 is untouched, proved against the SEALED hash rather than
against my own memory of writing it; and the cost table in the limitation document reproduces the sealed run's
own tallies, so the arithmetic used to advise the PI is the arithmetic that produced the figures.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DONOR = ROOT / "experiments/MP-E12/donor/gpt2"
V1 = "experiments/MP-E12/results/probe_list_v1.json"
V2 = "experiments/MP-E12/results/probe_list_v2_rule.json"
CLUST = "experiments/MP-E12/results/clustering_limitation_v1.json"
TOK_PROV = "experiments/MP-E12/donor/gpt2/PROVENANCE_tokenizer.json"
G1 = "experiments/MP-E12/results/association_graph_real_class1.json"
SYN = "experiments/MP-E12/results/probes_synthetic_calibration.json"
LEDGER = "experiments/MP-E12/registration.json"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def imports_of(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split(".")[0])
    return out


# ------------------------------------------------------------------ 1. the tokenizer landed as data
def test_every_tokenizer_file_on_disk_matches_its_provenance_hash():
    prov = load(TOK_PROV)
    assert len(prov["files"]) == 4
    for e in prov["files"]:
        path = DONOR / e["file"]
        assert path.exists(), e["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == e["sha256"], f"{e['file']} hash drifted from the provenance record"
        assert path.stat().st_size == e["bytes"], e["file"]


def test_the_tokenizer_is_pinned_to_the_same_revision_as_the_weights():
    prov = load(TOK_PROV)
    weights = load("experiments/MP-E12/donor/gpt2/PROVENANCE_gpt2.json")
    assert prov["source"]["revision_pinned"] == weights["source"]["revision_pinned"]
    assert prov["source"]["same_revision_as_the_weights"] is True
    assert prov["source"]["licence_text_reference"] == weights["source"]["licence_text_reference"]


def test_vocab_bpe_is_recorded_as_absent_with_the_measurement_not_an_assumption():
    prov = load(TOK_PROV)
    absent = {a["file"]: a for a in prov["absent_at_this_revision"]}
    assert "vocab.bpe" in absent
    assert "404" in absent["vocab.bpe"]["measured"], "the absence must be a measured HTTP status"
    assert not (DONOR / "vocab.bpe").exists()


def test_the_tokenizer_provenance_agrees_with_the_weights_provenance():
    prov = load(TOK_PROV)
    weights = load("experiments/MP-E12/donor/gpt2/PROVENANCE_gpt2.json")
    wfiles = {f["file"]: f["sha256"] for f in weights["files"]}
    for e in prov["files"]:
        if e["file"] in wfiles:
            assert e["sha256"] == wfiles[e["file"]], f"{e['file']} disagrees between two provenance files"
            assert e["matches_the_weights_provenance_record"] is True


@pytest.mark.parametrize("rel", ["tools/mp_e12_land_tokenizer.py", "tools/mp_e12_bpe_probe_rule.py",
                                 "tools/mp_e12_register_clustering_limitation.py"])
def test_no_donor_runtime_on_the_tokenizer_path(rel):
    banned = {"torch", "transformers", "tokenizers", "tensorflow", "jax", "flax", "keras", "numpy"}
    got = sorted(imports_of(rel) & banned)
    assert not got, f"{rel} imports donor runtime {got}"


def test_the_bpe_rule_is_arithmetic_over_data_files_not_a_library_call():
    src = (ROOT / "tools/mp_e12_bpe_probe_rule.py").read_text(encoding="utf-8")
    assert "merges.txt" in src and "vocab.json" in src
    assert "model.safetensors" not in src, "the BPE rule must not be able to read a weight byte"
    assert "DonorAddressSpace" not in src and "read_row" not in src.split('"""')[2]


# ------------------------------------------------------------------ 2. v1 is untouched, proved by the seal
def test_probe_list_v1_is_byte_identical_to_its_sealed_hash():
    sealed = load(LEDGER)["harness_hashes"]["files"][V1]
    disk = hashlib.sha256((ROOT / V1).read_bytes()).hexdigest()
    assert disk == sealed["sha256_lf"], "v1 was modified; the deferral list is supposed to survive intact"


def test_the_24_registered_probes_are_still_the_probes_of_record():
    v1, v2 = load(V1), load(V2)
    ids = [p["token_id"] for p in v1["probes"]]
    assert v2["relation_to_v1"]["probes_of_record"] == ids
    assert v2["relation_to_v1"]["n_probes_of_record"] == 24
    assert v2["relation_to_v1"]["v1_modified"] is False
    assert v2["relation_to_v1"]["v1_deferral_list_modified"] is False
    assert v2["status"].startswith("RULE REGISTERED, NOT APPLIED")
    assert v2["what_this_step_did_not_do"]["no_extraction"] is True
    assert v2["what_this_step_did_not_do"]["no_new_probe_authorized"] is True


def test_the_encoder_reproduces_every_id_v1_recorded_from_its_own_registered_form():
    v2 = load(V2)
    sc = v2["self_check"]
    assert sc["reproduced"] == sc["of"] == 24, sc
    assert sc["mismatches"] == []
    assert "nora" in v2["a_finding_the_self_check_produced"]["word"]


def test_the_17_deferred_words_genuinely_have_no_single_token_form():
    v2 = load(V2)
    table = v2["table_of_the_17"]
    assert len(table) == 17
    assert all(r["n_tokens"] >= 2 for r in table), "if one resolved to a single token, v1 deferred it wrongly"
    assert not any(r["any_candidate_is_a_single_token"] for r in table)
    assert v2["counts"]["resolve_to_one_token_under_bpe"] == 0
    assert v2["counts"]["total_rows"] == sum(r["n_tokens"] for r in table)
    for r in table:
        assert len(r["candidate_forms_under_v1_precedence"]) == 4, "the rule inherits v1's precedence, four forms"


def test_the_rule_states_what_a_sub_token_result_cannot_support():
    v2 = load(V2)
    cannot = " ".join(v2["what_a_sub_token_result_cannot_support"])
    assert "not one row" in cannot or "does not" in cannot
    assert any("mean" in s for s in v2["what_a_sub_token_result_cannot_support"])
    assert "no forward pass" in cannot or "behavioural" in cannot
    assert v2["the_rule"]["probe_object"].startswith("a SEQUENCE")


# ------------------------------------------------------------------ 3. the clustering limitation
def test_the_degeneracy_is_measured_from_the_sealed_artifacts_not_asserted():
    g, syn, doc = load(G1), load(SYN), load(CLUST)
    comps = [len(i["detail"].get("pool_clusters", [])) for i in g["items"]]
    sizes = [len(c) for i in g["items"] for c in i["detail"].get("pool_clusters", [])]
    assert set(comps) == {1} and set(sizes) == {10} and len(sizes) == 24
    syn_sizes = [len(c) for i in syn["items"] for c in i["detail"].get("pool_clusters", [])]
    assert set(syn_sizes) == {10}, "the degeneracy must also show on the synthetic donor, or it is a " \
                                   "finding about the real one"
    assert doc["the_finding_as_measured"]["components_per_item"] == {"1": 24}
    assert doc["the_finding_as_measured"]["also_true_of_the_synthetic_calibration"]


def test_the_cost_table_reproduces_the_sealed_run_tallies():
    g, doc = load(G1), load(CLUST)
    row = doc["cost_of_the_current_registration"]
    t = g["accounting_tallies"]
    assert row["registered_ops_run"] == t["registered_rule"]["operations"] == 48
    assert row["conservative_ops_run"] == t["conservative_reading"]["operations"] == 96
    assert row["per_row_ops_run"] == t["per_row_reading_reported_not_run_under"]["operations"] == 1584
    assert row["pool_rows"] == 63


def test_the_cost_table_is_monotone_and_names_where_the_caps_bind():
    doc = load(CLUST)
    tab = doc["cost_table_across_pool_sizes"]
    calls = [tab[str(p)]["read_calls_per_item"] for p in (63, 255, 511, 1023, 2047, 50257)]
    assert calls == sorted(calls) and calls[0] == 2 and calls[-1] == 787
    assert tab["50257"]["conservative_ops_per_item"] == 789
    assert tab["2047"]["fits_24_conservative"] is False
    assert all(v["fits_24_registered"] for v in tab.values()), "the registered rule prices every pool at 2 ops"


def test_no_cap_was_raised_to_make_any_option_fit():
    from tools.mp_e12_address_space import MAX_READS_PER_PROBE, MAX_ROWS_PER_READ
    from tools.mp_e12_pool_rule import POOL_CAP
    from tools.mp_e12_probes import READ_BUDGET_OPS
    doc = load(CLUST)
    assert doc["what_may_not_happen"]["no_cap_raised_here"]
    assert MAX_ROWS_PER_READ == 64 and MAX_READS_PER_PROBE == 256 and POOL_CAP == 63 and READ_BUDGET_OPS == 24
    assert doc["proposal_to_the_pi"]["if_yes"].count("1,023") or "1,023" in doc["proposal_to_the_pi"]["if_yes"]


def test_the_limitation_does_not_rewrite_the_sealed_graph():
    sealed = load(LEDGER)["harness_hashes"]["files"][G1]
    disk = hashlib.sha256((ROOT / G1).read_bytes()).hexdigest()
    assert disk == sealed["sha256_lf"], "the sealed class-1 graph must be byte-identical after this step"


def test_the_registration_records_that_nothing_was_extracted():
    doc = load(CLUST)
    assert doc["status"].startswith("LIMITATION REGISTERED WITH A PROPOSAL")
    assert doc["no_reads_in_this_step"]["donor_bytes_read_by_this_tool"] == 0
    assert doc["what_may_not_happen"]["no_choice_after_a_result"].startswith("neither A nor B may be picked")
