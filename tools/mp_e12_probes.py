"""MP-E12a: the three weight-reading extractions, under a hard per-item read budget, on TWO donors.

ONE CODE PATH, TWO SOURCES. The three extractions below ask a source for a row, a search domain, a layernorm
vector, a head slice. `SyntheticSource` answers from a numpy dict that is already in RAM; `RealDonorSource`
answers through the journaled address space, one capped read call at a time. The maths is written once, so a
figure from either donor is produced by the same arithmetic and the only thing that differs is what a read
COSTS. That is the point of the split: the sealed synthetic calibration stays runnable, byte-for-byte
reproducible in its structure, and it is labelled non-evidential in every field group.

READ-ONLY, AND THAT IS THE WHOLE CLAIM. Nothing here mutates a tensor, nothing here runs the donor: there is no
forward pass, no attention over a sequence, no sampling, no generated text. Each extraction multiplies a probe
vector by donor parameters and reads the result. `tests/test_mp_e12_probes.py` asserts the synthetic donor is
bit-identical after a full graph build, and `tests/test_mp_e12_real_source.py` asserts that the real path
writes a journal record for every value it touches and touches no mask buffer.

THE BUDGET IS IN THE READ PATH, NOT IN THE REPORT. `ReadBudgetExceeded` fires when an item would spend more
than the registered 24 operations. On the real source the check is made on the PLAN, from tensor shapes, BEFORE
any read is issued: performing 216 reads and then discarding the row would still have put 216 records in the
access journal, and C3's promise is that an over-budget item writes nothing. The post-hoc check stays too --
if an item ever spends more than it planned, that is a finding, not a rounding error.

TWO OPERATION TALLIES, EMITTED SIDE BY SIDE. The registered counting rule says one operation is a
vector-by-donor-matrix multiply or a similarity search, and that a GATHER OF ALREADY-READ ROWS IS NOT AN
OPERATION. Under that rule a full three-class item costs 23 operations. Under the conservative reading this run
adopted -- one operation charged for every journaled read call, however many values it returns -- the same item
costs 232, because it is 216 separate reads of the donor plus the 16 matrices they add up to. Both numbers are
in the artifact. The conservative reading is STRICTER than the rule, it was chosen before the first read, and
this file does not exploit the loophole while the ruling on it is open.

WHY A REFERENCE INFERENCE SIDE EXISTS AT ALL. H2's threshold is a comparison: reading at least ten times
cheaper per association than autoregressive inference. The read side is this file. The inference side is
`reference_inference`, which spends the donor-matrix operations a real generation loop would spend per generated
token, under the same registered counting rule. It is run for the SYNTHETIC donor only. Against the real donor
this file emits no latency ratio at all, because the threshold has never been re-based on the real shapes and a
ratio copied from the synthetic run would be a number about a machine that was not measured.
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_pool_rule import FORMULA as POOL_FORMULA, N_VOCAB, POOL_CAP, pool_for
from tools.mp_e12_synthetic_donor import GPT2_124M, TINY, build_donor, shape_manifest

REGISTRATION = "experiments/MP-E12/registration.json"
READ_BUDGET_OPS = 24                      # registered NUMBER; an item above it aborts (plan C3)
SCHEMA_VERSION = "droso.association_graph.v2"
SCHEMA_REVISION = ("v1 was the sealed synthetic calibration. v2 adds the two operation tallies, the source "
                   "kind, the candidate-pool rule and, on real nodes, the address each figure came from. v1 "
                   "artifacts are not rewritten: they carry their own version and stay reproducible.")
K_NEIGHBOURS, K_SUCCESSORS, K_NEURONS = 10, 5, 5
HEADS = [(0, 0), (3, 5), (7, 2), (11, 11)]   # registered (layer, head) subset
CLASSES = ("1_embedding_geometry", "2_association_edges", "3_circuit_motifs")

# the donor's real tensor names, as the header spells them. The PyTorch module path (`transformer.wte.weight`)
# is NOT in this file on purpose: it is the confusion the landing tool fell into first, and an address space
# that refuses it is the reason the bare name is written here.
REAL_TENSORS = {
    "wte": "wte.weight", "ln_f_weight": "ln_f.weight", "ln_f_bias": "ln_f.bias",
    "c_attn": "h.{l}.attn.c_attn.weight", "attn_c_proj": "h.{l}.attn.c_proj.weight",
    "mlp_c_fc": "h.{l}.mlp.c_fc.weight", "mlp_c_fc_bias": "h.{l}.mlp.c_fc.bias",
    "mlp_c_proj": "h.{l}.mlp.c_proj.weight",
}


class ReadBudgetExceeded(Exception):
    def __init__(self, item, planned_ops, budget, by_class=None, source_kind="synthetic"):
        super().__init__(f"item {item} would spend {planned_ops} operations against a budget of {budget} "
                         f"({source_kind} accounting)")
        self.item, self.planned_ops, self.budget = item, planned_ops, budget
        self.by_class, self.source_kind = by_class or {}, source_kind


class BulkReadNotPermitted(Exception):
    """Raised when the real source is asked for a whole matrix. It has no such method on purpose: the only
    way to get vocabulary-wide data through this path is a bounded pool, and a pool is a narrower question."""


class OpCounter:
    """Counts donor-matrix touches as registered: one op = one vector-by-donor-matrix multiply, or one
    similarity search against one donor matrix. Element-wise work and gathers of already-read rows are not
    ops, and attention between activation vectors touches no donor parameter so it is not an op either.

    The counter ALSO tallies read calls and rows touched, which the registered rule prices at zero. That is
    deliberate: the artifact has to show what the rule does not see, or the ruling on the rule has nothing to
    stand on. `entries` stays exactly the registered-operations log -- one entry per operation, each naming a
    donor matrix -- because tests and the sealed calibration read it as such.
    """

    def __init__(self):
        self.entries = []                 # (extraction, matrix, ops, macs)
        self.calls = []                   # one entry per journaled read call, from the source
        self.rows = []                    # rows touched per call, the per-row reading's basis

    def spend(self, extraction, matrix, ops, macs):
        self.entries.append({"extraction": extraction, "matrix": matrix, "ops": int(ops),
                             "macs": int(macs)})

    def note_call(self, tensor, rows, values, probe_id=""):
        self.calls.append({"tensor": tensor, "rows": int(rows), "values": int(values), "probe_id": probe_id})
        self.rows.append(int(rows))

    @property
    def ops(self):
        return sum(e["ops"] for e in self.entries)

    @property
    def macs(self):
        return sum(e["macs"] for e in self.entries)

    @property
    def read_calls(self):
        return len(self.calls)

    @property
    def rows_touched(self):
        return sum(self.rows)

    @property
    def values_returned(self):
        return sum(c["values"] for c in self.calls)

    @property
    def conservative_ops(self):
        """The stricter reading: registered operations, plus one charged operation per read call."""
        return self.ops + self.read_calls

    @property
    def per_row_ops(self):
        """Stricter still, reported but not run under: registered operations plus one per ROW touched."""
        return self.ops + self.rows_touched

    def per_extraction(self):
        out = {}
        for e in self.entries:
            d = out.setdefault(e["extraction"], {"ops": 0, "macs": 0, "matrices": []})
            d["ops"] += e["ops"]; d["macs"] += e["macs"]
            if e["matrix"] not in d["matrices"]:
                d["matrices"].append(e["matrix"])
        return out


# --------------------------------------------------------------------------- the two sources

class SyntheticSource:
    """The sealed calibration's donor: a numpy dict, already in memory. NON-EVIDENTIAL about GPT-2.

    It performs zero journaled read calls, so its conservative tally equals its registered one. That
    coincidence is the loophole in miniature and the artifact says so rather than letting a reader infer it:
    holding the whole matrix in RAM is what a free gather looks like.
    """

    kind = "synthetic"
    records_addresses = False

    def __init__(self, donor):
        self.d = donor
        self.cfg = donor["config"]

    @property
    def name(self):
        return self.d.get("name", "synthetic-124M-shaped-random")

    # NO dtype widening here, on purpose. The sealed calibration was built on the donor's own float32 arrays,
    # and a float64 copy changes the rounding of every dot product, which changes argsort tie-breaks and
    # therefore changes which tokens come back as neighbours. The first cut of this rewire cast to float64 and
    # silently produced a different graph from the same donor and the same seed; the regression check caught it.
    def _a(self, x):
        return np.asarray(x)

    @property
    def name(self):
        return self.d.get("name", "synthetic-124M-shaped-random")

    def probe_row(self, token_id, counter):
        return self._a(self.d["wte"][int(token_id)])

    def search_domain(self, token_id, counter):
        """Every row of wte: the global claim. Free here, and unaffordable against the real donor."""
        wte = self._a(self.d["wte"])
        return list(range(wte.shape[0])), wte

    def search_matrix_name(self):
        return "wte"

    def ln_f(self, counter):
        return self._a(self.d["ln_f_weight"]), self._a(self.d["ln_f_bias"])

    def head_value(self, layer, head, vec, counter):
        dh = self.cfg["d_head"]
        W = self._a(self.d["layers"][layer]["c_attn_weight"])
        return W[:, head * dh:(head + 1) * dh]

    def head_output(self, layer, head, vec, counter):
        dh = self.cfg["d_head"]
        W = self._a(self.d["layers"][layer]["attn_c_proj_weight"])
        return W[:, head * dh:(head + 1) * dh]

    def mlp_fc(self, layer, counter):
        return (self._a(self.d["layers"][layer]["mlp_c_fc_weight"]),
                self._a(self.d["layers"][layer]["mlp_c_fc_bias"]))

    def mlp_value_rows(self, layer, idxs, counter):
        return self._a(self.d["layers"][layer]["mlp_c_proj_weight"][idxs, :])

    def address(self, tensor_key, row, col=None):
        return None

    def donor_meta(self):
        return {"name": self.name, "is_synthetic": True, "param_count": self.d.get("param_count"),
                "config": self.cfg, "unembedding_tied_to_wte": True,
                "shapes": shape_manifest(self.d)["tensors"]}

    def plan(self, classes, token_id):
        """Analytic, from the design of the code path: the synthetic source has no calls to count."""
        reg = {"1_embedding_geometry": 2, "2_association_edges": 1 + len(HEADS),
               "3_circuit_motifs": len(HEADS) + self.cfg["n_layer"]}
        return {c: {"registered_ops": reg[c], "read_calls": 0, "conservative_ops": reg[c],
                    "rows_touched": 0} for c in classes}


class RealDonorSource:
    """The public GPT-2 library, through the journaled address space. Every value here has an address and a
    record behind it, and no method returns a whole matrix.

    Reads are cached per item, and the cache is REPORTED: a row fetched once and used by two classes is one
    read call, not two, and the artifact says which figures share a read. The planner does NOT give credit for
    the cache, because a plan that assumes a warm cache is a plan that changes when the classes change.
    """

    kind = "real"
    records_addresses = True

    def __init__(self, ax, cfg, probe_ids, journal_path):
        self.ax = ax
        self.cfg = cfg
        self.probe_ids = list(probe_ids)
        self.journal_path = journal_path
        self._cache = {}
        self.n_vocab = ax.shape(REAL_TENSORS["wte"])[0]
        # the config file does not state the MLP inner width, so the donor's own index does: c_fc is
        # [n_embd, mlp_inner] as stored. A shape read from the file beats the "4 * n_embd" convention, which
        # is a guess about a different model that happens to be true here.
        self.cfg = dict(cfg)
        self.cfg["mlp_inner"] = int(ax.shape(REAL_TENSORS["mlp_c_fc"].format(l=0))[1])
        self.cfg["n_embd"] = int(ax.shape(REAL_TENSORS["wte"])[1])
        self.cfg["n_layer"] = len({n.split(".")[1] for n in ax.tensor_names() if n.startswith("h.")})

    def reset_item(self, token_id):
        self._cache = {"token_id": int(token_id)}

    @property
    def name(self):
        return "gpt2-124M-public"

    def _read_row(self, tensor, row, counter, probe_id):
        if ("row", tensor, row) not in self._cache:
            vals = self.ax.read_row(tensor, row, probe_id=probe_id)
            counter.note_call(tensor, 1, len(vals), probe_id)
            self._cache[("row", tensor, row)] = np.asarray(vals, dtype=np.float64)
        return self._cache[("row", tensor, row)]

    def _read_rows(self, tensor, rows, counter, probe_id):
        out = []
        missing = [r for r in rows if ("row", tensor, r) not in self._cache]
        if missing:
            got = self.ax.read_rows(tensor, missing, probe_id=probe_id)
            counter.note_call(tensor, len(missing), sum(len(g) for g in got), probe_id)
            for r, g in zip(missing, got):
                self._cache[("row", tensor, r)] = np.asarray(g, dtype=np.float64)
        return np.asarray([self._cache[("row", tensor, r)] for r in rows], dtype=np.float64)

    def _read_full(self, tensor, counter, probe_id):
        """All rows of a 2-D tensor, in capped calls. This is what a column slice costs when the file stores
        the matrix row-major, and the registered rule prices it at zero operations."""
        if ("full", tensor) not in self._cache:
            rows = list(range(self.ax.shape(tensor)[0]))
            mat = self._read_rows(tensor, rows, counter, probe_id)
            self._cache[("full", tensor)] = mat
        return self._cache[("full", tensor)]

    def probe_row(self, token_id, counter):
        return self._read_row(REAL_TENSORS["wte"], int(token_id), counter, self._probe_id(token_id))

    def pool(self, token_id):
        return pool_for(int(token_id), [t for t in self.probe_ids if t != int(token_id)],
                        n_vocab=self.n_vocab)

    def search_domain(self, token_id, counter):
        ids = self.pool(token_id)
        pid = self._probe_id(token_id)
        return ids, self._read_rows(REAL_TENSORS["wte"], ids, counter, pid)

    def search_matrix_name(self):
        return f"{REAL_TENSORS['wte']} (candidate pool, {POOL_CAP} rows)"

    def ln_f(self, counter):
        pid = self._probe_id(self._cache.get("token_id"))
        wt = ("vec", REAL_TENSORS["ln_f_weight"])
        bs = ("vec", REAL_TENSORS["ln_f_bias"])
        for key, tensor in ((wt, REAL_TENSORS["ln_f_weight"]), (bs, REAL_TENSORS["ln_f_bias"])):
            if key not in self._cache:
                v = self.ax.read_vector(tensor, probe_id=pid)
                counter.note_call(tensor, 1, len(v), pid)
                self._cache[key] = np.asarray(v, dtype=np.float64)
        return self._cache[wt], self._cache[bs]

    def _column_slice(self, tensor, head, counter, pid):
        dh = self.cfg["d_head"]
        key = ("cols", tensor, head)
        if key not in self._cache:
            full = self._read_full(tensor, counter, pid)
            self._cache[key] = full[:, head * dh:(head + 1) * dh]
        return self._cache[key]

    def head_value(self, layer, head, vec, counter):
        return self._column_slice(REAL_TENSORS["c_attn"].format(l=layer), head, counter,
                                  self._probe_id(self._cache.get("token_id")))

    def head_output(self, layer, head, vec, counter):
        return self._column_slice(REAL_TENSORS["attn_c_proj"].format(l=layer), head, counter,
                                  self._probe_id(self._cache.get("token_id")))

    def mlp_fc(self, layer, counter):
        pid = self._probe_id(self._cache.get("token_id"))
        tensor = REAL_TENSORS["mlp_c_fc"].format(l=layer)
        bias_key = ("vec", REAL_TENSORS["mlp_c_fc_bias"].format(l=layer))
        if bias_key not in self._cache:
            v = self.ax.read_vector(REAL_TENSORS["mlp_c_fc_bias"].format(l=layer), probe_id=pid)
            counter.note_call(REAL_TENSORS["mlp_c_fc_bias"].format(l=layer), 1, len(v), pid)
            self._cache[bias_key] = np.asarray(v, dtype=np.float64)
        return self._read_full(tensor, counter, pid), self._cache[bias_key]

    def mlp_value_rows(self, layer, idxs, counter):
        return self._read_rows(REAL_TENSORS["mlp_c_proj"].format(l=layer), [int(i) for i in idxs], counter,
                               self._probe_id(self._cache.get("token_id")))

    def _probe_id(self, token_id):
        return f"extraction_e12a_item_{int(token_id)}"

    def donor_meta(self):
        prov = json.loads((ROOT / "experiments/MP-E12/donor/gpt2/PROVENANCE_gpt2.json").read_text(
            encoding="utf-8"))
        return {"name": self.name, "is_synthetic": False,
                "revision_pinned": prov["source"].get("revision_pinned"),
                "sha256": self.ax.sha256_of_file(),   # the file this source is reading, which for a fixture
                                                      # donor is not the module default
                "config": self.cfg, "unembedding_tied_to_wte": True,
                "journal": self.journal_path,
                "tensors_consulted": []}   # filled in after the run, from the reads actually recorded

    def address(self, tensor_key, row, col=None):
        """Where a figure came from, derived from the header without reading it. No journal record: this is
        arithmetic on offsets, and the claim it supports is 'which address, for which probe'."""
        tensor = REAL_TENSORS[tensor_key] if "{" not in REAL_TENSORS.get(tensor_key, "") else None
        if tensor is None:
            return None
        return self.ax.address_of(tensor, int(row), int(col) if col is not None else 0)

    def head_address(self, layer, head, which="c_attn"):
        tensor = REAL_TENSORS[which].format(l=layer)
        dh = self.cfg["d_head"]
        return {"tensor": tensor, "rows": [0, self.ax.shape(tensor)[0] - 1],
                "columns": [head * dh, (head + 1) * dh - 1],
                "first_value_byte_offset": self.ax.address_of(tensor, 0, head * dh)["byte_offset"]}

    def plan(self, classes, token_id):
        """Pre-flight arithmetic from the header. This is what makes a real budget event cost ZERO reads: the
        item is stopped on the plan, so an over-budget class never issues a read and never writes a record."""
        ax = self.ax
        sh = {k: ax.shape(v) for k, v in REAL_TENSORS.items() if "{" not in v}
        per_layer = {k: ax.shape(v.format(l=0)) for k, v in REAL_TENSORS.items() if "{" in v}
        cap = 64                                        # MAX_ROWS_PER_READ, as the instrument registers it
        calls = lambda rows: -(-int(rows) // cap)       # noqa: E731 -- ceiling division, used three times
        pool = len(self.pool(token_id))
        out = {}
        for c in classes:
            if c == "1_embedding_geometry":
                n_calls, n_rows = 2, 1 + pool
                reg = 2
            elif c == "2_association_edges":
                n_calls = (2 + len(HEADS) * calls(per_layer["c_attn"][0]) + 2)   # ln_f w/b, head slices, probe+pool
                n_rows = (2 * sh["ln_f_weight"][0]
                          + len(HEADS) * per_layer["c_attn"][0] + 1 + pool)
                reg = 1 + len(HEADS)
            else:
                n_calls = (len(HEADS) * calls(per_layer["attn_c_proj"][0])
                           + calls(per_layer["mlp_c_fc"][0]) * self.cfg["n_layer"]
                           + self.cfg["n_layer"]                                   # one c_fc bias per layer
                           + self.cfg["n_layer"]                                   # one neuron-value gather per layer
                           + 2)                                                    # probe row and pool, uncredited
                n_rows = (len(HEADS) * per_layer["attn_c_proj"][0]
                          + self.cfg["n_layer"] * per_layer["mlp_c_fc"][0]
                          + self.cfg["n_layer"] * per_layer["mlp_c_fc_bias"][0]
                          + self.cfg["n_layer"] * K_NEURONS + 1 + pool)
                reg = len(HEADS) + self.cfg["n_layer"]
            out[c] = {"registered_ops": reg, "read_calls": n_calls, "conservative_ops": reg + n_calls,
                      "rows_touched": n_rows}
        return out


def as_source(donor_or_source):
    """A raw numpy dict is the synthetic source; anything else is already a source object. Keeps the sealed
    call signature working, which is how the calibration stays runnable without a rewrite of its tests."""
    if isinstance(donor_or_source, (SyntheticSource, RealDonorSource)):
        return donor_or_source
    return SyntheticSource(donor_or_source)


def _normed(a):
    n = float(np.linalg.norm(a))
    return a / n if n > 0 else a


# --------------------------------------------------------------------------- the three extractions

def extraction_1_embedding_geometry(donor, token_id, counter, k=K_NEIGHBOURS):
    """Nearest-neighbour structure of the token-embedding matrix, clustered into candidate feature pools.

    One similarity search against wte. The clustering is mutual-nearest-neighbour linking over the ids already
    read, which touches no donor matrix and therefore spends no operation -- a consequence of the registered
    counting rule, stated here rather than left for a reader to infer. On the real source the domain is the
    bounded candidate pool, so the claim is 'nearest among these rows', not 'nearest in the vocabulary', and
    the artifact records the pool size beside every neighbour list.
    """
    src = as_source(donor)
    probe = src.probe_row(token_id, counter)
    ids, wte = src.search_domain(token_id, counter)
    sims = wte @ _normed(probe) / max(float(np.linalg.norm(probe)), 1e-12)
    counter.spend("1_embedding_geometry", src.search_matrix_name(), 1, wte.shape[0] * wte.shape[1])
    order = np.argsort(-sims)
    nbrs = [ids[int(i)] for i in order if ids[int(i)] != int(token_id)][:k]
    # Mutual-nearest-neighbour linking needs a gram over the k neighbour rows. Those rows are already read,
    # but the gram is still a multiply by a matrix assembled from donor rows, so it is COUNTED as one
    # operation rather than waved through as "element-wise". A budget that only counts what the author
    # remembered is not a budget.
    pos = {t: i for i, t in enumerate(ids)}
    rows = wte[[pos[t] for t in nbrs]]
    gram = rows @ rows.T
    counter.spend("1_embedding_geometry", f"{src.search_matrix_name()}[nbrs] gram (k rows of a donor matrix)",
                  1, len(nbrs) * len(nbrs) * wte.shape[1])
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
               "confidence": round(float(sims[pos[t]]), 6)} for t in nbrs]
    edges = [{"src": f"probe:{token_id}", "dst": f"succ:{t}", "type": "co_clustered",
              "confidence": round(float(sims[pos[t]]), 6), "extraction": "1_embedding_geometry",
              "provenance": {"source_model": src.name, "method": "embedding_geometry"}}
             for t in nbrs]
    if src.records_addresses:
        nodes[0]["address"] = src.address("wte", token_id)
        for nd in nodes[1:]:
            nd["address"] = src.address("wte", int(nd["node_id"].split(":")[1]))
    return nodes, edges, {"pool_clusters": pool, "neighbours": nbrs,
                          "search_domain_rows": len(ids),
                          "search_domain": "full vocabulary" if not src.records_addresses
                                           else f"candidate pool of {len(ids)} rows"}


def extraction_2_association_edges(donor, token_id, counter, heads=HEADS, k=K_SUCCESSORS):
    """Top-k associative successors read from the tied unembedding, plus each registered head's value read.

    Five operations: one multiply by wte (which IS the unembedding -- the tie is registered as a failure mode,
    because extraction 1 and this one read the same matrix and an agreement between them is partly
    arithmetic), and one per registered head's W_V slice.
    """
    src = as_source(donor)
    cfg = src.cfg; n = cfg["n_embd"]
    probe = src.probe_row(token_id, counter)
    ids, wte = src.search_domain(token_id, counter)
    ln, bias = src.ln_f(counter)   # the pre-unembedding norm, element-wise: no op
    scaled = (probe - probe.mean()) / (probe.std() + 1e-6) * ln + bias     # element-wise: no op spent
    logits = wte @ scaled
    counter.spend("2_association_edges", f"{REAL_TENSORS['wte'] if src.records_addresses else 'wte'} "
                                         f"(tied unembedding)", 1, wte.shape[0] * n)
    order = np.argsort(-logits)
    succ = [ids[int(i)] for i in order[:k]]
    nodes, edges = [], []
    for t in succ:
        nodes.append({"node_id": f"succ:{t}", "type": "successor_token", "source": "wte",
                      "confidence": round(float(logits[ids.index(t)]), 6)})
        edges.append({"src": f"probe:{token_id}", "dst": f"succ:{t}", "type": "association",
                      "confidence": round(float(logits[ids.index(t)]), 6), "extraction": "2_association_edges",
                      "provenance": {"source_model": src.name, "method": "unembedding_read"}})
    head_reads = {}
    for (layer, head) in heads:
        W = src.head_value(layer, head, probe, counter)
        v = W.T @ probe
        counter.spend("2_association_edges", f"h{layer}.{head}.W_V", 1, n * cfg["d_head"])
        head_reads[f"h{layer}.{head}"] = {"value_direction_norm": round(float(np.linalg.norm(v)), 6)}
    return nodes, edges, {"successors": succ, "head_value_reads": head_reads,
                          "donor_is_weight_tied": True}


def extraction_3_circuit_motifs(donor, token_id, counter, heads=HEADS, k=K_NEURONS):
    """Heads as directed association maps, MLP neurons as key-value feature detectors.

    Sixteen operations: one W_O slice per registered head, one c_fc per layer. The detector VALUES are rows
    gathered out of mlp_c_proj for the neurons that responded -- a gather of already-read rows, so it spends
    no operation under the registered rule, and the artifact says which is which rather than leaving a reader
    to guess whether the value read was counted.
    """
    src = as_source(donor)
    cfg = src.cfg; n = cfg["n_embd"]
    probe = src.probe_row(token_id, counter)
    nodes, edges, motifs = [], [], {"heads": {}, "neurons": {}}
    for (layer, head) in heads:
        # The head's output matrix maps its own d_head subspace into the residual stream. Reading that
        # slice against the probe is ONE multiply by ONE donor matrix, which is what keeps this extraction
        # inside the registered budget. An earlier draft also asked which token that direction is nearest
        # to -- a second read of wte per head, four uncounted operations, so it is dropped rather than
        # silently absorbed: a directed map is recorded as a direction, not as a word.
        W_O = src.head_output(layer, head, probe, counter)
        direction = W_O.T @ probe
        counter.spend("3_circuit_motifs", f"h{layer}.{head}.W_O", 1, cfg["d_head"] * n)
        key = f"h{layer}.{head}"
        motifs["heads"][key] = {"writes_direction_norm": round(float(np.linalg.norm(direction)), 6),
                               "written_in": "the head's own output subspace (d_head), not vocabulary space"}
        nodes.append({"node_id": f"map:{key}", "type": "feature_detector", "source": f"h{layer}.{head}.W_O",
                      "confidence": round(float(np.linalg.norm(direction)), 6)})
        edges.append({"src": f"probe:{token_id}", "dst": f"map:{key}", "type": "directed_map",
                      "confidence": round(float(np.linalg.norm(direction)), 6),
                      "extraction": "3_circuit_motifs",
                      "provenance": {"source_model": src.name, "method": "head_map"}})
    responded = {}
    for layer in range(cfg["n_layer"]):
        W_fc, b_fc = src.mlp_fc(layer, counter)
        pre = W_fc.T @ probe + b_fc
        counter.spend("3_circuit_motifs", f"L{layer}.c_fc", 1, n * cfg["mlp_inner"])
        top = [int(t) for t in np.argsort(-pre)[:k]]
        responded[f"L{layer}"] = top
        vals = src.mlp_value_rows(layer, top, counter).mean(axis=0)   # gather: no operation spent
        motifs["neurons"][f"L{layer}"] = {"top_neurons": top,
                                          "responses": [round(float(pre[t]), 6) for t in top],
                                          "mean_value_direction_norm": round(float(np.linalg.norm(vals)), 6)}
    return nodes, edges, motifs


def heads_for(donor, requested=HEADS):
    """The registered (layer, head) subset when the donor has one; the first valid pairs when it does not.

    The substitution exists so the tiny unit-test shape can run the same code path, and it is REPORTED in
    the item rather than hidden: an artifact built on a substituted subset says which.
    """
    cfg = donor["config"] if isinstance(donor, dict) else donor.cfg
    if all(layer < cfg["n_layer"] and head < cfg["n_head"] for layer, head in requested):
        return list(requested), True
    valid = [(l, h) for l in range(cfg["n_layer"]) for h in range(cfg["n_head"])]
    return valid[:len(requested)], False


CLASS_FN = {"1_embedding_geometry": (extraction_1_embedding_geometry, ()),
            "2_association_edges": (extraction_2_association_edges, ("heads",)),
            "3_circuit_motifs": (extraction_3_circuit_motifs, ("heads",))}


def probe_item(donor, token_id, budget=READ_BUDGET_OPS, classes=None, accounting="conservative"):
    """One probed association. Aborts before writing anything if it would exceed the budget.

    `accounting` selects which tally the budget is checked against. The synthetic calibration runs under
    "registered", as it always did; the real run runs under "conservative", which is the stricter reading
    registered before the first read. Choosing the looser word here would let a real item pass by invoking a
    loophole the run has said it will not use, so the choice is a parameter with a name that cannot be missed.
    """
    src = as_source(donor)
    classes = list(classes or CLASSES)
    counter = OpCounter()
    heads, registered = heads_for(src)
    plan = src.plan(classes, token_id)
    planned_ops = sum(p["conservative_ops" if accounting == "conservative" else "registered_ops"]
                      for p in plan.values())
    if planned_ops > budget:
        # pre-flight: on the real source this is where an over-budget item costs ZERO reads
        raise ReadBudgetExceeded(token_id, planned_ops, budget, plan, src.kind)
    if src.kind == "real":
        src.reset_item(token_id)
    nodes, edges, detail = [], [], {}
    for c in classes:
        fn, kw = CLASS_FN[c]
        n, e, d = fn(src, token_id, counter, **{k: heads for k in kw})
        nodes += n; edges += e; detail.update(d)
        if counter.ops > budget:                                  # C3, post-hoc as well: a plan is a claim
            raise ReadBudgetExceeded(token_id, counter.ops, budget, plan, src.kind)
    spent_registered = counter.ops
    if spent_registered != planned_ops and accounting == "conservative":
        detail["accounting_drift"] = {"planned": planned_ops, "actual_conservative": counter.conservative_ops}
    return {"item": int(token_id), "nodes": nodes, "edges": edges, "detail": detail,
            "registered_heads_used": registered, "head_subset": [list(h) for h in heads],
            "operations_spent": spent_registered, "macs_spent": counter.macs,
            "conservative_operations_spent": counter.conservative_ops,
            "per_row_operations_if_charged": counter.per_row_ops,
            "read_calls": counter.read_calls, "rows_touched": counter.rows_touched,
            "values_returned": counter.values_returned, "reads": counter.calls,
            "planned": plan, "extraction_classes": classes, "accounting": accounting,
            "per_extraction": counter.per_extraction(), "budget": budget,
            "aborted": False}


def reference_inference_run(donor, tokens_generated):
    """Spend, sequentially, the donor-matrix operations one autoregressive generation of k tokens pays.

    This is NOT a language model and does not produce text: no sampling, no attention between activations,
    no KV cache. It exists so H2's wall-clock side is a measurement on these shapes rather than a scaling of
    an op count, which would be the same number twice. Because it omits the activation-side work a real
    generation loop pays, it UNDERSTATES inference cost and therefore FLATTERS the read side; the artifact
    carries that caveat rather than burying the favourable direction.

    SYNTHETIC SOURCE ONLY. Against the real donor this would be a latency claim built on a path that is not
    the deployment path, and the >=10x threshold has not been re-based on the real shapes at all.
    """
    d = donor.d if isinstance(donor, SyntheticSource) else donor
    cfg = d["config"]; n = cfg["n_embd"]
    t0 = time.perf_counter()
    h = d["wte"][0].astype(np.float32).copy()
    for _ in range(tokens_generated):
        for blk in d["layers"]:
            qkv = blk["c_attn_weight"].T @ h                       # 1 donor matrix
            att = blk["attn_c_proj_weight"] @ qkv[:n]              # 1
            m = np.maximum(blk["mlp_c_fc_weight"].T @ att, 0.0)    # 1
            h = m @ blk["mlp_c_proj_weight"]                       # 1: (3072,) by (3072, 768)
            h = (h - h.mean()) / (h.std() + 1e-6)
        logits = d["wte"] @ h                                      # 1: the tied unembedding
        h = d["wte"][int(np.argmax(logits))].astype(np.float32).copy()
    return {"seconds": round(time.perf_counter() - t0, 6),
            "ops": (cfg["n_layer"] * 4 + 1) * tokens_generated}


def reference_inference(donor, tokens_generated):
    """The other side of H2's comparison: donor-matrix operations a generation loop spends per token."""
    d = donor.d if isinstance(donor, SyntheticSource) else donor
    cfg = d["config"]; n = cfg["n_embd"]
    ops_per_token = cfg["n_layer"] * 4 + 1          # c_attn, attn c_proj, mlp c_fc, mlp c_proj, unembed
    macs_per_token = cfg["n_layer"] * (n * 3 * n + n * n + n * cfg["mlp_inner"] + cfg["mlp_inner"] * n) \
        + d["wte"].shape[0] * n
    return {"tokens_generated": tokens_generated, "ops_per_generated_token": ops_per_token,
            "macs_per_generated_token": int(macs_per_token),
            "ops_for_this_association": ops_per_token * tokens_generated,
            "macs_for_this_association": int(macs_per_token) * tokens_generated,
            "counting_note": "attention between activation vectors touches no donor parameter matrix, so "
                             "under the registered counting rule it is not an operation on either side"}


def calibration_findings(bench, donor, items):
    """What the synthetic run taught, DERIVED from the rows above rather than typed in beside them."""
    d = donor.d if isinstance(donor, SyntheticSource) else donor
    cfg = d["config"]; n = cfg["n_embd"]

    def crossing(key):
        hits = [b["tokens_generated"] for b in bench if b[key]]
        return min(hits) if hits else None

    read_macs = bench[0]["read_macs_per_association"] if bench else 0
    vocab_macs = 2 * d["wte"].shape[0] * n           # the embedding search and the tied unembedding
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


def real_findings(items, aborted, plan_of_first_item):
    """What the real run taught, derived from the rows above. No latency figure appears here, because none was
    measured: the threshold's other side has not been re-based on these shapes."""
    reg = sum(i["operations_spent"] for i in items)
    cons = sum(i["conservative_operations_spent"] for i in items)
    calls = sum(i["read_calls"] for i in items)
    rows = sum(i["rows_touched"] for i in items)
    vals = sum(i["values_returned"] for i in items)
    return {
        "1_the_budget_is_a_statement_about_gathers": {
            "finding": f"{len(items)} class-1 items cost {reg} operations under the registered rule and {cons} "
                       f"under the conservative one, on {calls} read calls and {rows} rows",
            "consequence": "the registered 24-operation budget and a free gather are the same decision spoken "
                           "twice. Per item the difference here is 2 versus 4, which is small because class 1 "
                           "was designed around one pool call; classes 2 and 3 are where it is not."},
        "2_two_of_three_classes_do_not_fit_when_reads_are_charged": {
            "finding": "; ".join(f"{a['item']}: {c} planned {p['conservative_ops']} conservative ops "
                                 f"({p['read_calls']} reads) against a budget of {a['budget']}"
                                 for a in aborted for c, p in sorted(a["planned"].items())) or "none",
            "consequence": "no read was issued for an aborted class: the check is on the plan, from tensor "
                           "shapes, which is why an abort costs zero values and zero journal records rather "
                           "than 216 of each."},
        "3_the_replacement_of_a_global_claim_by_a_bounded_one": {
            "finding": f"every neighbour here is nearest among {POOL_CAP} rows, not among {N_VOCAB}",
            "consequence": "the synthetic graph could state the global version because the whole matrix was in "
                           "RAM and the rule priced that as nothing. A reader who wants the global claim from "
                           "the real donor has to buy it: 786 read calls per item, or a ruling that gathers "
                           "stay free."},
        "4_what_is_absent_from_this_run": {
            "finding": "no association edges, no head value reads, no circuit motifs, no latency ratio, no "
                       "energy estimate",
            "reason": "the first three are the classes that do not fit the conservative budget; the last two "
                      "are not this run's question (the >=10x threshold has never been re-based on the real "
                      "donor, and D-MPE12-02 still bars an energy figure)"},
    }


def build_graph(donor, item_ids, budget=READ_BUDGET_OPS, association_tokens=(1, 3, 5, 9), classes=None,
                accounting=None, prereg=None, donor_meta=None):
    src = as_source(donor)
    accounting = accounting or ("registered" if src.kind == "synthetic" else "conservative")
    classes = list(classes or CLASSES)
    items, aborted = [], []
    t_read = time.perf_counter()
    for tid in item_ids:
        try:
            items.append(probe_item(src, tid, budget, classes, accounting))
        except ReadBudgetExceeded as exc:
            aborted.append({"item": exc.item, "planned_ops": exc.planned_ops, "budget": exc.budget,
                            "planned": exc.by_class, "accounting": accounting, "source_kind": exc.source_kind})
    read_seconds = time.perf_counter() - t_read
    ops = sum(i["operations_spent"] for i in items)
    macs = sum(i["macs_spent"] for i in items)
    cons = sum(i["conservative_operations_spent"] for i in items)
    calls = sum(i["read_calls"] for i in items)
    rows = sum(i["rows_touched"] for i in items)
    vals = sum(i["values_returned"] for i in items)
    n_items = max(len(items), 1)
    out = {"schema_version": SCHEMA_VERSION, "schema_revision": SCHEMA_REVISION,
           "source_kind": src.kind, "accounting_used": accounting,
           "donor": donor_meta or src.donor_meta(),
           "read_budget": {"value": budget, "unit": "operations per probed association",
                           "enforcement": "plan C3: an item above budget aborts and writes nothing; on the "
                                          "real source the check is made on the plan, before any read",
                           "accounting": accounting},
           "extraction_classes_run": classes,
           "extraction_classes_planned": list(CLASSES),
           "items": items, "items_probed": len(items), "items_aborted": aborted,
           "operations_total": ops, "macs_total": macs,
           "operations_per_item_mean": round(ops / max(len(items), 1), 4),
           "accounting_tallies": {
               "registered_rule": {"operations": ops, "definition": "one operation = one vector-by-donor-matrix "
                   "multiply or one similarity search against one donor matrix; a gather of already-read rows "
                   "is not an operation", "read_calls_priced_at_zero": calls},
               "conservative_reading": {"operations": cons, "definition": "registered operations, plus one "
                   "charged operation for every journaled read call, however many values it returns",
                                        "read_calls": calls},
               "per_row_reading_reported_not_run_under": {"operations": ops + rows, "rows_touched": rows,
                   "definition": "registered operations, plus one per row touched. Stricter still, and not "
                                 "what this run used; emitted so the ruling has all three numbers."},
               "difference": {"ops": cons - ops, "read_calls": calls,
                              "meaning": "this is the loophole's price tag: the operations the registered rule "
                                         "does not see"},
               "conservative_equals_registered_when": "the synthetic source, which performs no journaled calls "
                   "because its donor is already in RAM. That coincidence is the loophole in miniature and it "
                   "is named here rather than left for a reader to infer."},
           "reads": {"read_calls": calls, "rows_touched": rows, "values_returned": vals},
           "wall_clock_read_s": round(read_seconds, 4),
           "energy_estimate": "NOT MEASURED -- no energy instrument in this repository (D-MPE12-02)"}
    if src.kind == "synthetic":
        bench = []
        for k in association_tokens:
            ref = reference_inference(src, k)
            run = reference_inference_run(src, k)
            read_ops_per_assoc = ops / n_items
            read_macs_per_assoc = macs / n_items
            read_s_per_assoc = (read_seconds / n_items) if read_seconds > 0 else None
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
        out["benchmark_vs_reference_inference"] = bench
        out["calibration_findings"] = calibration_findings(bench, src, items)
        out["benchmark_caveats"] = {
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
            "energy": "not estimated at all (D-MPE12-02)"}
        out["quoting_guard"] = {
            "meaning": "The donor is synthetic. No association, neighbour, motif or confidence figure in "
                       "this artifact is evidence about GPT-2, because this donor is not GPT-2 and holds "
                       "no library. Operation counts, shapes and MAC totals ARE valid measurements here: "
                       "they are properties of the code path and the registered shapes.",
            "rule_source": REGISTRATION,
            "blocking_external_fact": "resolved 2026-11-05: the public GPT-2 124M weights are on disk "
                                      "(experiments/MP-E12/donor/gpt2/), and the real path is now runnable "
                                      "through the journaled address space."}
    else:
        out["benchmark_vs_reference_inference"] = []
        out["benchmark_not_run_reason"] = (
            "the >=10x threshold has never been re-based on the real donor: reference_inference is a "
            "measurement against the synthetic shapes and the numpy path, not against the journaled address "
            "space. Emitting a ratio here would be a number about a machine that was not measured. Re-basing "
            "it is a separate item, and it is the one that would make a latency claim admissible.")
        out["real_findings"] = real_findings(items, aborted, items[0]["planned"] if items else
                                             (aborted[0]["planned"] if aborted else {}))
        out["candidate_pool_rule"] = {"formula": POOL_FORMULA, "value_blind": True,
                                      "registered_before_the_first_read": True,
                                      "preregistration": prereg or "experiments/MP-E12/results/"
                                                                   "real_run_preregistration.json"}
        out["what_these_figures_are_NOT"] = {
            "latency_or_10x": "NOT a claim about the >=10x threshold. No wall-clock ratio is emitted by this "
                              "run and none was measured against the real donor.",
            "MP-E12b": "NOT evidence about MP-E12b, which D-MPE12-04 bars.",
            "behaviour": "NOT a behavioural claim of any kind: no text generated, no prompt run, the donor was "
                        "never executed. R17 binds behavioural figures, so it does not bind these, and no "
                        "fresh-vs-fresh floor is required for them.",
            "knowledge_localisation": "NOT a localisation of a concept in a layer or head. A cosine between "
                                      "two embedding rows is a property of two vectors.",
            "global_reach": "NOT a vocabulary-wide nearest-neighbour result: every neighbour here is nearest "
                            f"among a fixed pool of {POOL_CAP} rows, chosen by an integer formula before any "
                            "value was read."}
        out["quoting_guard"] = {
            "meaning": "These are values read out of a public GPT-2 library at recorded addresses, and the "
                       "arithmetic done on them. They are measurements of a file. They are not a behavioural "
                       "finding, not a latency finding, and not evidence about MP-E12b.",
            "rule_source": REGISTRATION}
    return out


def load_probe_ids(path="experiments/MP-E12/results/probe_list_v1.json"):
    doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return [(int(p["token_id"]), p["word"]) for p in doc["probes"]]


def real_config():
    """The donor's own config.json, in the field names this file uses. Read from the file, not typed -- GPT-2
    spells its hidden size `n_embd`, not `hidden_size`, and the first cut of this function assumed the LLaMA-ish
    name and raised KeyError on the real file."""
    c = json.loads((ROOT / "experiments/MP-E12/donor/gpt2/config.json").read_text(encoding="utf-8"))
    n = int(c["n_embd"])
    return {"n_vocab": int(c["vocab_size"]), "n_positions": int(c["n_positions"]), "n_embd": n,
            "n_layer": int(c["n_layer"]), "n_head": int(c["n_head"]), "d_head": n // int(c["n_head"]),
            "mlp_inner": 4 * n}   # the config does not state it; RealDonorSource overwrites this from the
                                  # c_fc tensor's own shape, so the file decides and the guess is never used


def build_real_graph(n_items=24, classes=("1_embedding_geometry",), journal_rel=None, budget=READ_BUDGET_OPS,
                     prereg_rel="experiments/MP-E12/results/real_run_preregistration.json"):
    """The real run, end to end: address space, journal, pre-flight budget, graph.

    Returns (graph, journal_problems, mask_hits, donor_sha). The journal is verified AFTER the run rather than
    trusted during it, and the verification includes a scan for any record naming a causal-mask tensor -- the
    exclusion is asserted by the instrument, and re-asserted here against what was actually written.
    """
    from tools.mp_e12_access_journal import AccessJournal
    from tools.mp_e12_address_space import DonorAddressSpace, MASK_BUFFER_PATTERN, sha256_of_file

    journal_rel = journal_rel or "experiments/MP-E12/results/access_journal_extraction_e12a_class1.jsonl"
    probes = load_probe_ids()[:n_items]
    ids = [t for t, _ in probes]
    cfg = real_config()
    prov = json.loads((ROOT / "experiments/MP-E12/donor/gpt2/PROVENANCE_gpt2.json").read_text(encoding="utf-8"))
    abs_journal = ROOT / journal_rel
    abs_journal.parent.mkdir(parents=True, exist_ok=True)
    if abs_journal.exists():
        raise SystemExit(f"REFUSED: {journal_rel} already exists. The extraction journal is append-only and "
                         f"one run owns one file; re-running would mix two runs' records into one provenance "
                         f"chain. Delete it only as a deliberate act, with the reason in the ledger.")
    donor_sha = sha256_of_file()
    with AccessJournal(str(abs_journal), donor_sha256=donor_sha, run_label="extraction_e12a") as jr:
        with DonorAddressSpace(journal=jr) as ax:
            src = RealDonorSource(ax, cfg, ids, journal_rel)
            graph = build_graph(src, ids, budget=budget, classes=list(classes), accounting="conservative",
                                prereg=prereg_rel)
            # Cross-check the bytes, not the bookkeeping: every journal record carries the donor hash the read
            # was made against, so the run's own hash is compared to the records rather than re-derived (a
            # second 548 MB pass proves nothing the first one did not).
            graph["donor"]["sha256"] = donor_sha
            record_shas = {r["donor_sha256"] for r in jr.read()} | {donor_sha}
            if len(record_shas) != 1:
                raise SystemExit(f"REFUSED: the journal and the run disagree on the donor bytes: {record_shas}")
            prov_sha = next(f["sha256"] for f in prov["files"] if f["file"] == "model.safetensors")
            if prov_sha != donor_sha:
                raise SystemExit("REFUSED: the donor file no longer matches its provenance record")
            graph["donor"]["tensors_consulted"] = sorted({c["tensor"] for it in graph["items"]
                                                           for c in it.get("reads", [])})

            records = jr.read()
            summary = jr.verify()
            problems = summary["problems"] if isinstance(summary, dict) else summary
            mask_hits = sorted({r["tensor"] for r in records if MASK_BUFFER_PATTERN.match(r["tensor"])})
    calls = graph["reads"]["read_calls"]
    graph["access_journal"] = {"path": journal_rel, "n_records": len(records),
                               "verify": summary if isinstance(summary, dict) else None,
                               "verify_problems": problems, "mask_buffer_records": mask_hits,
                               "probe_ids": sorted({r["probe_id"] for r in records}),
                               "granularity_note": (
                                   f"the instrument writes one record per ROW read; the source issues one CALL "
                                   f"per bounded gather. {len(records)} records came from {calls} calls, which "
                                   f"is the difference between the two conservative readings, and the journal "
                                   f"counts the stricter one."),
                               "tensors_touched": sorted({r["tensor"] for r in records})}
    graph["accounting_tallies"]["journal_records"] = {
        "n": len(records), "relation_to_the_tallies": "registered + records is a fourth number, and the one "
                                                      "the journal itself can prove without trusting the "
                                                      "source's bookkeeping"}
    # The named-word view lives in the instrument, not in the script that happened to run it. It was first
    # written in the run script, which meant the most-quoted section of the artifact -- top-k per named word,
    # with both endpoints' addresses -- was produced by an untested wrapper rather than by the tested path.
    words = dict(load_probe_ids())
    graph["named_probe_words"] = {
        words[int(i["item"])]: {
            "token_id": i["item"],
            "source_address": next(n["address"] for n in i["nodes"] if n["type"] == "probe_token"),
            "top_k_neighbours": [
                {"token_id": int(n["node_id"].split(":")[1]),
                 "word": words.get(int(n["node_id"].split(":")[1]), "(not a probe word: sampled pool row)"),
                 "cosine": n["confidence"],
                 "source_address": n["address"],
                 "in_probe_list": int(n["node_id"].split(":")[1]) in words}
                for n in i["nodes"][1:]],
            "pool_size": i["detail"]["search_domain_rows"]}
        for i in graph["items"]}
    return graph, problems, mask_hits, donor_sha


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiny", action="store_true", help="the small test shape instead of 124M")
    ap.add_argument("--items", type=int, default=24, help="how many token ids to probe")
    ap.add_argument("--out", default="", help="write the association graph here")
    ap.add_argument("--real", action="store_true", help="the public GPT-2 library through the journaled "
                                                        "address space, instead of the synthetic donor")
    ap.add_argument("--classes", default="all", help="comma-separated extraction classes (real path only; "
                                                    "the synthetic calibration always runs all three)")
    ap.add_argument("--journal", default="", help="journal path for the real run (one run owns one file)")
    a = ap.parse_args(argv)
    if a.real:
        classes = list(CLASSES) if a.classes == "all" else [c.strip() for c in a.classes.split(",")]
        graph, problems, mask_hits, sha = build_real_graph(n_items=a.items, classes=classes,
                                                           journal_rel=a.journal or None)
        tally = graph["accounting_tallies"]
        print(f"REAL DONOR  items={graph['items_probed']} aborted={len(graph['items_aborted'])} "
              f"classes={graph['extraction_classes_run']} accounting={graph['accounting_used']}")
        print(f"  ops registered={tally['registered_rule']['operations']}  "
              f"conservative={tally['conservative_reading']['operations']}  "
              f"per-row-if-charged={tally['per_row_reading_reported_not_run_under']['operations']}  "
              f"read_calls={graph['reads']['read_calls']}  rows={graph['reads']['rows_touched']}  "
              f"values={graph['reads']['values_returned']}")
        for ab in graph["items_aborted"]:
            per_class = ", ".join(f"{c}={p['conservative_ops']} conservative ({p['read_calls']} reads)"
                                  for c, p in sorted(ab["planned"].items()))
            print(f"  BUDGET EVENT item {ab['item']}: planned {ab['planned_ops']} vs budget {ab['budget']} "
                  f"-- {per_class} -- zero reads issued")
        print(f"  journal: {graph['access_journal']['n_records']} records, verify problems={problems}, "
              f"mask-buffer records={mask_hits}")
        if a.out:
            p = Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"  wrote {a.out}")
        return 0
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
