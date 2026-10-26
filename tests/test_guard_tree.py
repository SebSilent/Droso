"""The harness's read-only invariant is a tree snapshot, not a list of names.

tools/converse.py guards every probe session with a before/after comparison of
state/.  The guard used to name nine files, and one of them --
language_state.json.san.npy -- does not exist: the real SAN file is
language_state.san.npy (the save code's with_suffix replaces ".json" instead of
appending), so a session that wrote the Hebbian weights would have gone
unreported.  A named list can only miss; a tree snapshot cannot.  This test
redirects the snapshot to a scratch tree and asserts the two properties that
make the guard trustworthy: a write to the real SAN path is caught, and the
harness's own outputs (sessions/, fitness/) are not.

Debt entry 6 (docs/speech_log.md) adds a third property: the guard window
starts before build(), and the known no-op churn of state/banc_brain.npz
(the growth organ's unconditional first-tick save; np.savez embeds zip
member timestamps, so the mtime moves even when the arrays do not) is
content-verified, not mtime-trusted -- an identical rewrite is not flagged,
a content change is.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.converse as converse  # noqa: E402


def _scratch(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "fitness").mkdir()
    (tmp_path / "language_state.json").write_text("{}")
    (tmp_path / "language_state.san.npy").write_bytes(b"\x00\x01")
    (tmp_path / "sessions" / "old.json").write_text("{}")
    converse.STATE = tmp_path
    return converse.guard_live_files("before")


def test_a_write_to_the_real_san_path_is_caught(tmp_path):
    before = _scratch(tmp_path)
    (tmp_path / "language_state.san.npy").write_bytes(b"\x00\x01\x02")
    assert converse.guard_check(before) == ["language_state.san.npy"]


def test_a_new_file_in_state_is_caught(tmp_path):
    before = _scratch(tmp_path)
    (tmp_path / "language_state.json.cortex.npz").write_bytes(b"x")
    assert converse.guard_check(before) == ["language_state.json.cortex.npz"]


def test_the_harnesss_own_outputs_are_not_flagged(tmp_path):
    before = _scratch(tmp_path)
    (tmp_path / "sessions" / "new.json").write_text("{}")
    (tmp_path / "fitness" / "report.json").write_text("{}")
    assert converse.guard_check(before) == []


# ---- debt entry 6: the known churn is content-verified, not mtime-trusted ----

def _banc(tmp_path, n: int):
    import numpy as np
    np.savez(tmp_path / "banc_brain.npz", w=np.arange(n))


def test_banc_churn_with_identical_content_is_not_flagged(tmp_path):
    _banc(tmp_path, 5)
    before = converse.guard_live_files("before", root=tmp_path)
    _banc(tmp_path, 5)  # same arrays, later mtime: the measured no-op churn
    assert converse.guard_check(before, root=tmp_path) == []


def test_a_banc_content_change_is_flagged(tmp_path):
    _banc(tmp_path, 5)
    before = converse.guard_live_files("before", root=tmp_path)
    _banc(tmp_path, 6)  # different arrays: a real write, not churn
    assert converse.guard_check(before, root=tmp_path) == ["banc_brain.npz"]