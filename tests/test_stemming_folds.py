"""The stemmer's contract: fold what has been measured, never guess.

These tests exist because `stem()` is shared by question answering, binder
postings and procedure retrieval, and because its whole policy is asymmetric:
under-folding refuses a question, over-folding makes two different things look
alike and gets believed. So the file asserts both directions -- the folds that
must happen and the ones that must not.
"""
from organs.stemming import IRREGULAR, stem


def test_the_measured_irregular_fold():
    # The defect this fold was written for: the tell says "then two eggs break"
    # and the ask says "how many eggs broke". No suffix rule can bridge a vowel
    # change, so the pair had to be stated.
    assert stem("broke") == "break"
    assert stem("break") == "break"


def test_the_map_is_a_fixed_point_of_itself():
    """No chains: a folded word must not fold again into something else.

    "broke" -> "break" is only safe because "break" is where it lands and stays.
    Were a value itself mapped, stem() would return the value's own target and
    the pair would silently mean a third word.
    """
    for src, dst in IRREGULAR.items():
        assert stem(dst) == dst, f"{src} -> {dst} does not hold"
        assert stem(src) == stem(dst)


def test_the_map_is_consulted_before_the_length_guard():
    """A stated fold beats a heuristic about length.

    The `len(w) <= 4` rule returns short words untouched, which is right for
    suffix guessing and wrong for an irregular pair: "did" or "bit" could never
    fold if the guard came first. "broke" is five letters so the ordering is not
    proven by it, hence the explicit check of where the lookup sits.
    """
    IRREGULAR["did"] = "do"
    try:
        assert stem("did") == "do"
    finally:
        del IRREGULAR["did"]
    assert stem("did") == "did"


def test_regular_folds_still_hold():
    for src, dst in [("holds", "hold"), ("places", "place"),
                     ("watches", "watch"), ("memories", "memory"),
                     ("sorting", "sort"), ("bites", "bite")]:
        assert stem(src) == dst, src


def test_words_that_must_not_fold():
    """The named failure mode of every previous version of this function."""
    for w in ["class", "this", "focus", "is", "gas", "less", "glass"]:
        assert stem(w) == w, w


def test_the_list_is_not_a_dictionary_of_english():
    """`spoke` is a real irregular and is deliberately NOT in the map.

    The map grows from a failure that has been seen. Asserting the absence is
    what keeps it honest: a well-meaning sweep that added every irregular verb
    would pass every other test in this file and change retrieval everywhere.
    """
    assert "spoke" not in IRREGULAR
    assert stem("spoke") == "spoke"
