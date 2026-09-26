"""Concept and subject vocabularies — the keys a fact is filed under.

THE ONE THING THIS MODULE EXISTS TO PREVENT. `(concept=surface_area, subject=cylinder)`
must return NOTHING, not the sphere formula. Word overlap cannot give you that: the two
tasks share "surface" and "area", so any similarity heuristic hands over the sphere fact
and the gate then rejects a formula that was never right. A fact is only useful if asking
for the wrong subject is a MISS, and the only way to get a miss is to have a fixed key
rather than a similarity score.

So this is a controlled vocabulary, not text matching. A concept and a subject are the
names of things that exist in a small closed list, and if either cannot be identified from
the task the answer is (None, None) — and a task with no key produces no fact. Inventing a
key by guessing is exactly the over-generalisation this file is here to stop.

Deliberately small and legible. Every entry is a thing whose formula could plausibly be
supplied by an oracle and reused by a differently-worded task about the same thing, which
is the only reason to file it at all.
"""
from __future__ import annotations

import re

# canonical concept -> phrases that mean it. Matched on word boundaries, longest phrase
# first, so "surface area" wins over "area" rather than the other way round.
# QUALIFIED CONCEPTS COME FIRST AND ARE LONGER, because the match is longest-phrase-wins
# and a fact filed under bare "sum" WILL be offered to "sum of squares". That is the
# measurement that showed transfer at zero three times running from three directions: a
# transfer test, the harness reporting system1_fact at 0, and a population merge carrying
# 2 of 8. The qualifier is the entire difference between two tasks that share a subject and
# share no formula, so it has to be part of the key rather than inferred later.
CONCEPTS = (
    ("sum_of_squares", ("sum of the squares", "sum of squares", "sum of square")),
    ("sum_of_distinct", ("sum of non repeated", "sum of non-repeated", "sum of distinct",
                         "sum of unique", "non repeated element", "non-repeated element")),
    ("sum_of_lengths", ("sum the length", "sum of the lengths", "sum of length",
                        "total length")),
    ("sum_of_digits", ("sum of the digits", "sum of digits", "digit sum")),
    ("elementwise_sum", ("element wise", "elementwise", "element-wise", "element by element",
                         "each corresponding")),
    ("elementwise_difference", ("element wise difference", "subtract the elements",
                                "difference between the elements")),
    ("interleave", ("interleave", "interleaving")),
    ("flatten", ("flatten", "flattening", "nested lists")),
    ("surface_area", ("surface area", "surfacearea", "surface-area")),
    ("circumference", ("circumference", "perimeter of a circle", "perimeter of the circle")),
    ("volume", ("volume",)),
    ("area", ("area",)),
    ("angle", ("angle", "argument", "phase")),
    ("divisor_sum", ("sum of the divisors", "sum of divisors", "divisor sum", "aliquot")),
    ("square_root", ("square root", "squareroot", "sqrt")),
    ("gcd", ("gcd", "greatest common divisor", "greatest common factor",
             "highest common factor")),
    ("frequency", ("frequency", "how many times each", "tally")),
    ("factorial", ("factorial",)),
    ("prime", ("prime", "non-prime", "nonprime")),
    ("average", ("average", "mean", "arithmetic mean")),
    ("product", ("product", "multiplied", "multiply all")),
    ("count", ("count", "how many", "number of times", "occurrences", "occurrence")),
    ("maximum", ("largest", "maximum", "greatest", "biggest")),
    ("minimum", ("smallest", "minimum", "least")),
    ("sum", ("sum", "total", "add up", "adds up", "summation")),
    ("reverse", ("reverse", "reversed", "backward", "backwards")),
    ("sort", ("sort", "sorted", "ascending", "descending", "in order")),
    ("unique", ("unique", "distinct", "duplicates", "deduplicate")),
    ("power", ("power", "exponent", "raised to the")),
    ("length", ("length",)),
)

# canonical subject -> phrases. The subject is what the fact is ABOUT, and it is the slot
# that must not be guessed loosely: a sphere and a cylinder share a concept and share no
# formula.
# (canonical, phrases, priority). Priority breaks ties AFTER phrase length: a container or
# a solid is a more specific statement of what a fact is about than the bare word "number"
# appearing somewhere in the sentence, and "count the occurrences in a list" keyed to
# (count, number) would collide with every count question about anything.
SUBJECTS = (
    ("sphere", ("sphere", "ball"), 3),
    ("cylinder", ("cylinder",), 3),
    ("cone", ("cone",), 3),
    ("cube", ("cube",), 3),
    ("cuboid", ("cuboid", "rectangular box"), 3),
    ("circle", ("circle", "circular"), 3),
    ("triangle", ("triangle", "triangular"), 3),
    ("rectangle", ("rectangle", "rectangular"), 3),
    ("complex_number", ("complex number", "complex"), 3),
    ("dictionary", ("dictionary", "dict", "hash"), 3),
    ("matrix", ("matrix", "matrices"), 3),
    ("tuple", ("tuple",), 3),
    ("list", ("list", "lists", "array", "arrays"), 3),
    ("string", ("string", "strings", "text"), 3),
    ("character", ("character", "characters", "letter", "letters"), 2),
    ("integer", ("integer", "integers"), 1),
    ("number", ("number", "numbers", "numeric"), 1),
)

# The solids, for the one disambiguation that matters most in this corpus: for a 3D solid,
# "area" MEANS surface area. Without this, a task worded "the area of a ball" keys to
# (area, sphere) and misses the fact filed under (surface_area, sphere) -- which is the
# exact reworded case the design is supposed to handle, so leaving it out would make the
# first acceptance test fail for a reason that has nothing to do with retrieval.
SOLIDS = ("sphere", "cylinder", "cone", "cube", "cuboid")

_WORD = re.compile(r"[a-z0-9]+")


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, pad with spaces.

    Punctuation is replaced by SPACES rather than kept. Matching is done on " word "
    boundaries, and a task that ends "...surface area of a sphere." has "sphere." in it,
    so a straight substring test for " sphere " fails on the most ordinary sentence there
    is. That bug read as "no subject could be identified" and would have silently filed
    nothing, forever, while looking like the vocabulary was simply too small.
    """
    t = str(text or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " " + " ".join(t.split()) + " "


def _best(table, text: str):
    """Best canonical match: longest phrase wins, then priority, then table order."""
    # PRIORITY FIRST, length only to break ties. Length-first picked "number" (6 letters)
    # over "list" (priority 3) for "count the occurrences of an element in a list", which
    # files a list fact under the word "number" and collides it with every other count
    # question in the corpus. What a fact is about is the container, not the noun that
    # happens to be longest.
    best, best_key = None, (0, 0)
    for row in table:
        canonical, phrases = row[0], row[1]
        prio = row[2] if len(row) > 2 else 0
        for phrase in phrases:
            for form in (phrase, phrase + "s"):
                p = " " + re.sub(r"[^a-z0-9]+", " ", form.strip().lower()).strip() + " "
                if p in text:
                    key = (prio, len(phrase))
                    if key > best_key:
                        best, best_key = canonical, key
    return best


def extract_concept_subject(task: str, extra: str = ""):
    """(concept, subject) for a task, or (None, None) if either is not identifiable.

    `extra` is the task's assertions, used only as additional text to look in — a task
    often names the thing it is about in its check rather than its prose.
    """
    text = normalise(task) + normalise(extra)
    concept = _best(CONCEPTS, text)
    subject = _best(SUBJECTS, text)
    if concept == "area" and subject in SOLIDS:
        concept = "surface_area"
    return concept, subject


def is_keyable(task: str, extra: str = "") -> bool:
    c, s = extract_concept_subject(task, extra)
    return bool(c) and bool(s)

# ---------------------------------------------------------------- the third key
_SHAPE_RX = None


def answer_shape(check: str) -> str:
    """What the assertions expect the answer to BE: int, str, list, dict, bool, ...

    THE THIRD COMPONENT, AND IT WAS IN THE ASSERTIONS ALL ALONG. The (concept, subject)
    pair is a TOPIC, and a topic is not a formula: "reverse words separated by spaces" and
    "count the pairs of reverse strings" both key to (reverse, string), and the first
    returns a rearranged string while the second returns a number. Measured, not guessed --
    the fact was filed, recall_fact found it, offered it to the sibling, and the sibling's
    own assertions rejected it, because no arrangement of two tasks that differ this way can
    share an answer.

    So the key gains the shape of the RESULT. It is read off the assertions rather than
    inferred, which is the only place it is stated unambiguously: `x == 2` and `x == "ab"`
    are not the same kind of claim, and the check is what the whole system already trusts to
    decide everything else.
    """
    import ast as _ast
    import re as _re
    kinds = set()
    for line in str(check or "").splitlines():
        line = line.strip()
        m = _re.match(r"^assert\s+(.+?)\s*==\s*(.+)$", line)
        if not m:
            # Not every check uses ==. math.isclose(got, WANT, rel_tol=...) is how the
            # geometry tasks are written, and missing it left exactly the tasks this whole
            # line of work is about reading as "unknown" -- the shape was there, in the
            # second argument, and the parser was not looking at it.
            m2 = _re.match(r"^assert\s+[\w.]*isclose\(\s*(?:[^,]+),\s*([^,)]+)", line)
            if m2:
                kinds.add("float")
            continue
        rhs = m.group(2).strip().rstrip(")")
        if rhs.endswith(",") or rhs.startswith("("):
            rhs = rhs.rstrip(",")
        try:
            node = _ast.parse(rhs, mode="eval").body
        except SyntaxError:
            kinds.add("expr")
            continue
        if isinstance(node, _ast.Constant):
            v = node.value
            kinds.add("bool" if isinstance(v, bool) else
                      "int" if isinstance(v, int) else
                      "float" if isinstance(v, float) else
                      "str" if isinstance(v, str) else
                      "none" if v is None else "const")
        elif isinstance(node, _ast.List):
            kinds.add("list")
        elif isinstance(node, _ast.Dict):
            kinds.add("dict")
        elif isinstance(node, _ast.Set):
            kinds.add("set")
        elif isinstance(node, _ast.Tuple):
            kinds.add("tuple")
        elif isinstance(node, _ast.Call):
            fn = getattr(node.func, "attr", getattr(node.func, "id", ""))
            kinds.add({"set": "set", "sorted": "list", "len": "int", "list": "list",
                       "sum": "int", "isclose": "float"}.get(fn, "call"))
        else:
            kinds.add("expr")
    if not kinds:
        return "unknown"
    if len(kinds) == 1:
        return kinds.pop()
    # A check that compares against more than one kind is ambiguous, and saying so is
    # better than picking the first one -- an ambiguous key must not be filed on.
    return "mixed"


def extract_key(task: str, check: str = ""):
    """(concept, subject, shape) -- the full key a fact is filed under."""
    c, s = extract_concept_subject(task, check)
    return c, s, (answer_shape(check) if c and s else None)


def keyable(task: str, check: str = "") -> bool:
    """Unknown is allowed; MIXED is not.

    `unknown` means the shape could not be read, which leaves the key exactly as precise as
    (concept, subject) alone -- the status quo, not an error. `mixed` means the assertions
    compare against more than one kind of thing, and a key that cannot say what the answer
    is would merge two tasks that share no answer. That is the one case where filing would
    do harm, so it is the one case that is refused.
    """
    c, s, shape = extract_key(task, check)
    return bool(c) and bool(s) and shape != "mixed"
