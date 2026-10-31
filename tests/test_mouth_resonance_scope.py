"""E9: RESONANCE_SESSION_SCOPE -- pinning the mouth-class repair before it exists.

The diagnosis (docs/evidence/mouth_diagnosis.md) is that the `mouth` failures are a
RESONANCE defect: `mates` at organs/neural_language.py:3947 is the entire 11,439-word
taught vocabulary, unscoped, so `max()` picks a static corpus attractor whose identity
barely depends on the question. Measured top resonance across four different asks:
0.5738 / 0.5811 / 0.5722 / 0.5730 -- a range of 0.009 -- with `numbered` top-5 in 4 of 4
and `sold` in 3 of 4, while the wanted words score 0.1134-0.4131.

These tests are written first and pin, in order:
  1. the flag exists as a class attribute and defaults False
  2. flag OFF is line-for-line the old candidate list (no brain required)
  3. flag ON excludes the attractor words -- P3, the load-bearing prediction
  4. empty-session fallback returns the FULL pool, so the flag can never turn a
     speaking organism into a silent one
  5. `_speakable` still rejects multi-word strings -- the rendering limit that puts
     the echo ask outside E9's target set
  6. the four journal rows this diagnosis rests on still carry their verified fields
  7. the empty-window regression: no threshold separates attractor from wanted word

Tests 2-5 run on a stub, so they need no connectome build.
"""

import io
import json
import os

import pytest

from organs.neural_language import NeuralLanguage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN10 = os.path.join(ROOT, "state", "selection", "generation_10_asks.jsonl")
PROBE = os.path.join(ROOT, "docs", "evidence", "mouth_probe.json")

# The measured corpus attractors (docs/evidence/mouth_probe.json): top-5 across the
# four mouth asks. P3 requires these to be ABSENT from a scoped pool, not merely
# out-scored -- that is what distinguishes scoping from reweighting.
ATTRACTORS = ["numbered", "sold", "agin", "tears", "composed", "unconsciousness",
              "midnight", "strain", "headway"]

# The wanted words, all confirmed present in the 11,439-word vocabulary.
WANTED = ["scarf", "lantern", "copper", "bell", "turns", "twice"]


class _Stub:
    """Just enough organ surface to exercise the candidate filter with no brain."""

    RESONANCE_SESSION_SCOPE = False
    RESONANCE_CONTENT_SCOPE = False

    def __init__(self, vocab, session=()):
        self.word_patterns = {w: None for w in vocab}
        self._session = set(session)

    _speakable = NeuralLanguage._speakable
    # staticmethod on the organ, so re-wrap it: bound as a plain attribute it
    # would receive `self` in place of `user_text`.
    _resonance_exclude = staticmethod(NeuralLanguage._resonance_exclude)
    _is_content_word = staticmethod(NeuralLanguage._is_content_word)

    def _session_words(self):
        return set(self._session)

    def _resonance_content(self, mates):
        # No store on the bare stub, which is exactly the organ's own fallback
        # path: unreadable binder -> keep the wider pool. _CStub overrides this
        # with a real fake binder to exercise the filter itself.
        return mates


class _FakeBinder:
    """A binder whose document frequencies are declared, not measured."""

    def __init__(self, df, n_mem):
        self._df, self._n = dict(df), int(n_mem)
        self.X = type("X", (), {"shape": (self._n, 128)})()

    def stem_rows(self, w):
        return [None] * int(self._df.get(w, 0))


class _CStub(_Stub):
    """_Stub plus a store, so RESONANCE_CONTENT_SCOPE has something to read.

    It must bind the organ's real `_resonance_content`, not the bare stub's
    pass-through -- otherwise the filter under test is never called and every
    assertion about it passes for the wrong reason.
    """

    _resonance_content = NeuralLanguage._resonance_content

    def __init__(self, vocab, session=(), df=None, n_mem=60000):
        _Stub.__init__(self, vocab, session)
        self.cortex = type("C", (), {})()
        self.cortex.binder = _FakeBinder(df or {}, n_mem)


def _speak(w):
    """`_speakable` is an instance method; the stubs have no brain to bind to."""
    return NeuralLanguage._speakable(None, w)


def _mates(stub, text):
    return NeuralLanguage._resonance_mates(stub, text)


# ---------------------------------------------------------------- 1. the flag

def test_flag_exists_as_class_attribute_and_defaults_false():
    assert hasattr(NeuralLanguage, "RESONANCE_SESSION_SCOPE")
    assert NeuralLanguage.RESONANCE_SESSION_SCOPE is False


def test_flag_sits_beside_the_other_answer_path_genes():
    # The three answer-path genes are one family and should stay visible together.
    for gene in ("ANSWER_COVERAGE_FLOOR", "RECALL_UNFILTERED_FALLBACK",
                 "RESONANCE_SESSION_SCOPE"):
        assert hasattr(NeuralLanguage, gene), gene


# ------------------------------------------------- 2. flag OFF is the old code

def test_flag_off_returns_exactly_the_old_candidate_list():
    vocab = ATTRACTORS + WANTED + ["36", "8", "a", "wet thing"]
    stub = _Stub(vocab, session=["scarf", "lantern"])
    stub.RESONANCE_SESSION_SCOPE = False
    got = _mates(stub, "which of them is wet and is not on the hook?")
    # Old behaviour: every speakable word, unscoped, attractors included.
    assert "numbered" in got and "sold" in got and "agin" in got
    assert "scarf" in got and "lantern" in got
    assert len(got) == len([w for w in vocab if NeuralLanguage._speakable(stub, w)])


def test_flag_off_ignores_the_session_set_entirely():
    # A non-empty session set must not narrow anything while the flag is off.
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["scarf"])
    stub.RESONANCE_SESSION_SCOPE = False
    assert set(_mates(stub, "name the wet thing")) == set(
        w for w in vocab if NeuralLanguage._speakable(stub, w))


def test_flag_off_still_applies_the_single_word_exclude():
    # Pre-existing behaviour, unchanged by E9: a one-word utterance cannot
    # resonate with itself.
    stub = _Stub(["scarf", "numbered"], session=[])
    stub.RESONANCE_SESSION_SCOPE = False
    assert _mates(stub, "scarf") == ["numbered"]
    # ...but a multi-word utterance excludes nothing.
    assert set(_mates(stub, "the scarf is wet")) == {"scarf", "numbered"}


# ------------------------------------- 3. flag ON excludes the attractors (P3)

def test_flag_on_excludes_every_measured_attractor_word():
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["scarf", "lantern", "wet", "hook"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet and is not on the hook?")
    for a in ATTRACTORS:
        assert a not in got, "attractor %r survived scoping" % a


def test_flag_on_keeps_the_wanted_word_as_a_candidate():
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["scarf", "lantern"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "name the wet thing that is not on the hook")
    assert "scarf" in got


def test_flag_on_pool_is_strictly_smaller_than_the_full_vocabulary():
    # P2 in miniature: the pool must actually shrink, or the mechanism did not engage.
    vocab = ATTRACTORS + WANTED + ["corpus%d" % i for i in range(200)]
    stub = _Stub(vocab, session=["scarf"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet?")
    assert len(got) < len(vocab)
    assert got == ["scarf"]


def test_flag_on_still_applies_the_single_word_exclude():
    stub = _Stub(["scarf", "lantern"], session=["scarf", "lantern"])
    stub.RESONANCE_SESSION_SCOPE = True
    assert _mates(stub, "scarf") == ["lantern"]


# ------------------------------------------- 4. empty-session fallback (P2 void)

def test_empty_session_falls_back_to_the_full_pool():
    # The flag must never silence an organism that would otherwise speak.
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=[])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet?")
    assert set(got) == set(w for w in vocab if NeuralLanguage._speakable(stub, w))
    assert "numbered" in got          # attractors are back, by design


def test_no_overlap_falls_back_rather_than_going_silent():
    # Session words exist but none is a speakable vocabulary word: narrowing would
    # empty the pool and the mouth path would return "no words it could answer
    # with". That is a silence the flag is not allowed to cause.
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["zzzqqq", "12345"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet?")
    assert got, "scoped pool must never be empty when the full pool is not"
    assert "numbered" in got


def test_session_words_reads_the_binder_you_rows_only():
    # The idiom is _ordinal_answer's (:3070-3080): who == "you" and when >= session_t0.
    class _Binder:
        meta = [
            {"who": "you", "when": 200.0, "tokens": ["the", "scarf", "is", "wet"]},
            {"who": "book", "when": 200.0, "tokens": ["numbered", "sold"]},
            {"who": "you", "when": 50.0, "tokens": ["lantern"]},   # before session_t0
            {"who": "you", "when": 300.0, "tokens": "copper bell turns twice"},
        ]

    class _Cortex:
        binder = _Binder()

    class _Organ:
        cortex = _Cortex()
        session_t0 = 100.0

    got = NeuralLanguage._session_words(_Organ())
    assert got == {"the", "scarf", "is", "wet", "copper", "bell", "turns", "twice"}
    assert "numbered" not in got and "sold" not in got   # corpus rows excluded
    assert "lantern" not in got                          # pre-session row excluded


def test_session_words_is_empty_without_a_store():
    class _Organ:
        cortex = None
        session_t0 = 0.0

    assert NeuralLanguage._session_words(_Organ()) == set()


# --------------------------------------------------- 5. the rendering limit

@pytest.mark.parametrize("w", ["wet thing", "copper bell turns twice", "a b"])
def test_speakable_rejects_multi_word_strings(w):
    # Why the echo ask is outside E9's target set: no ranking outcome can emit it.
    assert NeuralLanguage._speakable(_Stub([]), w) is False


@pytest.mark.parametrize("w", ["36", "8", "a", "", "  "])
def test_speakable_rejects_digits_and_single_characters(w):
    assert NeuralLanguage._speakable(_Stub([]), w) is False


def test_speakable_accepts_real_words():
    assert NeuralLanguage._speakable(_Stub([]), "scarf") is True


# ------------------------------------------------- 6. the journal evidence

def _gen10_mouth_rows():
    if not os.path.exists(GEN10):
        pytest.skip("generation 10 journal not present")
    rows = [json.loads(l) for l in io.open(GEN10, encoding="utf-8") if l.strip()]
    return [r for r in rows if r.get("stage") == "mouth"]


def test_generation_10_has_four_mouth_rows_all_probe_tier():
    rows = _gen10_mouth_rows()
    assert len(rows) == 4
    assert all(r.get("tier") == "probe" for r in rows)
    assert all(r.get("pass") is False for r in rows)
    assert all(r.get("cause") == "mouth" for r in rows)


def test_mouth_rows_never_reached_the_recall_gate():
    # coverage null is what separates this class from the recall class.
    for r in _gen10_mouth_rows():
        assert r.get("coverage") is None


def test_mouth_rows_answered_by_resonance_not_by_an_arbiter():
    for r in _gen10_mouth_rows():
        assert str(r.get("source") or "").startswith("meaning resonance")


def test_journal_does_not_store_the_utterance():
    # Provenance guard: the babble strings in the diagnosis come from the probe,
    # not from the journal. Any test asserting on `utterance` here would be
    # asserting on a field that is null.
    for r in _gen10_mouth_rows():
        assert r.get("utterance") is None


def test_mouth_class_cannot_move_the_frozen_score():
    rows = _gen10_mouth_rows()
    assert rows and all(r.get("tier") != "frozen" for r in rows)


# ------------------------------------------------- 7. the empty window

def _probe_rows():
    if not os.path.exists(PROBE):
        pytest.skip("mouth probe json not present")
    return json.load(io.open(PROBE, encoding="utf-8"))


def test_no_threshold_separates_attractor_from_wanted_word():
    rows = _probe_rows()
    assert len(rows) == 4
    winners = [r["argmax_score"] for r in rows]
    wanted = [s for r in rows for s in r["wanted_score"].values()]
    # Every winner sits above every wanted score, so the bands do not overlap and
    # no value of reply_threshold can admit one while excluding the other.
    assert min(winners) > max(wanted)
    assert min(winners) >= 0.55          # all four clear the standing threshold
    assert max(wanted) < 0.55            # no wanted word ever clears it


def test_the_resonance_winner_is_ask_independent():
    # The decisive measurement: four different asks, top score range 0.009.
    rows = _probe_rows()
    winners = [r["argmax_score"] for r in rows]
    assert max(winners) - min(winners) < 0.02
    asks = {r["ask"] for r in rows}
    assert len(asks) == 4                # ...on four genuinely different asks


def test_wanted_words_were_present_in_the_vocabulary():
    # Rules out retrieval: nothing was failed to be found.
    rows = _probe_rows()
    for r in rows:
        assert all(r["wanted_in_vocabulary"].values())
        assert r["vocabulary"] > 10000   # the pool is corpus-sized


# --------------------------------- 8. the bug this extraction actually caused

def test_no_function_reads_exclude_without_assigning_it():
    """Regression, and the reason _resonance_exclude is its own method.

    Lifting the candidate list into _resonance_mates removed the `exclude` local
    from the mouth path, but TWO downstream sites still read it: the `pool_mates`
    fallback and the bigram extension. Both became NameError, the caller swallowed
    it, and a greeting that should have been answered from learned patterns fell
    through to `reasoning_loop` -- a full-suite failure that no resonance test
    could see, because the flag was off and the candidate list was correct.

    This checks the whole module, not just that one function, so the same mistake
    on any name in any organ method is caught at test time rather than by a
    swallowed exception at run time.
    """
    import ast

    src = io.open(os.path.join(ROOT, "organs", "neural_language.py"),
                  encoding="utf-8").read()
    tree = ast.parse(src)
    checked = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [n for n in ast.walk(fn) if isinstance(n, ast.Name)]
        loads = {n.id for n in names if isinstance(n.ctx, ast.Load)}
        if "exclude" not in loads:
            continue
        stores = {n.id for n in names if isinstance(n.ctx, ast.Store)}
        params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        assert "exclude" in stores or "exclude" in params, (
            "%s reads `exclude` but never binds it -- an orphaned local, which "
            "the mouth path swallows as a NameError" % fn.name)
        checked.append(fn.name)
    assert checked, "nothing reads `exclude` any more; the mouth path changed shape"


def test_the_exclude_rule_is_single_sourced():
    # Both callers must agree, or the pool and its downstream filters diverge.
    stub = _Stub(["hi", "wet"])
    assert NeuralLanguage._resonance_exclude("hi") == {"hi"}
    assert NeuralLanguage._resonance_exclude("the scarf is wet") == set()
    assert NeuralLanguage._resonance_exclude("  hi  ") == {"hi"}


# ------------------------------------------- 9. the E9 OUTCOME, refuted

E9J = os.path.join(ROOT, "docs", "evidence", "e9_scope_probe.json")
GEN11 = os.path.join(ROOT, "state", "selection", "generation_11_asks.jsonl")
GEN12 = os.path.join(ROOT, "state", "selection", "generation_12_asks.jsonl")


def _e9_probe():
    if not os.path.exists(E9J):
        pytest.skip("e9 scope probe json not present")
    return json.load(io.open(E9J, encoding="utf-8"))


def _asks(path):
    if not os.path.exists(path):
        pytest.skip("%s not present" % os.path.basename(path))
    rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return {(r.get("script"), r.get("ask")): r for r in rows}


def test_the_flag_stays_default_off_because_e9_was_refuted():
    # P4 failed: the wanted word does not win its scoped pool. The pre-registered
    # abort condition fired, so the gene is kept inert as a measured negative --
    # not deleted, because deleting it invites someone to try it again.
    assert NeuralLanguage.RESONANCE_SESSION_SCOPE is False


def test_P2_scoping_engaged_and_shrank_the_pool():
    rows = _e9_probe()
    assert len(rows) == 4
    for r in rows:
        assert r["full_pool"] > 10000
        assert 0 < r["scoped_pool"] < 100, r["ask"]
        assert all(r["P2_wanted_in_pool"].values()), r["ask"]


def test_P3_the_corpus_attractor_was_excluded_not_outscored():
    for r in _e9_probe():
        assert r["P3_pass"] is True, r["ask"]
        assert all(r["P3_attractors_absent"].values())


def test_P4_refuted_the_wanted_word_never_wins_its_scoped_pool():
    # The abort condition. Pinned so the refutation cannot be quietly forgotten.
    rows = _e9_probe()
    assert rows and all(r["wanted_wins_scoped_pool"] is False for r in rows)


def test_the_second_attractor_is_the_function_word_the():
    # Removing the corpus attractor left the session's own function word on top,
    # in all four cases, at 0.504-0.522.
    rows = _e9_probe()
    assert all(r["scoped_argmax"] == "the" for r in rows)
    for r in rows:
        assert 0.50 <= r["scoped_argmax_score"] <= 0.53


def test_the_scoped_argmax_falls_below_the_threshold_so_the_organ_goes_silent():
    # `the` at ~0.52 is under reply_threshold 0.55, so understands is False and
    # the babble becomes a refusal. This is why mouth and gating both emptied.
    for r in _e9_probe():
        assert r["scoped_argmax_score"] < r["reply_threshold"]
        assert r["spoken"] is False
        assert r["said"] == ""


def test_lantern_and_bell_would_win_but_for_the_function_word():
    # Recorded because it is the seductive next step, and it is FORBIDDEN by the
    # E9 abort clause (no frequency/stopword penalty). If someone proposes it,
    # it needs its own pre-registration, not a widening of this one.
    rows = {r["ask"]: r for r in _e9_probe()}
    lantern = rows["which thing did i mention earlier than the kettle?"]
    assert lantern["wanted_rank_in_scoped"]["lantern"] == 2
    echo = rows["repeat after me the copper bell turns twice"]
    assert echo["wanted_rank_in_scoped"]["bell"] == 2


def test_P1_arm_a_is_identical_to_generation_10():
    a, b = _asks(GEN10), _asks(GEN11)
    assert set(a) == set(b)
    for k in a:
        for f in ("pass", "stage", "cause", "source", "coverage"):
            assert a[k].get(f) == b[k].get(f), (k, f)


def test_P4_no_ask_changed_its_pass_verdict_between_arms():
    a, b = _asks(GEN11), _asks(GEN12)
    assert set(a) == set(b)
    assert all(bool(a[k].get("pass")) == bool(b[k].get("pass")) for k in a)


def test_arm_b_emptied_the_mouth_and_gating_classes_into_silence():
    a, b = _asks(GEN11), _asks(GEN12)
    moved = [k for k in a
             if a[k].get("stage") in ("mouth", "gating")
             and b[k].get("stage") == "recall"]
    assert len(moved) == 7                      # 4 mouth + 3 gating
    for k in moved:
        assert b[k].get("source") is None       # it stopped speaking
        assert a[k].get("pass") is False and b[k].get("pass") is False


def test_understands_was_an_artifact_of_the_corpus_attractor():
    # The stronger finding: on the resonance path `understands` is
    # res[best] >= reply_threshold, and in arm A that bar was cleared by
    # `numbered`/`sold` -- corpus words unrelated to the question. Under
    # scoping all seven previously-"understood" asks report they do not
    # understand. Any future work reading `understands` as comprehension is
    # reading noise.
    rows = _probe_rows()
    assert all(r["argmax_score"] >= r["reply_threshold"] for r in rows)
    assert all(r["argmax_word"] not in WANTED for r in rows)
    for r in _e9_probe():
        assert r["spoken"] is False


def test_the_attractor_words_recur_across_asks():
    rows = _probe_rows()
    tops = [t[0] for r in rows for t in r["top5"]]
    assert tops.count("numbered") >= 3
    assert tops.count("sold") >= 3


# =============================================== 10. E10, RESONANCE_CONTENT_SCOPE
#
# E9 refuted session-scoping alone: it excluded the corpus attractor exactly as
# predicted (P2, P3 PASS) but the function word `the` won all four pools instead
# (P4 FAIL). E10 adds the other half. These tests are written BEFORE the battery.

V10 = ["the", "is", "on", "scarf", "wet", "coat", "hook",
       "numbered", "sold", "agin", "lantern", "bell"]
# Document frequencies as measured in the live binder: `the` is in nearly every
# row; the corpus attractors are RARE (df 14, 7, 2). That asymmetry is the whole
# reason E10 needs both filters and not just this one.
DF10 = {"the": 59000, "is": 41000, "on": 33000, "scarf": 14, "wet": 9,
        "coat": 11, "hook": 6, "numbered": 14, "sold": 7, "agin": 2,
        "lantern": 5, "bell": 8}
N_MEM = 60000


def _cstub(**kw):
    return _CStub(V10, df=DF10, n_mem=N_MEM, **kw)


def test_content_flag_exists_and_defaults_false():
    assert hasattr(NeuralLanguage, "RESONANCE_CONTENT_SCOPE")
    assert NeuralLanguage.RESONANCE_CONTENT_SCOPE is False


def test_the_distinctiveness_rule_is_the_recall_gates_own_rule():
    # `df > 0 and df * 4 <= n_mem`, lifted from `if df * 4 <= n_mem: must.add(w)`
    # and its `if not df: unknown.add(w); continue` guard. No new constant.
    f = NeuralLanguage._is_content_word
    assert f(0, 60000) is False            # never met: not evidence about anything
    assert f(1, 60000) is True
    assert f(15000, 60000) is True         # exactly a quarter: still distinctive
    assert f(15001, 60000) is False        # one row over: a function word
    assert f(59000, 60000) is False        # `the`
    assert f(14, 60000) is True            # `scarf`, and also `numbered`


def test_flag_off_returns_exactly_the_old_candidate_list():
    # Both genes off: line-for-line the pre-E9 computation.
    off = _cstub()
    assert off.RESONANCE_CONTENT_SCOPE is False
    got = _mates(off, "name the wet thing that is not on the hook")
    assert "the" in got and "numbered" in got and "scarf" in got
    assert len(got) == len([w for w in V10 if _speak(w)])


def test_flag_off_ignores_the_store_entirely():
    # A stub whose binder would reject everything must still return the full
    # pool when the flag is off -- proving the store is never read.
    s = _cstub()
    s.cortex.binder = _FakeBinder({}, 1)   # every word has df 0 -> all filtered
    assert len(_mates(s, "the scarf is wet")) == len([w for w in V10 if _speak(w)])


def test_flag_on_removes_function_words_and_keeps_content_words():
    s = _cstub()
    s.RESONANCE_CONTENT_SCOPE = True
    got = set(_mates(s, "name the wet thing that is not on the hook"))
    for fn in ("the", "is", "on"):
        assert fn not in got, fn
    for cw in ("scarf", "wet", "coat", "hook", "lantern", "bell"):
        assert cw in got, cw


def test_content_alone_does_NOT_remove_the_corpus_attractor():
    # The reason E10 must run with BOTH flags. `numbered` (df 14), `sold` (df 7)
    # and `agin` (df 2) are rare in the binder, so a distinctiveness filter
    # admits them. Content-without-scope tests a different hypothesis.
    s = _cstub()
    s.RESONANCE_CONTENT_SCOPE = True
    got = set(_mates(s, "name the wet thing that is not on the hook"))
    for a in ("numbered", "sold", "agin"):
        assert a in got, a


def test_scope_alone_does_NOT_remove_the_function_word():
    # The E9 result, pinned as a test: scoping admits `the` because every tell
    # contains it.
    s = _cstub(session={"the", "scarf", "wet", "coat", "hook", "is", "on"})
    s.RESONANCE_SESSION_SCOPE = True
    got = set(_mates(s, "name the wet thing that is not on the hook"))
    assert "the" in got
    assert "numbered" not in got           # scope DID remove the corpus attractor


def test_both_flags_remove_both_attractor_classes():
    # The E10 arm. Corpus attractors gone via scope, function words gone via
    # content, wanted word still a candidate.
    # The session is E9's measured 7-word pool. The corpus attractors are NOT in
    # it -- that is exactly why scope removes them. The two attractor classes are
    # disjoint: corpus attractors are rare words never told this session, session
    # function words are high-df words told in every tell. Each filter catches the
    # class the other admits.
    s = _cstub(session={"the", "scarf", "wet", "coat", "hook", "is", "on"})
    s.RESONANCE_SESSION_SCOPE = True
    s.RESONANCE_CONTENT_SCOPE = True
    got = set(_mates(s, "name the wet thing that is not on the hook"))
    for bad in ("the", "is", "on", "numbered", "sold", "agin"):
        assert bad not in got, bad
    for good in ("scarf", "wet", "coat", "hook"):
        assert good in got, good


def test_content_filter_falls_back_rather_than_going_silent():
    # Every word high-df: the filter would empty the pool, so it must not.
    s = _CStub(["the", "is", "on"], df={"the": 59000, "is": 41000, "on": 33000},
               n_mem=N_MEM)
    s.RESONANCE_CONTENT_SCOPE = True
    assert set(_mates(s, "the is on")) == {"the", "is", "on"}


def test_unreadable_store_falls_back_rather_than_raising():
    s = _cstub()
    s.RESONANCE_CONTENT_SCOPE = True
    s.cortex = None                        # AttributeError inside the filter
    assert len(_mates(s, "the scarf is wet")) == len([w for w in V10 if _speak(w)])


def test_the_single_word_exclude_survives_both_filters():
    s = _cstub(session=set(V10))
    s.RESONANCE_SESSION_SCOPE = True
    s.RESONANCE_CONTENT_SCOPE = True
    assert "scarf" not in _mates(s, "scarf")
    assert "scarf" in _mates(s, "the scarf is wet")


def test_the_content_flag_cannot_touch_the_recall_gate():
    # Guarded-floor preservation by construction: the gene is read in exactly
    # one place, _resonance_mates, which only builds the mouth's candidate list.
    # The recall gate computes its own `must` inline and never calls this.
    src = io.open(os.path.join(ROOT, "organs", "neural_language.py"),
                  encoding="utf-8").read()
    assert src.count("RESONANCE_CONTENT_SCOPE") >= 3      # decl, guard, docstring
    # The recall gate is inline in NeuralLanguage.answer, which computes its own
    # `must` set at `if df * 4 <= n_mem: must.add(w)`. The E10 gene must not be
    # readable from there: that is what keeps the guarded floor untouched.
    body = src.split("def answer(self, question")[1].split("\n    def ")[0]
    assert "must.add(w)" in body           # sanity: this IS the recall gate
    assert "RESONANCE_CONTENT_SCOPE" not in body
    assert "_resonance_content" not in body


# ---- the pre-registered arithmetic, computed from E9's measured scores ----

def test_E10_predicts_silence_because_the_wanted_word_is_below_threshold():
    # Written BEFORE the battery. E9 measured the wanted word's resonance inside
    # its own scoped pool: 0.1526, 0.1600, 0.1221, 0.4129. reply_threshold is
    # 0.55 and E10 is forbidden from lowering it. Filtering the pool changes
    # WHICH word wins, not the scores -- `res` is computed once over the full
    # vocabulary. So even a perfect content filter leaves the winner below the
    # bar, `understands` stays False, and the organ stays silent.
    rows = _e9_probe()
    assert rows
    for r in rows:
        best_wanted = max(r["wanted_score_in_scoped"].values())
        assert best_wanted < r["reply_threshold"], r["ask"]


# ---- the E10 OUTCOME, measured: refuted, aborted at conditions 1 and 4 ----

E10J = os.path.join(ROOT, "docs", "evidence", "e10_scope_probe.json")
GEN13 = os.path.join(ROOT, "state", "selection", "generation_13_asks.jsonl")
GEN14 = os.path.join(ROOT, "state", "selection", "generation_14_asks.jsonl")
GEN12 = os.path.join(ROOT, "state", "selection", "generation_12_asks.jsonl")


def _e10_probe():
    if not os.path.exists(E10J):
        pytest.skip("e10 scope probe json not present")
    return json.load(io.open(E10J, encoding="utf-8"))


def test_both_genes_stay_default_off_because_e10_was_refuted():
    assert NeuralLanguage.RESONANCE_SESSION_SCOPE is False
    assert NeuralLanguage.RESONANCE_CONTENT_SCOPE is False


def test_E10_P2_the_is_removed_everywhere_but_is_and_on_survive():
    # Finding 1: the distributional rule is not a function-word rule. Measured
    # against a binder that is 99.19% `book` rows, document frequency measures
    # corpus style, not lexical class -- so `is` and `on` count as distinctive.
    rows = _e10_probe()
    assert all(r["P2_function_words_absent"]["the"] for r in rows)
    survivors = [r for r in rows if not r["P2_pass"]]
    assert len(survivors) == 3                      # MIXED, 1/4
    assert any(not r["P2_function_words_absent"]["is"] for r in survivors)


def test_E10_P3_corpus_attractors_absent_on_every_ask():
    rows = _e10_probe()
    assert all(all(r["P3_corpus_absent"].values()) for r in rows)


def test_E10_P4_mixed_lantern_and_bell_win_but_scarf_loses():
    rows = {r["ask"]: r for r in _e10_probe()}
    assert rows["which thing did i mention earlier than the kettle?"]["P4_wanted_wins"]
    assert rows["repeat after me the copper bell turns twice"]["P4_wanted_wins"]
    for k in ("name the wet thing that is not on the hook",
              "which of them is wet and is not on the hook?"):
        assert rows[k]["P4_wanted_wins"] is False   # abort condition 1
        assert rows[k]["wanted_rank"]["scarf"] == 5


def test_E10_P7_no_winner_clears_the_threshold_so_all_four_are_silent():
    rows = _e10_probe()
    assert all(r["P7_winner_clears_threshold"] is False for r in rows)
    assert all(r["predicted_silent"] for r in rows)
    assert all(r["spoken"] is False and r["said"] == "" for r in rows)
    # abort condition 4, and the ceiling for an honest content word
    assert max(r["argmax_score"] for r in rows) < 0.55
    assert max(r["argmax_score"] for r in rows) == pytest.approx(0.4129, abs=1e-4)


def test_E10_arm_a_is_identical_to_generation_11():
    a, b = _asks(GEN11), _asks(GEN13)
    if a is None or b is None:
        pytest.skip("generation 11 or 13 journal not present")
    assert set(a) == set(b)
    for k in a:
        for f in ("pass", "stage", "cause", "source", "coverage"):
            assert a[k].get(f) == b[k].get(f), (k, f)


def test_E10_no_ask_changed_its_pass_verdict():
    a, b = _asks(GEN13), _asks(GEN14)
    if a is None or b is None:
        pytest.skip("generation 13 or 14 journal not present")
    assert set(a) == set(b)
    assert all(bool(a[k].get("pass")) == bool(b[k].get("pass")) for k in a)


def test_E10_arm_b_is_indistinguishable_from_E9_arm_b():
    # The content filter is battery-inert once scope has already driven the
    # winner below the bar: removing more candidates from a pool whose argmax
    # cannot clear 0.55 leaves the verdict unchanged. The ranking repair is
    # downstream of the real blocker.
    e9b, e10b = _asks(GEN12), _asks(GEN14)
    if e9b is None or e10b is None:
        pytest.skip("generation 12 or 14 journal not present")
    assert set(e9b) == set(e10b)
    for k in e9b:
        assert bool(e9b[k].get("pass")) == bool(e10b[k].get("pass")), k
        assert e9b[k].get("stage") == e10b[k].get("stage"), k


def test_E10_silenced_the_four_mouth_asks_and_added_no_babble():
    a, b = _asks(GEN13), _asks(GEN14)
    if a is None or b is None:
        pytest.skip("generation 13 or 14 journal not present")
    spoke_a = {k for k, r in a.items() if r.get("source")}
    spoke_b = {k for k, r in b.items() if r.get("source")}
    assert not (spoke_b - spoke_a)                  # P6: no new babble
    assert len(spoke_a - spoke_b) == 4              # the four mouth asks
    assert len(spoke_a) == 27 and len(spoke_b) == 23


def test_E10_abort_condition_is_stated_before_running():
    # If the wanted word still loses its content-scoped pool, or the winner
    # clears 0.55 and produces new babble, E10 aborts and is recorded -- not
    # widened. Pinned here so the condition cannot be revised after the fact.
    doc = io.open(os.path.join(ROOT, "docs", "evidence", "e10_preregistration.md"),
                  encoding="utf-8").read()
    for clause in ("ABORT", "reply_threshold", "df * 4 <= n_mem"):
        assert clause in doc
