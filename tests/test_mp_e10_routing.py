"""MP-E10 step 2 tests: both routing variants exist, are gated, and are measured without being chosen.

No test here asserts that one variant is better. That would be the answer to D-MPE10-03, which is the PI's
to give; what is pinned is the machinery, the gating, the exclusion semantics, and the C5 test's structure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e10_routing import (ALPHABET, FLAG_ENV, N_POOLS, POOL_FLOOR, PROBE_BATTERY, VARIANTS,
                                  ablation, pool_vector, project, routing_flag, run_battery,
                                  score_candidates, variant_i_drive, variant_ii_mask)
from tools.mp_e10_working_memory import DecayedTrace, unigram_context

POOLS = [pool_vector(i) for i in range(N_POOLS)]


def _trace(seq, k=8):
    t = DecayedTrace(k=k, dim=64)
    for w in seq:
        t.push(project(w))
    return t


# ------------------------------------------------------------------ the flag
def test_default_flag_is_off_and_off_is_the_legacy_path_not_a_third_variant(monkeypatch):
    monkeypatch.delenv(FLAG_ENV, raising=False)
    assert routing_flag() == "off"
    seq = ["w00", "w03"]
    t = _trace(seq)
    off = score_candidates(ALPHABET, t, flag="off", context_vecs=[project(w) for w in seq])
    expected = [float(np.dot(unigram_context([project(w) for w in seq]), project(c))) for c in ALPHABET]
    assert off["ranking"][0] == ALPHABET[int(np.argmax(expected))]


@pytest.mark.parametrize("bad", ["variant_iii", "primary", "nonsense", "i"])
def test_an_unknown_flag_is_an_error_not_a_silent_default(bad):
    with pytest.raises(ValueError):
        routing_flag(override=bad)


def test_all_four_conditions_are_accepted_and_none_is_a_no_op():
    t = _trace(["w01", "w02"])
    for f in VARIANTS:
        assert routing_flag(override=f) == f
        r = score_candidates(ALPHABET, t, flag=f)
        assert r["flag"] == f and r["mechanism"] and r["ranking"]


def test_env_var_gating_actually_gates(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "variant_ii")
    assert routing_flag() == "variant_ii"
    monkeypatch.setenv(FLAG_ENV, "variant_i")
    assert routing_flag() == "variant_i"


# ------------------------------------------------------------------ variant i: a drive, never a veto
def test_variant_i_returns_bounded_amplitude_pairs_and_never_excludes():
    t = _trace(["w00", "w05", "w09"], k=4)
    drive = variant_i_drive(t, POOLS)
    assert all(isinstance(i, int) and 0 <= i < N_POOLS and abs(a) <= 1.0 for i, a in drive)
    assert score_candidates(ALPHABET, t, flag="variant_i")["excluded"] == [], \
        "variant_i weights options; it must not remove them"


def test_an_empty_trace_injects_no_drive():
    assert variant_i_drive(DecayedTrace(k=4, dim=64), POOLS) == []


# ------------------------------------------------------------------ variant ii: a mask, floored
def test_variant_ii_keeps_at_least_the_floor_pools_legal():
    mask = variant_ii_mask(_trace(["w03"]))
    assert POOL_FLOOR <= len(mask) <= N_POOLS
    assert mask == sorted(set(mask)) and all(0 <= m < N_POOLS for m in mask)


def test_a_mask_excludes_some_candidates_but_never_vetoes_everything():
    r = score_candidates(ALPHABET, _trace(["w06"] * 5, k=2), flag="variant_ii")
    assert len(r["excluded"]) == len(ALPHABET) - POOL_FLOOR
    assert not set(r["excluded"]) & set(r["ranking"]), "an excluded candidate must never appear in a ranking"


def test_both_flag_still_excludes_even_though_the_drive_is_active():
    """The C5 condition, mechanically: 'both' is mask AND drive, so exclusion survives injection."""
    t = _trace(["w06"] * 5, k=2)
    assert score_candidates(ALPHABET, t, flag="both")["excluded"] == \
        score_candidates(ALPHABET, t, flag="variant_ii")["excluded"]


# ------------------------------------------------------------------ determinism and read-only
def test_selection_does_not_mutate_the_working_memory_state():
    t = _trace(["w00", "w01", "w02"], k=4)
    before = t.fingerprint()
    for f in VARIANTS:
        score_candidates(ALPHABET, t, flag=f)
    assert t.fingerprint() == before, "routing is a read; a selection that perturbs the trace is a second organ"


def test_the_same_sequence_selects_the_same_word():
    a = ablation(["w03", "w07", "w11"], ALPHABET, k=8)
    b = ablation(["w03", "w07", "w11"], ALPHABET, k=8)
    assert a["winners"] == b["winners"]
    assert a["trace_fingerprint_after_run"] == b["trace_fingerprint_after_run"]


# ------------------------------------------------------------------ the ablation and its guard
def test_ablation_runs_every_flag_once_and_reports_the_c5_test():
    art = run_battery(k=8)
    assert art["n_probes"] == len(PROBE_BATTERY) and art["flags_run"] == list(VARIANTS)
    for p in art["probes"]:
        assert set(p["result"]["per_flag"]) == set(VARIANTS)
        c5 = p["result"]["c5_ablation_test"]
        assert {"condition", "variants_disagree",
                "verdict_if_any_of_these_is_true"} <= set(c5)
        assert "ABLA" in c5["verdict_if_any_of_these_is_true"].upper()


def test_the_battery_artifact_carries_a_guard_naming_the_open_decisions():
    g = run_battery(k=8)["quoting_guard"]
    assert "D-MPE10-02" in g["meaning"] and "D-MPE10-03" in g["meaning"]
    assert "not a scored MP-E10 run" in g["meaning"]
    assert "house-side wiring" in g["what_it_does_not_measure"]


def test_k_changes_the_trace_and_therefore_can_change_the_drive():
    """k is a constructor argument, so routing must be able to depend on it -- without requiring it to."""
    a = ablation(["w00", "w01", "w02", "w03", "w04", "w05"], ALPHABET, k=2)
    b = ablation(["w00", "w01", "w02", "w03", "w04", "w05"], ALPHABET, k=6)
    assert a["trace_fingerprint_after_run"] != b["trace_fingerprint_after_run"], \
        "two k values with the same sequence must not leave the same state, or k is doing nothing here"
