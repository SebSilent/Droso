"""F1: per-entry morphological aliases. Behaviour tests on the key machinery, no house required.

These are the "pinned tests on both the read and write sides" the risk register asks MP-E9 to
register. They are deliberately about the MECHANISM, not about the bench: whether the fallback
recovers the toll class is a measurement in
experiments/MP-E9/results/treatment_per_entry_aliases.json, and this file cannot answer it. What
this file can guarantee is that the mechanism does what its registration says -- exact key first,
aliases only on a miss, per-entry only, contested aliases dropped, and nothing at all when the
flag is off.

The instance is built without __init__ because every function under test is pure arithmetic over
tokens and a dict. A real house would cost ~25 s per test and would not make any of these claims
stronger.
"""
import pytest

from organs.neural_language import NeuralLanguage


class Bare(NeuralLanguage):
    """An organ with only the state these paths read. No cortex, no connectome."""

    def __init__(self):
        self.qa_store = {}
        self.qa_alias = {}
        self.ELECTRIC_QA_MORPH_NORMALIZE = False
        self.ELECTRIC_QA_MORPH_ALIASES = False
        self.ELECTRIC_QA_PARAPHRASE = False


@pytest.fixture()
def lang():
    return Bare()


def test_aliases_are_derived_from_the_entry_s_own_words_only(lang):
    """Per-entry, not global: the alias set comes from this key's tokens."""
    got = lang.qa_alias_keys("when does the bell tolls")
    assert "when does the bell toll" in got, got
    assert all(a != "when does the bell tolls" for a in got), "the key is never its own alias"
    # Every alias differs from the key in exactly one token, or in all the foldable ones.
    kt = "when does the bell tolls".split()
    for a in got:
        at = a.split()
        assert len(at) == len(kt)
        assert sum(1 for x, y in zip(kt, at) if x != y) >= 1


def test_says_and_said_are_not_folded_to_each_other(lang):
    """The independence claim in PRE-1, checked here rather than asserted in prose.

    stem() under-folds these two on purpose. If that ever changes, the says leak would be a
    morphology problem too and P1's bound would need re-scoping -- which this test would surface
    as a changed alias set instead of as a surprise in a bench run.
    """
    assert lang.qa_alias_keys("droso says") == []
    assert lang.qa_alias_keys("droso said") == []


def test_exact_key_wins_and_the_alias_index_is_only_a_fallback(lang):
    lang.ELECTRIC_QA_MORPH_ALIASES = True
    lang.qa_store = {"the bell tolls twice": {"a": ["x"], "prov": {"source": "conversation"}}}
    lang.qa_alias = {"the bell toll twice": "the bell tolls twice"}
    rec, used, how = lang.qa_store_lookup("the bell tolls twice")
    assert (how, used) == ("exact", "the bell tolls twice")
    rec, used, how = lang.qa_store_lookup("the bell toll twice")
    assert (how, used) == ("alias", "the bell tolls twice")


def test_a_contested_alias_answers_nothing(lang):
    """Two records claiming one alias is evidence the alias is too broad, not a tie to break."""
    lang.ELECTRIC_QA_MORPH_ALIASES = True
    # Two records that differ ONLY in the inflection of one word fold onto the same alias.
    # (bell/dog would not: they differ in a content word, so their alias sets never meet.)
    lang.qa_store = {"the bell tolls twice": {"a": ["one"], "prov": {}},
                     "the bell tolled twice": {"a": ["two"], "prov": {}}}
    for k in lang.qa_store:
        lang.qa_alias_register(k, lang.qa_store[k])
    contested = [a for a, v in lang.qa_alias.items() if v is None]
    assert contested, "a shared alias should have been marked contested, not silently kept"
    for a in contested:
        rec, _used, how = lang.qa_store_lookup(a)
        assert rec is None and how is None, f"contested alias {a!r} resolved to an answer"


def test_the_whole_mechanism_is_inert_when_the_flag_is_off(lang):
    """The flag-OFF arm's claim, in miniature: no index is built and no alias is ever consulted."""
    lang.ELECTRIC_QA_MORPH_ALIASES = False
    lang.qa_store = {"the bell tolls twice": {"a": ["x"], "prov": {}}}
    lang.qa_alias_register("the bell tolls twice", lang.qa_store["the bell tolls twice"])
    assert lang.qa_alias == {}, "an alias index was built with the flag off"
    rec, _used, how = lang.qa_store_lookup("the bell toll twice")
    assert rec is None and how is None


def test_restore_rebuilds_the_index_instead_of_persisting_it(lang):
    """The alias index is a property of the keys currently in the store, not a field in the file."""
    lang.ELECTRIC_QA_MORPH_ALIASES = True
    qst = {"when does the bell tolls": {"q": ["when", "does", "the", "bell", "tolls"],
                                        "a": ["it", "tolls", "at", "dusk"],
                                        "word": "tolls", "role": 1, "filler": "tolls",
                                        "prov": {"source": "conversation"}}}
    store = lang._qa_restore_store(qst)
    assert list(store) == ["when does the bell tolls"], store
    assert lang.qa_alias.get("when does the bell toll") == "when does the bell tolls"
    assert lang._qa_restore_report["keys_re_derived"] is True


def test_aliases_and_the_global_fold_do_not_stack_into_a_third_key_form(lang):
    """Both morphology flags on must still be ONE key form, or a write and a read can disagree.

    qa_store_key is the only place that decides the form, so with the global fold on the index is
    keyed by folded keys and the alias step has nothing left to do -- which is correct, not a bug:
    F1 is the fallback FOR the global fold, and the plan never licenses running both as one arm.
    """
    lang.ELECTRIC_QA_MORPH_NORMALIZE = True
    lang.ELECTRIC_QA_MORPH_ALIASES = True
    k = lang.qa_store_key("when does the bell tolls")
    assert k == "when does the bell toll"
    assert lang.qa_alias_keys(k) == [], "a folded key has no per-entry aliases left to file"
