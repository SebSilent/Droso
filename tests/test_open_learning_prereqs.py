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


def test_teaching_is_currently_weighted_as_corpus():
    """THE DEFECT, pinned. `WITNESS_W` has no "you" key and nothing binds
    who="user", so testimony falls through .get(who, 0.6) to exactly the book
    weight -- at every count, not just at count 1.

    docs/open_learning_design.md section 3.2 measures this and section 7a names the
    one-entry fix. This test is expected to FAIL once 7a lands; update it then, and
    attach the before/after consolidation census the design requires.
    """
    assert "you" not in NeuralLanguage.WITNESS_W
    assert "user" in NeuralLanguage.WITNESS_W, (
        "WITNESS_W carries a 'user' key that no bind site ever writes")
    for count in (1, 2, 3, 10, 100):
        assert value("you", count) == value("book", count), count


def test_the_default_weight_is_the_book_weight():
    """Why the missing key is silent rather than loud: the fallback and the corpus
    weight are the same number, so an unrecognised `who` looks like a book row."""
    assert NeuralLanguage.WITNESS_W["book"] == 0.6
    assert value("never_bound_by_anything", 1) == value("book", 1)


def test_consolidation_currently_prefers_narration_then_arrival_order():
    """The consequence, stated as the ordering consolidate()'s sort actually produces
    on the live distribution: 19 parent rows outrank everything, own speech ranks
    below corpus, and the 59,665 count-1 rows -- book and you alike -- tie. With
    scan_top = 2000 the window therefore fills with tied rows in binder order, and a
    stable sort on a tied key preserves input order, which is arrival order.
    """
    assert value("parent", 1) > value("book", 1) > value("droso", 1)
    assert value("you", 1) == value("book", 1)
    # A taught row only outranks a corpus row by being REHEARSED, never by being
    # taught: count is the sole lever, because who contributes nothing.
    assert value("you", 2) > value("book", 1)
    assert value("you", 1) < value("parent", 1)


def test_a_taught_row_needs_rehearsal_to_outrank_the_corpus():
    """The one lever that currently works, and the reason the design's episode loop
    consolidates rather than only teaching."""
    assert value("you", 1) == value("book", 1)
    assert value("you", 2) > value("book", 1)
    assert value("you", 3) > value("book", 2)


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
