"""ELECTRIC teach mode -- ONE switch for the stack that makes a QA pair teachable.

Why this exists.  Eight flags stand between "he remembers the pair a person gave him" and
"he can be talked into remembering one": the store, the elicitation that fills it from chat,
the fold that lets a second phrasing reach it, the provenance rule that decides which records
may be reached at all, the mark channel that records that a `?` was actually typed, the
admissibility rule that keeps a remembered question out of the recall hits, the fragment
guard that stops the house speaking a piece of the ask when nothing answered it, and the
shape guard at the store write that stops a question being filed as the fact that answers it.
Each was added on its own, with its own live measurement, and each help text says what it does
and what it does not do.  The cost of that honesty is that someone who only wants to teach him
something has to read eight help texts and get the DEPENDENCIES right, because three of them
are inert without another:

    --electric-qa-store --electric-qa-elicit --electric-qa-paraphrase
    --electric-qa-provenance --electric-ask-marks --electric-ask-admissibility
    --electric-fragment-guard --electric-ask-shape-store

plus the three that ``--electric`` already means (ELECTRIC_TEACH, ELECTRIC_ANSWER,
ABSENCE_INVENTORY), plus the restart half -- ``load_state()`` -- which serve.py runs only
inside its ``--electric`` block, so a server started with the QA flags and not ``--electric``
comes up amnesiac even though every pair was saved.

``--electric-teach`` is that whole list in one flag, defined ONCE here so tools/serve.py and
tools/electric_chat.py cannot grow two different ideas of what "teach mode" means.  Duplicating
a rule in two wiring sites is the failure this project keeps hitting; the store's admission test
is a function for exactly the same reason.

What it is NOT.  It is not "everything ELECTRIC".  Four switches stay out because each one is a
WIDENING -- it lets more asks reach more matchers, and each was measured separately precisely so
a run could say which one cost something:

    ELECTRIC_ASK_SHAPE      tags unmarked interrogatives and book questions whose mark did not
                            survive, so it drops rows that marks alone would have left in place.
                            It is a widening of admissibility, not a part of it.
    ELECTRIC_REVERSE        a miss on a reverse-role ask can return the wrong fact about the
                            right noun instead of nothing.
    ELECTRIC_OBJECT_ROLE    a third matcher, added because reverse did not cover the shape and
                            the subject path mis-bound it.
    ELECTRIC_ASK_NORMALIZE  changes which asks reach which INVENTORY matchers.

The last one needs a word, because it looks like an omission: ELECTRIC_QA_PARAPHRASE calls
``normalize_ask_variants`` itself, so a folded ask DOES use the normalizer under teach mode with
``--electric-ask-normalize`` off. That is not this flag being smuggled in. The two uses have
different blast radii: ELECTRIC_ASK_NORMALIZE lets a variant reach the keyed INVENTORY, where a
wrong variant returns a wrong fact; the fold uses a variant only as a LOOKUP KEY into the store,
where a wrong key returns nothing. The normalizer brings its own warrant in both cases -- it
emits a variant only when the stem it needs is a verb a taught tell actually carries.

And one flag in the stack now shares its detector with one flag left out, which needs saying
before it reads as a smuggling: ``ELECTRIC_ASK_SHAPE`` (out) and ``ELECTRIC_ASK_SHAPE_STORE``
(in) both call ``question_shape``. They are not one experiment. The first is a WIDENING on the
read side -- more rows count as an asking, so more rows get dropped from the evidence a vote
can see, which is why it stayed behind its own switch. The second is a NARROWING on the write
side of a store no row switch reaches: it declines to file one sentence as a taught fact, and
can only ever lose a lookup, never gain one. The stack has always held the narrowings (the
fragment guard is in it for exactly that reason) and none of the widenings.

Everything here is set on the INSTANCE, never on ``NeuralLanguage``.  A demo that flipped the
class defaults would leak into whatever battery run came after it in the same interpreter, and
"battery runs are ELECTRIC-free" would be a sentence about intent.
"""
from __future__ import annotations

# (organ attribute, CLI dest, what it buys -- and what it is inert without)
STACK = (
    ("ELECTRIC_QA_STORE", "electric_qa_store",
     "keeps the question/answer pairs that were accepted and then thrown away, tagged with "
     "their provenance, and answers an ask from them by EXACT key"),
    ("ELECTRIC_QA_ELICIT", "electric_qa_elicit",
     "a PERSON is a book: an utterance ending in `?` is held, and the next thing that same "
     "speaker says is offered as its answer. Needs the store to remember anything"),
    ("ELECTRIC_QA_PARAPHRASE", "electric_qa_paraphrase",
     "a pair taught in one phrasing answers in another, by folding the ask through the "
     "project's one stemmer. A child of elicitation, which is what routes such an ask at all"),
    ("ELECTRIC_QA_PROVENANCE", "electric_qa_provenance",
     "a pair's provenance governs the pair: a refused pair teaches nothing, and an unmarked ask "
     "may hit the store when its words are exactly a marked question he was taught"),
    ("ELECTRIC_ASK_MARKS", "electric_ask_marks",
     "carries the question marks a book actually printed down into the row, so a question is "
     "recognised as an asking. Consulted only under admissibility"),
    ("ELECTRIC_ASK_ADMISSIBILITY", "electric_ask_admissibility",
     "a question someone asked is dropped from the recall hits before the arbiter, so no read "
     "path can answer from a remembered question"),
    ("ELECTRIC_FRAGMENT_GUARD", "electric_fragment_guard",
     "when nothing answered the ask, do not let the house speak a fragment of the ask itself "
     "(measured: `to?`). In the stack because it can only ever refuse to speak: it narrows the "
     "output, where the four switches left out widen what is reachable"),
    ("ELECTRIC_ASK_SHAPE_STORE", "electric_ask_shape_store",
     "a tell whose SHAPE is an ask is not filed as a taught fact. `_taught_says` is read before "
     "every other store, so a question the house could not classify used to answer itself here; "
     "the row-side switches above cannot reach it, because they govern rows and this is a "
     "different store. In the stack for the same reason as the fragment guard -- it can only "
     "ever refuse to write, and the four switches left out widen what is reachable"),
)

# What `--electric` already means, and what the stack is pointless without: an untaught ask has
# to produce an ADMITTED ignorance, not silence, or the demo cannot show the difference between
# "I was never told" and "I have nothing to say".
BASE = (
    ("ELECTRIC_TEACH", "electric", "a statement heard in chat may be taught into the inventory"),
    ("ELECTRIC_ANSWER", "electric", "a question may be answered from it"),
    ("ABSENCE_INVENTORY", "electric", "licenses the admission of ignorance at all"),
)

# Deliberately NOT in the mode. Kept here so `enable()` can prove it set nothing else.
EXCLUDED = (
    ("ELECTRIC_ASK_SHAPE", "electric_ask_shape", "widens which rows count as an asking"),
    ("ELECTRIC_REVERSE", "electric_reverse", "widens which asks reach the inventory"),
    ("ELECTRIC_OBJECT_ROLE", "electric_object_role", "widens which asks reach the inventory"),
    ("ELECTRIC_ASK_NORMALIZE", "electric_ask_normalize",
     "widens which asks reach the inventory matchers (the fold uses the normalizer as a store "
     "lookup key only, which is a different blast radius -- see the module docstring)"),
)

# A flag whose parent is off is INERT, not merely weaker: the user has to be told, because the
# symptom of an inert flag is that nothing happens and nothing is said. Text kept here rather
# than in the wiring sites so serve.py and electric_chat.py report the same fact in the same
# words.
DEPENDS_ON = {
    "ELECTRIC_QA_ELICIT": ("ELECTRIC_QA_STORE",
                           "--electric-qa-elicit without --electric-qa-store: a paired question "
                           "is voted and forgotten. Nothing said in chat will be answerable "
                           "from it."),
    "ELECTRIC_QA_PARAPHRASE": ("ELECTRIC_QA_ELICIT",
                               "--electric-qa-paraphrase without --electric-qa-elicit: nothing "
                               "routes a rephrased ask to answer(), so a pair taught in one "
                               "phrasing stays reachable only in that phrasing."),
    "ELECTRIC_ASK_MARKS": ("ELECTRIC_ASK_ADMISSIBILITY",
                           "--electric-ask-marks without --electric-ask-admissibility: the mark "
                           "is written into the row and nothing reads it, so nothing changes "
                           "anyone can hear."),
    "ELECTRIC_ASK_SHAPE": ("ELECTRIC_ASK_ADMISSIBILITY",
                           "--electric-ask-shape without --electric-ask-admissibility: it can "
                           "tag rows, but nothing reads the tag, so which rows exist does not "
                           "change."),
    "ELECTRIC_ASK_SHAPE_STORE": ("ELECTRIC_TEACH",
                                 "--electric-ask-shape-store without --electric: nothing is "
                                 "filed as a taught fact in the first place, so there is no "
                                 "write here for the guard to refuse."),
}

STACK_ATTRS = tuple(attr for attr, _cli, _why in STACK)
BASE_ATTRS = tuple(attr for attr, _cli, _why in BASE)
EXCLUDED_ATTRS = tuple(attr for attr, _cli, _why in EXCLUDED)
ALL_ATTRS = STACK_ATTRS + BASE_ATTRS + EXCLUDED_ATTRS


def enable(lang, base=True):
    """Turn the teachable stack on for THIS organ. Returns the attributes it set.

    ``base`` is on by default because the stack is useless without it: elicitation writes a
    pair into the store, and the store is only consulted on a path that is answering. Pass
    False only to measure the difference.
    """
    set_attrs = list(STACK_ATTRS) + (list(BASE_ATTRS) if base else [])
    for attr in set_attrs:
        setattr(lang, attr, True)
    return set_attrs


def state(lang):
    """The boolean state of every flag this module knows about, read off the organ."""
    return {attr: bool(getattr(lang, attr, False)) for attr in ALL_ATTRS}


def unmet(on):
    """One line per flag whose parent is off -- inert, so the user must be told.

    Takes the dict from ``state()``, not an organ, so a test can hand it a combination no boot
    would produce.
    """
    out = []
    for attr, (parent, message) in DEPENDS_ON.items():
        if on.get(attr) and not on.get(parent):
            out.append(message)
    return out


def warnings(lang):
    return unmet(state(lang))


def describe():
    """The stack, one line each, for whoever is staring at a terminal."""
    return [f"{attr:<26} {why}" for attr, _cli, why in STACK]
