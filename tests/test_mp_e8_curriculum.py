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


# THESE TWO TESTS WERE STALE, AND THE FIX IS NOT THE STRING. They asserted that tiers 120 and 300
# "do not exist as code". That was true when it was written and became false when D-MPE8-03 emitted
# them -- so editing the expected string to match the new message would have made the test say nothing
# at all. What never changed is why the tool refuses. The invariant is now: a tier is accepted only if
# it is authored as code OR a committed tier file re-derives from the rule. Measured against the tool
# as it actually behaves: --check-tier 120 = 19.4 s, --check-tier 300 = 47.6 s, --check-tier 200 used
# to die in a FileNotFoundError traceback, and --check-tier 40 used to report a false MISMATCH. The
# three tests below are those two refusals rebuilt, plus the two behaviours the probes exposed.

def test_committed_tiers_re_derive_from_the_rule():
    """120 and 300 exist now, so acceptance has to be proved the only way left open: the committed
    file re-derives from the registered rule and seed -- sessions and distractors equal, hash equal."""
    for tier in (120, 300):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "mp_e8_curriculum.py"),
                            "--check-tier", str(tier)], capture_output=True, text=True)
        assert r.returncode == 0, f"tier {tier} does not re-derive:\n{r.stdout}\n{r.stderr}"
        assert "PASS" in r.stdout, r.stdout


def test_a_tier_with_neither_code_nor_committed_file_is_refused_by_every_path():
    """The case the old pair could not express: 200 has no code AND no file, so there is nothing to
    interpolate it from. Both paths must refuse -- as refusals, naming the cost, not as a crash."""
    for flag in ("--tier", "--check-tier"):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "mp_e8_curriculum.py"),
                            flag, "200"], capture_output=True, text=True)
        assert r.returncode != 0, f"{flag} 200 was accepted"
        msg = (r.stderr + r.stdout).lower()
        assert "traceback" not in msg, f"{flag} 200 crashed instead of refusing:\n{r.stderr}"
        assert "not a registered tier" in msg, msg
        assert "before any run" in msg, f"refusal names no cost:\n{msg}"
        assert "curriculum_sha256" in msg, f"refusal does not say what must be committed:\n{msg}"


def test_the_code_tier_is_checked_against_its_source_not_re_derived():
    """Tier 40 is parsed from arm A, not emitted by the rule. Asking the rule to re-derive it produced
    a MISMATCH saying someone hand-edited the registered curriculum. That alarm was false, and a tool
    in the seal manifest does not get to cry wolf about editing."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "mp_e8_curriculum.py"),
                        "--check-tier", "40"], capture_output=True, text=True)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert "PASS (source match)" in r.stdout, r.stdout


def test_the_parse_path_still_refuses_the_emitted_tiers():
    """The half of the old invariant that survived: arm A's own lists hold 40 items and will not grow,
    so reading 120/300 out of the bench source stays a refusal. Acceptance runs through the file."""
    cur = mc.load()
    for tier in (120, 300):
        try:
            mc.validate_tier(tier, cur)
        except SystemExit as e:
            # SystemExit carries its message in .code, not .value.
            msg = str(e.code).lower()
            assert "not parsed from" in msg and "will not grow" in msg, msg
        else:
            raise AssertionError(f"tier {tier} was parsed out of a source that holds {cur['n_items']}")


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


# test_cli_refuses_a_tier_that_does_not_exist is gone, not weakened: it asserted the same stale string
# about tier 300, and tier 300 now exists. Its job -- the CLI refuses what has neither code nor a
# committed file -- is done more strictly by
# test_a_tier_with_neither_code_nor_committed_file_is_refused_by_every_path, which drives both flags,
# requires a refusal rather than a traceback, and requires the message to name the cost.
