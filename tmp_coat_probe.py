# One-off: what would a preposition-required locative matcher do to the cold
# "where is the coat" cell? List every corpus memory matching
# locative_unknown(is, [coat]) WITH a preposition after the copula, its
# filler, and whether it leaks a must_not word (hook/torn/wet).
import json
import sys

sys.path.insert(0, ".")
from organs.stemming import stem  # noqa: E402

META = "state/language_state.json.cortex.meta.json"
meta = json.load(open(META, encoding="utf-8"))

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
PREPS = {
    "in", "on", "at", "under", "over", "behind", "beside", "near", "by",
    "with", "among", "against", "beneath", "above", "below", "across",
    "through", "toward", "towards", "upon", "within", "inside", "outside",
    "off", "onto", "between", "beyond", "along", "around",
}
MUST_NOT = {"hook", "torn", "wet"}


def match_locative_prep(tokens, copula, subject):
    stems = [stem(t) for t in tokens]
    ci = [i for i, s in enumerate(stems) if s == stem(copula)]
    if not ci:
        return None
    ci = ci[0]
    for t in reversed(subject):
        if not [i for i, s in enumerate(stems[:ci]) if s == stem(t)]:
            return None
    tail = tokens[ci + 1:]
    if not any(t.lower() in PREPS for t in tail):
        return None
    after = [t for t in tail if t.lower() not in FUNCTION_WORDS]
    if not after:
        return None
    return after[-1]


matches = []
for m in meta:
    toks = [t.lower() for t in m.get("tokens") or []]
    f = match_locative_prep(toks, "is", ["coat"])
    if f is not None:
        leak = sorted(MUST_NOT & set(toks))
        matches.append((" ".join(toks), f, leak))
leaks = [m for m in matches if m[2]]
print(f"coat locative matches (prep required): {len(matches)}, "
      f"leaking must_not: {len(leaks)}")
for text, filler, leak in matches[:12]:
    print(f"  filler={filler!r} leak={leak} :: {text[:100]}")
if len(matches) > 12:
    print(f"  ... +{len(matches) - 12} more")