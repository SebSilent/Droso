"""ELECTRIC_ASK_DO_SUPPORT -- the widening that inserts exactly one word, and cannot invent a sentence.

Found by `tools/electric_learn_bench.py` and named by its mechanism, not by its symptom. The
benchmark taught 24 tells and asked each one in several shapes; the object ask WITH its auxiliary
("what does the dog bite") returned its tell verbatim 17 times in 21, and the SAME ask with the
auxiliary dropped ("what the dog bite") returned NOTHING 19 times in 21, refusing every time with
`nothing he remembers has that shape`. That is 20 of the 45 failing probes in the widest arm -- the
largest single mechanism in the QA gap -- and the distance between the two strings is one word, the
word English requires in that slot.

So the fix inserts that word and is gated behind a flag, and the two things this file exists to
hold still are exactly the two bounds the design has to keep:

  * THE WARRANT. A variant is emitted only when ONE taught tell carries the ask's noun as its
    SUBJECT and the ask's verb as its ACTION -- both read out of `_absence_frame`, the same
    extractor the absence licence uses. `what the moon bite` matches a moon tell and a bite verb
    separately and gets nothing, because no tell says the moon bit anything. This is the difference
    between folding a form and guessing an intent, and it is why an ask about an actor or an action
    nobody mentioned still refuses, with the flag on.
  * THE OUTPUT. What comes back is a verbatim taught tell, or nothing. The fold widens WHICH ASK
    reaches the matcher; it never touches what the matcher may say. Every reply in every test below
    is compared against the list of sentences the house was actually told.

Also pinned, because it is the bug this flag was nearly shipped inside: `--electric-learn` used to
set the widenings through the table and then have tools/serve.py overwrite three of them with
`bool(args.electric_x)` -- so the widest mode ran as teach mode plus one, and printed the user's
intent rather than the organ's state. The `or learn` on each assignment is the fix, and
`test_no_door_switches_a_mode_flag_back_off` is the guard.

The graded contract is untouched by construction: the flag is read only inside `_electric_answer`,
which is reached only under ELECTRIC_ANSWER, and nothing here moves a class default.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl                        # noqa: E402
import tools.electric_teach_mode as tm                     # noqa: E402
from connectome.engine import HybridEngine                 # noqa: E402
from connectome.substrate import build_core_graph          # noqa: E402
from organs.tokenizer import TokenizerOrgan                # noqa: E402

# One house, five tells. Every ask below is answerable from one of these and from nothing else, so
# a reply that is not in this list is the failure this file is watching for.
TELLS = ["the dog bites the latch",
         "the rope holds the shelf",
         "the lantern belongs to Mira",
         "the mouse chases the dog",
         "the moon pulls the tide"]

# The ask the flag exists for, and the tell each one must return.
FOLDS = [("what the dog bite", "the dog bites the latch"),
         ("what the rope hold", "the rope holds the shelf"),
         ("who the lantern belong to", "the lantern belongs to Mira"),
         ("what the mouse chase", "the mouse chases the dog"),
         ("what the moon pull", "the moon pulls the tide")]

# Asks whose halves come from DIFFERENT tells, or from no tell at all. Each one is a variant the
# warrant must refuse to emit: the noun is a subject somewhere, the verb is a verb somewhere, and
# no sentence in this house joins them.
NO_WARRANT = ["what the moon bite", "what the dog swim", "what the harbor sleep",
              "what the latch chase", "what the dog tide"]

CLASS_DEFAULTS = {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS}


def _organ(learn=True):
    """A bare organ, taught the five tells. Same discipline as the learn-mode file's `_organ`:
    no persistence, no wall-clock throttle, no exposure rows, and the mode applied through the
    table rather than by hand."""
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    o.exposure_enabled = False
    if learn:
        tm.enable_learn(o)
    for t in TELLS:
        o.hear(t, speaker="you")
    return o


def _said(o, ask):
    r = o.answer(ask) or {}
    return str(r.get("utterance") or "").strip(), r


# ------------------------------------------------------------------ the flag ----

def test_the_flag_is_off_on_the_class_and_learn_mode_never_moves_it():
    assert nl.NeuralLanguage.ELECTRIC_ASK_DO_SUPPORT is False
    before = dict(CLASS_DEFAULTS)
    o = _organ()
    assert o.ELECTRIC_ASK_DO_SUPPORT is True
    assert {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS} == before, \
        "a demo flag moved a class default; every battery number after this is suspect"


def test_the_aux_dropped_object_ask_returns_its_own_tell_verbatim():
    o = _organ()
    for ask, want in FOLDS:
        got, r = _said(o, ask)
        assert got == want, f"{ask!r} -> {got!r}, expected {want!r}"
        assert r.get("source") == "electric_taught", (ask, r.get("source"))


def test_with_the_flag_off_the_same_ask_still_refuses():
    """The counterfactual, on the SAME organ: this is not a mode that got luckier, it is one word
    that was and was not inserted. `answered` is the assertion, not emptiness -- a licensed
    absence SPEAKS ("i don't know, ...") and is still a refusal, and a test that called that an
    answer would be measuring the wrong thing."""
    o = _organ()
    o.ELECTRIC_ASK_DO_SUPPORT = False
    for ask, want in FOLDS:
        got, r = _said(o, ask)
        assert not r.get("answered"), f"{ask!r} answered {got!r} with the flag off"
        assert got != want, (ask, got)


def test_the_warrant_needs_both_halves_from_one_tell():
    """`what the moon bite`: the moon IS a subject in this house and bite IS a verb in this house.
    No tell says the moon bit anything, so no variant may be emitted -- and a variant that was
    emitted here would be answered with somebody else's sentence, which is the exact failure the
    benchmark's role-swap probes were built to catch."""
    o = _organ()
    says = o._taught_says
    for ask in NO_WARRANT:
        toks = [t for t in ask.split()]
        assert nl._do_support_variant(toks, says) is None, f"{ask!r} got a variant with no warrant"
        got, r = _said(o, ask)
        assert not r.get("answered"), f"{ask!r} answered {got!r} with no warrant for it"


def test_everything_the_fold_says_is_a_sentence_it_was_told():
    """The invariant the widening cannot break, stated as a sweep rather than a hope: for any of
    these asks, whatever comes out is one of the five tells."""
    o = _organ()
    for ask in [a for a, _w in FOLDS] + NO_WARRANT + ["what the dog bites", "who the moon pull"]:
        got, r = _said(o, ask)
        if r.get("answered"):
            assert got in TELLS, f"{ask!r} -> {got!r} is not a sentence it was told"


def test_a_stranded_preposition_stays_where_the_person_put_it():
    """The reverse-role path is keyed on that preposition. Dropping it would fold `who the lantern
    belong to` onto the form of a different question."""
    v = nl._do_support_variant(["who", "the", "lantern", "belong", "to"], _organ()._taught_says)
    assert v == "who does the lantern belong to", v


# ---------------------------------------------------------------- the boundary ----

def test_normalize_ask_variants_without_the_parameter_is_the_measured_function():
    """`normalize_ask_variants` is also the store's paraphrase key, and that path is in the TEACH
    stack. So the fold is a parameter, not an addition to the default list: with the argument
    absent this function returns what it returned before the flag existed."""
    says = _organ()._taught_says          # taught, so the warrant has something to check against
    assert says, "an organ with no ELECTRIC_TEACH files no tells -- the test would prove nothing"
    assert nl.normalize_ask_variants("what the dog bite", says) == []
    assert nl.normalize_ask_variants("what the dog bite", says, do_support=True) \
        == ["what does the dog bite"]
    # the passive fold, unchanged in both calls -- it fires first and returns first
    door = {"door": {"agent": "the key opens the door"}}
    assert nl.normalize_ask_variants("what was the door opened by", door) \
        == nl.normalize_ask_variants("what was the door opened by", door, do_support=True)


def test_inert_without_the_normalizer_and_says_so():
    """The variant is generated inside the normalizer's own block, so a door that turns this flag
    on without ELECTRIC_ASK_NORMALIZE has turned on nothing. Inert is worse than off only when it
    is silent, so the table declares the dependency and the warning names it."""
    o = _organ()
    o.ELECTRIC_ASK_NORMALIZE = False
    o.ELECTRIC_ASK_DO_SUPPORT = True
    for ask, _want in FOLDS:
        got, r = _said(o, ask)
        assert not r.get("answered"), f"{ask!r} answered {got!r} with the parent off"
    st = tm.state(o)
    assert tm.unmet(st), "the dependency is not declared in the table"
    assert any("do-support" in line for line in tm.unmet(st)), tm.unmet(st)


def test_the_table_lists_it_as_a_widening_and_not_as_part_of_the_stack():
    assert "ELECTRIC_ASK_DO_SUPPORT" in tm.EXCLUDED_ATTRS
    assert "ELECTRIC_ASK_DO_SUPPORT" in tm.LEARN_ATTRS
    assert "ELECTRIC_ASK_DO_SUPPORT" not in tm.STACK_ATTRS, \
        "a widening is not in the mode that can only ever refuse"
    assert len(tm.EXCLUDED) == 6 and len(tm.ALL_ATTRS) == 17
    assert any(l.startswith("WIDENS") and "ELECTRIC_ASK_DO_SUPPORT" in l
               for l in tm.describe_learn()), tm.describe_learn()
    # and the narrow mode must not have it
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    tm.enable(o)
    assert o.ELECTRIC_ASK_DO_SUPPORT is False


def test_no_door_switches_a_mode_flag_back_off():
    """serve.py sets the widenings from the table and THEN from its own argparse lines. That order
    is fine; `= bool(args.x)` in that second pass is not, because it takes the mode's own widening
    back off for anyone who asked for the mode and not for the switch. Measured before the fix:
    `--electric --electric-learn` ran with REVERSE, OBJECT_ROLE and ASK_NORMALIZE all False."""
    serve = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    for dest in ("electric_reverse", "electric_object_role", "electric_ask_normalize",
                 "electric_ask_do_support", "electric_ask_shape_store"):
        assert f"or learn" in serve.split(dest + ")")[1][:120], dest
    assert "bool(args.electric_ask_do_support) or learn" in serve
    # the mode implies --electric, and the block that runs load_state() is inside it
    assert "if teach or learn:" in serve, "learn mode skipped the restart half of --electric"
    # and the banner reports the ORGAN, not the parsed intent
    assert "reverse={lang.ELECTRIC_REVERSE}" in serve, serve[serve.find("ELECTRIC on:"):]


# ------------------------------------------------- the benchmark's own taxonomy ----

def test_the_benchmark_calls_this_failure_what_it_is():
    """The mechanism split is what chose this fix over the others, so the split is pinned here:
    an ask that reached no question path is `ask_not_recognized`, not `refusal_silence`, and the
    two have different fixes."""
    import tools.electric_learn_bench as bench
    row = dict(item="tell0.0", shape="object_fold", ask="what the dog bite",
               own="the dog bites the latch", taught="the dog bites the latch",
               answered=False, said="", src="",
               reason="nothing he remembers has that shape")
    assert bench.mechanism(row, set()) == "ask_not_recognized"
    row2 = dict(row, reason="nothing remembered about that", item="pair0.1",
               shape="pair_exact", ask="what does Mira love most",
               taught="she loves the lantern most", own="she loves the lantern most")
    assert bench.mechanism(row2, set()) == "pair_never_admitted"
