# One-off: bound the veto's blast radius. For each cold ask with a parser
# shape, find every corpus memory that matches the shape (the exact matcher
# the implementation will use) and check whether it contains a taught word --
# the script's told_words (expects' any_of + must_contain). A shape match
# without a taught word is a clean override (cold pass); one with a taught
# word would leak and fail; no match means the veto fires (silence, pass).
import json
import sys

sys.path.insert(0, ".")
from organs.stemming import stem  # noqa: E402

META = "state/language_state.json.cortex.meta.json"
with open(META, encoding="utf-8") as fh:
    meta = json.load(fh)

FUNCTION_WORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "by",
    "from", "up", "about", "into", "over", "after", "is", "are", "was",
    "were", "be", "been", "being", "am", "and", "or", "but", "nor", "so",
    "yet", "that", "this", "these", "those", "it", "its", "he", "she",
    "his", "her", "him", "they", "them", "their", "we", "us", "our", "you",
    "your", "i", "my", "me", "as", "than", "then", "there", "here", "not",
    "no", "yes", "do", "does", "did", "done", "doing", "have", "has", "had",
    "having", "will", "would", "shall", "should", "can", "could", "may",
    "might", "must", "very", "too", "also", "just", "now", "still", "even",
}
COPULAS = {"is", "are", "was", "were", "be", "been", "being", "am"}


def content(tokens):
    return [t for t in tokens if t.lower() not in FUNCTION_WORDS]


def match_subject_unknown(tokens, verb, tail):
    """who/what + VERB + tail: filler is content before the verb."""
    stems = [stem(t) for t in tokens]
    vs = stem(verb)
    vi = [i for i, s in enumerate(stems) if s == vs]
    if not vi:
        return None
    vi = vi[0]
    before = content(tokens[:vi])
    if not before:
        return None
    pos = vi + 1
    for t in tail:
        ts = stem(t)
        nxt = [i for i, s in enumerate(stems[pos:], start=pos) if s == ts]
        if not nxt:
            return None
        pos = nxt[0] + 1
    return before[0]


def match_object_unknown(tokens, subject, verb, tail):
    """who/what + does + SUBJECT + VERB: filler is content after the verb."""
    stems = [stem(t) for t in tokens]
    vs = stem(verb)
    vi = [i for i, s in enumerate(stems) if s == vs]
    if not vi:
        return None
    vi = vi[0]
    for t in subject:
        si = [i for i, s in enumerate(stems[:vi]) if s == stem(t)]
        if not si:
            return None
    after = content(tokens[vi + 1:])
    if not after:
        return None
    pos = vi + 1
    for t in tail:
        ts = stem(t)
        nxt = [i for i, s in enumerate(stems[pos:], start=pos) if s == ts]
        if not nxt:
            return None
        pos = nxt[0] + 1
    return after[0]


def match_locative_unknown(tokens, copula, subject):
    """where + COPULA + subject: filler is last content after the copula."""
    stems = [stem(t) for t in tokens]
    cs = stem(copula)
    ci = [i for i, s in enumerate(stems) if s == cs]
    if not ci:
        return None
    ci = ci[0]
    for t in reversed(subject):
        si = [i for i, s in enumerate(stems[:ci]) if s == stem(t)]
        if not si:
            return None
    after = content(tokens[ci + 1:])
    if not after:
        return None
    return after[-1]


ASKS = [
    ("reference", "what rings at noon",
     ("subject_unknown", "rings", ["noon"]),
     ["kettle", "lantern"]),
    ("reference", "what shines at midnight",
     ("subject_unknown", "shines", ["midnight"]),
     ["kettle", "lantern"]),
    ("accumulation", "where is the box",
     ("locative_unknown", "is", ["box"]),
     ["shelf"]),
    ("role_chain", "who follows the sparrow",
     ("subject_unknown", "follows", ["sparrow"]),
     ["crow", "sparrow"]),
    ("role_chain", "who watches the crow",
     ("subject_unknown", "watches", ["crow"]),
     ["crow", "sparrow"]),
    ("session_context", "what shines at dawn",
     ("subject_unknown", "shines", ["dawn"]),
     ["kettle", "dawn"]),
    ("session_context", "what rings at noon",
     ("subject_unknown", "rings", ["noon"]),
     ["kettle", "dawn"]),
]

for script, ask, shape, taught in ASKS:
    kind = shape[0]
    matches = []
    for m in meta:
        toks = [t.lower() for t in m.get("tokens") or []]
        if kind == "subject_unknown":
            f = match_subject_unknown(toks, shape[1], shape[2])
        elif kind == "object_unknown":
            f = match_object_unknown(toks, shape[1], shape[2])
        else:
            f = match_locative_unknown(toks, shape[1], shape[2])
        if f is not None:
            leak = sorted(set(taught) & set(toks))
            matches.append((" ".join(toks), f, leak))
    leaks = [m for m in matches if m[2]]
    print(f"\n== {script} / {ask!r} [{kind}] taught={taught}")
    print(f"   shape matches in corpus: {len(matches)}"
          f"   leaking taught words: {len(leaks)}")
    for text, filler, leak in matches[:4]:
        print(f"     filler={filler!r} leak={leak} :: {text[:90]}")
    if len(matches) > 4:
        print(f"     ... +{len(matches) - 4} more")