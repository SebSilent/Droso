"""The arbiter names the HEAD of a span, not its first word.

English noun phrases are head-final: determiners and modifiers precede the
head, so "the copper bell turns twice" is about `bell` and "the frost holds
the heavy latch" is about `latch`. `_shape_matches` used to return the first
content word of the span, which named the modifier -- measured, not argued:
rendering that filler said `copper` and tripped the same forbid the whole
sentence did.

These tests exist because no ask in tools/scripts.json and none in the
held-out 24 exercises a multi-word OBJECT span, so the suites cannot see the
second half of the rule at all. They pin the position rule directly, and the
last test checks that the tests themselves can tell first from last -- if a
case has only one content word in the span, it proves nothing about heads.
"""

import os

import pytest

from organs.neural_language import NeuralLanguage


@pytest.fixture()
def nl(tmp_path):
    """A real carve + the real tokenizer, offline."""
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine
    from organs.tokenizer import TokenizerOrgan
    return NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(),
                          state_path=tmp_path / "neural_lang.json")


def subject_shape(verb, tail):
    return {"kind": "subject_unknown", "verb": verb, "tail": list(tail)}


def object_shape(verb, subject):
    return {"kind": "object_unknown", "verb": verb, "subject": list(subject)}


def test_multi_word_subject_span_yields_the_head(nl):
    got = nl._shape_matches(subject_shape("turns", ["twice"]),
                            ["the", "copper", "bell", "turns", "twice"])
    assert got == "bell", f"head of 'the copper bell' is bell, got {got!r}"
    assert got != "copper", "the modifier is not the answer"


def test_multi_word_object_span_yields_the_head(nl):
    got = nl._shape_matches(object_shape("holds", ["frost"]),
                            ["the", "frost", "holds", "the", "heavy", "latch"])
    assert got == "latch", f"head of 'the heavy latch' is latch, got {got!r}"
    assert got != "heavy", "the modifier is not the answer"


def test_single_word_spans_are_unaffected_by_the_rule(nl):
    """last == first when the span has one content word, so the fallback is
    automatic -- and these are the only spans the suites currently walk."""
    assert nl._shape_matches(subject_shape("bites", ["latch"]),
                             ["the", "frost", "bites", "the", "latch"]) == "frost"
    assert nl._shape_matches(object_shape("bites", ["frost"]),
                             ["the", "frost", "bites", "the", "latch"]) == "latch"


def test_a_three_word_span_still_names_only_the_head(nl):
    got = nl._shape_matches(subject_shape("rings", ["at", "noon"]),
                            ["the", "small", "brass", "bell", "rings", "at",
                             "noon"])
    assert got == "bell", f"head of 'the small brass bell' is bell, got {got!r}"


def test_the_tests_can_tell_first_from_last(nl):
    """If this passes on a span whose first and last content word are the same
    word, it is not evidence of anything. Guarded explicitly."""
    for toks, shape in [(["the", "copper", "bell", "turns", "twice"],
                         subject_shape("turns", ["twice"])),
                        (["the", "frost", "holds", "the", "heavy", "latch"],
                         object_shape("holds", ["frost"]))]:
        content = [t for t in toks if t not in nl.SHAPE_FUNCTION_WORDS]
        verb_i = max(i for i, t in enumerate(content)
                     if t in ("turns", "holds"))
        span = content[:verb_i] if shape["kind"] == "subject_unknown" \
            else content[verb_i + 1:]
        assert len(span) >= 2, f"{toks}: span has one word, proves nothing"
        assert span[0] != span[-1], f"{toks}: first and last are the same word"
        assert nl._shape_matches(shape, toks) == span[-1]
