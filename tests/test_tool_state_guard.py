"""A tool may READ the being's state and must never WRITE it.

This is the one test in this phase that prevents a catastrophe rather than measuring
something, and it exists because the original breach was SILENT: a tool rooted at the
project root saved its own small binder over the live one, and 30,091 propositions became
86 with `load_error: None` and `last_error: None` -- because the save succeeded, and so did
the load of the smaller file. Nothing raised, nothing looked wrong, and ~14,000
propositions were unrecoverable.

`persist=False` alone is not a guard: it is a flag set once at build time and never
re-read. So the tools now read the REAL state (state/language_state.json, 5.8 MB plus a
344 MB cortex sidecar) and `tools.curriculum_run._forbid_writes` REPLACES the write path.
This asserts the file, not the flag.

WHY SIZE AND NOT mtime. The live house is a legitimate concurrent writer of this exact
file, so "mtime unchanged" would fail whenever the house happened to save mid-test, and it
could not tell the house's write from a tool's. The failure this test is for is a COLLAPSE:
a tool save replaces a 5.8 MB brain with a few kilobytes. That signal is unambiguous and
the house's own writes move the size up, not down.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REAL_STATE = ROOT / "state" / "language_state.json"


def test_tool_agent_reads_the_real_brain_and_cannot_write_it():
    from tools.curriculum_run import _loop_agent

    if not REAL_STATE.exists():
        # Nothing to protect in a checkout without the being's state.
        return
    before_size = REAL_STATE.stat().st_size

    agent = _loop_agent()
    lang = agent.language

    # It reads the being, not a blank head. Before this fix a tool agent built from a cfg
    # with no language block fell back to state/house_agent_language_state.json -- a file
    # that DOES NOT EXIST -- and ran with 0 propositions.
    held = int(lang.cortex.binder.X.shape[0])
    assert held > 1000, f"tool agent loaded {held} propositions; it is not reading the being"
    assert Path(lang.state_path).resolve() == REAL_STATE.resolve(), lang.state_path

    # The flag ...
    assert lang.persist is False, "a tool agent left persist on"
    # ... and the mechanism, which is the part that survives nobody re-reading the flag.
    assert getattr(lang.save_state, "__name__", "") == "_refused", \
        "the write guard is not installed on the language organ"

    # Call the actual write path. This is the thing the guard exists for.
    out = lang.save_state(force=True)
    assert isinstance(out, dict) and out.get("saved") is False, out

    after_size = REAL_STATE.stat().st_size
    assert after_size >= before_size * 0.9, (
        "a tool agent collapsed the being's brain: "
        f"{before_size} bytes -> {after_size} bytes")


def test_every_tool_that_touches_the_real_state_is_guarded():
    """The guard is installed by `_loop_agent`, so every tool built on it inherits it.

    `tools.knowledge_run._agent` wraps `_loop_agent`, and `population_experiment` uses
    `_agent` -- one place to get this right, and this asserts the wrapper does not undo it.
    """
    from tools.knowledge_run import _agent
    agent = _agent()
    for name in ("language", "learning_loop"):
        obj = getattr(agent, name, None)
        assert obj is not None, name
        assert obj.persist is False, f"{name}.persist is on in a tool"
    assert getattr(agent.language.cortex, "save", None) is not None
    assert getattr(agent.language.cortex.save, "__name__", "") == "_refused", \
        "the cortex write path is not guarded"
