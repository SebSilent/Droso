
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np
from scipy import sparse

from connectome.substrate import CoreGraph

@dataclass
class CoreParams:
    sub_steps: int = 10
    leak: float = 0.6
    tau_e: float = 0.95
    lr: float = 3.0
    gamma: float = 0.9
    # Per SECOND of real time, not per decision -- see _reset_episode_impl. At
    # 3.2e-5 the half-life is about six hours, which is what forgetting a memory
    # should cost. The old 0.003 was applied on every decision, so the same brain
    # forgot 29x faster in the accelerated worker (190 decisions/s, 1.2 s
    # half-life) than in the house (6.6 decisions/s, 35 s).
    weight_decay: float = 3.2e-5
    w_cap: float = 8.0
    hysteresis: float = 0.002
    epsilon: float = 0.15
    epsilon_floor: float = 0.02
    epsilon_decay: float = 0.995
    temperature: float = 0.02
    temperature_decay: float = 1.0
    input_gain: float = 2.0

class RateCore:
    # Weight decay is a function of elapsed time, and applying it more often than
    # this buys nothing except invalidating the folded matrix every decision.
    DECAY_MIN_INTERVAL_S = 5.0
    def __init__(self, graph: CoreGraph, params: CoreParams | None = None, seed: int = 0,
                 dopamine: bool = True):
        self.g = graph
        self.p = params or CoreParams()
        self.rng = np.random.default_rng(seed)
        self.dopamine = dopamine
        self._lock = threading.RLock()

        self.w = graph.plastic_w0.copy()
        self.e = np.zeros_like(self.w)
        self._last_decay_t = time.time()
        self.teach_count = 0
        self.last_e_mean = 0.0
        self.last_dw_mean = 0.0
        self.last_rpe = 0.0
        self.r = np.zeros(graph.n_nodes)
        self.prev_action: int | None = None

        self.pool_baseline = np.zeros(len(self.g.mbon_pools))
        self._last_v = None
        self._last_action = None
        self._pool_of_post = np.empty(len(self.w), dtype=int)
        post_to_pool = {}
        for a, pool in enumerate(self.g.mbon_pools):
            for node in pool:
                post_to_pool[node] = a
        self._post_to_pool = post_to_pool
        for k, q in enumerate(self.g.plastic_post):
            self._pool_of_post[k] = post_to_pool[int(q)]
        fanin = np.bincount(self.g.plastic_post, minlength=self.g.n_nodes)
        fanin[fanin == 0] = 1
        self._plastic_norm = 1.0 / fanin[self.g.plastic_post]
        self._w_sign = np.sign(graph.plastic_w0)
        self._plastic_active = self._w_sign != 0
        self._sync_compartments()

        self._pp = sparse.coo_matrix(
            (np.ones(len(self.w)),
             (graph.plastic_post, graph.plastic_pre)),
            shape=(graph.n_nodes, graph.n_nodes),
        ).tocsr()

    def calibrate(self, drive_sampler, n_states: int = 60) -> None:
        """Estimate per-pool baseline valuations over random input states."""
        vs = []
        for _ in range(n_states):
            self.reset_episode()
            drive = drive_sampler()
            _, v = self.decide(drive)
            vs.append(v)
        self.pool_baseline = np.mean(vs, axis=0)

    def valuations(self) -> np.ndarray:
        """Baseline-corrected valuation vector from the last decide()."""
        return self._last_v - self.pool_baseline

    def reset_episode(self) -> None:
        with self._lock:
            self._reset_episode_impl()

    def _reset_episode_impl(self) -> None:
        self.r[:] = 0.0
        # The eligibility trace is deliberately NOT cleared here. It exists to
        # bridge the delay between an action and its consequence, and zeroing it
        # at the start of every decision meant a consequence arriving later --
        # care, praise, punishment, a phrase heard -- landed on whatever trace the
        # newest decision happened to leave behind, or on nothing at all. It is
        # bounded by its own per-sub-step decay instead.
        now = time.time()
        dt = now - getattr(self, "_last_decay_t", now)
        # Applied at most every few seconds rather than every decision. It is
        # exactly the same compounding over the same elapsed time, but touching w
        # on every decision invalidated the folded static+plastic matrix every
        # time, forcing a rebuild of a 193k-entry CSR: measured 1.0 ms of the
        # 8.95 ms a decision costs once the plastic layer had grown to 20k.
        if dt >= self.DECAY_MIN_INTERVAL_S:
            self._last_decay_t = now
            dt = min(3600.0, max(0.0, dt))
            if self.p.weight_decay > 0.0:
                self.w *= (1.0 - float(self.p.weight_decay)) ** dt
        self.p.epsilon = max(self.p.epsilon_floor, self.p.epsilon * self.p.epsilon_decay)
        self.p.temperature = self.p.temperature * self.p.temperature_decay
        self.prev_action = None

    def pulse(self, idx: np.ndarray, amplitude: float, scale: np.ndarray | None = None) -> None:
        """Inject current into a node subset (goal-slot pulses, sensory drive)."""
        if len(idx) == 0:
            return
        with self._lock:
            self.r[idx] += amplitude * (scale if scale is not None else 1.0)

    def decide(self, drive: list[tuple[np.ndarray, np.ndarray]] | None = None,
               allowed=None) -> tuple[int, np.ndarray]:
        """Run the network for one decision; WTA action with hysteresis+noise.

        `drive`: list of (node-index-array, amplitude-array) external current
        pairs applied every sub-step. `allowed`: optional iterable of MBON-pool
        indices the WTA may choose from (the reasoning loop's legality
        structure); exploration respects it too. Returns (action, valuation).
        Serialized against the heartbeat's neural ticks and any concurrent
        decision: the rate vector is shared state.
        """
        with self._lock:
            return self._decide_impl(drive, allowed)

    def _folded_W(self):
        """Static plus plastic wiring as ONE matrix, reused while nothing moved.

        This is the speed. A decision is 10 sub-steps, and propagating the static
        and plastic layers separately cost 20 sparse matvecs where 10 do exactly
        the same arithmetic ((W + Wp) @ r == W @ r + Wp @ r). The matrix is also
        kept between decisions, because the accelerated-life thread decides
        thousands of times with the same weights: rebuilding a 176k-entry CSR is
        milliseconds, and that was most of the cost of a tick.

        The reuse test compares the ARRAYS, not a dirty flag on purpose. A flag
        has to be remembered at every place that touches a weight -- teach,
        decay, homeostasis, grow, prune, load -- and one forgotten site means a
        brain silently running on last week's synapses with no error anywhere.
        """
        g = self.g
        pre = np.asarray(g.plastic_pre)
        post = np.asarray(g.plastic_post)
        cached = getattr(self, "_fold_cache", None)
        if cached is not None and cached[0].shape == self.w.shape \
                and np.array_equal(cached[0], self.w) \
                and np.array_equal(cached[1], pre) \
                and np.array_equal(cached[2], post):
            return cached[3]
        Wp = sparse.coo_matrix((self.w, (post, pre)),
                               shape=(g.n_nodes, g.n_nodes)).tocsr()
        folded = (g.W + Wp).tocsr()
        self._fold_cache = (self.w.copy(), pre.copy(), post.copy(), folded)
        return folded

    def _decide_impl(self, drive: list[tuple[np.ndarray, np.ndarray]] | None = None,
                     allowed=None) -> tuple[int, np.ndarray]:
        g, p = self.g, self.p
        Wtot = self._folded_W()
        ext = np.zeros(g.n_nodes)
        if drive:
            for idx, amp in drive:
                ext[idx] += amp
        ext *= p.input_gain

        for _ in range(p.sub_steps):
            u = Wtot @ self.r
            u += ext
            np.clip(u, 0.0, 1.0, out=u)
            # r = (1 - leak) * r + leak * u, done in place: the vector form spent
            # three fresh 12,867-element arrays per sub-step, ten sub-steps per
            # decision, on a loop that is memory traffic all the way down.
            self.r *= (1.0 - p.leak)
            u *= p.leak
            self.r += u
        np.clip(self.r, 0.0, 1.0, out=self.r)

        pools = g.mbon_pools
        wpn = self.w * self._plastic_norm
        # Same arithmetic as (plastic matrix @ r), summed straight into the
        # post-synaptic bins: no third matrix built per decision.
        drive_mbon = np.bincount(
            np.asarray(g.plastic_post, dtype=np.int64),
            weights=wpn * self.r[np.asarray(g.plastic_pre, dtype=np.int64)],
            minlength=g.n_nodes)
        v_raw = np.array([drive_mbon[pool].mean() for pool in pools])
        v = v_raw - self.pool_baseline

        cand = np.asarray(sorted(allowed), dtype=int) if allowed is not None \
            else np.arange(len(pools))
        scores = v[cand].copy()
        if self.prev_action is not None and self.prev_action in cand:
            scores[cand == self.prev_action] += p.hysteresis
        if self.rng.random() < p.epsilon:
            action = int(self.rng.choice(cand))
        else:
            z = (scores - scores.max()) / max(p.temperature, 1e-9)
            probs = np.exp(z)
            probs /= probs.sum()
            action = int(self.rng.choice(cand, p=probs))

        self.e *= self._comp_tau
        self.e += (self.r[g.plastic_pre] * self.r[g.plastic_post])

        self._last_v = v
        self._last_action = action
        return action, v

    def grow_plastic(self, k: int = 50, w0: float = 0.01) -> int:
        """Synaptogenesis: k brand-new KC->MBON synapses with small weights.

        New learnable routes: the pool they land on becomes a place where a
        fresh association can form. The arrays are rebuilt by every decide,
        so appended synapses are live immediately.

        Structural changes RESIZE the plastic layer, so they take the same
        lock as decide()/reinforce() -- an unlocked resize once interleaved
        with a concurrent decide and tore (w, _plastic_norm) apart."""
        with self._lock:
            return self._grow_plastic_impl(k, w0)

    def _assert_structural_alignment(self) -> None:
        """The five structural arrays are one thing and must agree in length.

        Ownership was the fault here, not shape. The structural index lives on the
        graph (plastic_pre/post/w0) and the learner state lives on the core
        (w/e/_pool_of_post), so a single grow is a resize of two owners -- and only
        two of the five appends were inside the lock. A prune arriving between them
        built its mask from a 20,071-long self.w and applied it to a 20,101-long
        plastic_pre, which is the reported IndexError verbatim: boolean index did
        not match indexed array along axis 0.

        Fail loud. _sync_plastic_meta has defensive slicing that would paper over a
        drift like this, and a silently misindexed synapse is worse than a crash.
        """
        g = self.g
        sizes = {
            "plastic_pre": len(np.asarray(g.plastic_pre)),
            "plastic_post": len(np.asarray(g.plastic_post)),
            "plastic_w0": len(np.asarray(g.plastic_w0)),
            "w": len(np.asarray(self.w)),
            "e": len(np.asarray(self.e)),
        }
        distinct = set(sizes.values())
        assert len(distinct) == 1, (
            "structural arrays out of alignment around a resize: " + repr(sizes))

    def _grow_plastic_impl(self, k: int, w0: float) -> int:
        k = max(1, int(k))
        g = self.g
        self._assert_structural_alignment()
        kc = np.asarray(g.kc_idx)
        mb = np.asarray(g.mbon_idx)
        pre = kc[self.rng.integers(0, len(kc), k)]
        post = mb[self.rng.integers(0, len(mb), k)]
        # ONE mutation, ONE lock acquisition. Every array that has to stay
        # index-aligned with every other grows inside this block or none of them do.
        with self._lock:
            g.plastic_pre = np.concatenate([np.asarray(g.plastic_pre), pre])
            g.plastic_post = np.concatenate([np.asarray(g.plastic_post), post])
            g.plastic_w0 = np.concatenate(
                [np.asarray(g.plastic_w0),
                 np.full(k, w0, dtype=np.asarray(g.plastic_w0).dtype)])
            self.w = np.concatenate([self.w,
                                     np.full(k, w0, dtype=self.w.dtype)])
            self.e = np.concatenate([self.e, np.zeros(k, dtype=self.e.dtype)])
            self._pool_of_post = np.concatenate(
                [self._pool_of_post,
                 np.array([self._pool_of(int(b)) for b in post],
                          dtype=self._pool_of_post.dtype)])
        self._sync_plastic_meta()
        self._sync_compartments()
        self._assert_structural_alignment()
        return k

    def _pool_of(self, node: int) -> int:
        """Pool (action) index of a postsynaptic node; unknown nodes -> 0."""
        return int(self._post_to_pool.get(int(node), 0))

    def prune_plastic(self, threshold: float = 0.004) -> int:
        """Pruning: synapses whose weight decayed to ~zero are removed.
        Structural forgetting -- only connections that EARNED plasticity
        survive. The born-strong synapses (plastic_w0) never reach this."""
        with self._lock:
            return self._prune_plastic_impl(threshold)

    def _prune_plastic_impl(self, threshold: float) -> int:
        mask = np.abs(np.asarray(self.w)) >= float(threshold)
        g = self.g
        pre_arr = np.asarray(g.plastic_pre)
        # Fail loud rather than silently misindex. A mask and the arrays it is
        # applied to are the same vector of synapses; if they disagree in length
        # the mask does not mean "drop these synapses", it means nothing at all.
        assert mask.shape[0] == pre_arr.shape[0] == len(np.asarray(self.w)), (
            f"prune mask of {mask.shape[0]} against structural arrays "
            f"{pre_arr.shape[0]} / {len(np.asarray(self.w))}")
        removed = int((~mask).sum())
        if removed:
            g = self.g
            with self._lock:
                g.plastic_pre = np.asarray(g.plastic_pre)[mask]
                g.plastic_post = np.asarray(g.plastic_post)[mask]
            g.plastic_w0 = np.asarray(g.plastic_w0)[mask]
            self.w = np.asarray(self.w)[mask]
            self.e = np.asarray(self.e)[mask]
            self._sync_plastic_meta()
            if hasattr(self, "_pool_of_post") and \
                    len(self._pool_of_post) == len(mask):
                self._pool_of_post = self._pool_of_post[mask]
            self._sync_compartments()
        return removed

    # ── compartment-specific plasticity ──────────────────────────────
    # One three-factor rule for every synapse is not what a mushroom body does.
    # It is a set of compartments, each with its own dopaminergic neuron and its
    # own write rule, which is how one small structure holds fast and slow
    # memory, and appetitive and aversive learning, side by side. We have 13
    # pools and 83 real DANs and were using none of that structure: every synapse
    # learned at the same rate, forgot at the same rate, and treated reward and
    # punishment identically.
    #
    # DECLARED MODEL CHOICE, not measurement. The fly's compartments are known to
    # differ, but not in these numbers. Pools are assigned by index modulo four so
    # the assignment is deterministic and reproducible, and the control condition
    # for the experiment is the uniform rule this replaces.
    #        name               lr gain  tau_e   rpe gain  cap gain
    COMPARTMENT_TYPES = (
        ("fast_appetitive",     2.0,     0.85,   +1.0,     1.0),
        ("slow_semantic",       0.4,     0.995,  +1.0,     1.5),
        ("aversive",            1.0,     0.95,   -1.0,     1.0),
        ("monitor",             0.7,     0.95,   +0.3,     1.0),
    )

    def _sync_compartments(self) -> None:
        """Per-synapse plasticity parameters, derived from which pool each
        synapse writes onto. Rebuilt whenever the plastic layer changes size.

        Defensive about length on purpose: grow and prune both resize the pool
        map after calling _sync_plastic_meta, so this can be reached while the
        two arrays briefly disagree, and a silent length mismatch here would put
        one compartment's rule on another's synapses.
        """
        n = len(self.w)
        pools = np.asarray(self._pool_of_post, dtype=np.int64) if \
            hasattr(self, "_pool_of_post") else np.zeros(n, dtype=np.int64)
        if len(pools) < n:
            pools = np.concatenate([pools, np.zeros(n - len(pools), dtype=np.int64)])
        pools = pools[:n]
        kinds = pools % len(self.COMPARTMENT_TYPES)
        self._comp_kind = kinds
        self._comp_lr = np.array([c[1] for c in self.COMPARTMENT_TYPES])[kinds]
        self._comp_tau = np.array([c[2] for c in self.COMPARTMENT_TYPES])[kinds]
        self._comp_gain = np.array([c[3] for c in self.COMPARTMENT_TYPES])[kinds]
        self._comp_cap = np.array([c[4] for c in self.COMPARTMENT_TYPES])[kinds]

    def plasticity_report(self) -> dict:
        """Whether teaching is landing, in numbers rather than impressions."""
        return {"teach_calls": int(self.teach_count),
                "last_rpe": self.last_rpe,
                "last_eligibility_mean_abs": self.last_e_mean,
                "last_weight_change_mean_abs": self.last_dw_mean,
                "eligibility_nonzero": int(np.count_nonzero(self.e)),
                "weight_decay_per_s": float(self.p.weight_decay),
                "forgetting_half_life_s": round(
                    0.6931 / max(1e-12, float(self.p.weight_decay)), 1)}

    def compartment_stats(self) -> list:
        """What each compartment has actually done, measured off the weights."""
        out = []
        w = np.asarray(self.w, dtype=float)
        birth = np.asarray(self.g.plastic_w0, dtype=float)
        if len(birth) != len(w):
            birth = np.resize(birth, len(w))
        pools = np.asarray(self._pool_of_post, dtype=np.int64)[:len(w)]
        for p in sorted(set(pools.tolist())):
            m = pools == p
            if not m.any():
                continue
            kind = self.COMPARTMENT_TYPES[int(p) % len(self.COMPARTMENT_TYPES)]
            out.append({"pool": int(p), "compartment": kind[0],
                        "synapses": int(m.sum()),
                        "lr_gain": kind[1], "tau_e": kind[2],
                        "rpe_gain": kind[3], "cap_gain": kind[4],
                        "mean_abs_weight": round(float(np.mean(np.abs(w[m]))), 5),
                        "mean_change_from_birth": round(
                            float(np.mean(w[m] - birth[m])), 6),
                        "strengthened": int(((w[m] - birth[m]) > 1e-6).sum()),
                        "weakened": int(((w[m] - birth[m]) < -1e-6).sum())})
        return out

    def _sync_plastic_meta(self) -> None:
        """Keep the per-synapse normalization / sign / active masks in sync
        after the plastic layer changes size."""
        fanin = np.bincount(np.asarray(self.g.plastic_post, dtype=int),
                            minlength=int(self.g.n_nodes))
        fanin[fanin == 0] = 1
        self._plastic_norm = 1.0 / fanin[
            np.asarray(self.g.plastic_post, dtype=int)]
        self._w_sign = np.sign(
            np.asarray(self.g.plastic_w0)[:len(self.w)]
            if len(np.asarray(self.g.plastic_w0)) >= len(self.w)
            else self._w_sign)
        if len(self._w_sign) < len(self.w):
            self._w_sign = np.concatenate(
                [self._w_sign, np.ones(len(self.w) - len(self._w_sign),
                                       dtype=self._w_sign.dtype)])
        self._w_sign = self._w_sign[:len(self.w)]
        self._plastic_active = self._w_sign != 0
        if hasattr(self, "_pp"):
            self._pp = sparse.coo_matrix(
                (np.ones(len(self.w)),
                 (np.asarray(self.g.plastic_post, dtype=int),
                  np.asarray(self.g.plastic_pre, dtype=int))),
                shape=(int(self.g.n_nodes), int(self.g.n_nodes)))

    def grow_pool(self, nodes: int = 8, fanin: int = 40) -> dict:
        """Neurogenesis: a new MBON pool. New neurons join the round-robin
        partition (the carve's own pooling rule), get fresh plastic inputs,
        and open a new slot in the WTA -- literal capacity growth. Learned
        weights are keyed to (KC, MBON) pairs, so they survive the
        re-bucketing untouched."""
        with self._lock:
            return self._grow_pool_impl(nodes, fanin)

    def _grow_pool_impl(self, nodes: int, fanin: int) -> dict:
        nodes = max(1, int(nodes))
        fanin = max(1, int(fanin))
        g = self.g
        n0 = int(g.n_nodes)
        new_nodes = np.arange(n0, n0 + nodes)
        kc = np.asarray(g.kc_idx)
        pre = kc[self.rng.integers(0, len(kc), nodes * fanin)]
        post = np.repeat(new_nodes, fanin)
        self.r = np.concatenate([self.r,
                                 np.zeros(nodes, dtype=self.r.dtype)])
        g.mbon_idx = np.concatenate([np.asarray(g.mbon_idx), new_nodes])
        g.n_actions = int(g.n_actions) + 1
        g.n_nodes = n0 + nodes
        with self._lock:
            g.plastic_pre = np.concatenate([np.asarray(g.plastic_pre), pre])
            g.plastic_post = np.concatenate([np.asarray(g.plastic_post), post])
        g.plastic_w0 = np.concatenate(
            [np.asarray(g.plastic_w0),
             np.full(len(pre), 0.01,
                     dtype=np.asarray(g.plastic_w0).dtype)])
        self.w = np.concatenate([self.w,
                                 np.full(len(pre), 0.01,
                                         dtype=self.w.dtype)])
        self.e = np.concatenate([self.e, np.zeros(len(pre),
                                                  dtype=self.e.dtype)])
        W = g.W
        if hasattr(W, "tocsr"):
            W = W.tocsr()
            W = sparse.vstack([W, sparse.csr_matrix(
                (nodes, W.shape[1]))], format="csr")
            W = sparse.hstack([W, sparse.csr_matrix(
                (W.shape[0], nodes))], format="csr")
            g.W = W
        else:
            W = np.asarray(W)
            W = np.vstack([W, np.zeros((nodes, W.shape[1]), dtype=W.dtype)])
            W = np.hstack([W, np.zeros((W.shape[0], nodes), dtype=W.dtype)])
            g.W = W
        base = float(np.mean(self.pool_baseline))             if len(self.pool_baseline) else 0.0
        self.pool_baseline = np.concatenate(
            [np.asarray(self.pool_baseline),
             np.full(1, base, dtype=self.pool_baseline.dtype)])
        self._post_to_pool = {}
        for a, pool in enumerate(self.g.mbon_pools):
            for node in pool:
                self._post_to_pool[int(node)] = a
        self._pool_of_post = np.array(
            [self._post_to_pool[int(q)] for q in self.g.plastic_post],
            dtype=self._pool_of_post.dtype)
        self._sync_plastic_meta()
        return {"new_neurons": int(nodes),
                "pool": int(g.n_actions) - 1,
                "new_synapses": int(len(pre)),
                "total_neurons": int(g.n_nodes),
                "total_pools": int(g.n_actions),
                "plastic_synapses": int(len(self.w))}

    def commit(self, action: int) -> None:
        self.prev_action = action

    def reinforce(self, reward: float, v_chosen: float, v_next_max: float) -> float:
        """Apply the three-factor update from a measured reward. Returns rpe."""
        with self._lock:
            return self._reinforce_impl(reward, v_chosen, v_next_max)

    def _reinforce_impl(self, reward: float, v_chosen: float,
                        v_next_max: float) -> float:
        rpe = float(np.clip(reward + self.p.gamma * v_next_max - v_chosen, -1.0, 1.0))
        if not self.dopamine:
            rpe = 0.0
        # Per compartment: its own learning rate, its own sign on the teaching
        # signal, its own ceiling. An aversive compartment strengthens on
        # punishment what an appetitive one strengthens on reward, which is the
        # whole reason the fly has twenty kinds of dopamine neuron and not one.
        e_mean = float(np.mean(np.abs(self.e)))
        dw = (self.p.lr * rpe * self._comp_lr * self._comp_gain
              * self.e * self._plastic_active)
        self.w += dw
        # Instrumented on purpose. "Did the teaching signal actually land?" was
        # not answerable before, and the answer turned out to be barely.
        self.teach_count += 1
        self.last_e_mean = round(e_mean, 8)
        self.last_dw_mean = round(float(np.mean(np.abs(dw))), 10)
        self.last_rpe = round(float(rpe), 6)
        cap = self.p.w_cap * self._comp_cap
        pos = self._w_sign > 0
        neg = self._w_sign < 0
        self.w[pos] = np.clip(self.w[pos], 0.0, cap[pos])
        self.w[neg] = np.clip(self.w[neg], -cap[neg], 0.0)
        self.w[~self._plastic_active] = 0.0
        return rpe

    def tutor_correct(self, chosen_action: int, correct_action: int,
                      lr_good: float = 20.0, lr_bad: float = 12.0) -> None:
        """Tutor reveals the correct word->action pair: synapses whose
        eligibility connects the current input pattern to the CORRECT pool
        strengthen; the wrongly-chosen pool's eligible synapses weaken.
        Same sign/cap/modulatory constraints as reinforce()."""
        with self._lock:
            self._tutor_correct_impl(chosen_action, correct_action,
                                     lr_good, lr_bad)

    def _tutor_correct_impl(self, chosen_action: int, correct_action: int,
                            lr_good: float = 20.0, lr_bad: float = 12.0) -> None:
        good = self._plastic_active * (self._pool_of_post == correct_action)
        bad = self._plastic_active * (self._pool_of_post == chosen_action)
        self.w += lr_good * self.e * good
        self.w -= lr_bad * self.e * bad
        pos = self._w_sign > 0
        neg = self._w_sign < 0
        self.w[pos] = np.clip(self.w[pos], 0.0, self.p.w_cap)
        self.w[neg] = np.clip(self.w[neg], -self.p.w_cap, 0.0)
        self.w[~self._plastic_active] = 0.0