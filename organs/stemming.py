"""One stemmer, because the same bug was found in three places.

Procedure retrieval, the procedural-memory mirror, and question answering each
compared a query against stored text using raw tokens, and each failed the same
way: a plural could not meet its singular, "holding" could not meet "holds", and a
question rephrased with a different inflection was refused outright. Each was
fixed separately as it was found, which is how there came to be three copies.

This is deliberately minimal -- the plural and the two commonest verbal suffixes,
and nothing else. A stemmer that over-folds is worse than one that under-folds,
because it makes two different tasks look alike and a wrong recall gets believed.
"class" must not become "clas".
"""
from __future__ import annotations

_SUFFIXES = ("ations", "ing", "ed")

# Words that carry no retrieval signal on the question side: function words, the
# request verbs that surround an ask, and the interrogatives, which are handled
# separately by the role machinery and must not also be treated as content.
#
# This is deliberately NOT the procedure store's stopword list. Those words are
# baked into 295 stored signatures, so changing them would orphan every procedure
# he knows; the two lists serve different lookups and are allowed to differ.
STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "should", "must", "write",
    "creat", "make", "code", "function", "please", "when", "then", "into",
    "from", "which", "what", "who", "where", "how", "why", "does", "tell",
    "about", "person", "people", "place",
})


def stem(word) -> str:
    """Fold inflection, and never fold a word into something that is not a word.

    The version this replaces stripped any trailing "s" unless the *base* ended in
    ss/us/is -- so it checked the wrong string and turned "class" into "clas",
    which is the one example its own docstring said must not happen. It also tried
    "es" before "s", so "places" became "plac" while "place" stayed "place" and the
    two could never meet, which is the whole purpose of stemming.

    Under-folding is safe and over-folding is not: two words that stem alike are
    believed to be the same word, and a wrong recall gets believed.
    """
    w = str(word or "").strip().lower()
    if len(w) <= 4:
        return w
    # class, focus, this -- the trailing s is part of the word
    if w.endswith(("ss", "us", "is")):
        return w
    for suf in ("ations", "ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) > 3:
            return w[:-len(suf)]
    if w.endswith("ies") and len(w) > 5:
        return w[:-3] + "y"                      # memories -> memory
    if w.endswith(("ches", "shes", "ses", "xes", "zes")) and len(w) > 5:
        return w[:-2]                            # watches -> watch
    if w.endswith("s"):
        return w[:-1]                            # places -> place, holds -> hold
    return w


def stems(words) -> set:
    """The distinctive stems of an iterable of words, stopwords removed."""
    return {stem(w) for w in words
            if str(w).strip().lower() not in STOPWORDS}
