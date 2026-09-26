"""Substrate tests: carve integrity, role sets, compartment pools, control."""

from __future__ import annotations

import numpy as np
import pytest

from connectome.substrate import build_core_graph

def test_carve_scale_matches_source_project(graph):
    m = graph.meta
    assert graph.n_nodes == 12_867
    assert m["n_static_edges"] == 173_294
    assert m["n_plastic_edges"] == 2_983

def test_role_sets_sane(graph):
    g = graph
    assert len(g.kc_idx) == 4419
    assert len(g.mbon_idx) == 85
    assert len(g.dan_idx) == 83
    assert len(g.pn_idx) == 382
    s = g.input_slices()
    assert len(s["pos_x"]) == 32 and len(s["scent"]) == 8

def test_mbon_pools_are_12_compartments_with_source_pool_sizes(graph):
    pools = graph.mbon_pools
    assert len(pools) == 12
    assert [len(p) for p in pools] == [8, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]
    assert sum(len(p) for p in pools) == 85
    all_mb = np.concatenate(pools)
    assert len(np.unique(all_mb)) == 85

def test_plastic_synapses_are_kc_to_mbon(graph):
    kc, mb = set(graph.kc_idx.tolist()), set(graph.mbon_idx.tolist())
    assert all(int(p) in kc for p in graph.plastic_pre)
    assert all(int(q) in mb for q in graph.plastic_post)
    assert np.all(np.sign(graph.plastic_w0[graph.plastic_w0 != 0]) != 0)

def test_static_graph_is_row_normalized_and_signed(graph):
    W = graph.W
    row_abs = np.abs(W).sum(axis=1).A.ravel()
    assert np.allclose(row_abs[row_abs > 0], 0.5)
    signs = np.sign(W.data)
    assert (signs > 0).any() and (signs < 0).any()

def test_degree_matched_control(graph):
    real = graph
    control = build_core_graph(control=True, seed=0)
    assert np.array_equal(real.node_ids, control.node_ids)
    assert np.array_equal(np.diff(real.W.indptr), np.diff(control.W.indptr))
    assert np.array_equal(real.plastic_pre, control.plastic_pre)
    assert np.array_equal(real.plastic_post, control.plastic_post)
    assert np.array_equal(real.plastic_w0, control.plastic_w0)
    assert not np.array_equal(real.W.indices, control.W.indices)