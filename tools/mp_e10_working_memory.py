"""MP-E10 checklist step 1 -- the decayed working-memory trace, parameterized by k.

    "Plasticize the central-complex loop into a decayed activation trace over the last k
     tokens; a fast-weight state computed by spread, replacing unigram context."
                                                DROSO Master Plan v1.1, 6.3 / B.4 step 1

WHAT THIS IS FOR. The house selects on a bag of the words present: a token contributes to the
semantic state whether it arrived first or last, so "the dog bites the man" and "the man bites
the dog" select the same way. This module is the seconds-scale alternative -- an explicit trace of
the last k tokens, each one fading with its age, and a fast-weight state that reads a probe vector
through that trace instead of through an unigram count. It is a harness organ, not a Droso internal:
nothing here is imported by the house, and no house file is modified. The plan forbids that during a
run, and MP-E10's own registration says so in `constraints_from_the_plan`.

THE TWO THINGS THAT MUST BE TRUE, because the registration makes them abort conditions rather than
preferences (experiments/MP-E10/registration.json, abort_conditions C4):
  * BOUNDED DECAY. A token older than k steps contributes at most `floor_eps` of one fresh token's
    weight, and the state's norm cannot grow with the number of tokens ever seen -- only with k.
    A trace that only looks short is not bounded; this one is arithmetic, not attention.
  * RESTART CLEARING. A restart clears the trace completely. If any of it survives, C4 fires by
    definition: the state is seconds-scale, and a seconds-scale memory that outlives a restart is
    not a seconds-scale memory. tests/test_mp_e10_working_memory.py is that test, and it exists as
    code rather than as a sentence in a decision file for exactly that reason.

SPREAD, NOT A NEW PRIMITIVE. `read()` sums the rows of the fast-weight matrix that the probe
touches, which is the same algebra `organs/neural_language.py:_spread()` uses on `san_w` (a
gather instead of a gemv, because the matrix is large and the probe is sparse). It is reimplemented
here on THIS module's own state; the house's weights are not read, touched or required.

k is a constructor argument and MP-E10 registers the sweep [1, 2, 4, 8, 14, 16, 22] against the
longest taught utterance (14 tokens) -- see k_sweep in the registration. Nothing in this file picks
a k: that is the experiment's measurement, and the grid was registered before any treatment.

WHAT k BOUNDS, AND WHAT IT DOES NOT (PI ruling D-MPE10-06, 2026-08-10). The plan describes two
objects -- "a decayed activation trace over the last k tokens" and "a fast-weight state computed by
spread" -- and this module implements exactly that: `k` bounds the RING (`self.ring`, `self.age`),
never the associative store. `self.w` accumulates every adjacent pair pushed since construction or
`clear()`, and its Frobenius norm grows with tokens pushed, not with k -- measured identical at
k=2, k=8 and k=22 over a 64-token stream. That is a property of the design, not a defect: every
MP-E10 artifact reports ||w||_F against tokens pushed as its own quantity rather than folding it
into a capacity claim.

k=1 IS DEGENERATE AND EXCLUDED FROM THE SCORED GRID (D-MPE10-07, same date). At k=1,
`(head-1) % k == head`, so `prev` aliases the slot `push()` is about to overwrite and the "pair"
recorded is outer(v, v). Measured diagonal mass 3.679 at k=1 against -0.039 (zero) at every other k.
The value stays in the registered grid and keeps being printed, because the diagonal mass is the
detector; it is excluded from any grid used to score a run.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECAY = 0.5      # geometric, per step; a token's weight is DECAY ** age
FLOOR_EPS = 1e-3         # "contributes nothing" threshold, in units of one fresh token


class DecayedTrace:
    """A trace of the last k token vectors, with a fast-weight state beside it.

    The trace holds activity; the fast-weight state holds ASSOCIATIONS formed while that activity
    was live -- what was present when each token arrived. `read()` is the second-timescale answer
    to a probe: it returns what the trace would spread into, given the links formed during it.
    """

    def __init__(self, k: int, dim: int, *, decay: float = DEFAULT_DECAY,
                 seed: int | None = None) -> None:
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k!r}")
        if not 0.0 < decay < 1.0:
            raise ValueError(f"decay must be in (0,1) so the trace is bounded, got {decay!r}")
        self.k = int(k)
        self.dim = int(dim)
        self.decay = float(decay)
        self.ring = np.zeros((self.k, self.dim), dtype=np.float32)
        self.age_ok = np.zeros(self.k, dtype=bool)
        self.head = 0
        self.n_pushed = 0
        # Fast-weight state: outer(post, pre) accumulated for adjacent pairs in the trace.
        self.w = np.zeros((self.dim, self.dim), dtype=np.float32)
        self._rng = np.random.default_rng(seed)

    # -- the trace ---------------------------------------------------------
    def push(self, vec) -> None:
        v = np.asarray(vec, dtype=np.float32).reshape(-1)
        if v.shape[0] != self.dim:
            raise ValueError(f"vector of {v.shape[0]} into a trace of dim {self.dim}")
        prev = self.ring[(self.head - 1) % self.k] if self.age_ok.any() else None
        self.ring[self.head] = v
        self.age_ok[self.head] = True
        self.head = (self.head + 1) % self.k
        self.n_pushed += 1
        if prev is not None:
            self.w += np.outer(v, prev)          # the pair that was contiguous when it happened

    def weights(self) -> np.ndarray:
        """Weight of each slot by its AGE: newest 1.0, then decay, decay**2 ...

        Anything older than k steps is not in the trace at all -- it was overwritten -- so the
        oldest slot's weight is exactly decay**(k-1), and that is the bound the test checks.
        """
        out = np.zeros(self.k, dtype=np.float32)
        n = min(self.n_pushed, self.k)
        for age in range(n):
            out[(self.head - 1 - age) % self.k] = self.decay ** age
        return out

    def state(self) -> np.ndarray:
        """The activation trace as a single vector: each slot's vector times its age weight."""
        w = self.weights()[:, None]
        return (self.ring * w).sum(axis=0)

    def read(self, probe) -> np.ndarray:
        """Spread a probe through the fast-weight state -- rows it touches, summed.

        Same gather-not-gemv shape as the house's `_spread()`: the probe is sparse, so the touched
        rows are read directly. An asymmetric state is what carries ORDER, and a symmetric one
        cannot (see organs/sequence_organ.py's design note).

        WHICH WAY IT READS, named because a bare "alignment" figure is not enough (PI ruling
        D-MPE10-08, 2026-08-10). The state is outer(post, pre), so a link maps a token to the token
        that PRECEDED it: this is a PREDECESSOR map. Probing the later token returns the earlier one
        strongly; probing the earlier token does not return the later one -- measured 0.982 against
        0.056 on the tier-40 calibration sweep. Producing the NEXT word needs the successor
        transpose, and supplying it is a registered organ change with its own design step, not
        something this method may quietly become.

        SELF-LINKS are excluded for k >= 2, since a link is always outer(v_i, v_{i-1}) with distinct
        i. They are NOT excluded at k = 1: there `(head-1) % k == head`, so `prev` is a view of the
        slot push() has just overwritten and the link recorded is outer(v, v). Measured diagonal
        mass 3.679 at k=1 against -0.039 (zero) at every other k. An earlier revision of this
        docstring claimed exclusion "by construction", which that measurement shows to be false; the
        behaviour was left as it is and the claim is what was corrected (D-MPE10-07, 2026-08-10).
        """
        p = np.asarray(probe, dtype=np.float32).reshape(-1)
        idx = np.nonzero(p)[0]
        if idx.size == 0:
            return np.zeros(self.dim, dtype=np.float32)
        return p[idx] @ self.w[idx, :]

    # -- restart -----------------------------------------------------------
    def clear(self) -> None:
        """A restart. Everything goes: the ring, the validity mask, the fast-weight state."""
        self.ring[:] = 0.0
        self.age_ok[:] = False
        self.w[:] = 0.0
        self.head = 0
        self.n_pushed = 0

    def fingerprint(self) -> str:
        """Bytes of everything that could survive a restart. C4's test compares these."""
        h = hashlib.sha256()
        for arr in (self.ring, self.w):
            h.update(np.ascontiguousarray(arr, dtype=np.float32).tobytes())
        h.update(np.packbits(self.age_ok).tobytes())
        return h.hexdigest()

    def report(self) -> dict:
        w = self.weights()
        return {
            "k": self.k, "dim": self.dim, "decay_per_step": self.decay,
            "n_pushed": self.n_pushed,
            "oldest_slot_weight": round(float(w[w > 0].min()) if (w > 0).any() else 0.0, 8),
            "newest_slot_weight": round(float(w.max()), 8) if (w > 0).any() else 0.0,
            "state_norm": round(float(np.linalg.norm(self.state())), 6),
            "fast_weight_norm": round(float(np.linalg.norm(self.w)), 6),
            "fingerprint": self.fingerprint(),
        }


def unigram_context(tokens: list[np.ndarray]) -> np.ndarray:
    """The thing being replaced, kept so the comparison is measured rather than asserted.

    The house's current context is a count over the words present. Order is invisible to it: two
    sequences with the same multiset give the same vector. The test asserts the trace separates
    those two and the unigram context cannot.
    """
    if not tokens:
        return np.zeros(0, dtype=np.float32)
    return np.mean(np.stack([np.asarray(t, dtype=np.float32) for t in tokens]), axis=0)


def sweep(k_values: list[int], seq: list[np.ndarray], *, dim: int,
          decay: float = DEFAULT_DECAY) -> list[dict]:
    """Run the same sequence through the trace at each registered k, and report what it held."""
    out = []
    for k in k_values:
        t = DecayedTrace(k, dim, decay=decay)
        for v in seq:
            t.push(v)
        r = t.report()
        r["tokens_held"] = min(len(seq), k)
        r["tokens_dropped"] = max(0, len(seq) - k)
        out.append(r)
    return out


def main() -> int:
    """Emit the k-sweep grid the checklist step 5 asks for, over a synthetic sequence.

    This is a CHARACTERISATION of the organ, not a scored run: no curriculum, no tier, no
    hypothesis. It exists so the grid is reproducible from the command line before any treatment
    arm is measured, and so the artifact's provenance can name the commit that produced it.
    """
    reg = json.loads((ROOT / "experiments" / "MP-E10" / "registration.json")
                     .read_text(encoding="utf-8"))
    grid = reg["k_sweep"]["grid_tokens"]
    dim = 16
    rng = np.random.default_rng(20261104)
    seq = [rng.normal(size=dim).astype("float32") for _ in range(24)]
    out = {
        "experiment": "MP-E10",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "organ characterisation -- NOT a scored run, NOT a hypothesis test",
        "k_sweep": sweep(grid, seq, dim=dim),
        "provenance": {"module": "tools/mp_e10_working_memory.py", "dim": dim,
                       "n_tokens": len(seq), "decay_per_step": DEFAULT_DECAY,
                       "seed": 20261104},
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
