"""The pass-set diff is the instrument meant to catch drift by itself.

It exists because I recorded a "the bar drifted" finding that was false: I
compared a campaign against a recollection of per-script numbers instead of
against the journal, and read a control that disproved the story as confirming
it. The fix was to make membership a field and diff it mechanically -- which
only works if the diff works. A tool I have to remember to trust is the same
tool I already misread once, so these tests pin what it prints.

Four things must hold: identical membership reports no moves; a score that
holds while membership changes is called out as drift; a row present on one
side only is labelled coverage and NOT counted as movement (a chunked campaign
against a whole one otherwise reads as dozens of changes); and journals written
before ask ids existed still key correctly.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.heldout_eval as he  # noqa: E402


def write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(p)


def row(ask, ok, stage=None, script="alpha", **over):
    r = {"id": f"{script}::{ask}", "script": script, "ask": ask,
         "pass": bool(ok), "stage": None if ok else stage}
    r.update(over)
    return r


def test_identical_membership_reports_no_moves(tmp_path, capsys):
    rows = [row("what turns twice?", True), row("what bites the latch?", True),
            row("did any egg break?", False, "recall")]
    a = write(tmp_path, "a.jsonl", rows)
    b = write(tmp_path, "b.jsonl", rows)
    assert he.compare([a, b]) == 0
    out = capsys.readouterr().out
    assert "differs: 0" in out
    assert "MOVED" not in out
    assert "MEMBERSHIP" not in out


def test_equal_pass_counts_over_different_asks_are_named_as_drift(tmp_path,
                                                                  capsys):
    """The exact shape of the mistake: two passes in both campaigns, over
    different asks. A score delta of zero must not look like nothing happened."""
    a = write(tmp_path, "a.jsonl", [row("which did i tell you first the lantern "
                                        "or the kettle?", True),
                                    row("how many objects did i tell you about?",
                                        True),
                                    row("did i ever tell you about the moon?",
                                        False, "gating")])
    b = write(tmp_path, "b.jsonl", [row("which did i tell you first the lantern "
                                        "or the kettle?", False, "mouth"),
                                    row("how many objects did i tell you about?",
                                        False, "recall"),
                                    row("did i ever tell you about the moon?",
                                        False, "gating"),
                                    row("what is both wet and on the hook?", True),
                                    row("where did i say the scarf is?", True)])
    # Both sides pass two asks in total, but they are different asks, and B ran
    # two the A never saw. The totals must NOT be subtracted.
    assert he.compare([a, b]) == 0
    out = capsys.readouterr().out
    assert "score delta" not in out, "a raw delta across unequal ask sets is noise"
    assert "the only comparable number" in out
    assert "A 2/3  B 0/3  delta -2" in out
    assert "differs: 2" in out
    for moved in ("which did i tell you first", "how many objects"):
        assert moved in out


def test_equal_score_with_swapped_passes_is_flagged(tmp_path, capsys):
    a = write(tmp_path, "a.jsonl", [row("one?", True), row("two?", False, "mouth"),
                                    row("three?", False, "recall")])
    b = write(tmp_path, "b.jsonl", [row("one?", False, "mouth"),
                                    row("two?", True),
                                    row("three?", False, "recall")])
    he.compare([a, b])
    out = capsys.readouterr().out
    assert "score delta +0" in out
    assert "differs: 2" in out
    assert "SAME SCORE, DIFFERENT MEMBERSHIP" in out


def test_rows_present_on_one_side_only_are_coverage(tmp_path, capsys):
    """A chunk of 8 asks diffed against a campaign of 24 must report the 8
    shared rows, not 16 phantom changes."""
    whole = [row(f"ask {i}?", i < 3, stage=None if i < 3 else "recall")
             for i in range(8)]
    chunk = whole[:2]
    a = write(tmp_path, "a.jsonl", whole)
    b = write(tmp_path, "b.jsonl", chunk)
    he.compare([a, b])
    out = capsys.readouterr().out
    assert "coverage, not movement" in out
    assert "differs: 0" in out
    assert "MOVED" not in out


def test_journals_without_ask_ids_still_key(tmp_path, capsys):
    """Rows written before the id field existed -- every campaign up to this
    cut -- must diff against rows that have one."""
    old = [{"script": "alpha", "ask": "what turns twice?", "pass": False,
            "stage": "shape_arbiter"}]
    new = [row("what turns twice?", True)]
    a = write(tmp_path, "a.jsonl", old)
    b = write(tmp_path, "b.jsonl", new)
    he.compare([a, b])
    out = capsys.readouterr().out
    assert "shape_arbiter  PASS            alpha::what turns twice?   << MOVED" in out
    assert "differs: 1" in out


# --- which campaign is the control -------------------------------------------
# The first real run of this picked a 4-ask chunk as the control for a 24-ask
# campaign because it sorted archives by mtime. A diff against the wrong control
# prints a delta that means nothing, which is the error class this whole
# instrument exists to stop.

def archive(tmp_path, name, n, mtime):
    p = tmp_path / name
    p.write_text("".join(json.dumps(row(f"ask {i}?", True)) + "\n"
                         for i in range(n)), encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return p


def test_the_fullest_archive_wins_not_the_newest(tmp_path):
    old_whole = archive(tmp_path, "heldout_ind_prev_a.jsonl", 24, 1_700_000_100)
    new_chunk = archive(tmp_path, "heldout_ind_prev_b.jsonl", 4, 1_700_000_900)
    got = he.prior_campaign([old_whole, new_chunk])
    assert got == old_whole, f"newest-but-4-rows is not a control: got {got.name}"


def test_equal_size_ties_go_to_the_fresher_write(tmp_path):
    older = archive(tmp_path, "heldout_ind_prev_old.jsonl", 24, 1_700_000_100)
    just_archived = archive(tmp_path, "heldout_ind_prev_new.jsonl", 24,
                            1_700_000_900)
    assert he.prior_campaign([older, just_archived]) == just_archived


def test_a_full_live_journal_beats_a_short_archive(tmp_path):
    short = archive(tmp_path, "heldout_ind_prev_short.jsonl", 4, 1_700_000_900)
    whole = archive(tmp_path, "heldout_ind_live_now_prev.jsonl", 24,
                    1_700_000_100)
    assert he.prior_campaign([short], live=whole) == whole


def test_nothing_to_compare_against_is_not_an_error(tmp_path):
    assert he.prior_campaign([]) is None
    assert he.prior_campaign([], live=None) is None
