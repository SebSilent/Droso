
from __future__ import annotations

import numpy as np
import pandas as pd

from connectome.data.loading import (
    NEUROPIL_COL,
    POST_COL,
    PRE_COL,
    SYN_COL,
    aggregate_pairs,
)
from connectome.data.neurotransmitters import normalize_nt, resolve_sign

def neuropil_node_set(connections: pd.DataFrame, neuropils: frozenset[str]) -> set[int]:
    """Neurons touching at least one edge annotated with a target neuropil."""
    mask = connections[NEUROPIL_COL].isin(neuropils)
    sub = connections.loc[mask]
    return set(sub[PRE_COL]).union(sub[POST_COL])

def induced_subgraph(
    connections: pd.DataFrame, nodes: set[int]
) -> pd.DataFrame:
    """All rows with both endpoints in `nodes`, aggregated to weighted edges."""
    node_index = pd.Index(sorted(nodes))
    pre_in = connections[PRE_COL].isin(node_index)
    post_in = connections[POST_COL].isin(node_index)
    rows = connections.loc[pre_in & post_in]
    return aggregate_pairs(rows)

def attach_signs(
    edges: pd.DataFrame, neuron_nt: pd.Series
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Assign each edge a sign from the PRE-neuron's predicted NT.

    `neuron_nt`: Series indexed by root id with raw predicted NT labels.
    Returns (edges_with_sign, exclusions_dict). Excluded rows are DROPPED.
    """
    pre_nt = edges[PRE_COL].map(neuron_nt)
    normalized = pre_nt.map(normalize_nt)
    signs = normalized.map(resolve_sign)
    excluded_unknown = int(signs.isna().sum())
    out = edges.loc[signs.notna()].copy()
    out["nt"] = normalized[signs.notna()].to_numpy()
    out["sign"] = signs[signs.notna()].to_numpy(dtype=np.int8)
    stats = {
        "edges_in": int(len(edges)),
        "edges_excluded_unknown_nt": excluded_unknown,
        "distinct_excluded_presynaptic_ids": int(
            edges.loc[signs.isna(), PRE_COL].nunique()
        ),
    }
    return out, stats

def degree_stats(edges: pd.DataFrame) -> dict[str, float]:
    """Degree/weighted-degree summary over a collapsed edge table.

    Reports out-degree (unique targets) and out-strength (summed syn_count);
    symmetric in-degree info derived by stacking both directions.
    """
    out_deg = edges.groupby(PRE_COL)[POST_COL].nunique()
    in_deg = edges.groupby(POST_COL)[PRE_COL].nunique()
    out_str = edges.groupby(PRE_COL)[SYN_COL].sum()
    qs = [0.5, 0.9, 0.99]

    def summarize(s: pd.Series, prefix: str) -> dict[str, float]:
        base = {
            f"{prefix}_mean": float(s.mean()),
            f"{prefix}_max": int(s.max()),
            f"{prefix}_median": float(s.quantile(0.5)),
            f"{prefix}_p90": float(s.quantile(0.9)),
            f"{prefix}_p99": float(s.quantile(0.99)),
        }
        return base

    stats: dict[str, float] = {}
    stats.update(summarize(out_deg, "out_degree"))
    stats.update(summarize(in_deg, "in_degree"))
    stats.update(summarize(out_str, "out_strength"))
    stats["nodes"] = int(
        len(set(out_deg.index).union(in_deg.index))
    )
    stats["edges"] = int(len(edges))
    return stats