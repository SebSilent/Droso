"""The binder's incremental postings must equal a fresh rebuild, always.

remember() has two write paths. Below capacity it appends a row and posts it
into _postings/_stem_postings. At capacity it evicts row 0, appends the new row
at the end, and calls _rebuild_postings() -- which rebuilds BOTH indexes from
meta, including the row it just appended. The fall-through that posts the new
row then ran a second time, so from the first eviction onward the newest row
was posted twice: every posting list for its words held the same index twice,
and overlap counting counted that row's words double. Found by reading, not by
a failing test -- no test had ever constructed a binder past its capacity.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.higher_cortex import Binder, ConceptSpace
from organs.stemming import stem


def _expected(b):
    words, stems = {}, {}
    for i, m in enumerate(b.meta):
        for w in set(str(t).strip().lower() for t in m["tokens"]):
            words.setdefault(w, []).append(i)
            stems.setdefault(stem(w), []).append(i)
    return words, stems


def test_postings_equal_a_rebuild_past_capacity():
    space = ConceptSpace(dim=64, seed=0)
    b = Binder(space, max_roles=4, capacity=3)
    for i in range(6):
        out = b.remember([f"w{i}", "shared"], who="t", when=float(i))
        assert out.get("stored") is True, out
    assert len(b.meta) == 3, len(b.meta)
    words, stems = _expected(b)
    assert b._postings == words, (b._postings, words)
    assert b._stem_postings == stems, (b._stem_postings, stems)


def test_no_row_is_posted_twice_for_one_word():
    """The visible symptom, stated directly: one index, one posting."""
    space = ConceptSpace(dim=64, seed=0)
    b = Binder(space, max_roles=4, capacity=3)
    for i in range(6):
        b.remember([f"w{i}", "shared"], who="t", when=float(i))
    for w, rows in b._postings.items():
        assert rows == sorted(set(rows)), (w, rows)