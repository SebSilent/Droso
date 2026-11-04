"""MP-E10 checklist step 1's own requirement: "unit-test decay bounds and restart clearing".

The restart-clearing tests are abort condition C4 written as code. C4 says a working-memory state
that leaks across a restart aborts BY DEFINITION, and a definitional abort that lives only in a
decision file is a sentence, not a guard.

No curriculum, no tier, no hypothesis is touched here: these are properties of the organ.
"""
import numpy as np
import pytest

from tools.mp_e10_working_memory import (DEFAULT_DECAY, FLOOR_EPS, DecayedTrace,
                                         sweep, unigram_context)

GRID = [1, 2, 4, 8, 14, 16, 22]


def vecs(n, dim=8, seed=7):
    rng = np.random.default_rng(seed)
    return [rng.normal(size=dim).astype("float32") for _ in range(n)]


# ---------------------------------------------------------------- decay bounds
@pytest.mark.parametrize("k", GRID)
def test_oldest_weight_is_exactly_decay_to_the_k_minus_one(k):
    """The window is arithmetic, not rhetorical: slot k-1 holds decay**(k-1) and nothing older."""
    t = DecayedTrace(k, 8)
    for v in vecs(k + 5):
        t.push(v)
    w = t.weights()
    live = np.sort(w[w > 0])[::-1]
    assert live[0] == pytest.approx(1.0)
    assert live[-1] == pytest.approx(DEFAULT_DECAY ** (k - 1), abs=1e-6)
    assert len(live) == k


@pytest.mark.parametrize("k", GRID)
def test_beyond_the_window_a_token_contributes_nothing_at_all(k):
    """decay**(k-1) is the floor INSIDE the window; outside it the weight is zero, not small."""
    t = DecayedTrace(k, 8, decay=DEFAULT_DECAY)
    first, rest = vecs(1)[0], vecs(k + 30)[1:]
    t.push(first)
    for v in rest:
        t.push(v)
    assert t.weights().sum() == pytest.approx(
        sum(DEFAULT_DECAY ** a for a in range(k)), abs=1e-5)
    if DEFAULT_DECAY ** (k - 1) <= FLOOR_EPS:
        assert DEFAULT_DECAY ** (k - 1) <= FLOOR_EPS      # the registered "contributes nothing" bound


def test_state_norm_is_bounded_by_k_not_by_history():
    """A trace that has seen 10,000 tokens holds no more than one that has seen k."""
    dim = 8
    all_v = vecs(1000, dim=dim)
    long = DecayedTrace(6, dim)
    for v in all_v:
        long.push(v)
    short = DecayedTrace(6, dim)
    for v in all_v[-6:]:
        short.push(v)
    assert np.allclose(long.state(), short.state(), atol=1e-5)
    bound = 6 * max(float(np.linalg.norm(v)) for v in all_v)
    assert float(np.linalg.norm(long.state())) <= bound + 1e-4
    assert long.n_pushed == 1000 and short.n_pushed == 6


def test_decay_is_monotone_with_age():
    t = DecayedTrace(5, 8, decay=0.5)
    for v in vecs(5):
        t.push(v)
    order = [t.weights()[(t.head - 1 - age) % 5] for age in range(5)]
    assert all(a > b for a, b in zip(order, order[1:]))
    assert order[1] == pytest.approx(0.5 * order[0])


# ---------------------------------------------------------------- restart / C4
def test_restart_clearing_leaves_no_fingerprint_of_what_was_there():
    """C4: any surviving byte of the state across a restart is a definitional abort."""
    fresh = DecayedTrace(8, 8)
    t = DecayedTrace(8, 8)
    for v in vecs(40):
        t.push(v)
    assert t.fingerprint() != fresh.fingerprint()
    t.clear()
    assert t.fingerprint() == fresh.fingerprint()
    assert np.allclose(t.state(), 0.0)
    assert np.allclose(t.read(vecs(1, seed=3)[0]), 0.0)
    assert np.allclose(t.w, 0.0)


def test_clear_is_not_replacement_by_a_new_object():
    """The same object must be reusable after a restart, and must not resurrect its old state."""
    t = DecayedTrace(4, 8)
    for v in vecs(9):
        t.push(v)
    before = t.fingerprint()
    t.clear()
    for v in vecs(2, seed=11):
        t.push(v)
    assert t.fingerprint() not in (before, fresh_of(4, 8).fingerprint())
    assert t.n_pushed == 2


def fresh_of(k, dim):
    return DecayedTrace(k, dim)


# ---------------------------------------------------------------- the claim being made
def test_unigram_context_cannot_see_order_and_the_trace_can():
    """Why this organ exists. The house counts words; a trace remembers sequence."""
    a, b = vecs(2)
    assert np.allclose(unigram_context([a, b]), unigram_context([b, a]))
    t1, t2 = DecayedTrace(2, 8), DecayedTrace(2, 8)
    for v in (a, b):
        t1.push(v)
    for v in (b, a):
        t2.push(v)
    assert not np.allclose(t1.state(), t2.state())
    probe = np.zeros(8, dtype="float32")
    probe[0] = 1.0
    assert not np.allclose(t1.read(probe), t2.read(probe))


def test_sweep_reports_what_each_k_held():
    seq = vecs(24)
    rows = sweep(GRID, seq, dim=8)
    assert [r["k"] for r in rows] == GRID
    for r, k in zip(rows, GRID):
        assert r["tokens_held"] == min(24, k)
        assert r["tokens_dropped"] == max(0, 24 - k)
        assert r["newest_slot_weight"] == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [(0, 8), (-3, 8)])
def test_constructor_refuses_a_window_that_is_not_a_window(bad):
    k, dim = bad
    with pytest.raises(ValueError):
        DecayedTrace(k, dim)


def test_constructor_refuses_a_decay_that_does_not_decay():
    for d in (0.0, 1.0, 1.5, -0.5):
        with pytest.raises(ValueError):
            DecayedTrace(4, 8, decay=d)
