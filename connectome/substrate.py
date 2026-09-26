
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import sparse

from connectome.data.loading import (
    NEURON_ID_COL,
    POST_COL,
    PRE_COL,
    SYN_COL,
    load_connections,
    load_neurons,
)
from connectome.data.neuropils import CX_NEUROPILS, MB_NEUROPILS
from connectome.data.subcircuit import attach_signs, induced_subgraph, neuropil_node_set
from connectome.paths import CACHE_DIR

CLASS_COL = "Class"
_CACHE_DIR = CACHE_DIR

N_POS_BINS = 16
POS_NEURONS_PER_BIN = 2
N_SCENT_BITS = 8

@dataclass
class CoreGraph:
    node_ids: np.ndarray
    W: sparse.csr_matrix
    plastic_pre: np.ndarray
    plastic_post: np.ndarray
    plastic_w0: np.ndarray
    pn_idx: np.ndarray
    kc_idx: np.ndarray
    mbon_idx: np.ndarray
    dan_idx: np.ndarray
    cx_in_idx: np.ndarray
    cx_out_idx: np.ndarray
    n_actions: int = 12
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.n_nodes = len(self.node_ids)

    @property
    def mbon_pools(self) -> list[np.ndarray]:
        """MBON indices partitioned round-robin into one pool per action.

        85 MBONs / 12 pools -> pool sizes (8,7,7,7,7,7,7,7,7,7,7,7)."""
        return [self.mbon_idx[a :: self.n_actions] for a in range(self.n_actions)]

    def input_slices(self) -> dict[str, np.ndarray]:
        """Partition PN ports into named sensory channels."""
        pn = self.pn_idx
        n_pos = N_POS_BINS * POS_NEURONS_PER_BIN
        return {
            "pos_x": pn[0:n_pos],
            "pos_y": pn[n_pos : 2 * n_pos],
            "goal_x": pn[2 * n_pos : 3 * n_pos],
            "goal_y": pn[3 * n_pos : 4 * n_pos],
            "scent": pn[4 * n_pos : 4 * n_pos + N_SCENT_BITS],
            "word": pn[4 * n_pos + N_SCENT_BITS : 4 * n_pos + N_SCENT_BITS + 64],
            "cx_goal": self.cx_in_idx[:128],
        }

def _signed_union_edges():
    """Signed induced-subgraph edges of the MB+CX union carve, disk-cached.

    The CSV loads + aggregation take ~30s; the result is immutable, so it is
    cached as parquet + roles JSON after the first computation.
    """
    import json

    _CACHE_DIR.mkdir(exist_ok=True, parents=True)
    edges_pq = _CACHE_DIR / "union_edges.parquet"
    roles_js = _CACHE_DIR / "union_roles.json"
    if edges_pq.exists() and roles_js.exists():
        signed = pd.read_parquet(edges_pq)
        roles = json.loads(roles_js.read_text(encoding="utf-8"))
        node_set = set(int(x) for x in roles["node_set"])
        cls = pd.Series(roles["class"])
        cls.index = pd.Index([np.int64(k) for k in roles["class"].keys()])
        return signed, cls, node_set, roles["exclusions"]

    neurons = load_neurons()
    conns = load_connections()
    targets = MB_NEUROPILS | CX_NEUROPILS
    nodes = neuropil_node_set(conns, targets)
    sub = induced_subgraph(conns, nodes)
    neuron_nt = neurons.set_index(NEURON_ID_COL)["Predicted NT type"]
    signed, exclusions = attach_signs(sub, neuron_nt)
    cls = neurons.set_index(NEURON_ID_COL)[CLASS_COL]

    signed.reset_index(drop=True).to_parquet(edges_pq)
    roles_js.write_text(json.dumps({
        "node_set": [int(x) for x in sorted(nodes)],
        "class": {str(int(k)): str(v) for k, v in cls.items()},
        "exclusions": exclusions,
    }), encoding="utf-8")
    return signed, cls, nodes, exclusions

def build_core_graph(control: bool = False, seed: int = 0, row_gain: float = 0.5,
                     n_actions: int = 12) -> CoreGraph:
    """Build the signed sparse core graph (or its degree-matched random control)."""
    signed, cls, node_set, exclusions = _signed_union_edges()
    node_ids = np.array(sorted(node_set), dtype=np.int64)
    index = pd.Index(node_ids)
    pos_of = pd.Series(np.arange(len(node_ids)), index=node_ids)

    kc = {int(r) for r in cls[cls == "kenyon_cell"].index} & node_set
    mbon = {int(r) for r in cls[cls == "mushroom_body_output_neuron"].index} & node_set
    dan = {int(r) for r in cls[cls == "mushroom_body_dopaminergic_neuron"].index} & node_set
    pn = {int(r) for r in cls[cls == "antennal_lobe_projection_neuron"].index} & node_set
    cx_in = {int(r) for r in cls[cls == "central_complex_input_neuron"].index} & node_set
    cx_out = {int(r) for r in cls[cls == "central_complex_output_neuron"].index} & node_set

    pre_idx = pos_of[signed[PRE_COL]].to_numpy()
    post_idx = pos_of[signed[POST_COL]].to_numpy()
    weights = (
        signed["sign"].to_numpy(dtype=np.float64) * np.log1p(signed[SYN_COL].to_numpy(dtype=np.float64))
    )

    is_plastic = np.array(
        [int(p) in kc and int(q) in mbon for p, q in zip(signed[PRE_COL], signed[POST_COL])]
    )

    static_mask = (~is_plastic) & (signed["sign"].to_numpy() != 0)
    n_modulatory = int((~is_plastic & (signed["sign"].to_numpy() == 0)).sum())
    pre_s = pre_idx[static_mask].copy()
    post_s = post_idx[static_mask].copy()
    w_s = weights[static_mask]
    N = len(node_ids)

    if control:
        rng = np.random.default_rng(seed)
        post_s = rng.permutation(post_s)
        all_i = np.arange(len(post_s))
        for _ in range(50):
            key = pre_s.astype(np.int64) * np.int64(N) + post_s.astype(np.int64)
            dup = pd.Series(key).duplicated(keep="first").to_numpy()
            if not dup.any():
                break
            dup_i = all_i[dup]
            free_i = all_i[~dup]
            partners = rng.choice(free_i, size=len(dup_i), replace=False)
            post_s[dup_i], post_s[partners] = post_s[partners].copy(), post_s[dup_i].copy()
        else:
            raise RuntimeError("control rewiring could not eliminate duplicates")

    W = sparse.coo_matrix((w_s, (post_s, pre_s)), shape=(N, N)).tocsr()
    W.sum_duplicates()
    row_abs = np.abs(W).sum(axis=1).A.ravel()
    row_abs[row_abs == 0] = 1.0
    W = sparse.diags(row_gain / row_abs) @ W

    plastic_pre = pre_idx[is_plastic]
    plastic_post = post_idx[is_plastic]
    plastic_w0 = weights[is_plastic]

    meta = {
        "control": bool(control),
        "seed": int(seed),
        "exclusions": exclusions,
        "row_gain": row_gain,
        "n_static_edges": int(W.nnz),
        "n_plastic_edges": int(len(plastic_w0)),
        "n_modulatory_edges_excluded_from_fast_graph": n_modulatory,
        "role_counts": {
            "kc": len(kc), "mbon": len(mbon), "dan": len(dan),
            "pn": len(pn), "cx_in": len(cx_in), "cx_out": len(cx_out),
        },
    }
    return CoreGraph(
        node_ids=node_ids,
        W=W,
        plastic_pre=plastic_pre,
        plastic_post=plastic_post,
        plastic_w0=plastic_w0,
        pn_idx=np.array(sorted(pos_of[list(pn)])),
        kc_idx=np.array(sorted(pos_of[list(kc)])),
        mbon_idx=np.array(sorted(pos_of[list(mbon)])),
        dan_idx=np.array(sorted(pos_of[list(dan)])),
        cx_in_idx=np.array(sorted(pos_of[list(cx_in)])),
        cx_out_idx=np.array(sorted(pos_of[list(cx_out)])),
        n_actions=int(n_actions),
        meta=meta,
    )