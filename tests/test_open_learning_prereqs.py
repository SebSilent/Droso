r"""Prerequisites for the open-learning programme (docs/open_learning_design.md).

These tests pin the CURRENT state of mechanisms the design depends on, including one
that is broken. A test that asserts a defect exists is not an endorsement of it: it
is friction. Whoever fixes `WITNESS_W` will fail `test_teaching_is_currently_weighted_as_corpus`
and must then update it deliberately, which is the point -- the alternative is a
one-key change to a class constant that silently alters what consolidation selects
on the live brain, with nothing in the tree noticing.

Nothing here builds a house.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.neural_language import NeuralLanguage  # noqa: E402


def value(who: str, count: int) -> float:
    """consolidate()'s own ranking function, neural_language.py:501-504."""
    return NeuralLanguage.WITNESS_W.get(who, 0.6) * float(math.log1p(int(count)))


def test_the_binder_marks_user_teaching_as_you_not_user():
    """The `who` value the bind site actually writes for testimony. Established in
    three independent places: freshness_key gates on it (neural_language.py:70),
    answer()'s sort-key comment names it (:3285), and tests/test_binder_postings.py
    binds with it. If this ever changes, WITNESS_W has to change with it.
    """
    src = (ROOT / "organs" / "neural_language.py").read_text(encoding="utf-8")
    assert 'if who != "you":' in src, "freshness_key no longer gates on who == 'you'"
    assert 'who == "you"' in src or "who=\"you\"" in src


def test_teaching_is_weighted_above_corpus():
    """Section 7a, landed. This test previously asserted the DEFECT -- that "you" was
    absent from WITNESS_W and so tied with "book" at every count -- and it was
    written to fail on the fix, which is what happened. It is updated deliberately,
    with the census the design requires attached below.

    Census (docs/evidence/consolidation_census.py, live binder, budget 200,
    scan_top 2000): BEFORE and AFTER are byte-identical -- scanned 2000, urgent 294,
    picked 200, distribution book 188 / droso 11 / parent 1, counts {1: 187, ...} --
    because the live binder holds ZERO who="you" rows, so there was nothing for the
    new weight to act on. That is the proof of no unintended perturbation; the proof
    of the intended effect is this test plus episode E2, which teaches into a binder
    and can therefore show the selection actually moving.
    """
    assert "you" in NeuralLanguage.WITNESS_W
    assert NeuralLanguage.WITNESS_W["you"] == 1.0
    assert NeuralLanguage.WITNESS_W["you"] > NeuralLanguage.WITNESS_W["book"]
    for count in (1, 2, 3, 10, 100):
        assert value("you", count) > value("book", count), count
    # Testimony ranks with narration and the teacher, not with the corpus.
    for count in (1, 5):
        assert value("you", count) == value("parent", count) == value("teacher", count)
    # And above his own speech, which is the ordering the answer sort already uses.
    assert value("you", 1) > value("droso", 1)


def test_the_dead_user_key_is_still_there_and_still_unbound():
    """7a added a key; it did not remove one. "user" is dead -- no bind site writes
    it -- and removing it would have been a second change in a commit that is meant
    to be attributable to one. Pinned so the dead key is a known fact rather than
    something the next reader rediscovers.
    """
    assert "user" in NeuralLanguage.WITNESS_W
    src = (ROOT / "organs" / "neural_language.py").read_text(encoding="utf-8")
    assert 'who="user"' not in src and "who='user'" not in src


def test_the_default_weight_is_the_book_weight():
    """Still true after 7a, and still worth pinning: the fallback and the corpus
    weight are the same number, so any `who` value this dict does not know is scored
    as corpus. That is what made the missing "you" key silent rather than loud, and
    it will do the same for the next witness category someone adds to the bind site
    without adding it here."""
    assert NeuralLanguage.WITNESS_W["book"] == 0.6
    assert value("never_bound_by_anything", 1) == value("book", 1)


def test_the_consolidation_ordering_now_puts_testimony_above_corpus():
    """The ordering consolidate()'s sort produces, before and after 7a.

    BEFORE: parent > book == you > droso, with 1782 of the 2000 scanned rows tied at
    the cutoff 0.415888, so the window filled by stable sort on arrival order and
    replayed the OLDEST corpus lines (docs/evidence/consolidation_census.py).
    AFTER:  parent == you == teacher > oracle > book > droso, so a taught row at
    count 1 outranks the 59,515 book rows at count 1 and is selected ahead of them.
    """
    assert value("parent", 1) == value("you", 1) > value("book", 1) > value("droso", 1)
    assert value("oracle", 1) < value("you", 1)
    assert value("you", 1) > value("book", 1)


def test_rehearsal_still_compounds_on_top_of_the_witness_weight():
    """count remains a lever; 7a added a second one rather than replacing it. And a
    heavily rehearsed corpus row can still outrank a taught row heard once, which is
    correct -- familiarity is evidence, and the ordering should not make a single tell
    unbeatable."""
    assert value("you", 2) > value("you", 1)
    assert value("book", 2) > value("book", 1)
    assert value("book", 3) > value("you", 1)


def test_the_binder_is_at_capacity_and_eviction_is_blind_fifo():
    """Pinned from source, because the whole design turns on it. higher_cortex.py:46
    sets the capacity and :399-413 evicts the OLDEST row with no reference to who,
    count or value. If eviction ever becomes value-weighted (design section 7b) this
    test must be rewritten in the same commit, not left to pass on a stale reading.
    """
    import organs.higher_cortex as hc
    assert hc.MAX_PROPOSITIONS == 60000
    src = (ROOT / "organs" / "higher_cortex.py").read_text(encoding="utf-8")
    assert "if self.X.shape[0] >= self.capacity:" in src
    assert "self.meta.pop(0)" in src, "eviction no longer drops the oldest row"
    # Take exactly the `if` branch, bounded by indentation. Splitting on the next
    # "def " ran past the eviction into the append/grow path and matched a max() that
    # has nothing to do with eviction -- a check that fails for the wrong reason is
    # worse than no check, because it gets loosened instead of fixed.
    lines = src.splitlines()
    start = next(i for i, l in enumerate(lines)
                 if "if self.X.shape[0] >= self.capacity:" in l)
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = []
    for l in lines[start + 1:]:
        if not l.strip():
            block.append(l)
            continue
        if len(l) - len(l.lstrip()) <= indent:
            break
        block.append(l)
    block = "\n".join(block)
    assert "np.roll" in block and "self.meta.pop(0)" in block, block
    # Check CODE, not prose. The first version of this matched the word "count"
    # inside a comment about overlap counting and reported that eviction had become
    # value-weighted, which is the kind of false alarm that gets a check deleted.
    code = "\n".join(l.split("#", 1)[0] for l in block.splitlines())
    # The value signals. If any of these appears, eviction is no longer blind.
    for term in ("WITNESS_W", "who", "count", "value"):
        assert term not in code, (
            f"eviction now consults {term!r}: it is no longer blind FIFO, so design "
            f"section 7b has landed and this test must be rewritten in the same "
            f"commit rather than left passing on a stale reading")


def test_the_lineage_directory_is_the_declared_home_and_hygiene_would_eat_it():
    """state/lineage/ is managed by tools/state_hygiene.py and was empty until
    episode 1 wrote the ledger there. The cap is the part that matters: hygiene keeps
    2, so a third episode's checkpoint would delete the first. Design section 9 flags
    this as needing to be raised before the second episode, and this test is what
    makes that flag mechanical rather than a sentence in a document.
    """
    hygiene = (ROOT / "tools" / "state_hygiene.py").read_text(encoding="utf-8")
    assert 'LINEAGE = STATE / "lineage"' in hygiene
    assert '"lineage": 2' in hygiene, (
        "state_hygiene no longer caps lineage at 2: either the cap was raised (update "
        "this test and design section 9) or the constant moved")


LEDGER = ROOT / "state" / "lineage" / "episodes.jsonl"
REQUIRED_EPISODE_KEYS = (
    "episode", "at", "checkpoint_id", "parent_checkpoint", "promoted_to_live",
    "generator", "teaching", "eval", "displacement", "san", "seals", "guard",
    "erosion", "gates", "verdict", "provenance", "seconds")
REQUIRED_GATES = ("absence_verified", "erosion_zero", "census_reported",
                  "live_seals_unchanged", "row_self_contained")


def test_every_ledger_row_is_self_contained_and_verdict_consistent():
    """Section 6.4's ledger-schema test, and the reason the row is called
    self-contained: one row has to carry enough to tell which animal was taught, what
    it was taught, what it could still do afterwards, and what the teaching displaced.
    Skipped only if no episode has ever run.
    """
    import json
    if not LEDGER.exists():
        pytest.skip("no episode has been run yet")
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    assert rows, "ledger exists but is empty"
    for e in rows:
        missing = [k for k in REQUIRED_EPISODE_KEYS if k not in e]
        assert not missing, f"episode {e.get('episode')} lacks {missing}"
        for g in REQUIRED_GATES:
            assert g in e["gates"], f"episode {e['episode']} lacks gate {g}"
            assert g + "_detail" in e["gates"], f"gate {g} has no detail string"
        # The verdict must follow from the gates, recomputed here rather than trusted.
        import tools.teach_episode as te
        assert e["verdict"] == te.verdict_of(e["gates"]), f"episode {e['episode']}"
        # Provenance has to identify the interpreter and the tree, or two episodes
        # measured differently are indistinguishable in the ledger.
        for k in ("python", "numpy", "head"):
            assert e["provenance"].get(k), f"episode {e['episode']} lacks {k}"
        assert e["seals"]["before"] and e["seals"]["after"]
        assert e["generator"].get("seal") and e["generator"].get("seed") is not None


def test_a_passing_episode_really_did_measure_erosion():
    """The pilot ran --tier open, so frozen and guarded were 0/0 and the erosion gate
    passed on nothing. A PASS verdict is only meaningful if the guarded battery was
    actually run, so check that on every row that claims one."""
    import json
    if not LEDGER.exists():
        pytest.skip("no episode has been run yet")
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    for e in rows:
        if e.get("correction"):
            # A corrected row keeps its correction and must not claim a pass: the
            # episode-99 pilot was recorded as PASS on an unmeasured erosion gate and
            # was corrected in place, with the original verdict kept beside the fix.
            assert e["verdict"] != "PASS", f"corrected row {e['episode']} claims PASS"
            assert "original_verdict" in e["correction"]
            continue
        if e["verdict"] != "PASS":
            continue
        ev = e["eval"]
        assert ev["frozen_asked"] == 24, (
            f"episode {e['episode']} claims PASS having run "
            f"{ev['frozen_asked']} frozen asks")
        assert ev["guard_asked"] >= 1, (
            f"episode {e['episode']} claims PASS with no guarded probe measured")
        assert e["erosion"] == []
        assert e["guard"]["live_files_untouched"] is True
        assert e["seals"]["unchanged"] is True
        assert e["promoted_to_live"] is False, (
            "E1 must not promote anything to live state")
