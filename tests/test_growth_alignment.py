"""Track A regression: one structural change is five arrays and they must agree.

The reported failure, from `/api/neural/growth`:

    IndexError: boolean index did not match indexed array along axis 0;
    size of axis is 20101 but size of corresponding boolean axis is 20071

Ownership, not shape. The structural index lives on the graph
(`plastic_pre/post/w0`) and the learner state lives on the core
(`w/e/_pool_of_post`), so one grow is a resize of two owners -- and only two of the
five appends were inside the lock. A prune arriving between them built its mask from
a 20,071-long `self.w` and applied it to a 20,101-long `plastic_pre`.

These tests fail against that version. The threaded one reproduces the interleaving
directly; the last one checks the guard actually fires, because a guard that never
fires is a guard nobody has verified.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def core():
    from connectome.engine import HybridEngine
    from connectome.substrate import build_core_graph
    graph = build_core_graph()
    eng = HybridEngine(graph=graph)
    return eng.static


def _sizes(core) -> dict:
    g = core.g
    return {"plastic_pre": len(np.asarray(g.plastic_pre)),
            "plastic_post": len(np.asarray(g.plastic_post)),
            "plastic_w0": len(np.asarray(g.plastic_w0)),
            "w": len(np.asarray(core.w)),
            "e": len(np.asarray(core.e)),
            "pool_of_post": len(np.asarray(core._pool_of_post))}


def _assert_all_equal(core, why: str):
    s = _sizes(core)
    assert len(set(s.values())) == 1, f"{why}: {s}"


def test_growth_keeps_the_structural_arrays_aligned(core):
    """Grow N steps; no shape drift."""
    before = _sizes(core)["w"]
    for _ in range(12):
        core.grow_plastic(7)
    after = _sizes(core)
    assert after["w"] == before + 12 * 7, after
    _assert_all_equal(core, "after 12 grows")


def test_pruning_after_growth_does_not_misindex(core):
    """The exact reported failure: a mask from one array applied to another."""
    core.grow_plastic(20)
    _assert_all_equal(core, "before prune")
    before = _sizes(core)["w"]
    # Make some synapses prunable, or prune removes nothing and the mask path is
    # never exercised -- which is how this shipped. Count the ones already below
    # threshold so the assertion is exact rather than approximately right.
    pre_prunable = int((np.abs(np.asarray(core.w)) < 0.004).sum())
    kill = 20
    core.w[:kill] = 0.0
    removed = core.prune_plastic(threshold=0.004)
    assert removed == kill + pre_prunable, (removed, kill, pre_prunable)
    after = _sizes(core)
    assert after["w"] == before - removed, after
    _assert_all_equal(core, "after prune")


def test_concurrent_growth_and_pruning_never_desynchronise(core):
    """The interleaving that caused it, run deliberately.

    Every append is now inside one lock acquisition. Before that fix this raised
    IndexError within a few hundred iterations, because a prune could land between
    the locked appends and the unlocked ones.
    """
    stop = threading.Event()
    errors: list = []

    def grower():
        while not stop.is_set():
            try:
                core.grow_plastic(3)
            except AssertionError:
                raise
            except Exception as e:                       # pragma: no cover
                errors.append(("grow", repr(e)))
                break

    def pruner():
        while not stop.is_set():
            try:
                np.asarray(core.w)[:2] = 0.0
                core.prune_plastic(threshold=0.004)
            except AssertionError:
                raise
            except Exception as e:                       # pragma: no cover
                errors.append(("prune", repr(e)))
                break

    threads = [threading.Thread(target=grower) for _ in range(2)] + \
              [threading.Thread(target=pruner) for _ in range(2)]
    for t in threads:
        t.start()
    import time
    time.sleep(2.0)
    stop.set()
    for t in threads:
        t.join(timeout=10)
    assert not errors, f"concurrent resize desynchronised: {errors}"
    _assert_all_equal(core, "after concurrent grow/prune")


def test_the_alignment_guard_actually_fires(core):
    """A guard nobody has seen fire is a guard nobody has verified."""
    core.grow_plastic(5)
    _assert_all_equal(core, "healthy before deliberate damage")
    core.w = np.asarray(core.w)[:-3]        # desynchronise on purpose
    with pytest.raises(AssertionError) as e:
        core.grow_plastic(3)
    assert "out of alignment" in str(e.value)
