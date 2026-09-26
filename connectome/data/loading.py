
from __future__ import annotations

import numpy as np
import pandas as pd

from connectome.paths import CONNECTIONS_CSV, NEURON_CSV

NEURON_ID_COL = "Root ID"
PRE_COL = "pre_root_id"
POST_COL = "post_root_id"
SYN_COL = "syn_count"
NEUROPIL_COL = "neuropil"
EDGE_NT_COL = "nt_type"

NEURON_NT_PRED_COL = "Predicted NT type"
NEURON_NT_VER_COL = "Verified NT type"

EXPECTED_NEURON_COLS = 21
EXPECTED_CONN_COLS = 5

INT64_MAX = np.int64(2**63 - 1)

class IDIntegrityError(RuntimeError):
    """Raised when a root ID cannot round-trip losslessly through int64."""

def _parse_ids_int64(raw: pd.Series, col_name: str) -> pd.Series:
    """Parse an ID column from string -> int64 with lossless round-trip check."""
    if raw.dtype.kind == "f":
        raise IDIntegrityError(
            f"{col_name}: float dtype input for ID column is forbidden "
            "(64-bit root IDs exceed float53 precision)"
        )
    as_str = raw.astype(str).str.strip()
    try:
        ids = as_str.map(np.int64)
    except ValueError as exc:
        raise IDIntegrityError(f"{col_name}: non-integer ID values ({exc})") from exc
    if (ids.astype(str) != as_str).any():
        bad = as_str[ids.astype(str) != as_str].head(3).tolist()
        raise IDIntegrityError(f"{col_name}: non-integer or lossy ID values: {bad}")
    if (ids > INT64_MAX - 1).any() or (ids < 0).any():
        raise IDIntegrityError(f"{col_name}: ID out of expected [0, int64) range")
    return ids

def load_neurons(path=None) -> pd.DataFrame:
    """Load neuron.csv.gz. All annotation columns read as strings; Root ID int64."""
    path = path or NEURON_CSV
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.shape[1] != EXPECTED_NEURON_COLS:
        raise ValueError(
            f"neuron table has {df.shape[1]} columns, expected {EXPECTED_NEURON_COLS}; "
            "quoted-field parsing is broken"
        )
    df[NEURON_ID_COL] = _parse_ids_int64(df[NEURON_ID_COL], NEURON_ID_COL)
    if df[NEURON_ID_COL].duplicated().any():
        raise IDIntegrityError("neuron table contains duplicate Root IDs")
    return df

def load_connections(path=None) -> pd.DataFrame:
    """Load connections_princeton.csv.gz. IDs int64, syn_count int64.

    Zero/negative synapse rows are dropped here (they encode no connection)
    and their count is returned via the `dropped_nonpositive` attribute.
    """
    path = path or CONNECTIONS_CSV
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.shape[1] != EXPECTED_CONN_COLS:
        raise ValueError(
            f"connection table has {df.shape[1]} columns, expected {EXPECTED_CONN_COLS}"
        )
    df[PRE_COL] = _parse_ids_int64(df[PRE_COL], PRE_COL)
    df[POST_COL] = _parse_ids_int64(df[POST_COL], POST_COL)
    df[SYN_COL] = df[SYN_COL].map(np.int64)
    nonpositive = int((df[SYN_COL] <= 0).sum())
    df = df[df[SYN_COL] > 0].reset_index(drop=True)
    df.attrs["dropped_nonpositive"] = nonpositive
    return df

def aggregate_pairs(connections: pd.DataFrame) -> pd.DataFrame:
    """Collapse (pre, post) pairs appearing in several neuropils into one
    weighted edge: syn_count summed; neuropil list retained for provenance."""
    agg = (
        connections.groupby([PRE_COL, POST_COL], sort=False)
        .agg(
            syn_count=(SYN_COL, "sum"),
            neuropils=(NEUROPIL_COL, lambda s: sorted(set(s))),
            n_neuropil_rows=(SYN_COL, "size"),
        )
        .reset_index()
    )
    return agg