"""ELECTRIC_ASK_NORMALIZE: form, not meaning. Off by default; guarded contract untouched.

The claim under test is narrow: an ask whose RELATION is known but whose FORM the binders
never see -- a copula where do-support was expected, a passive where the object-role path
expects the active -- should reach the tell it reaches anyway, and nothing else should
move. Every guard here is therefore about the asks that must stay silent.

Written against a literal inventory rather than a built organ wherever possible: the
matchers are pure functions of (question, says), and a hermetic fixture is the only way to
assert "no variant was emitted" without also asserting which writes the organ's 50 ms
throttle happened to allow (see tests/test_electric_ask_admissibility._no_throttle).
"""
import importlib.util as _u
import io
import inspect
import sys

sys.path.insert(0, ".")

import organs.neural_language as nl  # noqa: E402

_s = _u.spec_from_file_location("obj_nmz", "tools/electric_object_ab.py")
_ob = _u.module_from_spec(_s)
_s.loader.exec_module(_ob)

SAYS = {
    "lantern": {"agent": "the lantern belongs to Mira"},
    "mouse": {"agent": "the mouse chases the cat"},
    "scarf": {"place": "the scarf is on the hook"},
    "ledger": {"place": "the ledger is under the desk"},
    "frost": {"agent": "the frost bites the latch"},
    "latch": {"agent": "the latch holds the door"},
    "boy": {"agent": "the boy opens the door"},
    "mira": {"agent": "Mira gives the lantern"},
}
TELLS = sorted({t for v in SAYS.values() for t in v.values()})

ALL = [(q, w) for q, _s2, w in _ob.ASKS] + [
    ("who is the lantern with?", "the lantern belongs to Mira"),
    ("what was the door opened by?", "the boy opens the door"),
    ("what is the latch bitten by?", "the frost bites the latch"),
    ("who was the lantern given by?", "Mira gives the lantern"),
    ("what was the latch broken by?", None),
    ("who is the mouse with?", None),
    ("who is the scarf with?", None),
]


def ask(q, normalize=False):
    return nl._electric_answer(q, SAYS, reverse=True, object_role=True,
                               normalize=normalize)


# ---------------------------------------------------------------------- the stem table

def test_the_irregular_table_is_closed_and_no_en_rule_exists():
    """A 16-entry table is the whole lexical commitment, and there is deliberately no
    `-%en` rule: it would mangle `green`, `men`, `ten`. Anything the rule cannot do and the
    table does not list produces no variant -- the table is a candidate generator, and the
    house's own taught verbs are the authority that accepts one."""
    assert len(nl.ASK_IRREGULAR_PARTICIPLE) <= 20, \
        f"the table has grown into a lexicon: {len(nl.ASK_IRREGULAR_PARTICIPLE)}"
    assert nl.participle_stem("opened") == "open"
    assert nl.participle_stem("bitten") == "bite"
    for untouched in ("green", "men", "ten", "door", "often"):
        assert nl.participle_stem(untouched) == untouched, untouched


def test_a_passive_ask_becomes_the_active_key_the_object_path_already_reads():
    v = nl.normalize_ask_variants("what was the door opened by?", SAYS)
    assert v == ["what open the door"], v   # a key, not a sentence: no mark, no mood
    # the variant is a LOOKUP KEY, not a sentence: bare stem, and the nouns are the ask's
    assert "door" in v[0] and "opened" not in v[0]
    assert ask("what was the door opened by?") is None, "answered without the flag"
    assert ask("what was the door opened by?", normalize=True) == "the boy opens the door"


def test_no_variant_for_a_verb_the_house_was_never_told():
    """`broken` stems to `break`, which no tell here uses. The normalizer must not answer
    with the nearest action it DOES know -- that is the confabulation this whole design
    exists to avoid, and it is stopped by the taught-verb gate, not by luck."""
    for q in ("what was the latch broken by?", "what was the ledger hidden by?",
              "who was the scarf lost by?"):
        assert nl.normalize_ask_variants(q, SAYS) == [], q
        assert ask(q, normalize=True) is None, q


def test_a_bare_verb_in_the_participle_slot_is_not_read_as_a_passive():
    assert nl.normalize_ask_variants("what was the door open by?", SAYS) == []
    assert ask("what was the door open by?", normalize=True) is None


def test_no_variant_for_a_row_that_is_not_an_ask_in_the_passive_shape():
    for q in ("the door was opened by Mira", "how was the door opened by?",
              "what is the door", "who opened the door?", ""):
        assert nl.normalize_ask_variants(q, SAYS) == [], q


# ------------------------------------------------------------------- copula participants

def test_a_copula_ask_reaches_the_tell_that_strands_the_same_participant():
    """`who is the lantern with?` and `who does the lantern belong to?` ask for the same
    person and the same tell answers both -- but only under the flag, and only because the
    tell itself strands a preposition the ask's `with` can mean."""
    for q in ("who is the lantern with?", "who is the lantern with"):
        assert ask(q) is None, q
        assert ask(q, normalize=True) == "the lantern belongs to Mira", q
        assert nl._electric_bind(q, SAYS, normalize=True) == ("agent", "lantern"), q


def test_a_tell_that_strands_nothing_answers_nothing():
    """The mouse's only agent fact is `the mouse chases the cat` -- no participant left
    stranded, so nothing can be the answer to `who is the mouse with?`. This is the row
    that a shared-stem guard could not protect: `mouse` is in both, and the wrong fact
    would fit the question's shape perfectly."""
    assert ask("who is the mouse with?", normalize=True) is None


def test_a_place_frame_is_not_a_participant():
    assert ask("who is the scarf with?", normalize=True) is None
    assert ask("who is the ledger with?", normalize=True) is None


def test_an_ask_about_something_else_is_refused_not_approximated():
    """A content word the bound subject does not account for means the ask is after
    something other than this tell's participant, so the guard declines even though the
    tell would answer a nearby question."""
    assert ask("who is the old lantern with?", normalize=True) is None
    assert ask("who is the lantern really with?", normalize=True) is None


def test_the_participant_guard_only_ever_returns_a_verbatim_tell():
    """The strongest cheap statement of no-confabulation: whatever the ask, whatever the
    flag, anything this path speaks is a sentence that was taught, byte for byte."""
    probes = [q for q, _w in ALL] + [
        "who is the door with?", "what is the latch on?", "who was the mouse chased by?",
        "what are the lanterns given by?", "who is the lantern from?",
        "what was the door opened?", "who was the lantern given to?"]
    for q in probes:
        got = ask(q, normalize=True)
        assert got is None or got in TELLS, f"invented a sentence: {q!r} -> {got!r}"


# ---------------------------------------------------------------------- the guarded paths

def test_the_licence_never_sees_the_normalizer():
    """E24's licence calls `_electric_bind` with the defaults, so the set of asks it may
    refuse -- and the measured wording -- cannot move. Asserted behaviourally AND at the
    call site, because a future edit that threads `normalize` through would otherwise be
    invisible until a refusal went missing."""
    assert nl._electric_bind("who is the lantern with?", SAYS) is None
    assert nl._electric_bind("who is the lantern with?", SAYS, normalize=True) == \
        ("agent", "lantern")
    src = inspect.getsource(nl._absence_licence)
    assert "normalize" not in src, src
    # ...and the licence's own bind call stays on defaults.
    assert "_electric_bind(question, inventory)" in src, src


def test_measured_refusals_stay_refusals_under_the_flag():
    """These two bind to NOTHING either way, which is what keeps the licence in charge of
    them: `what is the scarf like?` is the property ask E24 refuses in words, and
    `what was the ledger hidden by?` is an action nobody taught."""
    for q in ("what is the scarf like?", "what was the ledger hidden by?"):
        assert ask(q) is None, q
        assert ask(q, normalize=True) is None, q


def test_inert_without_the_flag_over_the_whole_object_role_table():
    """Every ask the previous arms measured must bind, match and answer identically when
    the switch is off -- including the explicit-default call, so the flag cannot be
    silently re-defaulted to True."""
    for q, _w in ALL:
        plain = nl._electric_answer(q, SAYS, reverse=True, object_role=True)
        off = nl._electric_answer(q, SAYS, reverse=True, object_role=True,
                                  normalize=False)
        assert plain == off, (q, plain, off)
        got = ask(q)
        assert got is None or got in TELLS, (q, got)


def test_the_flag_recovers_and_never_subtracts():
    """Set relation: recovery is a superset. Any ask that answered before answers the same
    tell after -- the normalizer runs last and only when nothing was found."""
    for q, _w in ALL:
        off = ask(q)
        on = ask(q, normalize=True)
        if off is not None:
            assert on == off, f"the flag changed an answer: {q!r} {off!r} -> {on!r}"


# ---------------------------------------------------------------------------- wiring

def test_serve_wires_the_switch_inside_the_electric_block():
    s = io.open("tools/serve.py", encoding="utf-8").read()
    assert '"--electric-ask-normalize"' in s
    assign = s.index("lang.ELECTRIC_ASK_NORMALIZE = bool(args.electric_ask_normalize)")
    block = s.index("    if args.electric:")
    assert block < assign, "must be read inside --electric, like reverse and object-role"
    assert "normalize=self.ELECTRIC_ASK_NORMALIZE" in \
        io.open("organs/neural_language.py", encoding="utf-8").read()


def test_the_switch_defaults_off_on_the_class_and_the_organ():
    assert nl.NeuralLanguage.ELECTRIC_ASK_NORMALIZE is False
    o = nl.NeuralLanguage.__new__(nl.NeuralLanguage)
    assert o.ELECTRIC_ASK_NORMALIZE is False
