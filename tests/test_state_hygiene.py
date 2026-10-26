"""The three failures that produced 450 GB of state and two fake 0.0s.

`tools.state_hygiene` is the one place that fixes all three: saves go
through one delta path that is fatal on failure, and a retention sweep
bounds what a run leaves behind.  These tests pin each behaviour to the
incident that demanded it:

  - a failed save must exit nonzero with the reason (2026-10-26 10:07:
    "67108864 requested and 0 written" was printed and swallowed, and ask
    phases scored 0.0 against shadows that held two files instead of
    eight -- a fake language regression);
  - the disk-full tell must be named, because that exact string is what
    the incident looked like;
  - the sweep must keep the newest N per kind and count real bytes, not
    hardlink sizes (a shadow tree reports ~660 MB if you count links).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import state_hygiene


class FakeLang:
    """Stands in for the language organ: records the save call."""

    def __init__(self, res):
        self.res = res
        self.calls = []

    def save_state(self, delta=False):
        self.calls.append(delta)
        return self.res


# ------------------------------------------------------------- fatal saves ----

def test_require_saved_passes_a_saved_result():
    res = {"saved": True, "mode": "delta"}
    assert state_hygiene.require_saved(res, "ask phase") is res


def test_require_saved_is_fatal_and_names_the_reason():
    res = {"saved": False, "reason": "boom"}
    try:
        state_hygiene.require_saved(res, "ask phase")
    except SystemExit as e:
        assert "ask phase" in str(e) and "boom" in str(e)
    else:
        raise AssertionError("a failed save must exit nonzero")


def test_require_saved_hints_disk_full():
    res = {"saved": False, "reason": "67108864 requested and 0 written"}
    try:
        state_hygiene.require_saved(res, "tell phase")
    except SystemExit as e:
        assert "disk full" in str(e)
    else:
        raise AssertionError("the disk-full tell must be named")


def test_save_session_state_uses_delta_and_is_fatal():
    lang = FakeLang({"saved": True, "mode": "delta"})
    out = state_hygiene.save_session_state(lang, "session")
    assert lang.calls == [True]  # delta=True, never the full tree
    assert out["saved"] is True

    lang = FakeLang({"saved": False, "reason": "io error"})
    try:
        state_hygiene.save_session_state(lang, "session")
    except SystemExit:
        pass
    else:
        raise AssertionError("a failed save must exit nonzero")


def test_save_session_state_prints_when_delta_refused(capsys):
    lang = FakeLang({"saved": True, "mode": "full", "delta_refused": "cap"})
    state_hygiene.save_session_state(lang, "session")
    assert "delta refused" in capsys.readouterr().out


# ----------------------------------------------------------- retention sweep ----

def _mk(root, name, files=1, size=10):
    d = root / name
    d.mkdir(parents=True)
    for i in range(files):
        (d / f"f{i}.bin").write_bytes(b"x" * size)
    return d


def test_kind_of_strips_both_timestamp_shapes():
    assert state_hygiene._kind_of(
        "cross_reference_tell_20261026_100704") == "cross_reference_tell"
    assert state_hygiene._kind_of("live_2026-10-26") == "live"
    assert state_hygiene._kind_of("wordcheck") == "wordcheck"


def test_prune_sessions_keeps_newest_per_kind(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    lineage = tmp_path / "lineage"
    sessions.mkdir()
    lineage.mkdir()
    monkeypatch.setattr(state_hygiene, "SESSIONS", sessions)
    monkeypatch.setattr(state_hygiene, "LINEAGE", lineage)

    # four probe sessions: keep 3, the oldest goes
    for ts in ("20261023_100000", "20261024_100000",
               "20261025_100000", "20261026_100000"):
        _mk(sessions, f"probe_{ts}", files=2, size=100)
    # a one-off with no timestamp: its own kind of one, kept
    _mk(sessions, "wordcheck", files=1, size=50)
    # two lineage copies: keep 2, both stay
    _mk(lineage, "live_2026-10-25")
    _mk(lineage, "live_2026-10-26")

    out = state_hygiene.prune_sessions()

    assert not (sessions / "probe_20261023_100000").exists()
    assert (sessions / "probe_20261024_100000").exists()
    assert (sessions / "probe_20261025_100000").exists()
    assert (sessions / "probe_20261026_100000").exists()
    assert (sessions / "wordcheck").exists()
    assert (lineage / "live_2026-10-25").exists()
    assert (lineage / "live_2026-10-26").exists()
    assert out["roots"]["sessions"]["deleted"] == 1
    assert out["roots"]["sessions"]["freed"] == 200  # real bytes, not links
    assert out["roots"]["lineage"]["deleted"] == 0
    assert out["freed"] == 200


def test_prune_sessions_dry_run_deletes_nothing(tmp_path, monkeypatch, capsys):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(state_hygiene, "SESSIONS", sessions)
    monkeypatch.setattr(state_hygiene, "LINEAGE", tmp_path / "lineage")
    for ts in ("20261023_100000", "20261024_100000",
               "20261025_100000", "20261026_100000"):
        _mk(sessions, f"probe_{ts}")

    out = state_hygiene.prune_sessions(dry_run=True)

    assert (sessions / "probe_20261023_100000").exists()
    assert out["roots"]["sessions"]["deleted"] == 1
    assert "would delete" in capsys.readouterr().out


def test_prune_sessions_survives_a_missing_root(tmp_path, monkeypatch):
    monkeypatch.setattr(state_hygiene, "SESSIONS", tmp_path / "nope")
    monkeypatch.setattr(state_hygiene, "LINEAGE", tmp_path / "nada")
    out = state_hygiene.prune_sessions()
    assert out["freed"] == 0 and out["deleted"] == 0