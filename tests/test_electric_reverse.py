"""ELECTRIC reverse-role asks (ELECTRIC_REVERSE) and the churn-key fix.

Two things are pinned here that a battery run cannot see:

  * the shape of a reverse ask that is ALLOWED to reach the inventory, and the
    near-miss shapes that must NOT;
  * the guard's content key applying to every copy of the churn file, not just
    the one at the state root.

Everything runs against the module functions or a temp tree -- no house boot.
"""
import zipfile
from pathlib import Path

import pytest

import organs.neural_language as nl
import tools.converse as converse

SAYS = {
    "lantern": {"agent": "the lantern belongs to Mira"},
    "mouse": {"agent": "the mouse chases the cat"},
    "ledger": {"place": "the ledger is under the desk"},
    "scarf": {"place": "the scarf is on the hook"},
}


# ---------------------------------------------------- the reverse-role branch

def test_a_stranded_who_ask_reaches_the_keyed_tell():
    got = nl._electric_answer("who does the lantern belong to?", SAYS, reverse=True)
    assert got == "the lantern belongs to Mira", \
        f"the reverse ask must return the VERBATIM tell, got {got!r}"


def test_without_the_flag_the_same_ask_is_still_a_miss():
    assert nl._electric_answer("who does the lantern belong to?", SAYS) is None, \
        "reverse-role binding leaked into the default path"


def test_an_unstranded_who_ask_returns_nothing():
    """`who does the mouse chase?` wants the CHASER. The frame stored under
    `mouse` is "the mouse chases the cat", which is about the mouse chasing --
    answering it would be the wrong fact about the right noun. The stranded
    preposition is the only thing that distinguishes these two asks, so this test
    is the safety of the whole feature."""
    assert nl._electric_answer("who does the mouse chase?", SAYS, reverse=True) is None


def test_a_subject_with_no_agent_fact_is_not_answered():
    """`who does the ledger belong to?` is well-formed and `ledger` IS in the
    inventory -- but only with a place. Falling through is the correct answer;
    inventing a possessor is not."""
    assert nl._electric_answer("who does the ledger belong to?", SAYS, reverse=True) is None


def test_a_different_verb_is_still_rejected_after_stemming():
    """Stemming must not become matching. `belong` and `report` share nothing."""
    assert nl._electric_answer("who does the lantern report to?", SAYS, reverse=True) is None


def test_stemming_is_a_literal_suffix_rule_and_no_more():
    assert nl._verb_stem("belongs") == "belong"
    assert nl._verb_stem("chases") == "chase"
    assert nl._verb_stem("lantern") == "lantern"        # a noun is not a verb
    assert nl._verb_stem("is") == "is"                  # too short to strip
    assert nl._verb_stem("gas") == "gas"                # ends in s, len 3: left alone


def test_the_licence_did_not_gain_the_who_branch():
    """E24's refusal set is measured. Widening the ANSWER path is safe; widening
    the LICENCE would let the organ claim knowledge it was never licensed about."""
    inv = {"lantern": {"agent": "mira"}, "scarf": {"place": "hook"}}
    assert nl._absence_licence("who does the lantern belong to?", inv) is None
    assert nl._absence_licence("who does the scarf belong to?", inv) is None
    # and the property refusal it already made is word-for-word unchanged
    assert nl._absence_licence("what is the scarf like?", inv) == (
        "refusal", "scarf was told but no property was ever told for scarf")


def test_reverse_is_a_class_default_off():
    assert nl.NeuralLanguage.ELECTRIC_REVERSE is False
    o = nl.NeuralLanguage.__new__(nl.NeuralLanguage)
    assert o.ELECTRIC_REVERSE is False
    o.ELECTRIC_REVERSE = True
    assert nl.NeuralLanguage.ELECTRIC_REVERSE is False, \
        "the flag was set on the CLASS: it would leak into every other run"


def test_serve_exposes_the_flag_and_leaves_it_off(tmp_path):
    """--electric-reverse must exist, default off, and be INERT without --electric:
    the block that sets organ flags only runs under `if args.electric`, so a lone
    --electric-reverse cannot turn the read path on."""
    import subprocess
    import sys as _sys
    from pathlib import Path as _P

    root = _P(__file__).resolve().parents[1]
    p = subprocess.run([_sys.executable, str(root / "tools" / "serve.py"), "--help"],
                       capture_output=True, text=True, timeout=300, cwd=str(root))
    assert p.returncode == 0, p.stderr
    assert "--electric-reverse" in p.stdout
    src = (root / "tools" / "serve.py").read_text(encoding="utf-8")
    assert 'add_argument("--electric-reverse", action="store_true"' in src
    assert "lang.ELECTRIC_REVERSE = bool(args.electric_reverse)" in src
    guard = src.split("if args.electric:", 1)[1]
    assert "lang.ELECTRIC_REVERSE" in guard.split("\n    session_dir", 1)[0], \
        "the reverse flag must be set inside the --electric block, not globally"


# ------------------------------------------------------------- the churn key

def _zip(tmp: Path, name: str, payload: bytes) -> Path:
    f = tmp / name
    f.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(f, "w") as zf:      # any zip parses; np.savez writes one
        zf.writestr("x.npy", payload)
    return f


def test_subdir_churn_is_content_keyed_now(tmp_path):
    """The bug: KNOWN_CHURN was compared against a RELATIVE PATH, so only the copy
    at the state root ever got a content key. Every copy under live_learner/ was
    keyed by mtime and flagged on a no-op rewrite -- which is what made the live
    house print "live files untouched: False" for churn that changed nothing."""
    root = tmp_path / "state"
    _zip(root, "banc_brain.npz", b"same")
    churn = _zip(root, Path("live_learner") / "current" / "banc_brain.npz", b"same")
    _zip(root, "other.npz", b"different file")
    before = converse.guard_live_files("t", root)

    churn.unlink()
    _zip(root, Path("live_learner") / "current" / "banc_brain.npz", b"same")
    assert converse.guard_check(before, root) == [], \
        "a content-identical rewrite of a churn copy must not flag"


def test_a_real_content_change_in_a_churn_copy_still_flags(tmp_path):
    root = tmp_path / "state"
    churn = Path("live_learner") / "versions" / "v0" / "banc_brain.npz"
    _zip(root, churn, b"one")
    before = converse.guard_live_files("t", root)
    _zip(root, churn, b"two")
    assert converse.guard_check(before, root) == [str(churn)], \
        "the fix must not hide a genuine write"


def test_an_unparseable_churn_file_falls_back_to_the_stat_key(tmp_path):
    """The old code stored ("crc", None) for a file it could not open, which
    compares equal forever: an unreadable churn file was invisible to the guard."""
    root = tmp_path / "state"
    root.mkdir(parents=True)
    f = root / "banc_brain.npz"
    f.write_bytes(b"not a zip at all")
    before = converse.guard_live_files("t", root)
    f.write_bytes(b"still not a zip, but longer")
    assert converse.guard_check(before, root) == ["banc_brain.npz"]


# ------------------------------------------------- the guard, not luck, is what stops it

MISBIND = {
    "frost": {"agent": "the frost bites the latch"},
    "latch": {"agent": "the latch holds the door"},
}


def test_a_live_misbind_is_caught_by_the_verb_guard():
    """Measured in the A/B arm, not assumed: `what bites the latch?` DOES bind --
    to ('agent', 'latch'), because `latch` is a subject in its own right -- and the
    tell behind that key is "the latch holds the door", the WRONG FACT ABOUT THE
    RIGHT NOUN. The ask names the OBJECT of the frost tell, so this is the C3
    reverse-role shape. Silence here comes from the verb guard rejecting `bites`
    against `holds`, so it must stay silence if either half is ever loosened."""
    assert nl._electric_bind("what bites the latch?", MISBIND,
                             broad_agent=True, who_agent=True) == ("agent", "latch"), \
        "the mis-bind must stay live, or this test proves nothing"
    for rev in (False, True):
        assert nl._electric_answer("what bites the latch?", MISBIND, reverse=rev) is None, \
            "a bound-but-wrong tell must never be spoken"
