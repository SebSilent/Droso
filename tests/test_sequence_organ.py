"""The sequence organ: what he can say, and what stops him saying it.

The second test is the one that matters. A dense chain normalised its successor
scores by total chain activity, so every word learned afterwards made the words
already known score lower -- at 512 cells and 5,291 words heard, 62 words shared
each cell and nothing cleared the floor. He knew more and said less, and it looked
from outside like a mood. These tests fail against that version.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.sequence_organ import SequenceOrgan  # noqa: E402


# Every opener is unique AND no two sentences share a word at the same position,
# so a seed has exactly one continuation at every slot. Sharing a word at a slot
# makes the chain genuinely ambiguous there, and refusing to guess is correct --
# tested separately below.
SENTENCES = [
    "parent holds a light",
    "droso wants some food",
    "water feels cold today",
    "night stays quiet now",
    "morning brings one word",
    "sister reads that book",
    "father opens the door",
    "friend says my name",
]

# Two sentences, one opener: after "parent" the next word really could be either.
AMBIGUOUS = ["parent holds a light", "parent pets the child"]


def _teach(org, sentences, times=40):
    for _ in range(times):
        for s in sentences:
            org.learn_sequence(s.split())


def test_a_learned_sequence_is_reproduced_in_order():
    org = SequenceOrgan()
    _teach(org, SENTENCES)
    out = org.generate("parent", max_len=6)
    assert out["from_sequence_organ"] is True, out
    assert out["words"] == ["parent", "holds", "a", "light"], out
    # every word he produced is one he was actually taught in that position
    for i, w in enumerate(out["words"]):
        assert w in org.slot_words[i], (i, w, out)


# One opener, three continuations: the material argmax has to refuse.
BRANCHING = [
    "parent holds a light",
    "parent pets the child",
    "parent opens that door",
]


def test_zero_temperature_is_deterministic():
    """recall() depends on this: a reproduction test cannot sample."""
    org = SequenceOrgan()
    _teach(org, SENTENCES)
    a = org.generate("parent", max_len=6, temperature=0.0)
    b = org.generate("parent", max_len=6, temperature=0.0)
    assert a["words"] == b["words"] == ["parent", "holds", "a", "light"]


def test_sampling_says_different_things_from_the_same_seed():
    """What argmax refuses as ambiguous, sampling can say -- and varies.

    Three continuations of "parent" with equal evidence is not a collision at
    16,384 cells, it is a fact about what he heard: all three really did follow.
    Stopping there is honest but silent, and saying the same one every time is not
    speech. Saying a different one each time is.
    """
    org = SequenceOrgan()
    _teach(org, BRANCHING, times=40)
    det = org.generate("parent", max_len=5, temperature=0.0)
    assert det["words"] == ["parent"] and "ambiguous" in det["stopped"], det

    outs = [tuple(org.generate("parent", max_len=5, temperature=0.9)["words"])
            for _ in range(40)]
    assert len(set(outs)) >= 2, f"sampling produced one sentence: {set(outs)}"


def test_sampling_only_ever_says_what_he_was_taught():
    """With three clean branches and nothing else in memory, there is no material
    to splice -- so every sampled sentence must be a taught one, whole."""
    org = SequenceOrgan()
    _teach(org, BRANCHING, times=40)
    taught = {tuple(s.split()) for s in BRANCHING}
    for _ in range(30):
        out = org.generate("parent", max_len=5, temperature=1.2)
        got = tuple(out["words"])
        assert got in taught, f"{got} is not one of {taught}"


def test_avoid_suppresses_a_word_he_just_said():
    org = SequenceOrgan()
    _teach(org, BRANCHING, times=40)
    got = set()
    for _ in range(24):
        out = org.generate("parent", max_len=5, temperature=0.9,
                           avoid={"holds", "a", "light"})
        got.add(tuple(out["words"]))
    assert got and all("holds" not in g for g in got), got


def test_sampling_never_invents_a_link():
    """The guarantee a positional bigram chain can actually make.

    The first version of this test demanded whole-sentence fidelity and caught
    ('parent', 'pets', 'the', 'door'): the first three words from "parent pets the
    child" and the last from "father opens the door", joined at a slot where "the"
    really had been followed by both. Every transition in it was taught. The
    sentence was not.

    That is not a bug to fix here, it is what this organ IS. It conditions on one
    word and a position, so it recombines; insisting otherwise would need a chain
    conditioned on the whole prefix, which is a different and larger machine. What
    it must never do is invent a link -- a pair of adjacent words at a slot that
    were never heard adjacent. That is the line between generalising and
    confabulating, and it is the line the first sampling attempt crossed: thirty
    requests gave thirty distinct sentences reading 'bigrams you angry probe',
    because a bare floor of 12% of candidate mass leaves a long tail and
    temperature 0.7 sharpens a distribution barely at all.
    """
    org = SequenceOrgan()
    taught = BRANCHING + SENTENCES
    _teach(org, taught, times=40)
    links = set()
    for s in taught:
        ws = s.split()
        for i in range(len(ws) - 1):
            links.add((i, ws[i], ws[i + 1]))
    for temp in (0.2, 0.5, 1.0, 3.0):
        for _ in range(25):
            out = org.generate("parent", max_len=5, temperature=temp)
            got = out["words"]
            for i in range(len(got) - 1):
                assert (i, got[i], got[i + 1]) in links, \
                    f"temperature {temp}: {got} invents {got[i]}->{got[i+1]} " \
                    f"at slot {i}"


def test_a_genuinely_ambiguous_opener_is_refused_not_guessed():
    """Two continuations, equal evidence: he stops rather than pick one.

    This is the property that makes the refusal above correct instead of merely
    conservative. A chain that broke ties at random would speak fluently and be
    wrong half the time, and nothing downstream could tell the difference.
    """
    org = SequenceOrgan()
    _teach(org, AMBIGUOUS)
    out = org.generate("parent", max_len=6)
    assert out["words"] == ["parent"], out
    assert "ambiguous" in out["stopped"], out


def test_learning_more_vocabulary_does_not_shorten_known_sentences():
    """The regression. Knowing more words must not cost him the ones he knows."""
    org = SequenceOrgan()
    _teach(org, SENTENCES)
    before = org.generate("parent", max_len=6)
    assert len(before["words"]) >= 3, before

    rng = random.Random(7)
    novel = []
    for i in range(1400):
        novel.append(" ".join(f"word{rng.randrange(4000)}" for _ in range(9)))
    _teach(org, novel, times=1)
    assert len(org.words_seen) > 1400, len(org.words_seen)

    after = org.generate("parent", max_len=6)
    assert len(after["words"]) >= len(before["words"]), (
        f"a vocabulary of {len(org.words_seen)} shortened a sentence he already "
        f"knew: {before['words']} -> {after['words']} ({after['stopped']})")


def test_an_unheard_opener_is_refused_rather_than_invented():
    org = SequenceOrgan()
    _teach(org, SENTENCES, times=5)
    out = org.generate("xylophone", max_len=5)
    assert out["words"] == ["xylophone"]
    assert out["from_sequence_organ"] is False
    assert "never heard opening" in out["stopped"]


def test_a_sequence_needs_two_words():
    org = SequenceOrgan()
    assert org.learn_sequence(["only"])["reason"]
    assert org.learn_sequence([])["reason"]


def test_save_and_load_roundtrip_preserves_the_chain(tmp_path):
    org = SequenceOrgan()
    _teach(org, SENTENCES, times=20)
    p = tmp_path / "seq.npz"
    assert org.save(str(p))["saved"] is True

    other = SequenceOrgan()
    loaded = other.load(str(p))
    assert loaded["loaded"] is True, loaded
    assert other.sequences_learned == org.sequences_learned
    assert other.words_seen == org.words_seen
    assert [sorted(s) for s in other.slot_words] == \
           [sorted(s) for s in org.slot_words]
    # and it still speaks, which is the only part of a roundtrip that matters
    out = other.generate("parent", max_len=6)
    assert out["words"] == ["parent", "holds", "a", "light"], out


def test_a_chain_built_at_a_different_cell_count_is_refused(tmp_path):
    """The cell count is the geometry, not metadata.

    A word's cells are hash % cells, so a chain saved at one count and loaded at
    another has every index still resolving -- to the wrong word. It does not fail
    loudly, it speaks: two restarts ran on such a chain and produced "carcase
    sharing those earth forty days" from a vocabulary no book on the shelf
    contained. The dense format refused on shape; a sparse one has no shape to
    refuse on, so the count is recorded and checked.
    """
    small = SequenceOrgan(cells_per_slot=1024)
    _teach(small, SENTENCES, times=20)
    p = tmp_path / "geometry.npz"
    assert small.save(str(p))["saved"] is True

    out = SequenceOrgan(cells_per_slot=4096).load(str(p))
    assert out["loaded"] is False
    assert "cells" in out["reason"], out

    same = SequenceOrgan(cells_per_slot=1024)
    assert same.load(str(p))["loaded"] is True
    assert same.generate("parent", max_len=5)["words"][:2] == ["parent", "holds"]


def test_a_dense_file_from_an_older_life_is_refused_with_a_reason(tmp_path):
    """Not silently accepted. The projections mean different things at a
    different cell count, so a restored dense chain would read as competence he
    does not have."""
    import numpy as np
    p = tmp_path / "old.npz"
    small = SequenceOrgan(cells_per_slot=64)
    _teach(small, ["parent holds a light"], times=3)
    np.savez_compressed(str(p),
                        chain=np.zeros((small.n_slots - 1, 64, 64), np.float32),
                        words=np.array(["the", "food"]),
                        counts=np.array([1, 1]))
    out = SequenceOrgan().load(str(p))
    assert out["loaded"] is False
    assert "sparse" in out["reason"] or "dense" in out["reason"]


def test_stats_describe_a_sparse_chain():
    org = SequenceOrgan()
    _teach(org, SENTENCES, times=3)
    st = org.stats()
    assert st["representation"] == "sparse"
    assert st["nonzero_transition_weights"] > 0
    assert st["sparse_mb"] < st["dense_equivalent_mb"]
