"""Three bugs, each of which produced a confident uniform zero, pinned as PROPERTIES.

None of them was caught by someone noticing a number looked wrong. Each was caught by a
guard refusing to guess -- the resolvability guard, the provenance tag, the read-only
fence. These tests exist so the next "simplify this" pass cannot quietly put any of them
back, and they are written against behaviour rather than against the lines that happen to
implement it today.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.concepts import extract_key, keyable          # noqa: E402
from organs.higher_cortex import Binder, ConceptSpace     # noqa: E402
from organs.knowledge import KnowledgeChannel, fact_source, file_fact   # noqa: E402
from organs.learning_loop import signature                # noqa: E402

# A task whose key is clean, so `keyable` passes and a fact is fileable.
TASK = "Write a function to find the surface area of a sphere."
CHECK = "assert surfacearea_sphere(2) == 50.26548245743669"
CODE = "def surfacearea_sphere(r):\n    return 4 * math.pi * r ** 2"


class _Stub:
    """The minimum a KnowledgeChannel needs, with the REAL Binder behind it."""

    class _Cortex:
        def __init__(self):
            self.binder = Binder(ConceptSpace())

    class _Language:
        def __init__(self):
            self.cortex = _Stub._Cortex()

    class _Learning:
        def __init__(self):
            self.store = {}

        def learn_from_task(self, task, code, meta=None, verified=True):
            # exactly what the real loop does: keyed by the signed task, holding the code
            self.store[signature(task)] = {"solutions": [{"text": code}],
                                           "confidence": 0.9}
            return True

    class _Loop:
        def __init__(self):
            self.language = _Stub._Language()
            self.learning = _Stub._Learning()
            self.trace = []

        def _attempt(self, cand, check):
            return True, None

    class _Oracle:
        def __init__(self, text):
            self.text = text
            self.budget = type("B", (), {"start_task": lambda s: None})()

        def query(self, q, max_tokens=0, temperature=0.0, purpose="",
                  no_reasoning=False):
            return {"ok": True, "text": self.text, "model": "stub",
                    "prompt_tokens_est": 1, "completion_tokens_est": 1,
                    "latency_s": 0.0}


def test_an_accepted_oracle_answer_is_actually_filed():
    """ORDERING, AS A PROPERTY: the store must be written before the fact is filed.

    `distill_fact` ran before `learn_from_task`, so `file_fact` asked whether the reference
    it was about to file existed in a store that had not been written yet, and refused. The
    ordering was harmless while filing was unconditional -- the fact is only ever RECALLED
    later -- and became fatal the moment the guard landed. Measured at the time: 25 accepted
    answers, 25 skipped, 0 facts filed, and every downstream merge read zero.

    The assertion is the consequence, not the line: an accepted answer FILES, and what it
    filed resolves.
    """
    loop = _Stub._Loop()
    ch = KnowledgeChannel(oracle=_Stub._Oracle(CODE), loop=loop)
    out = ch.ask(TASK, CHECK)
    assert out["accepted"] is True, out
    assert ch.facts_filed == 1, ("an accepted answer filed nothing -- the store is not being "
                                 "written before the fact is filed: %r" % (out.get("fact"),))
    c, s, sh = extract_key(TASK, CHECK)
    ref = loop.language.cortex.binder.facts.get((c, s, sh))
    assert ref, "no fact under the key"
    assert ref in loop.learning.store, (
        "the filed reference does not resolve in the learning store, so System 1 would find "
        "the key and then discover there is no code behind it")
    assert fact_source(loop, c, s, sh) == "oracle"


def test_file_fact_refuses_a_reference_it_cannot_resolve():
    """The guard itself, and the reason a merged fact needs its store."""
    loop = _Stub._Loop()
    out = file_fact(loop, TASK, CHECK, source="self")
    assert out["filed"] is False and "point at nothing" in out["reason"], out
    # ... and the same call succeeds once the thing it points at exists.
    loop.learning.store[signature(TASK)] = {"solutions": [{"text": CODE}]}
    out2 = file_fact(loop, TASK, CHECK, source="self")
    assert out2["filed"] is True, out2
    assert out2["source"] == "self", "provenance was not recorded at filing time"
    assert fact_source(loop, *extract_key(TASK, CHECK)) == "self"


def test_merging_arms_merges_the_learning_stores_too():
    """Facts alone are not a merge.

    A fact's value is a REFERENCE into the store it was filed from. Merging the facts dict
    without the stores produced six confident zeros -- `recall_fact` found every key and then
    reported "the fact points at a procedure with no code" -- which read as a finding about
    lives until the guard made it visible.
    """
    from tools.population_experiment import merge_arms
    k1, k2 = ("surface_area", "sphere", "float"), ("sum", "list", "int")
    arms = {
        "a": {"facts": {k1: "refA"}, "fact_sources": {k1: "self"},
              "store": {"refA": {"solutions": [{"text": "CODE A"}]}}},
        "b": {"facts": {k2: "refB"}, "fact_sources": {k2: "oracle"},
              "store": {"refB": {"solutions": [{"text": "CODE B"}]}}},
    }
    facts, sources, store = merge_arms(arms, ["a", "b"])
    assert set(facts) == {k1, k2}
    assert sources[k1] == "self" and sources[k2] == "oracle"
    assert {"refA", "refB"} <= set(store), (
        "the merged facts point at references that are not in the merged store, so every one "
        "of them would resolve to nothing")


def test_arms_learn_so_they_can_self_distil():
    """`learn=True` in `_run_arm`, pinned against a future "simplify this" pass.

    With `learn=False` the procedure is never stored, and because a fact needs a stored
    reference the guard refuses EVERY filing -- oracle and self alike. The arms were
    therefore unable to self-distil at all, which was the one behaviour the experiment
    existed to measure.
    """
    import tools.population_experiment as pe
    from organs import harness as H

    calls = []

    class _FakeLoop:
        solver = sandbox = learning = None

    class _FakeAgent:
        reasoning_loop = _FakeLoop()
        language = api_oracle = learning_loop = None

    def spy(self, task, check="", *, learn=True, oracle=True):
        calls.append(learn)
        return {"solved": False, "branch": "unsolved"}

    real_agent, real_solve = pe._agent, H.Harness.solve
    pe._agent = lambda: _FakeAgent()
    H.Harness.solve = spy
    try:
        pe._run_arm([{"task": "t", "check": "assert True"}], "probe")
    finally:
        pe._agent, H.Harness.solve = real_agent, real_solve
    assert calls == [True], (
        "arms must call solve(learn=True); with False nothing is stored and no fact can be "
        "filed, which silently disables self-distillation in every arm. Got %r" % (calls,))
