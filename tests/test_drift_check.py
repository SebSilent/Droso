"""The drift check's comparison logic, without any server or state.

compare() is the verdict function: turn-by-turn reply equality, the
first difference named.  banc_content_identical() is the debt-entry-6
verification: npz files never compare equal by bytes (np.savez embeds
zip member timestamps), so the known no-op churn is cleared by array
content or not at all.  Both are pure; these tests need no Droso.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.drift_check as dc  # noqa: E402


def turns(*texts):
    return [{"kind": "ask", "said": t, "spoken": True, "reply_text": r}
            for t, r in texts]


# ---------------------------------------------------------------- compare

def test_identical_runs_are_identical():
    cli = turns(("hi", "hello"), ("where", "there"))
    http = turns(("hi", "hello"), ("where", "there"))
    assert dc.compare(cli, http) == {"turns": 2, "identical": True,
                                     "first_diff": None}


def test_first_differing_turn_is_named():
    cli = turns(("hi", "hello"), ("where", "there"), ("bye", "goodbye"))
    http = turns(("hi", "hello"), ("where", "elsewhere"), ("bye", "goodbye"))
    row = dc.compare(cli, http)
    assert row["identical"] is False
    assert row["first_diff"]["turn"] == 2
    assert row["first_diff"]["cli"] == "there"
    assert row["first_diff"]["http"] == "elsewhere"


def test_turn_count_mismatch_is_a_difference():
    row = dc.compare(turns(("hi", "hello")), [])
    assert row["identical"] is False
    assert "turn counts differ" in row["first_diff"]["note"]


def test_silence_maps_to_empty_content():
    """A silent turn's content is "": the HTTP layer must not pass off a
    reason as his words."""
    cli = [{"kind": "ask", "said": "q", "spoken": False, "reply_text": ""}]
    http = [{"kind": "ask", "said": "q", "reply_text": ""}]
    assert dc.compare(cli, http)["identical"] is True


# ------------------------------------------------- banc content identity

@pytest.fixture
def banc_pair(tmp_path):
    def make(tag, w):
        p = tmp_path / f"banc_{tag}.npz"
        np.savez_compressed(str(p), w=w, meta=np.array([1, 2, 3]))
        return p
    return make


def test_identical_arrays_are_identical_despite_new_timestamps(banc_pair):
    """Two saves of the same arrays: byte hashes may or may not differ
    (np.savez embeds zip member timestamps at 2 s resolution, so saves
    within one tick are byte-identical too) -- but the content comparison
    must say identical either way."""
    w = np.random.default_rng(7).normal(size=(10, 10))
    a, b = banc_pair("a", w), banc_pair("b", w)
    assert dc.banc_content_identical(a, b) is True


def test_differing_arrays_are_not_identical(banc_pair):
    a = banc_pair("a", np.zeros((10, 10)))
    b = banc_pair("b", np.ones((10, 10)))
    assert dc.banc_content_identical(a, b) is False


def test_shape_change_is_not_identical(banc_pair):
    a = banc_pair("a", np.zeros((10, 10)))
    p = Path(str(a)).with_name("other.npz")
    np.savez_compressed(str(p), w=np.zeros((9, 10)),
                        meta=np.array([1, 2, 3]))
    assert dc.banc_content_identical(a, p) is False


def test_unreadable_file_returns_none_not_a_crash(tmp_path):
    a = tmp_path / "a.npz"
    a.write_bytes(b"not an npz")
    b = tmp_path / "b.npz"
    b.write_bytes(b"also not")
    assert dc.banc_content_identical(a, b) is None