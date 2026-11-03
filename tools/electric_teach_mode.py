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

What it is NOT.  It is not "everything ELECTRIC" -- that is ``--electric-learn``, the FULL
teach/learn mode, this same stack plus the seven widenings below, and it is a different flag
because it has a different blast radius.  ``enable_learn`` exists so the two modes cannot drift
into two lists in two wiring sites, and so the mode that reaches more can still be named exactly.

Seven switches stay out of the NARROW mode because each one is a WIDENING -- it lets more asks
reach more matchers, and each was measured separately precisely so a run could say which one
cost something:

    ELECTRIC_ASK_SHAPE      tags unmarked interrogatives and book questions whose mark did not
                            survive, so it drops rows that marks alone would have left in place.
                            It is a widening of admissibility, not a part of it.
    ELECTRIC_REVERSE        a miss on a reverse-role ask can return the wrong fact about the
                            right noun instead of nothing.
    ELECTRIC_OBJECT_ROLE    a third matcher, added because reverse did not cover the shape and
                            the subject path mis-bound it.
    ELECTRIC_ASK_NORMALIZE  changes which asks reach which INVENTORY matchers.
    ELECTRIC_ASK_DO_SUPPORT  the same widening one word narrower: it folds an object ask that
                            dropped its auxiliary onto the do-support form the object-role path
                            already answers, and it is inert unless ASK_NORMALIZE is on, because
                            the variant is generated inside that block.
    ELECTRIC_QA_ANSWER_MEMORY  reaches the STORE instead of the matchers: a pair the role
                            arithmetic refuses is kept as a memory, verbatim and with its
                            provenance, and casts no grammar vote.
    ELECTRIC_ARBITER_TELL reaches the MOUTH instead of the matchers: where the shape arbiter
                            verified a memory and named its answering word, that memory is said
                            whole -- but only when it adds no word the ask did not name, so the
                            modifier leak the head-only branch exists to stop stays stopped.

ELECTRIC_ASK_NORMALIZE needs a word, because it looks like an omission: ELECTRIC_QA_PARAPHRASE calls
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
     "output, where the seven switches left out widen what is reachable"),
    ("ELECTRIC_ASK_SHAPE_STORE", "electric_ask_shape_store",
     "a tell whose SHAPE is an ask is not filed as a taught fact. `_taught_says` is read before "
     "every other store, so a question the house could not classify used to answer itself here; "
     "the row-side switches above cannot reach it, because they govern rows and this is a "
     "different store. In the stack for the same reason as the fragment guard -- it can only "
     "ever refuse to write, and the seven switches left out widen what is reachable"),
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
    ("ELECTRIC_ASK_DO_SUPPORT", "electric_ask_do_support",
     "an object ask whose auxiliary is missing (`what the dog bite`) is tried in the do-support "
     "form the object-role path already answers (`what does the dog bite`). One inserted word, "
     "and only when a tell this house was TOLD carries that noun as its subject and that verb as "
     "its action. Measured: 17 of 21 asks WITH the auxiliary answer, 0 of 21 without it -- the "
     "largest single mechanism in the QA gap. Inert without --electric-ask-normalize, whose "
     "block generates it"),
    ("ELECTRIC_QA_ANSWER_MEMORY", "electric_qa_answer_memory",
     "a question-answer pair the ROLE arithmetic refuses is still kept as a MEMORY, with its "
     "provenance and its verbatim answer, and it casts no grammar vote. The arithmetic admits a "
     "pair only when the answer differs from the ask by exactly one word on each side, which is "
     "the right rule for learning what `what` asks about and the wrong rule for remembering a "
     "lesson: measured on 16 pairs taught in conversation, 10 reached the store and the 3 whose "
     "answer sentence exists nowhere else in the house reached it ZERO times -- an answer that "
     "says something new was unteachable by construction. Bounds: a conversation pair the person "
     "marked with `?`, the shared admissibility test, an answer that adds at least one word, and "
     "one content word in common. Inert without --electric-qa-store"),
    ("ELECTRIC_ARBITER_TELL", "electric_arbiter_tell",
     "when the shape arbiter verified a memory and NAMED the word that answers the ask, say that "
     "memory whole instead of the word it named. The head-only branch is deliberate -- reading a "
     "row out loud speaks its modifiers too, which is how `what turns twice?` tripped its own "
     "forbid on `copper` -- and that reason is kept: it fires only when the row adds no word the "
     "ask did not already name except the answering word itself. Measured: of the 8 "
     "`fallback_fragment` probes left in learn mode at depth 3, SEVEN are this branch, and in "
     "seven of seven the row the arbiter chose IS the tell the person taught, word for word. "
     "Bounds: the row was said to him (`who == you`), it is not itself an asking, the named word "
     "is in it, and every content word of it is in the ask or is that word. No parent switch -- "
     "it lives inside the branch the shape arbiter already gates"),
)

# MP-E9 TREATMENT ARMS. Deliberately NOT in BASE, which is the deviation from
# experiments/MP-E9/organs_precondition.md section 3, recorded here rather than left in a prose
# note: that document says to add both to BASE so the learn arm gets them and control does not,
# and the second half is what matters -- but BASE is what every bench run and every generation
# applies by default, and `second_brain_on()` states the house rule for that: "an unvalidated
# mechanism does not get to be the default until the gate has been measured". These two have not
# been measured yet; measuring them IS B.2. So they are opt-in per run (--flag-on in the bench),
# they are in ALL_ATTRS so state()/warnings() report them, and the arm that turns them on is the
# one that has to say so in its own provenance.
CANDIDATE = (
    ("ELECTRIC_ARBITER_HEAD_BOUND", "electric-arbiter-head-bound",
     "bound the HEAD branch, which never had one: when the shape arbiter verifies a memory and "
     "the tell path refuses to speak it whole, the branch still speaks the single word it named. "
     "The bound is one predicate -- the row must be something he was told (who == 'you') -- and "
     "NOT a re-application of _arbiter_tell, whose five other refusal reasons would take the "
     "whole arbiter-head population with them. Registered against H1/H2 as P1."),
    ("ELECTRIC_QA_MORPH_NORMALIZE", "electric-qa-morph-normalize",
     "fold the store's keys through stem(), so `when does the bell toll?` reaches a pair stored "
     "under an inflected form. Measured with this project's own stemmer: tolls/tolling/tolled "
     "fold to toll while says stays says and said stays said, which is why the six kin answer and "
     "toll alone does not. Re-keys the store at RESTORE as well as at write, because qa_store "
     "survives restart and a pre-flag record left under its old key fails silently -- silence is "
     "indistinguishable from an empty memory. Registered against H3/C4 as P2. Inert without "
     "--electric-qa-store"),
)

# A flag whose parent is off is INERT, not merely weaker: the user has to be told, because the
# symptom of an inert flag is that nothing happens and nothing is said. Text kept here rather
# than in the wiring sites so serve.py and electric_chat.py report the same fact in the same
# words.
DEPENDS_ON = {
    "ELECTRIC_QA_MORPH_NORMALIZE": ("ELECTRIC_QA_STORE",
                                    "--electric-qa-morph-normalize without --electric-qa-store: "
                                    "there is no store to key, so nothing is folded, nothing is "
                                    "re-read and nothing changes anyone can hear. The restore "
                                    "path still runs, which is why this is reported rather than "
                                    "assumed away."),
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
    "ELECTRIC_ASK_DO_SUPPORT": ("ELECTRIC_ASK_NORMALIZE",
                                "--electric-ask-do-support without --electric-ask-normalize: the "
                                "do-support variant is generated inside the normalizer's own "
                                "block, so with the parent off nothing computes it and the ask "
                                "refuses exactly as it did before this flag existed."),
    "ELECTRIC_QA_ANSWER_MEMORY": ("ELECTRIC_QA_STORE",
                                  "--electric-qa-answer-memory without --electric-qa-store: the "
                                  "pair passes every bound and then has nowhere to be kept, so "
                                  "nothing is remembered and nothing changes (and the "
                                  "conversation route needs --electric-qa-elicit to deliver a "
                                  "MARKED ask at all, which is bound 2 of the five)."),
    "ELECTRIC_ASK_SHAPE_STORE": ("ELECTRIC_TEACH",
                                 "--electric-ask-shape-store without --electric: nothing is "
                                 "filed as a taught fact in the first place, so there is no "
                                 "write here for the guard to refuse."),
}

STACK_ATTRS = tuple(attr for attr, _cli, _why in STACK)
BASE_ATTRS = tuple(attr for attr, _cli, _why in BASE)
EXCLUDED_ATTRS = tuple(attr for attr, _cli, _why in EXCLUDED)
LEARN_ATTRS = STACK_ATTRS + EXCLUDED_ATTRS
CANDIDATE_ATTRS = tuple(attr for attr, _cli, _why in CANDIDATE)
# CANDIDATE_ATTRS is in ALL_ATTRS so state() reports a treatment flag's state instead of
# silently omitting it, and is in NO enable*() so nothing turns it on by accident.
ALL_ATTRS = STACK_ATTRS + BASE_ATTRS + EXCLUDED_ATTRS + CANDIDATE_ATTRS


# What the FULL teach/learn mode adds on top of the stack: the seven widenings the narrow mode
# leaves off, each measured alone (docs/STATE.md: ELECTRIC_ASK_SHAPE, ELECTRIC_REVERSE,
# ELECTRIC_OBJECT_ROLE, ELECTRIC_ASK_NORMALIZE, ELECTRIC_ASK_DO_SUPPORT,
# ELECTRIC_QA_ANSWER_MEMORY, ELECTRIC_ARBITER_TELL).
#
# Six of the seven change WHICH ASK REACHES WHICH MATCHER, and none of those six changes what a
# matcher says about an ask it already reaches. The seventh is a different kind of widening and
# has to be described as one: ELECTRIC_ARBITER_TELL changes what the MOUTH says about a memory
# the shape arbiter has already verified. It belongs here rather than in the stack because it is
# a widening, not a narrowing -- it lets out a sentence that was previously not spoken -- and its
# bound is exactly the modifier leak the short branch was written to stop.
#
# Read the two halves together and the mode's shape is honest: the stack can only ever refuse
# (a row dropped, a fragment unspoken, a write declined), while these seven can only ever
# REACH MORE -- more rows counted as an asking, more asks matched against the inventory, more
# phrasings folded onto one key, one more sentence spoken. That is why they were never in
# `--electric-teach`, and why this mode is a different flag rather than a wider default: a
# widening that is right on the object arm's table is not thereby right on the corpus, and the
# only claim made here is that the COMBINATION is the combination that was measured, one switch
# at a time.
#
# What the mode still does NOT do, and this is the safety property a single flag has to
# preserve: every attribute is set on the INSTANCE, never on `NeuralLanguage`, so the graded
# contract -- `_absence_licence` bound on the class defaults, `ABSENCE_INVENTORY` defaulting on,
# `_electric_answer` reached only under ELECTRIC_TEACH -- is untouched by construction. The
# battery path never sees a learn-mode organ.
LEARN = STACK + EXCLUDED


def _set(lang, attrs):
    """Set instance attributes, and refuse to pretend about a name the class does not have.

    `setattr` on an instance never raises for an unknown name -- it just creates one that no
    path reads. A mode that turns on eighteen switches must not be able to report eighteen on
    and behave like the eleven that are real, so the name is checked against the CLASS first and
    a missing one raises. This is the sentence `enable()`'s docstring used to claim was true.
    """
    missing = [attr for attr in attrs if not hasattr(type(lang), attr)]
    if missing:
        raise AttributeError(
            f"{type(lang).__name__} has no attribute {missing[0]!r}"
            + (f" (and {len(missing) - 1} more)" if len(missing) > 1 else "")
            + ": a flag the organ does not read is not a flag, it is a rumour")
    for attr in attrs:
        setattr(lang, attr, True)
    return list(attrs)


def enable(lang, base=True):
    """Turn the teachable stack on for THIS organ. Returns the attributes it set.

    ``base`` is on by default because the stack is useless without it: elicitation writes a
    pair into the store, and the store is only consulted on a path that is answering. Pass
    False only to measure the difference.
    """
    return _set(lang, STACK_ATTRS + (BASE_ATTRS if base else ()))


def enable_learn(lang, base=True):
    """Turn the FULL teach/learn mode on for THIS organ: the stack plus the seven widenings.

    Returns the attributes it set. Same instance-only discipline as ``enable``; the difference
    is blast radius, and it is the user's, made by one explicit flag.
    """
    return _set(lang, LEARN_ATTRS + (BASE_ATTRS if base else ()))


def enable_candidate(lang, attrs=None, on=True):
    """Turn MP-E9 treatment arms on or off for THIS organ, and say which were touched.

    Not wired into enable()/enable_learn(): a treatment flag is turned on by the run that is
    measuring it, and the run has to record that it did. Returns the resulting state of every
    candidate flag, which is what a bench artifact writes into provenance.electric_flags -- the
    A/B is only evidence if the artifact says which arm it is, rather than being identified by the
    filename somebody gave it.
    """
    for attr in (attrs or CANDIDATE_ATTRS):
        setattr(lang, attr, bool(on))
    return {attr: bool(getattr(lang, attr, False)) for attr in CANDIDATE_ATTRS}


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


def describe_learn():
    """The full mode, one line each: the stack, then the seven widenings marked as such.

    A terminal that turns on eighteen switches should say which seven of them reach more, in the
    same words, rather than leaving that in a docstring nobody opens at 2 a.m.
    """
    return ([f"{attr:<26} {why}" for attr, _cli, why in STACK]
            + [f"WIDENS {attr:<20} {why}" for attr, _cli, why in EXCLUDED])
