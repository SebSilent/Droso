"""A zero must say WHY it is zero.

`KnowledgeChannel.ask` returned "no target name in the assertions" before counting anything,
so a three-arm experiment over 94 tasks reported `asked: 0` -- indistinguishable from a channel
that was never called. That is the same failure the oracle fence produced twice: a report
reading zero for "never engaged", with the real cause only recoverable by reading source.

These tests pin the two directions: a program-shaped task must report `entered` with a named
reason, and a normal function-shaped task must still be counted as an ordinary ask.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.knowledge import KnowledgeChannel  # noqa: E402
from organs.program_task import encode  # noqa: E402


class _Oracle:
    """Reachable, and it answers -- so any zero below is the channel's doing, not the wire."""

    provider = "stub"
    model = "stub"
    has_key = True

    class _Budget:
        def start_task(self):
            return None

    budget = _Budget()

    def __init__(self):
        self.calls = 0

    def query(self, *a, **k):
        self.calls += 1
        return {"ok": True, "text": "def f(*a):\n    return a[0]\n", "finish_reason": "stop"}


def test_a_program_shaped_task_reports_the_reason_instead_of_a_bare_zero():
    """CodeContests-shaped check: a JSON blob, no Python assertion to read a name from."""
    check = encode([["2\n1 2\n", "3\n"], ["4\n5 6 7 8\n", "26\n"]])
    ch = KnowledgeChannel(oracle=_Oracle(), loop=None)
    out = ch.ask("Sum the integers that appear on stdin.", check)
    st = ch.stats()

    assert out["asked"] is False, "a program task cannot be asked in function form"
    assert "no target name" in out["reason"]
    # THE POINT: the call was SEEN. A zero on `asked` alone would have meant nothing.
    assert st["entered"] == 1, "the call must be counted even though it returned early"
    assert st["no_target"] == 1, "the reason must be named, not inferred"
    assert st["asked"] == 0 and st["accepted"] == 0
    assert ch.oracle.calls == 0, "no oracle call is made without a target"


def test_a_function_shaped_task_is_still_an_ordinary_ask():
    """The counter that was added must not swallow the normal path."""
    ch = KnowledgeChannel(oracle=_Oracle(), loop=None)

    class _Loop:
        def _attempt(self, artifact, check):
            return True, "stub accepted"

    ch.loop = _Loop()
    out = ch.ask("Return the first argument.", "assert f(2, 3) == 2")
    st = ch.stats()

    assert out["asked"] is True
    assert st["entered"] == 1
    assert st["no_target"] == 0
    assert st["asked"] == 1, "the ordinary path still counts a call"


def test_a_refused_call_is_not_filed_under_no_target():
    """Reachable-but-closed and never-engaged are different, and must not share a counter."""
    class _Closed(_Oracle):
        def query(self, *a, **k):
            self.calls += 1
            return {"ok": False, "reason": "offline_mode"}

    ch = KnowledgeChannel(oracle=_Closed(), loop=None, retries=0)
    ch.ask("Return the first argument.", "assert f(2, 3) == 2")
    st = ch.stats()

    assert st["entered"] == 1
    assert st["asked"] == 1
    assert st["refused_offline"] == 1, "the fence must be visible as its own reason"
    assert st["no_target"] == 0
    assert st["accept_rate"] == 0.0
