# One-off: unit-check the shape parser and arbiter without building the brain.
# The methods only touch class constants and stem(), so a bare instance works.
import sys

sys.path.insert(0, ".")
from organs.neural_language import NeuralLanguage  # noqa: E402

nl = object.__new__(NeuralLanguage)

CASES = [
    # (question tokens, expected shape or None)
    (["who", "follows", "the", "sparrow"],
     {"kind": "subject_unknown", "verb": "follows", "tail": ["sparrow"]}),
    (["what", "rings", "at", "noon"],
     {"kind": "subject_unknown", "verb": "rings", "tail": ["noon"]}),
    (["where", "is", "the", "box"],
     {"kind": "locative_unknown", "copula": "is", "subject": ["box"]}),
    (["where", "is", "the", "box", "kept"],
     {"kind": "locative_unknown", "copula": "is", "subject": ["box"]}),
    (["what", "does", "droso", "want"],
     {"kind": "object_unknown", "subject": ["droso"], "verb": "want",
      "tail": []}),
    (["what", "is", "the", "box"], None),
    (["who", "is", "droso"], None),
    (["who", "is", "the", "one", "holding", "the", "light"], None),
    (["how", "is", "the", "garden"], None),
    (["what", "is", "for", "dinner"], None),
    (["who", "feeds"], None),
    (["where", "does", "the", "box", "live"], None),
    (["what", "shines", "at", "dawn"],
     {"kind": "subject_unknown", "verb": "shines", "tail": ["dawn"]}),
]
ok = True
for q, want in CASES:
    got = nl._question_shape(q)
    tag = "ok " if got == want else "FAIL"
    if got != want:
        ok = False
    print(f"{tag} {q!r} -> {got}")

MATCHES = [
    # (shape, candidate tokens, expected filler or None)
    ({"kind": "subject_unknown", "verb": "follows", "tail": ["sparrow"]},
     ["the", "crow", "follows", "the", "sparrow"], "crow"),
    ({"kind": "subject_unknown", "verb": "follows", "tail": ["sparrow"]},
     ["answered", "the", "sparrow", "as", "she", "flew", "away", "now"],
     None),
    ({"kind": "subject_unknown", "verb": "follows", "tail": ["sparrow"]},
     ["the", "sparrow", "follows", "the", "crow"], None),
    ({"kind": "subject_unknown", "verb": "rings", "tail": ["noon"]},
     ["the", "kettle", "rings", "at", "noon"], "kettle"),
    ({"kind": "subject_unknown", "verb": "watches", "tail": ["crow"]},
     ["the", "sparrow", "watches", "the", "crow"], "sparrow"),
    ({"kind": "locative_unknown", "copula": "is", "subject": ["box"]},
     ["the", "box", "is", "on", "the", "shelf"], "shelf"),
    # A place is stated with a preposition after the copula; a state has none.
    ({"kind": "locative_unknown", "copula": "is", "subject": ["box"]},
     ["the", "box", "is", "heavy"], None),
    ({"kind": "locative_unknown", "copula": "is", "subject": ["box"]},
     ["the", "box", "is", "red"], None),
    ({"kind": "locative_unknown", "copula": "is", "subject": ["box"]},
     ["the", "box", "is", "kept", "in", "the", "pantry"], "pantry"),
    # Accepted limit: a preposition-less locative is refused too.
    ({"kind": "locative_unknown", "copula": "is", "subject": ["box"]},
     ["the", "box", "is", "downstairs"], None),
    ({"kind": "object_unknown", "subject": ["droso"], "verb": "want"},
     ["droso", "wants", "food"], "food"),
    ({"kind": "subject_unknown", "verb": "shines", "tail": ["dawn"]},
     ["the", "iron", "kettle", "shines", "at", "dawn"], "iron"),
]
for shape, toks, want in MATCHES:
    got = nl._shape_matches(shape, toks)
    tag = "ok " if got == want else "FAIL"
    if got != want:
        ok = False
    print(f"{tag} {toks} -> {got!r} (want {want!r})")

# Arbiter: agree / override / veto over a ranked pool.
pool = [{"tokens": ["answered", "the", "sparrow", "as", "she", "flew"]},
        {"tokens": ["the", "crow", "follows", "the", "sparrow"]}]
shape = {"kind": "subject_unknown", "verb": "follows", "tail": ["sparrow"]}
best, verdict, filler = nl._arbitrate_shape(shape, pool)
print("override case:", verdict, filler,
      "ok" if (verdict, filler) == ("override", "crow") else "FAIL")
if (verdict, filler) != ("override", "crow"):
    ok = False
best, verdict, filler = nl._arbitrate_shape(
    shape, [{"tokens": ["the", "crow", "follows", "the", "sparrow"]}])
print("agree case:", verdict,
      "ok" if verdict == "agree" else "FAIL")
if verdict != "agree":
    ok = False
best, verdict, filler = nl._arbitrate_shape(
    shape, [{"tokens": ["answered", "the", "sparrow", "as", "she", "flew"]}])
print("veto case:", verdict,
      "ok" if (verdict, best) == ("veto", None) else "FAIL")
if (verdict, best) != ("veto", None):
    ok = False

print("ALL OK" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)