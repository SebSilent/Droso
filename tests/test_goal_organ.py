"""Phase 5a: does a goal survive the moment it was set?

The property under test is delay activity, and it is the one thing a Python dict
cannot do. A dict holds a goal while a function is in scope and not one millisecond
after, so every step of a multi-step task started from scratch. These tests fail
against that design by construction -- not because it was buggy, but because it had
no persistence to be buggy about.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.goal import GoalOrgan  # noqa: E402


class FakeLanguage:
    """Stands in for the projection-neuron address the real organ hashes onto."""

    def __init__(self, cells=8):
        self.asked = []
        self.cells = cells

    def _pn_percept(self, key):
        self.asked.append(key)
        import numpy as np
        idx = np.arange(self.cells, dtype=np.int64)
        amp = np.ones(self.cells, dtype=float)
        return (idx, amp)


def test_a_held_goal_produces_drive():
    g = GoalOrgan(FakeLanguage())
    r = g.hold("find the file that writes state")
    assert r["held"] is True
    d = g.drive()
    assert d is not None
    idx, amp = d
    assert len(idx) == 8 and float(amp.max()) > 0.0


def test_the_goal_survives_silence():
    """Delay activity: still driving after time passed and nothing restated it."""
    g = GoalOrgan(FakeLanguage(), half_life=1.0)
    g.hold("count the books on the shelf")
    time.sleep(0.35)
    d = g.drive()
    assert d is not None, "the goal did not survive 0.35s of silence"
    assert g.sustained_for() >= 0.3
    # and it is weaker, which is what leaking means
    _, amp = d
    assert float(amp.max()) < 1.0


def test_a_goal_fades_out_and_is_recorded_as_faded():
    g = GoalOrgan(FakeLanguage(), half_life=0.05)
    g.hold("something he will forget")
    time.sleep(0.5)
    assert g.drive() is None
    rep = g.report()
    assert rep["goal"] is None and rep["expired_total"] == 1
    # "he dropped it" and "he never had one" are different facts
    assert rep["held_total"] == 1


def test_returning_to_a_goal_strengthens_rather_than_resets():
    g = GoalOrgan(FakeLanguage(), half_life=5.0)
    g.hold("fix the failing test", strength=1.0)
    first = g.report()["strength"]
    g.hold("fix the failing test", strength=1.0)
    second = g.report()["strength"]
    assert second > first
    assert g.report()["refreshed_total"] == 1
    assert g.report()["held_total"] == 1, "a refresh is not a new goal"


def test_a_new_goal_replaces_the_old_one():
    lang = FakeLanguage()
    g = GoalOrgan(lang)
    g.hold("read the corpus")
    g.hold("write the report")
    assert g.report()["goal"] == "write the report"
    assert g.report()["held_total"] == 2
    assert "goal|write the report" in lang.asked


def test_release_is_not_the_same_as_fading():
    g = GoalOrgan(FakeLanguage(), half_life=5.0)
    g.hold("a goal he abandons on purpose")
    out = g.release()
    assert out["released"] == "a goal he abandons on purpose"
    assert g.drive() is None
    assert g.report()["expired_total"] == 0, "a release is not an expiry"


def test_a_goal_needs_words_and_needs_neurons():
    g = GoalOrgan(FakeLanguage())
    assert g.hold("   ")["held"] is False

    class NoNeurons:
        def _pn_percept(self, key):
            return None

    assert GoalOrgan(NoNeurons()).hold("anything")["held"] is False


def test_the_drive_is_shaped_like_a_scent():
    """It has to drop straight into engine.decide(extra_drive=[...])."""
    g = GoalOrgan(FakeLanguage())
    g.hold("hold this shape")
    idx, amp = g.drive()
    assert list(idx) == list(range(8))
    assert len(amp) == len(idx)
