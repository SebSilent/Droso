
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from connectome.substrate import CoreGraph

@dataclass
class HybridEngineParams:
    """Perception shape only. The dynamics live in the carve."""
    n_input_kc: int = 3840
    k_code: int = 16
    code_seed: int = 0

def text_code(text: str, n_kc: int = 3840, k: int = 16, seed: int = 0) -> np.ndarray:
    """Deterministic text -> sparse k-of-n Kenyon-cell code.

    Token unigrams and bigrams are hashed (blake2b, salted with `seed`) to
    cell indices; the first `k` unique cells are the code, amplitude 1.
    Deterministic across processes (unlike Python's salted hash()).
    """
    cells: list[int] = []
    toks = "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    for g in grams:
        h = hashlib.blake2b(g.encode("utf-8"), digest_size=8, salt=str(seed).encode()).digest()
        idx = int.from_bytes(h, "little") % n_kc
        if idx not in cells:
            cells.append(idx)
        if len(cells) >= k:
            break
    n_pad = 0
    while len(cells) < k:
        h = hashlib.blake2b(f"{text}|pad{n_pad}".encode(), digest_size=8,
                            salt=str(seed).encode()).digest()
        n_pad += 1
        idx = int.from_bytes(h, "little") % n_kc
        if idx not in cells:
            cells.append(idx)
        if n_pad > n_kc * 4:
            break
    x = np.zeros(n_kc, dtype=np.float32)
    x[np.asarray(cells[:k], dtype=np.int64)] = 1.0
    return x

class HybridEngine:
    """The carved connectome, and nothing else.

    - perception: text -> k-of-n KC code (`perceive_text`);
    - decision  : the code injected into the carve's real KCs, 10 sub-steps of
      rate propagation through measured synapses, WTA over the 12 real MBON
      pools (`decide`);
    - learning  : the measured three-factor dopamine rule on the measured
      plastic synapses (`teach`).

    There is no fallback brain. If the BANC data files are absent, construction
    raises: an agent without its connectome is a shell, and a silent shell that
    answered anyway is precisely the failure mode this project removed.
    """

    def __init__(self, graph: CoreGraph | None = None,
                 params: HybridEngineParams | None = None, seed: int = 0):
        from connectome.rate_core import RateCore
        if graph is None:
            raise RuntimeError(
                "HybridEngine requires the carved BANC connectome "
                "(connectome.substrate.build_core_graph). There is no fallback "
                "substrate: the grown-colony toy was removed by operator "
                "decision, and the connectome is the brain.")
        self.params = params or HybridEngineParams()
        # One engine, one plastic layer. The carve itself is shared process-wide
        # on purpose (world/reasoning_agent.py keeps one _BANC_GRAPH rather than
        # paying 8.6 s per agent), but the plastic arrays are the part a brain
        # CHANGES: adopting a lived geometry, grow_plastic and prune_plastic all
        # resize them in place. Sharing those meant one brain's life rewrote the
        # shape of every other engine in the process. So the read-only wiring
        # stays shared and only the mutable layer is copied per engine.
        import copy as _copy
        own = _copy.copy(graph)
        own.plastic_pre = np.asarray(graph.plastic_pre).copy()
        own.plastic_post = np.asarray(graph.plastic_post).copy()
        own.plastic_w0 = np.asarray(graph.plastic_w0).copy()
        self.graph = own
        self.static = RateCore(own, seed=seed, dopamine=True)
        self._kc_of_code = own.kc_idx[:self.params.n_input_kc]
        self.rng = np.random.default_rng(seed)
        self.last_code: np.ndarray | None = None
        self.last_action: int | None = None
        self.last_v: np.ndarray | None = None
        self.last_probs: np.ndarray | None = None
        self.rpe_last: float = 0.0
        self.decisions = 0

    def perceive_text(self, text: str) -> np.ndarray:
        self.last_code = text_code(text, self.params.n_input_kc, self.params.k_code,
                                   self.params.code_seed)
        return self.last_code

    def decide(self, code: np.ndarray | None = None, text: str | None = None,
               allowed_pools=None, extra_drive=None) -> int:
        """One decision: 50 ms of neural time in the carve.

        `allowed_pools` restricts the WTA to a subset of the 12 MBON pools (the
        reasoning loop's legality structure); `None` means all pools.
        `extra_drive` adds more (node-index, amplitude) pairs to the same
        episode -- how a scent, a body state or a voice enters alongside the
        words, through the fly's own wiring rather than around it.
        """
        if code is None:
            code = self.perceive_text(text) if text else self.last_code
        if code is None:
            raise ValueError("no code: pass `code` or `text`")
        self.last_code = np.asarray(code, dtype=np.float32)
        amp = np.ones(len(self._kc_of_code), dtype=float) * self.last_code
        nz = np.nonzero(amp)[0]
        drive = [(self._kc_of_code[nz], amp[nz])] if len(nz) else None
        if extra_drive:
            pairs = [(np.asarray(i, dtype=np.int64), np.asarray(a, dtype=float))
                     for i, a in extra_drive]
            drive = (drive or []) + pairs
        self.static.reset_episode()
        action, v = self.static.decide(drive, allowed=allowed_pools)
        self.last_action = int(action)
        self.last_v = np.asarray(v, dtype=float)
        z = (self.last_v - self.last_v.max()) / 0.05
        e = np.exp(z)
        self.last_probs = e / e.sum()
        self.decisions += 1
        return self.last_action

    def decide_sequence(self, codes, extra_drive=None) -> int:
        """Perceive a SEQUENCE: each word's drive lands on a state that still
        carries the one before it.

        This is what makes word order exist for him. `decide()` resets the episode
        every call, so hashing a whole sentence into one code leaves him with a
        bag of words: "dog bites man" and "man bites dog" differ only in which
        bigram cells the hash happens to hit. Here the rate vector is not reset
        between words, so the trajectory through the carve depends on the order
        the words arrived in -- and the final readout is taken after the last one.

        Costs one decision per word instead of one per sentence, so it is used
        for hearing and speaking, not for the accelerated life loop.
        """
        seq = [np.asarray(c, dtype=np.float32) for c in codes if c is not None]
        seq = [c for c in seq if np.any(c)]
        if not seq:
            raise ValueError("no codes: nothing to perceive")
        self.last_code = seq[-1]
        self.static.reset_episode()
        extra = [(np.asarray(i, dtype=np.int64), np.asarray(a, dtype=float))
                 for i, a in (extra_drive or [])]
        action = None
        for code in seq:
            amp = np.ones(len(self._kc_of_code), dtype=float) * code
            nz = np.nonzero(amp)[0]
            drive = [(self._kc_of_code[nz], amp[nz])] if len(nz) else None
            if extra:
                drive = (drive or []) + extra
            action, v = self.static.decide(drive)
        self.last_action = int(action)
        self.last_v = np.asarray(v, dtype=float)
        z = (self.last_v - self.last_v.max()) / 0.05
        e = np.exp(z)
        self.last_probs = e / e.sum()
        self.decisions += len(seq)
        return self.last_action

    def teach(self, reward: float) -> float:
        """Broadcast consequence -> dopamine -> plasticity on the measured
        synapses. Returns the RPE; 0.0 when there is nothing to reinforce."""
        if self.last_action is None or self.last_v is None:
            self.rpe_last = 0.0
            return 0.0
        rpe = self.static.reinforce(float(reward),
                                    float(self.last_v[self.last_action]), 0.0)
        self.rpe_last = float(rpe)
        return self.rpe_last

    def save_brain(self, path) -> dict:
        """Persist the LIVED synapse weights to disk.

        The weights in `static.w` are the learning: every word driven, every
        lesson reinforced, every consolidation tick is a delta on these 2,983
        measured synapses. Without this file the brain resets to its birth
        state on every restart -- which is the opposite of a being that learns.
        """
        import numpy as np
        from pathlib import Path as _P
        path = _P(path)
        path.parent.mkdir(exist_ok=True, parents=True)
        with self.static._lock:
            w = self.static.w.copy()
            plastic_pre = np.asarray(self.graph.plastic_pre).copy()
            plastic_post = np.asarray(self.graph.plastic_post).copy()
        np.savez_compressed(str(path), w=w,
                            plastic_pre=plastic_pre,
                            plastic_post=plastic_post,
                            provenance=np.array(
                                [int(bool(self.graph.meta.get("control", False))),
                                 int(self.graph.n_nodes),
                                 int(len(plastic_pre))]))
        grown = int((w != self.graph.plastic_w0).sum())
        return {"saved": True, "path": str(path), "synapses": len(w),
                "changed_from_birth": grown,
                "mean_abs_weight": round(float(np.mean(np.abs(w))), 6)}

    def load_brain(self, path) -> dict:
        """Restore lived synapse weights.

        Accepts a brain recorded from the SAME base carve geometry (same
        plastic synapse indices) -- or a brain that GREW beyond it: the
        recorded (pre, post) indices are adopted so a lifetime of structural
        growth survives rebirth instead of being discarded as "a different
        geometry". Grown synapses are born +0.01 (excitatory) in the birth
        record, exactly as grow_plastic created them."""
        import numpy as np
        from pathlib import Path as _P
        path = _P(path)
        if not path.exists():
            return {"loaded": False, "reason": "no brain file yet"}
        data = np.load(str(path))
        w = data["w"]
        pre_f = np.asarray(data["plastic_pre"])
        post_f = np.asarray(data["plastic_post"])
        # Provenance before geometry. The control condition is degree-matched
        # random WIRING on the SAME neurons, and its plastic layer is identical
        # pair for pair -- so synapse identity can never tell the two apart.
        # Without this stamp, a control run's weights could be loaded into the
        # experimental brain and nothing in the file would say so.
        if "provenance" in data.files:
            pv = [int(x) for x in np.asarray(data["provenance"]).ravel()]
            rec_control = bool(pv[0]) if pv else False
            mine_control = bool(self.graph.meta.get("control", False))
            if rec_control != mine_control:
                return {"loaded": False,
                        "reason": "condition mismatch: brain is from the "
                                  f"{'control' if rec_control else 'experimental'} "
                                  "carve, this engine is the "
                                  f"{'control' if mine_control else 'experimental'}"
                                  " one"}
            if len(pv) > 1 and pv[1] != int(getattr(self.graph, "n_nodes", pv[1])):
                return {"loaded": False,
                        "reason": "brain file is from a different carve geometry "
                                  f"({pv[1]} neurons recorded, this carve has "
                                  f"{int(self.graph.n_nodes)})"}
        same = (len(w) == len(self.static.w)
                and np.array_equal(pre_f, self.graph.plastic_pre)
                and np.array_equal(post_f, self.graph.plastic_post))
        adopted = None
        if not same:
            # Geometry is matched by IDENTITY, not by position. A synapse is the
            # pair (pre, post); a life spent growing and pruning changes how many
            # pairs exist and in what order, but never what a pair means. So the
            # recorded pair list is adopted whole, each pair's birth weight is
            # looked up in the base carve, and pairs the base does not know are
            # taken as grown-in (born +0.01, as grow_plastic creates them).
            # This accepts both a brain that GREW past its carve and one that
            # PRUNED below it -- the old code accepted only the first, so every
            # consolidated brain was silently discarded at restart.
            base_pre = np.asarray(self.graph.plastic_pre, dtype=np.int64)
            base_post = np.asarray(self.graph.plastic_post, dtype=np.int64)
            base_w0 = np.asarray(self.graph.plastic_w0)
            rec = list(zip([int(x) for x in pre_f], [int(x) for x in post_f]))
            base = list(zip([int(x) for x in base_pre],
                            [int(x) for x in base_post]))
            n_rec, n_base = len(rec), len(base)
            overlap = len(set(rec) & set(base))
            bounds = np.concatenate([pre_f, post_f]) if n_rec else np.array([0])
            n_nodes = int(getattr(self.graph, "n_nodes",
                                  int(max(bounds.max(), 0)) + 1))
            legit = (len(w) == n_rec == len(post_f) > 0
                     and len(set(rec)) == n_rec
                     and int(bounds.min()) >= 0
                     and int(bounds.max()) < n_nodes
                     and overlap / float(max(n_base, n_rec, 1)) >= 0.5)
            if not legit:
                return {"loaded": False,
                        "reason": "brain file is from a different carve geometry "
                                  f"({overlap} of {n_base} base synapse identities "
                                  f"shared over {n_rec} recorded)"}
            birth_of = dict(zip(base, [float(x) for x in base_w0]))
            self.graph.plastic_pre = pre_f.astype(base_pre.dtype)
            self.graph.plastic_post = post_f.astype(base_post.dtype)
            self.graph.plastic_w0 = np.array(
                [birth_of.get(p, 0.01) for p in rec], dtype=base_w0.dtype)
            with self.static._lock:
                self.static.w = np.zeros(n_rec, dtype=self.static.w.dtype)
                self.static.e = np.zeros(n_rec, dtype=self.static.e.dtype)
                self.static._pool_of_post = np.array(
                    [self.static._pool_of(int(b)) for b in post_f],
                    dtype=self.static._pool_of_post.dtype)
                self.static._sync_plastic_meta()
            adopted = {"synapses": n_rec, "shared_with_birth": overlap,
                       "grown_since_birth": n_rec - overlap,
                       "pruned_since_birth": max(0, n_base - overlap)}
        with self.static._lock:
            self.static.w = w.copy()
            self.static._w_sign = np.sign(self.graph.plastic_w0)
            self.static._plastic_active = self.static._w_sign != 0
        self.static._sync_compartments()
        grown = int((self.static.w != self.graph.plastic_w0).sum())
        out = {"loaded": True, "path": str(path), "synapses": len(w),
               "changed_from_birth": grown}
        if adopted is not None:
            out["adopted_geometry"] = adopted
        return out