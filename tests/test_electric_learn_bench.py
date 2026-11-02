"""ELECTRIC_LEARN_BENCH -- tests for the measuring instrument, not the house.

`tools/electric_learn_bench.py` costs about eleven minutes and boots nine houses, so nothing here
runs it. What is under test instead is the thing that would make its numbers meaningless: the
CLASSIFIER. The first draft of that classifier scored 16 confabulations in the control arm, which
has no ELECTRIC at all -- an impossibility that turned out to be three real behaviours being called
by the wrong name: the licensed refusal SPEAKING, the question word falling out of a parse, and an
item answered correctly from a tell the house already had. A benchmark whose classes are wrong does
not measure a capability, it measures its own vocabulary, so each class gets a row here.

These are pure-function tests: no organ, no house, no state file, no flag. They run in under a
second, which is the point -- the classifier is the part that must be cheap to check.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from organs.neural_language import NeuralLanguage            # noqa: E402
import tools.electric_learn_bench as bench                   # noqa: E402


def row(ask, said, want=None, src="", own=None):
    return dict(item="t", shape="subject", ask=ask, taught=want, own=own or want,
                answered=bool(said), said=said, src=src, reason="")


# ---------------------------------------------------------------- the curriculum's own integrity

def test_the_curriculum_is_the_size_the_report_claims():
    assert bench.ALL_ITEMS == 40, bench.ALL_ITEMS
    assert len(bench.PROBES) == 136, len(bench.PROBES)
    assert sum(1 for p in bench.PROBES if p[3] is None) == 12, "the distractor set moved"
    # 40 items x their shapes, plus 12 distractors -- derived, not remembered
    shapes = sum(len(list(bench.probes_for(f))) for s in bench.SESSIONS for f in s) \
        + sum(len(list(bench.probes_for_pair(q, a))) for s in bench.PAIRS for q, a in s)
    assert shapes + 12 == 136, shapes


def test_every_expected_answer_is_a_sentence_the_curriculum_actually_says():
    for _iid, _shape, _ask, tell, _d in bench.PROBES:
        if tell is not None:
            assert tell.lower() in bench.TOLD, (_shape, tell)


def test_no_distractor_is_answered_by_any_tell():
    """The 12 untaught probes have to be untaught IN THE STRONG SENSE: no tell in the curriculum
    states the thing they ask. If one ever did, the refusal rate would be measuring politeness."""
    for _iid, _shape, ask, tell, _d in bench.PROBES:
        if tell is None:
            assert ask not in {p[2] for p in bench.PROBES if p[3] is not None}, ask
    # and the sharpest one by name, because it is the fault the tool found: nothing in the
    # curriculum says what chases the mouse, while it does say the mouse chases the dog.
    assert "the mouse chases the dog" in bench.TOLD
    assert not any("chases the mouse" in t for t in bench.TOLD)


def test_the_pair_only_items_are_exactly_the_sentences_no_tell_carries():
    """The bottleneck claim about pair admission rests on there being THREE such items -- the only
    ones whose answer lives nowhere but the store. If the curriculum grows a fourth tell that says
    one of them, the claim goes stale, and this is the test that notices."""
    told = {f["tell"].lower() for s in bench.SESSIONS for f in s}
    only = [(q, a) for s in bench.PAIRS for q, a in s if a.lower() not in told]
    assert len(only) == 3, only
    assert {q for q, _a in only} == {"what does Mira love most?", "when does the bell toll?",
                                     "how many dogs sleep?"}, only


def test_probes_ask_in_words_the_house_is_told_except_where_that_is_the_point():
    """A refusal is only evidence about capability if the house knew the words. Every probe word
    must be a word some tell or pair answer contains (or an inflection of one, or an interrogative,
    or a function word) -- and the exceptions are named here rather than tolerated, because they are
    two probes whose whole purpose is to be unanswerable on vocabulary: `what rings in the tower`
    and `where is the harbor`. That distinction is why pair0.2 is reported as refused and not as
    forgotten: the tower was never in this house."""
    # Deliberately NOT the organ's `stem`: a test that folds words with the same stemmer the
    # matching path uses cannot see a stemmer that under-folds, and `what chase the dog` would read
    # as a vocabulary refusal when it is really a stem mismatch. So the vocabulary is the
    # curriculum's own words plus the two mechanical inflections English hangs on a present verb,
    # and the probe side is compared UNFOLDED -- which is the harsher direction.
    def forms(w):
        """A word and the mechanical shapes of it English allows: `carries` <-> `carry`,
        `sleep` <-> `sleeps`, `bites` <-> `bite`. Both directions, because the curriculum uses
        the inflected form and the probe often uses the stem -- and the first version of this
        helper folded only one way, which reported `carry` and `sleeps` as words the house had
        never been told. They had: `Nora carries the lantern` and `two dogs sleep`."""
        out = {w, w + "s", w + "es"}
        if w.endswith("ies") and len(w) > 3:
            out.add(w[:-3] + "y")
        if w.endswith("y") and len(w) > 2:
            out.add(w[:-1] + "ies")
        if len(w) > 3:
            out.add(w[:-1])
        if w.endswith("es") and len(w) > 4:
            out.add(w[:-2])
        return out

    raw = {w for s in bench.TOLD for w in s.split()}
    vocab = set().union(*(forms(w) for w in raw)) | bench.QWORDS | {
        "the", "to", "on", "in", "at", "does", "did", "was", "is", "by",
        "for", "most", "how", "many", "which", "why"}
    unknown = {w for _i, _s, a, _t, _d in bench.PROBES for w in a.lower().split()
               if w not in vocab}
    assert unknown == {"tower", "harbor"}, unknown


def test_importing_the_tool_turns_nothing_on():
    for attr in bench.tm.ALL_ATTRS:
        assert getattr(NeuralLanguage, attr) is False, attr


# ------------------------------------------------------------------------------------ the classes

def test_the_licensed_refusal_speaking_is_not_a_confabulation():
    """`i don't know, bell was told but no place was ever told for bell` is a sentence nobody said,
    and the first draft called that an invention. It is the ABSENCE path, it is a refusal, and it
    has to be counted apart or the invention rate means nothing."""
    said = "i don't know, bell was told but no place was ever told for bell"
    assert bench.classify(row("where does the bell hang", said, src="electric_absence")) == "absence"
    assert bench.classify(row("where does the bell hang", said,
                              want="the bell hangs on the wall",
                              src="electric_absence")) == "absence"


def test_an_answer_the_house_earns_from_an_earlier_tell_is_not_a_false_acceptance():
    """At depth 1 the future curriculum is a distractor set, and `what holds the shelf` is answered
    `the rope holds the shelf` from a tell already in the house. Calling that a false acceptance is
    a benchmark bug: it penalises the behaviour the mode is for."""
    assert bench.classify(row("what holds the shelf", "the rope holds the shelf",
                              want=None, own="the rope holds the shelf")) == "entailed"


def test_a_question_handed_back_is_an_echo_and_not_an_invention():
    for ask, said in (("where does the bell hang", "where the bell hang"),
                      ("where the bell hang", "droso says where the bell hang"),
                      ("what the dog guard", "what")):
        assert bench.classify(row(ask, said, want=None)) == "echo", (ask, said)


def test_a_DIFFERENT_question_out_of_the_pool_is_cross_echo():
    other = "why does the dog bite the latch"
    assert bench.classify(row("what sleeps at dusk", other, want=None)) == "cross_echo"


def test_a_told_sentence_on_the_wrong_ask_is_misattribution_not_invention():
    assert bench.classify(row("what bites the latch", "the dog bites the moon",
                              want=None)) == "invented"
    assert bench.classify(row("what bites the latch", "the mouse chases the dog",
                              want=None)) == "misattrib"
    assert bench.classify(row("what holds the shelf", "the shelf holds the lamp",
                              want="the rope holds the shelf")) == "misattrib"


def test_one_word_out_of_the_right_tell_is_partial_not_correct():
    """The shape arbiter saying `dog` where the inventory says `the dog bites the latch` is a REACH
    failure. Scoring it correct would hide the exact gap this benchmark exists to find; scoring it
    invented would call it a lie."""
    assert bench.classify(row("what bites the latch", "dog",
                              want="the dog bites the latch")) == "partial"
    assert bench.classify(row("what bites the latch", "the dog bites the latch",
                              want="the dog bites the latch")) == "correct"
    assert bench.classify(row("what bites the latch", "", want="the dog bites the latch")) \
        == "refused"


def test_invented_is_reserved_for_a_sentence_nobody_said_and_is_the_only_hard_class():
    got = bench.classify(row("what bites the latch", "the cat drives the car", want=None))
    assert got == "invented", got
    # the exit-code floor is exactly this class, so the class list must name it once
    assert bench.CLS.count("invented") == 1


def test_every_verdict_the_classifier_can_return_is_a_declared_class():
    """A class the report does not know about is a probe that vanishes from every column."""
    samples = [row("what bites the latch", "", want="the dog bites the latch"),
               row("what bites the latch", "the dog bites the latch", want="the dog bites the latch"),
               row("what bites the latch", "dog", want="the dog bites the latch"),
               row("what bites the latch", "the mouse chases the dog", want=None),
               row("what bites the latch", "the cat drives the car", want=None),
               row("what holds the shelf", "the rope holds the shelf", want=None,
                   own="the rope holds the shelf"),
               row("where does the bell hang", "where the bell hang", want=None),
               row("what sleeps at dusk", "why does the dog bite the latch", want=None),
               row("where does the bell hang", "i don't know, no place was ever told",
                   src="electric_absence")]
    for r in samples:
        assert bench.classify(r) in bench.CLS, (r["said"], bench.classify(r))
    # and the nine samples above really do exercise all nine classes -- a class with no test here
    # is a class whose numbers nobody checked
    assert {bench.classify(r) for r in samples} == set(bench.CLS), \
        sorted(set(bench.CLS) - {bench.classify(r) for r in samples})


def test_norm_compares_an_ask_and_an_answer_on_the_same_ground():
    assert bench.norm("Droso says WHERE the bell hang?") == bench.norm("where does the bell hang")
    assert bench.norm("  the Dog  Bites   the Latch ") == "dog bites latch"
    assert bench.norm("what the dog guard") == bench.norm("what does the dog guard")
    assert bench.norm("what the dog guard") in bench.ASK_NORMS


def test_no_tell_can_ever_normalize_onto_an_ask():
    """The ordering that makes ECHO safe: classify checks echo BEFORE correct, so if a tell's norm
    collided with an ask's norm, a right answer would be reported as a question handed back. Every
    ask here opens with an interrogative and no tell does -- which is what keeps that check from
    being a landmine, and it is a property of the CURRICULUM, not of the classifier."""
    assert not {bench.norm(t) for t in bench.TOLD} & bench.ASK_NORMS
    for t in bench.TOLD:
        assert t.split()[0] not in bench.QWORDS, t


def test_retention_counts_items_and_not_probes():
    """KEPT = every way of asking an item gets its own tell back. An item that answers three of its
    four phrasings is PART, and the gap between kept and part is the whole shape report: at depth 3
    the learn arm had 10 kept and 23 part, which is a mode that answers the shape it was taught in
    and not the others."""
    def r(item, ask, said, want):
        return dict(item=item, shape="subject", ask=ask, taught=want, own=want,
                    said=said, src="", answered=bool(said), reason="")
    rows = [r("i1", "what bites the latch", "the dog bites the latch", "the dog bites the latch"),
            r("i2", "what holds the shelf", "the rope holds the shelf", "the rope holds the shelf"),
            r("i2", "what does the rope hold", "", "the rope holds the shelf"),
            r("i3", "what rings", "dog", "the copper bell rings")]
    got = bench.retention(rows)
    assert got == dict(items=3, kept=1, part=1, lost=1, probes=4, probes_correct=2), got


def test_tally_and_by_shape_cover_every_class_without_keyerrors():
    rows = [dict(row("what bites the latch", "dog", want="the dog bites the latch"),
                 item="i", shape="object")]
    t = bench.tally(rows)
    assert t == {"partial": 1}, t
    bs = bench.by_shape(rows)["object"]
    for c in bench.CLS:
        assert c in bs, c
