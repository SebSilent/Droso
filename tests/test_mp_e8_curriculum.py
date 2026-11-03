"""MP-E8's shared curriculum must be arm A's curriculum, not a description of it.

The plan requires the three arms to run "under identical curricula" with B and C reading "the same
curriculum files arm A reads", and arm A's curriculum is literal lists inside its own harness. These
tests hold the reader to that: the item count must equal what arm A computes, the tier refusal must
stay a refusal, and the hash must be a property of the material rather than of the run.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import mp_e8_curriculum as mc  # noqa: E402


def _bench_all_items():
    """ALL_ITEMS as arm A itself computes it.

    It is NOT a literal -- the bench writes `ALL_ITEMS = sum(len(s) for s in SESSIONS) + ...`, so
    reading the source with ast.literal_eval fails. Importing the module is the faithful way: it
    only defines lists at import time, and the number arm A runs on is then the number under test.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import electric_learn_bench as bench
    return bench.ALL_ITEMS


def test_item_count_is_arms_own_count():
    cur = mc.load()
    assert cur["n_items"] == _bench_all_items(), \
        f"curriculum reader says {cur['n_items']}, arm A says {_bench_all_items()}"


def test_composition_measured():
    cur = mc.load()
    assert (cur["n_tell_frames"], cur["n_qa_pairs"]) == (24, 16)
    assert (cur["n_session_groups"], cur["n_pair_groups"]) == (3, 3)


def test_three_sessions_carry_every_item():
    """The plan's design line is three sessions per tier with a real restart between them."""
    cur = mc.load()
    sess = mc.sessions_for(40, cur)
    assert len(sess) == 3
    assert sum(s["n_items"] for s in sess) == cur["n_items"], \
        "an item dropped in the session split would silently change the interference curve"


def test_tiers_without_code_refuse_rather_than_interpolate():
    cur = mc.load()
    for tier in (120, 300):
        try:
            mc.validate_tier(tier, cur)
        except SystemExit as e:
            # SystemExit carries its message in .code, not .value.
            msg = str(e.code)
            assert "does not exist as code" in msg
            assert "author" in msg, "the refusal must name the cost, not just say no"
        else:
            raise AssertionError(f"tier {tier} was accepted without existing")


def test_hash_is_a_property_of_the_material():
    a, b = mc.load(), mc.load()
    assert a["curriculum_sha256"] == b["curriculum_sha256"]
    assert len(a["curriculum_sha256"]) == 64


def test_cli_manifest_round_trips():
    out = ROOT / "_tmp" / "mp_e8_cur_test.json"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "mp_e8_curriculum.py"),
                        "--tier", "40", "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import json
    m = json.loads(out.read_text(encoding="utf-8"))
    assert m["n_items"] == _bench_all_items()
    assert m["curriculum_sha256"] == mc.load()["curriculum_sha256"]
    out.unlink()


def test_cli_refuses_a_tier_that_does_not_exist():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "mp_e8_curriculum.py"),
                        "--tier", "300"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "does not exist as code" in r.stderr
