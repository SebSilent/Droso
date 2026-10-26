"""
The held-out set is an instrument, and an instrument that can silently bank its
own answers is broken: the 30-day-old `novel` group decayed from first-contact
tasks into 9/9 replay because solutions got learned from earlier runs.

Two layers protect it, and both are tested here against the real module:

    --heldout without --no-learn   implies --no-learn (CLI convenience)
    run(tasks=HELDOUT, learn=True) raises (programmatic misuse)

The second layer is the one that matters: a caller who bypasses the CLI must
not be able to hand the first-contact set to a learning run.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.task_battery as tb                                # noqa: E402


def test_heldout_implies_no_learn(monkeypatch, capsys):
    """--heldout alone must reach run() as learn=False, with the HELDOUT set."""
    seen = {}

    def fake_run(only=None, learn=True, use_oracle=True, provider="ollama",
                 tasks=None):
        seen.update(only=only, learn=learn, tasks=tasks)
        return {}

    monkeypatch.setattr(tb, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["task_battery.py", "--heldout"])
    assert tb.main() == 0
    assert seen["learn"] is False
    assert seen["tasks"] is tb.HELDOUT
    assert "--heldout implies --no-learn" in capsys.readouterr().err


def test_explicit_no_learn_still_heldout(monkeypatch):
    """--heldout --no-learn: the explicit flag is not second-guessed."""
    seen = {}

    def fake_run(only=None, learn=True, use_oracle=True, provider="ollama",
                 tasks=None):
        seen.update(learn=learn, tasks=tasks)
        return {}

    monkeypatch.setattr(tb, "run", fake_run)
    monkeypatch.setattr(sys, "argv",
                        ["task_battery.py", "--heldout", "--no-learn"])
    assert tb.main() == 0
    assert seen["learn"] is False
    assert seen["tasks"] is tb.HELDOUT


def test_default_battery_still_learns(monkeypatch):
    """Without --heldout the 30-day battery keeps its own behaviour."""
    seen = {}

    def fake_run(only=None, learn=True, use_oracle=True, provider="ollama",
                 tasks=None):
        seen.update(learn=learn, tasks=tasks)
        return {}

    monkeypatch.setattr(tb, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["task_battery.py"])
    assert tb.main() == 0
    assert seen["learn"] is True
    assert seen["tasks"] is None


def test_run_refuses_heldout_with_learning():
    """The programmatic guard: learning from the first-contact set refuses."""
    import pytest
    with pytest.raises(ValueError, match="learn=False"):
        tb.run(tasks=tb.HELDOUT, learn=True)


# ------------------------------------------------------------------ rungs
#
# The run loop is a ladder: router (+repair) -> compose -> grammar -> oracle.
# The 0/10 was a rung the battery never fired, so these tests pin the ladder's
# order and its honesty properties against stubbed organs: house-down, off the
# live library, and fast.

import pytest                                                   # noqa: E402
import organs.reasoning_loop as rl                              # noqa: E402
import organs.api_oracle as ao                                  # noqa: E402


class _Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)


_TASK = {"group": "own", "task": "write f", "check": "assert f() == 1"}
_DECLINE = {"solution": "", "route_path": "reasoning_loop", "method": "none"}


def _stub_organs(monkeypatch, *, compose_out, router_run=None, oracle=None,
                 store=None):
    """Replace _build with stubs. The sandbox always reports success, so the
    battery's own gate passes whatever code reaches it; the tests then assert
    on WHICH rung's code got there."""
    def fake_build(use_library, learn=True):
        solver = _Stub(repair_against=lambda code, check: {"ok": False},
                       compose_against=lambda task, check, budget=4:
                           compose_out)
        sb = _Stub(run_python=lambda code, timeout=25, name="x":
                   {"success": True, "returncode": 0, "stderr": "",
                    "output": ""})
        router = _Stub(run=router_run or (lambda task: dict(_DECLINE)))
        learning = _Stub(store=store) if store is not None else None
        return router, solver, learning, sb
    monkeypatch.setattr(tb, "_build", fake_build)
    if oracle is not None:
        monkeypatch.setattr(ao, "oracle_from_config",
                            lambda cfg, provider=None: oracle)


def test_compose_rung_fires_and_oracle_is_skipped(monkeypatch):
    """A compose pass is labelled compose, and the model is never called."""
    def boom(*a, **k):
        raise RuntimeError("oracle must not be called")
    _stub_organs(monkeypatch,
                 compose_out={"ok": True, "code": "def f():\n    return 1",
                              "method": "primitives", "tried": 3},
                 oracle=_Stub(mode="fake", has_key=True, query=boom))
    out = tb.run(tasks=[dict(_TASK)], learn=False, use_oracle=True)
    row = out["rows"][0]
    assert row["passed"] is True
    assert row["rung"] == "compose"
    assert row["oracle_calls"] == 0
    assert out["by_rung"] == {"compose": 1}


def test_grammar_rung_fires_when_compose_declines(monkeypatch):
    """compose declines -> the loop's grammar gets its turn, labelled grammar.

    The fake loop also asserts learn=False itself: the battery must not learn
    from the loop's episodes."""
    class FakeLoop:
        def __init__(self, **kw):
            self.trace = []

        def step(self, task, check, learn=True):
            assert learn is False, "battery must not learn from the loop"
            return {"outcome": "solved", "candidate": "prog:count+plain",
                    "candidates": 5, "attempts": 2, "best_pred": 0.5}

        def _candidates(self, task, check):
            return ([{"code": "def f():\n    return 1",
                      "label": "prog:count+plain", "score": 0.45}], {})
    monkeypatch.setattr(rl, "ReasoningLoop", FakeLoop)
    _stub_organs(monkeypatch, compose_out={"ok": False, "reason": "nothing"})
    out = tb.run(tasks=[dict(_TASK)], learn=False, use_oracle=False)
    row = out["rows"][0]
    assert row["passed"] is True
    assert row["rung"] == "grammar"
    assert row["grammar"]["outcome"] == "solved"
    assert row["solution_chars"] > 0
    assert out["by_rung"] == {"grammar": 1}


def test_oracle_still_fires_after_both_local_rungs_decline(monkeypatch):
    """The ladder keeps its order: both local rungs decline -> the model runs."""
    class RefusingLoop:
        def __init__(self, **kw):
            self.trace = []

        def step(self, task, check, learn=True):
            return {"outcome": "refused", "candidates": 0, "attempts": 0}

        def _candidates(self, task, check):
            return ([], {})
    monkeypatch.setattr(rl, "ReasoningLoop", RefusingLoop)
    oracle = _Stub(mode="fake", has_key=True,
                   query=lambda *a, **k: {"ok": True, "mode": "api",
                                          "text": "```python\ndef f():\n"
                                                  "    return 1\n```",
                                          "tokens": 5})
    _stub_organs(monkeypatch, compose_out={"ok": False, "reason": "nothing"},
                 oracle=oracle)
    out = tb.run(tasks=[dict(_TASK)], learn=False, use_oracle=True)
    row = out["rows"][0]
    assert row["passed"] is True
    assert row["rung"] == "oracle"
    assert row["oracle_calls"] == 1


def test_grammar_error_is_contained(monkeypatch):
    """A raising loop must not crash the run; the row records the error."""
    class BrokenLoop:
        def __init__(self, **kw):
            self.trace = []

        def step(self, task, check, learn=True):
            raise RuntimeError("boom")
    monkeypatch.setattr(rl, "ReasoningLoop", BrokenLoop)
    _stub_organs(monkeypatch, compose_out={"ok": False, "reason": "nothing"})
    out = tb.run(tasks=[dict(_TASK)], learn=False, use_oracle=False)
    row = out["rows"][0]
    assert row["passed"] is False
    assert row["rung"] == "router"
    assert row["grammar"]["outcome"] == "error"
    assert "boom" in row["grammar"]["reason"]


def test_no_learn_run_refuses_store_mutation(monkeypatch):
    """Third no-learn layer: ANY leak that changes the library during a
    learn=False run hard-fails, no matter which line did it."""
    store = {"sig1": {}}

    def leaky(task):
        store["leaked"] = {}
        return dict(_DECLINE)

    _stub_organs(monkeypatch, compose_out={"ok": False, "reason": "nothing"},
                 router_run=leaky, store=store)
    with pytest.raises(RuntimeError, match="changed the live library"):
        tb.run(tasks=[dict(_TASK)], learn=False, use_oracle=False)


def test_no_learn_run_with_intact_store_passes(monkeypatch):
    """The same guard, positive control: an intact store raises nothing."""
    class RefusingLoop:
        def __init__(self, **kw):
            self.trace = []

        def step(self, task, check, learn=True):
            return {"outcome": "refused", "candidates": 0, "attempts": 0}

        def _candidates(self, task, check):
            return ([], {})
    monkeypatch.setattr(rl, "ReasoningLoop", RefusingLoop)
    store = {"sig1": {}}
    _stub_organs(monkeypatch, compose_out={"ok": False, "reason": "nothing"},
                 store=store)
    out = tb.run(tasks=[dict(_TASK)], learn=False, use_oracle=False)
    assert out["rows"][0]["passed"] is False
    assert out["rows"][0]["rung"] == "router"


# ----------------------------------------------------------------- the seal
#
# Measured 2026-10-25: a --no-learn regression run banked 12 reinforces. The
# learn flag gated the battery's own bank call, but the router's recall branch
# (fast_router) reinforces and aliases on its own account, and an earlier
# probe batch had already done the same to one entry. The fix is a read_only
# seal on the LearningLoop itself -- the object every writer converges on --
# and _build threads the flag down to it. The store-count guard in run()
# remains the end-to-end verifier; these tests pin the seal's own behaviour.

def test_read_only_loop_writes_nothing(tmp_path):
    """A read_only loop refuses every writer and touches no file, in memory
    or on disk: learn=False must mean zero writes, not a gated bank path."""
    from organs.learning_loop import LearningLoop
    st = tmp_path / "st.json"
    ev = tmp_path / "ev.jsonl"
    loop = LearningLoop(state_path=st, events_path=ev, persist=True,
                        read_only=True)
    task = "write a function fib(n) returning the nth fibonacci number"
    code = "def fib(n):\n    return n if n < 2 else fib(n - 1) + fib(n - 2)"
    banked = loop.learn_from_task(task, code,
                                  {"source": "test", "verified": True},
                                  verified=True)
    reinforced = loop.reinforce(task, True)
    aliased = loop.alias_request("fibonacci number return", task)
    assert banked == {"stored": False, "reason": "read_only"}
    assert reinforced == {"known": False, "reason": "read_only"}
    assert aliased == {"aliased": False, "reason": "read_only"}
    assert loop.store == {}
    assert not st.exists() and not ev.exists()


def test_unsealed_loop_still_writes(tmp_path):
    """Positive control: the same calls on a loop without the seal do write,
    so the gate above is the flag and not a writer that was already broken."""
    from organs.learning_loop import LearningLoop, signature
    st = tmp_path / "st.json"
    ev = tmp_path / "ev.jsonl"
    loop = LearningLoop(state_path=st, events_path=ev, persist=True)
    task = "write a function fib(n) returning the nth fibonacci number"
    code = "def fib(n):\n    return n if n < 2 else fib(n - 1) + fib(n - 2)"
    banked = loop.learn_from_task(task, code,
                                  {"source": "test", "verified": True},
                                  verified=True)
    assert banked.get("stored") is True
    assert st.exists() and ev.exists()
    aliased = loop.alias_request(signature(task),
                                 "please write fib that gives the nth "
                                 "fibonacci number")
    assert aliased.get("aliased") is True


def test_build_threads_read_only(monkeypatch):
    """_build must pass the learn flag down as read_only on the loop: the
    seal lives on the object, so the battery's gate has to reach it."""
    import organs.learning_loop as ll
    seen = {}
    real_init = ll.LearningLoop.__init__

    def spy_init(self, *a, **kw):
        seen.update(kw)
        real_init(self, *a, **kw)

    monkeypatch.setattr(ll.LearningLoop, "__init__", spy_init)
    _, _, learning, _ = tb._build(True, learn=False)
    assert seen.get("read_only") is True
    assert learning.read_only is True
    _, _, learning2, _ = tb._build(True, learn=True)
    assert learning2.read_only is False