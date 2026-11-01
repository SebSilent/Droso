"""ELECTRIC object-role asks: the ask that names a tell's OBJECT and wants its SUBJECT.

C4d measured the boundary of --electric-reverse: `what bites the latch?` stays a miss with
that flag ON, because that shape has no preposition to strand -- and worse than a miss,
`_electric_bind` returns ('agent','latch') and the tell under that key is
`the latch holds the door`, the wrong fact about the right noun, stopped only by the verb
guard. This arm covers exactly that shape, behind its own flag.

These tests are deliberately adversarial about the ONE thing that could make this feature
dangerous: answering a role-clipped ask with a real but different fact.
"""

import io
import re

import organs.neural_language as nl

S = {
    "frost": {"agent": "the frost bites the latch"},
    "latch": {"agent": "the latch holds the door"},
    "mouse": {"agent": "the mouse chases the cat"},
    "lantern": {"agent": "the lantern belongs to Mira"},
    "scarf": {"place": "the scarf is on the hook"},
}


# --------------------------------------------------------------- the target shape

def test_the_object_role_ask_reaches_its_tell():
    got = nl._electric_answer("what bites the latch?", S, object_role=True)
    assert got == "the frost bites the latch", \
        f"must return the tell whose OBJECT was named, got {got!r}"


def test_the_answer_is_the_verbatim_tell_not_a_composed_sentence():
    """Nothing here regenerates a sentence: a composed one could invent a preposition,
    and `the frost bites the latch` is exactly what was taught."""
    assert nl._electric_answer("what bites the latch?", S, object_role=True) \
        == S["frost"]["agent"]


def test_without_the_flag_the_same_ask_is_still_a_miss():
    assert nl._electric_answer("what bites the latch?", S) is None, \
        "object-role binding leaked into the default path"


def test_the_flag_is_off_on_the_class():
    assert nl.NeuralLanguage.ELECTRIC_OBJECT_ROLE is False, \
        "an experimental read path must not default on"


# ------------------------------------------------------- the safety cases, one each

def test_an_unstranded_who_ask_stays_silent_even_with_object_role():
    """`who does the mouse chase?` wants the CHASER. The tell about chasing is keyed
    under the chaser, so answering it is the wrong fact about the right noun. The
    do-support in the ask is the only signal, and it must be enough."""
    assert nl._electric_answer("who does the mouse chase?", S, object_role=True) is None


def test_a_do_support_ask_never_reaches_the_object_path():
    """`what does the latch bite?` asks for the OBJECT; the forward key serves that. If
    the object path also answered it, one question could get two different facts."""
    assert nl._electric_object_answer("what does the latch bite?", S) is None
    assert nl._electric_object_answer("what did the latch bite?", S) is None


def test_a_tell_that_makes_the_asks_noun_its_subject_is_skipped():
    """`what holds the door?` -- `door` is the OBJECT of the latch tell, so that tell
    answers it, and the ask's noun never appears as a subject. Correct, and pinned."""
    assert nl._electric_object_answer("what holds the door?", S) == "the latch holds the door"
    # The clash rule itself, exercised directly: a reflexive tell is the only shape where
    # one noun is BOTH the subject and the object of the same verb, so it isolates the
    # guard from every other reason to stay silent. Artificial tell, real rule: a tell
    # that makes the ask's noun the DOER must not answer an ask that treats it as the DONEE.
    clash = {"mouse": {"agent": "the mouse chases the mouse"}}
    assert nl._electric_object_answer("what chases the mouse?", clash) is None, \
        "role clash must be silence, not the doer's own tell"


def test_two_taught_tells_that_both_match_is_silence_never_a_pick():
    """The inventory can hold `the frost bites the latch` and `the dog bites the latch`.
    Then `what bites the latch?` is ambiguous and NOTHING is said -- no ranking, no
    first-key-wins, no tie-break. Ambiguity is the failure this feature would most
    plausibly get wrong, because both candidates are true facts."""
    two = {"frost": {"agent": "the frost bites the latch"},
           "dog": {"agent": "the dog bites the latch"},
           "latch": {"agent": "the latch holds the door"}}
    assert nl._electric_object_answer("what bites the latch?", two) is None, \
        "an ambiguous object-role ask must be silence"
    one = {"dog": {"agent": "the dog bites the latch"},
           "latch": {"agent": "the latch holds the door"}}
    assert nl._electric_object_answer("what bites the latch?", one) == "the dog bites the latch"


def test_a_verb_that_is_not_the_taught_verb_is_silence():
    assert nl._electric_object_answer("what bites the door?", S) is None
    assert nl._electric_object_answer("what breaks the latch?", S) is None


def test_the_subject_path_wins_when_it_answers_at_all():
    """ORDER IS THE SAFETY. `what holds the latch?` is answered by the SUBJECT path with
    `the latch holds the door` -- which is arguably the wrong fact for that ask (it wants
    the holder of the latch), but it is the PRE-EXISTING measured behaviour, unchanged by
    this feature. Pinned so that any future re-ordering of the two paths is a deliberate
    act with its own arm, not an accident of where a fallback was inserted."""
    for orole in (False, True):
        assert nl._electric_answer("what holds the latch?", S, object_role=orole) \
            == "the latch holds the door", \
            "the object-role path must not override the subject path"


def test_a_place_ask_is_untouched():
    assert nl._electric_answer("where is the scarf?", S, object_role=True) \
        == "the scarf is on the hook"


# ------------------------------------------------------------- serve wiring

def test_serve_exposes_the_object_role_flag_and_leaves_it_off():
    s = io.open("tools/serve.py", encoding="utf-8").read()
    assert "--electric-object-role" in s
    # The enable must be CONDITIONAL on the switch, exactly like its sibling: serve.py
    # sets `= bool(args.<flag>)` inside the `if args.electric:` block. A bare `= True`
    # anywhere would put an experimental read path on the live demo by default, and an
    # assignment outside that block would make it live without --electric at all.
    assert "lang.ELECTRIC_OBJECT_ROLE = bool(args.electric_object_role)" in s
    assert "ELECTRIC_OBJECT_ROLE = True" not in s, "unconditional enable"
    assign = s.index("lang.ELECTRIC_OBJECT_ROLE = bool(args.electric_object_role)")
    opens = s[:assign].rindex("    if args.electric:")
    assert s[opens:assign].count("def ") == 0, \
        "the object-role enable escaped the --electric block"
    # and the argparse default must be store_true, not a default of True
    m = re.search(r"--electric-object-role[^\n]*", s)
    assert m and "action=\"store_true\"" in s[m.start():m.start() + 200]
