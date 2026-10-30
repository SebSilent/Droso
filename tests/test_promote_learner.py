r"""Pins the promotion path: what it refuses, and why the learner area is separate.

The refusals are the point. Promotion is the one operation in the open-learning
programme that can change what the guarded baseline refers to, so every reason to say
no is pinned here rather than left to the code path happening not to be reached.

All of it runs against tmp_path with the module's path constants monkeypatched, so no
test touches the real learner area or the real live state. The refusal paths return
before the state guard is taken, which is what makes them cheap to test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.promote_learner as pl  # noqa: E402

LIVE_SEALS = {"language_state.json": "aaaa", "banc_brain.npz": "bbbb"}
CK_SEALS = {"language_state.json": "cccc", "banc_brain.npz": "bbbb"}


def good_row(**over):
    r = {"episode": 3, "verdict": "PASS",
         "gates": {k: True for k in ("absence_verified", "erosion_zero",
                                     "census_reported", "live_seals_unchanged",
                                     "row_self_contained")},
         "eval": {"frozen_asked": 24, "acquisition": {"passed": 20, "asked": 20}},
         "seals": {"before": dict(LIVE_SEALS), "after": dict(LIVE_SEALS)},
         "checkpoint_id": "ck1", "checkpoint_files": dict(CK_SEALS),
         "erosion": []}
    r.update(over)
    return r


def manifest(versions=("v0_aaa",), current=None):
    return {"schema": 1, "current": current or versions[-1],
            "bootstrapped_from": {"root": "state/", "seals": dict(LIVE_SEALS),
                                  "id": "aaa"},
            "versions": [{"version": v, "parent": (versions[i - 1] if i else None),
                          "source": "bootstrap" if i == 0 else "promotion",
                          "id": v.split("_", 1)[1], "seals": dict(LIVE_SEALS),
                          "files": {}} for i, v in enumerate(versions)]}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point the whole module at tmp_path and stub the two things that would
    otherwise read the real tree."""
    ll = tmp_path / "live_learner"
    for d in ("current", "versions", "staging"):
        (ll / d).mkdir(parents=True)
    monkeypatch.setattr(pl, "LL", ll)
    monkeypatch.setattr(pl, "MANIFEST", ll / "manifest.json")
    monkeypatch.setattr(pl, "CURRENT", ll / "current")
    monkeypatch.setattr(pl, "VERSIONS", ll / "versions")
    monkeypatch.setattr(pl, "STAGING", ll / "staging")
    monkeypatch.setattr(pl, "LEDGER", tmp_path / "promotions.jsonl")
    monkeypatch.setattr(pl, "live_seals", lambda: dict(LIVE_SEALS))
    return ll


def stage(ll, seals=CK_SEALS, name="ep3_ck1"):
    d = ll / "staging" / name
    d.mkdir(parents=True, exist_ok=True)
    for n in seals:
        (d / n).write_text("x")
    return d


def args(**kw):
    import argparse
    base = dict(episode=3, force=False, reason="", bootstrap=False, promote=False,
                rollback=False, verify=False, status=False)
    base.update(kw)
    return argparse.Namespace(**base)


# ------------------------------------------------------------ pure helpers ----

def test_the_state_id_is_a_function_of_the_seals_alone():
    assert pl.state_id(CK_SEALS) == pl.state_id(dict(reversed(list(CK_SEALS.items()))))
    assert pl.state_id(CK_SEALS) != pl.state_id(LIVE_SEALS)
    assert len(pl.state_id(CK_SEALS)) == 12


def test_a_file_that_cannot_be_linked_is_recorded_as_a_copy(tmp_path, monkeypatch):
    """Silently copying 222 MB and calling it a link would make the disk cost of
    versioning invisible, so the record says which happened."""
    src = tmp_path / "s"
    src.mkdir()
    (src / "language_state.json").write_text("hello")
    monkeypatch.setattr(pl.os, "link",
                        lambda a, b: (_ for _ in ()).throw(OSError("cross-device")))
    out = pl.link_tree({"language_state.json": src / "language_state.json"},
                       tmp_path / "d")
    assert out["language_state.json"]["link"] is False
    assert (tmp_path / "d" / "language_state.json").read_text() == "hello"


# ---------------------------------------------------------------- refusals ----

def test_no_manifest_refuses(sandbox, monkeypatch):
    monkeypatch.setattr(pl, "load_manifest", lambda: None)
    assert pl.cmd_promote(args(promote=True)) == 1


def test_no_episode_row_refuses(sandbox, monkeypatch):
    pl.save_manifest(manifest())
    monkeypatch.setattr(pl, "episode_row", lambda n: None)
    assert pl.cmd_promote(args(promote=True)) == 1


@pytest.mark.parametrize("mutate,why", [
    (lambda r: r.update(verdict="FAIL"), "verdict"),
    (lambda r: r["gates"].update(erosion_zero=False), "a gate False"),
    (lambda r: r["gates"].update(erosion_zero=None), "a gate unmeasured"),
    (lambda r: r["eval"].update(frozen_asked=0), "erosion never really measured"),
    (lambda r: r.update(seals={"before": {"language_state.json": "ZZZZ"},
                               "after": {}}), "live state drifted"),
    (lambda r: r.pop("checkpoint_files"), "no recorded checkpoint seals"),
    (lambda r: r["checkpoint_files"].update({"language_state.json": "WRONG"}),
     "staging does not match what was measured"),
])
def test_each_promotion_refusal(sandbox, monkeypatch, mutate, why):
    """Every reason to say no, checked one at a time. A promotion gate that is never
    exercised is a gate nobody knows works."""
    pl.save_manifest(manifest())
    row = good_row()
    mutate(row)
    monkeypatch.setattr(pl, "episode_row", lambda n: row)
    stage(sandbox)
    assert pl.cmd_promote(args(promote=True)) == 1, why


def test_a_missing_staging_checkpoint_refuses(sandbox, monkeypatch):
    pl.save_manifest(manifest())
    monkeypatch.setattr(pl, "episode_row", lambda n: good_row())
    assert pl.cmd_promote(args(promote=True)) == 1
    assert not list((sandbox / "versions").iterdir()), "nothing was versioned"


def test_repromoting_identical_bytes_refuses(sandbox, monkeypatch):
    """A second promotion of the same content would fork the chain onto identical
    bytes and make the version list lie about how much learning happened."""
    m = manifest(versions=("v0_aaa", "v1_" + pl.state_id(CK_SEALS)))
    pl.save_manifest(m)
    monkeypatch.setattr(pl, "episode_row", lambda n: good_row())
    stage(sandbox)
    assert pl.cmd_promote(args(promote=True)) == 1


def test_rollback_without_a_parent_refuses(sandbox):
    pl.save_manifest(manifest(versions=("v0_aaa",)))
    assert pl.cmd_rollback(args(rollback=True)) == 1


def test_rollback_without_a_manifest_refuses(sandbox):
    assert pl.cmd_rollback(args(rollback=True)) == 1


# ------------------------------------------------------- the separation ----

def test_the_learner_area_is_not_the_guarded_live_state():
    """The whole reason promotion is safe: the learner lives somewhere else, so the
    live state the guarded baseline was measured against is never the thing being
    overwritten. If these ever coincide, every generation recorded so far stops being
    comparable to the next one."""
    assert pl.LL == pl.STATE / "live_learner"
    assert pl.LL != pl.STATE
    assert pl.CURRENT.parent == pl.LL
    # And the files the guarded baseline describes are read from state/ itself, never
    # from the learner area: live_seals() globs STATE, not LL.
    import inspect
    src = inspect.getsource(pl.live_seals)
    assert "learner_files(STATE)" in src and "LL" not in src


def test_the_learner_file_set_is_the_language_family_plus_the_plastic_weights():
    assert pl.LEARNER_GLOBS == ("language_state*", "banc_brain.npz")


def test_bootstrap_refuses_to_restart_an_existing_chain(sandbox, monkeypatch):
    """Re-bootstrapping would orphan every version descended from the old root, so it
    needs --force and says what it is doing."""
    pl.save_manifest(manifest())
    monkeypatch.setattr(pl, "guard_live_files", lambda t, root=None: {})
    monkeypatch.setattr(pl, "guard_check", lambda b, root=None: [])
    monkeypatch.setattr(pl, "learner_files",
                        lambda root: {n: sandbox / "current" / n for n in LIVE_SEALS})
    for n in LIVE_SEALS:
        (sandbox / "current" / n).write_text("x")
    assert pl.cmd_bootstrap(args(bootstrap=True)) == 1
