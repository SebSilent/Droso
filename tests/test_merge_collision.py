"""Two lives must not be able to quietly overwrite each other's procedures.

THE MEASURED DEFECT THIS EXISTS FOR. `exp_screened2`'s number-slice marginal curve dropped
1L->16 to 2L->15: adding a life made a solved task unsolved. The task's fact reference
('divisible find number python whether') was identical at both points and present in the
store at both -- but the code it resolved to changed from 51 characters to 42. The 51-char
procedure passed the task's own assertions; the 42-char one did not. Two lives had filed
different code under one store signature and `dict.update` let the later one win, silently.

So the policy is stated here rather than left implicit: KEEP THE FIRST, and say so out loud.
A fact's value is a store key, and overwriting that key changes what an already-filed fact
resolves to without changing the fact itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.population_experiment import (  # noqa: E402
    LAST_MERGE_COLLISIONS, MergeCollision, merge_arms, merge_stores)


def _arm(facts=None, store=None, sources=None):
    return {"facts": dict(facts or {}), "fact_sources": dict(sources or {}),
            "store": dict(store or {})}


def test_a_colliding_store_key_keeps_the_first_and_reports_it(capsys):
    """The exact shape of the defect: same key, different code."""
    arms = {
        "a": _arm(store={"divisible find number python whether": {"solutions": [{"text": "GOOD-51-chars"}]}}),
        "b": _arm(store={"divisible find number python whether": {"solutions": [{"text": "BAD-42"}]}}),
    }
    st, collisions = merge_stores(arms, ["a", "b"])

    assert len(collisions) == 1
    assert collisions[0]["key"] == "divisible find number python whether"
    assert collisions[0]["kept_from"] == "a"
    assert collisions[0]["dropped_from"] == "b"
    # THE POINT: the first life's procedure survives, so any fact pointing at this key still
    # resolves to the code that was filed with it.
    assert st["divisible find number python whether"]["solutions"][0]["text"] == "GOOD-51-chars"
    assert "MERGE COLLISION" in capsys.readouterr().out, "the collision must be LOUD"


def test_strict_mode_raises_instead_of_choosing(tmp_path):
    arms = {"a": _arm(store={"k": {"solutions": [{"text": "one"}]}}),
            "b": _arm(store={"k": {"solutions": [{"text": "two"}]}})}
    with pytest.raises(MergeCollision):
        merge_stores(arms, ["a", "b"], strict=True)


def test_identical_values_under_one_key_are_not_a_collision(capsys):
    """Two lives that worked out the SAME procedure have not collided in any way that matters."""
    same = {"solutions": [{"text": "identical"}]}
    arms = {"a": _arm(store={"k": dict(same)}), "b": _arm(store={"k": dict(same)})}
    st, collisions = merge_stores(arms, ["a", "b"])
    assert collisions == []
    assert st["k"]["solutions"][0]["text"] == "identical"
    assert "MERGE COLLISION" not in capsys.readouterr().out


def test_merge_arms_does_not_reintroduce_the_silent_overwrite(capsys):
    """The regression guard: `merge_arms` is the function the experiment actually calls."""
    before = len(LAST_MERGE_COLLISIONS)
    arms = {"a": _arm(store={"sig": {"solutions": [{"text": "correct"}]}}),
            "b": _arm(store={"sig": {"solutions": [{"text": "wrong"}]}})}
    f, s, st = merge_arms(arms, ["a", "b"])
    assert st["sig"]["solutions"][0]["text"] == "correct"
    assert len(LAST_MERGE_COLLISIONS) > before, "the collision must be recorded, not swallowed"
    assert "MERGE COLLISION" in capsys.readouterr().out


def test_disjoint_stores_still_union_completely(capsys):
    """The guard must not cost anything when there is no collision -- which is the normal case."""
    arms = {"a": _arm(store={"ka": {"solutions": [{"text": "A"}]}},
                      facts={("count", "list", "int"): "ref-a"}),
            "b": _arm(store={"kb": {"solutions": [{"text": "B"}]}},
                      facts={("sum", "list", "int"): "ref-b"})}
    f, s, st = merge_arms(arms, ["a", "b"])
    assert set(st) == {"ka", "kb"}
    assert set(f) == {("count", "list", "int"), ("sum", "list", "int")}
    assert "MERGE COLLISION" not in capsys.readouterr().out
