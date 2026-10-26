import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.api_oracle import APIOracle, Budget, NoAPIKeyError
from organs.neural_language import NeuralLanguage

WORDS = [{"word": w, "sentence": f"today the word {w} appears in use"} for w in
         ("verify", "assemble", "execute", "replay", "provenance", "stale",
          "ceiling", "refusal", "budget", "evidence", "recall", "procedure",
          "attempt", "confirm", "malformed", "truncated", "interval",
          "approval", "argument", "branch", "scope", "index", "summarise",
          "clarify", "notify", "proceed", "abort", "ready", "whether",
          "assume", "intend", "prefer", "specify", "allow", "enough")]

def words_transport(calls_box=None):
    """A stand-in teacher socket: one JSON lesson per ask, real shape."""
    state = {"n": 0}

    def transport(url, headers, payload):
        state["n"] += 1
        i = state["n"]
        pool = WORDS[((i - 1) * 20) % len(WORDS):][:20]
        body = {"vocabulary": pool}
        return {"choices": [{"message": {"content": json.dumps(body)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 100}}
    transport.state = state
    return transport

def teacher(tmp_path):
    return APIOracle(provider="zai", api_key="zk-test-key",
                     transport=words_transport(),
                     usage_path=tmp_path / "u.jsonl",
                     budget=Budget(per_query=4000, per_task=20000,
                                   per_day=100000))

def make(tmp_path, **over):
    """A real carve + the real tokenizer + the neural language organ."""
    import os
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine
    from organs.tokenizer import TokenizerOrgan
    eng = HybridEngine(graph=build_core_graph())
    tok = TokenizerOrgan()
    kw = {"state_path": tmp_path / "neural_lang.json"}
    kw.update(over)
    return NeuralLanguage(eng, tok, **kw)

def test_teach_word_creates_a_real_neural_pattern(tmp_path):
    nl = make(tmp_path)
    rec = nl.teach_word("verify", "verify the result and check that it stands", source="test")
    assert rec is not None
    assert len(rec["kc"]) == 16, "a k-of-16 code: WHICH KCs fire for 'verify'"
    assert all(0 <= i < nl.engine.static.g.kc_idx.size or i < 3840
               for i in rec["kc"])
    assert 0 <= rec["pool"] < 12, "the pattern won a real MBON pool"
    assert nl.vocabulary_size() == 1 and nl.can_speak() is False
    assert nl.engine.decisions >= 1, "a real decide placed the pattern"
    assert nl.engine.rpe_last > 0

def test_teaching_the_same_word_twice_does_not_duplicate(tmp_path):
    nl = make(tmp_path)
    first = nl.teach_word("stale", "the stale value is older than its source")
    again = nl.teach_word("stale", "the stale value is older than its source")
    assert again is None and nl.vocabulary_size() == 1
    assert first["word"] == "stale"

def test_gibberish_that_encodes_to_nothing_is_refused(tmp_path):
    nl = make(tmp_path)
    assert nl.teach_word("") is None
    assert nl.teach_word("   ") is None

def test_words_used_together_become_neuronally_related(tmp_path):
    """THE MEANING TEST. Nobody stores a definition anywhere. Words are
    taught only IN USE, inside sentences; co-activation wires them
    together; afterwards the being's entire 'opinion' on how related two
    words are is a cosine in its semantic matrix. Greeting words must end
    up related to each other and UNRELATED to kitchen/tech words."""
    nl = make(tmp_path)
    nl.teach_word("hello", "hello my good friend, welcome and good day",
                  source="test")
    nl.teach_word("welcome", "welcome back, my good friend, hello again",
                  source="test")
    nl.teach_word("cache", "clear the cache and free the memory",
                  source="test")
    near = nl.similarity("hello", "welcome")
    far = nl.similarity("hello", "cache")
    # Measured under the sparse Hebb write: near 0.389, far EXACTLY 0.0 --
    # two words that never shared a sentence now share no synapses at all.
    # The old clique rule left everything weakly related to everything
    # (far was a small positive), which is the saturation this rule removed.
    assert near > far and near > 0.2, (near, far)
    fp = nl._footprint("hello")
    spread = nl.understand("hello") - fp / np.linalg.norm(fp)
    assert np.linalg.norm(spread) > 0.05, "associations did the work"

def test_a_new_word_learns_its_meaning_from_context_alone(tmp_path):
    """The being has never seen 'howdy'. It meets it ONCE, inside a
    greeting sentence. No lesson names it a greeting -- but its meaning
    vector moves toward the greeting cluster and away from tech words.
    That is learning meaning from usage, in synapses, with zero English
    stored anywhere."""
    nl = make(tmp_path)
    nl.teach_word("hello", "hello my good friend, welcome and good day",
                  source="test")
    nl.teach_word("cache", "clear the cache and free the memory",
                  source="test")
    v_before = nl.understand("howdy").copy()
    before_hello = nl.similarity("howdy", "hello")
    nl.live("howdy my good friend, hello and welcome")
    v_after = nl.understand("howdy")
    after_hello = nl.similarity("howdy", "hello")
    # The absolute cosine is the wrong measure of "moved toward": an
    # untrained word's hash footprint lands inside whatever neighbourhood
    # the taught words wired, so howdy starts ~0.97-similar to BOTH greeting
    # words (measured: hello 0.9757, welcome 0.9708) before it has lived a
    # single sentence. Learning SPECIALISES the vector -- the absolute
    # cosine to any one word falls as the footprint narrows (hello:
    # 0.9757 -> 0.7369) -- so `after > before` could only pass if living
    # did NOTHING. What the architecture honestly claims, and what this
    # asserts: the vector MOVES (0.71 L2 between unit vectors here), and
    # the moved vector sits with the greeting cluster -- hello AND welcome,
    # the words it actually co-occurred with -- far above the tech word it
    # never met.
    moved = float(np.linalg.norm(v_after - v_before))
    assert moved > 0.1, (before_hello, after_hello, moved)
    assert after_hello > nl.similarity("howdy", "cache"), \
        "context alone taught howdy the greeting cluster"
    assert nl.similarity("howdy", "welcome") > \
        nl.similarity("howdy", "cache"), \
        "the whole co-occurred cluster, not one word"

def test_sparse_hebb_write_separates_co_lived_from_strangers(tmp_path):
    """THE SPARSE-WRITE REGRESSION. The old rule wired the FULL clique of
    every percept: a ~241-cell utterance added all ~58k pairs in one go,
    every row marched to the clip, and words that never shared a sentence
    became as related as words that did. The sparse rule keeps only the
    SAN_TOP_K strongest co-activations per write and caps row totals, so
    two words that actually lived together must sit far above a stranger
    neither of them ever met."""
    from organs.neural_language import SAN_ROW_CAP, SAN_TOP_K
    nl = make(tmp_path)
    nl.teach_word("alpha", "alpha north river stone", source="test")
    nl.teach_word("charlie", "charlie south meadow clay", source="test")
    for _ in range(10):
        nl.live("alpha bravo harbour", learn=True)
    ab = nl.similarity("alpha", "bravo")
    ac = nl.similarity("alpha", "charlie")
    assert ab > ac + 0.15, (ab, ac)
    # The write stayed sparse: 12 utterances, at most SAN_TOP_K new pairs
    # each (the old clique rule would have left hundreds of thousands).
    nnz = int(np.count_nonzero(nl.san_w))
    assert nnz <= 13 * SAN_TOP_K, nnz
    # Homeostasis held: no row keeps more total weight than the cap, however
    # often its cells fired.
    assert float(nl.san_w.sum(axis=1).max()) <= SAN_ROW_CAP + 1e-3, \
        float(nl.san_w.sum(axis=1).max())

def test_persisted_meaning_survives_a_restart(tmp_path):
    nl = make(tmp_path)
    nl.teach_word("hello", "hello my good friend, welcome and good day",
                  source="test")
    nl.teach_word("cache", "clear the cache and free the memory",
                  source="test")
    nl.save_state(force_san=True)
    before = nl.similarity("hello", "welcome")
    again = make(tmp_path)
    assert again.vocabulary_size() == 2
    assert abs(again.similarity("hello", "welcome") - before) < 1e-6, \
        "the learned meaning structure survives a restart"

def test_form_thought_returns_neural_activity_not_prose(tmp_path):
    nl = make(tmp_path)
    nl.teach_word("verify", "verify the result and check it")
    t = nl.form_thought("verify the cache")
    assert set(t) >= {"action", "valuation", "valuation_max", "active_neurons",
                      "known_words_fired"}
    assert 0 <= t["action"] < 12
    assert "verify" in t["known_words_fired"], \
        "the thought's activation overlaps the learned 'verify' pattern"
    assert isinstance(t["valuation"], list)

def test_pattern_overlap_finds_only_learned_words(tmp_path):
    nl = make(tmp_path)
    nl.teach_word("verify", "verify the result and check it")
    t = nl.form_thought("verify")
    assert t["known_words_fired"] == ["verify"]
    t2 = nl.form_thought("qqq zzz")
    assert isinstance(t2["known_words_fired"], list)

def test_learn_from_teacher_encodes_real_words_into_the_carve(tmp_path):
    nl = make(tmp_path, min_vocabulary=15)
    before = nl.engine.static.g.meta
    r = nl.learn_from_teacher(teacher(tmp_path), num_words=20)
    assert r["calls"] == 1 and r["words_added"] == 20
    assert nl.vocabulary_size() == 20
    assert all(0 <= rec["pool"] < 12 for rec in nl.word_patterns.values())
    assert nl.engine.decisions >= 20, "each word was a real propagate+reinforce (settling may re-decide)"
    assert "cost_usd" not in r, "a lesson report claims no money"

def test_no_teacher_no_vocabulary_and_no_lie(tmp_path):
    nl = make(tmp_path)
    r = nl.learn_from_teacher(None)
    assert r["stopped_reason"] == "no_teacher_configured"
    assert nl.vocabulary_size() == 0

def test_no_api_key_means_silence_not_a_seed_list(tmp_path):
    nl = make(tmp_path)
    oracle = APIOracle(provider="zai", api_key=None,
                       usage_path=tmp_path / "u.jsonl")
    with pytest.raises(NoAPIKeyError):
        oracle.require_key("neural_language")
    r = nl.learn_from_teacher(oracle)
    assert r["stopped_reason"] == "no_api_key"
    assert nl.vocabulary_size() == 0, \
        "SILENCE is the honest state; a seed list would be a lie"

def test_the_teacher_asking_for_words_is_refused_at_the_budget(tmp_path):
    nl = make(tmp_path)
    tiny = APIOracle(provider="zai", api_key="zk-test",
                     transport=words_transport(),
                     usage_path=tmp_path / "t.jsonl",
                     budget=Budget(per_query=50, per_task=50, per_day=50))
    r = nl.learn_from_teacher(tiny, num_words=20)
    assert r["calls"] == 0 and "ceiling" in (r.get("stopped_reason") or "")
    assert tiny.calls == 0, "refused before the wire, so no spend"

def test_can_speak_is_the_threshold_not_a_vibe(tmp_path):
    nl = make(tmp_path, min_vocabulary=5)
    for w in WORDS[:4]:
        nl.teach_word(w["word"], w["sentence"])
    assert nl.can_speak() is False
    nl.teach_word("argument", "an argument is a reason in a debate")
    assert nl.can_speak() is True
    s = nl.stats()
    assert s["vocabulary_size"] == 5 and s["can_speak"] is True
    assert s["neural_basis"] == "BANC_v888_KC_neurons + SAN256_hebbian"

def test_conversation_is_experience_never_vocabulary(tmp_path):
    nl = make(tmp_path)
    r = nl.observe_exchange("What is a cache?", "a cache holds paid-for rows")
    assert r["turn"] == "observed" and 0 <= r["pool"] < 12
    assert nl.vocabulary_size() == 0, \
        "traffic may not create words; only a teacher can teach_word"
    assert nl.exchanges_observed == 1

def test_patterns_persist_as_kc_indices_and_resume(tmp_path):
    nl = make(tmp_path)
    nl.teach_word("stale", "the stale value is older than its source", source="test")
    nl.teach_word("verify", "check it", source="test")
    f = nl.state_path
    assert f.exists()
    raw = json.loads(f.read_text(encoding="utf-8"))
    assert raw["version"] == 2
    assert raw["words"]["stale"]["kc"] and \
        raw["words"]["stale"]["pool"] in range(12)
    assert "meaning" not in raw["words"]["stale"], \
        "no English gloss is stored: meaning lives in the SAN matrix"
    nl.save_state(force_san=True)
    assert f.with_suffix(".san.npz").exists(), \
        "the semantic synapses persist beside the words"
    again = make(tmp_path)
    assert again.vocabulary_size() == 2
    assert again.word_patterns["stale"]["kc"] == \
        nl.word_patterns["stale"]["kc"], "the SAME neurons fire after a restart"

def test_the_language_endpoints_serve_the_neural_contract(tmp_path):
    import os
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from world.connectome_house import ConnectomeHouse
    from world.reasoning_agent import ReasoningAgent
    from organs.code_assembler import CodeAssembler
    from organs.memory import MemoryOrgan
    from organs.terminal import TerminalOrgan
    a = ReasoningAgent(
        {"code_assembler": CodeAssembler(), "filesystem": None,
         "terminal": TerminalOrgan(timeout_s=5), "memory": MemoryOrgan()},
        state_path=tmp_path / "s.json",
        config={"model": {"api_key": None, "provider": "zai"},
                "language": {"state_path": str(tmp_path / "lang.json"),
                             "auto_train": False},
                "connectome": {"project_root": str(tmp_path)},
                "sandbox": {"project_root": str(tmp_path)}})
    a.language.teach_word("verify", "check it", source="test")
    house = ConnectomeHouse(a, a.config, port=0,
                            config_path=tmp_path / "hybrid_config.json")
    code, s = house.route_get("/api/language/state")
    assert code == 200 and s["present"] is True
    for k in ("vocabulary_size", "can_speak", "word_patterns",
              "neural_basis", "recent_words"):
        assert k in s, k
    assert s["neural_basis"] == "BANC_v888_KC_neurons + SAN256_hebbian"
    assert s["vocabulary_size"] == 1
    code, v = house.route_get("/api/language/store",
                              {"section": ["vocabulary"], "q": ["verify"]})
    row = v["vocabulary"][0]
    assert row["word"] == "verify" and len(row["kc"]) == 16
    a.api_oracle.api_key = None
    # THE ENDPOINT WAS DELIBERATELY REMOVED. `GET /api/language/train` returns 410 with
    # `gone: True` -- "cron teaching removed; teachers are connected by the administrator"
    # -- and POST is not routed at all. The old assertion checked a `success`/`no_api_key`
    # shape the endpoint no longer has, which made a deliberate removal look like a
    # regression. What must still hold is that it does not silently pretend to train.
    gcode, g = house.route_get("/api/language/train")
    assert gcode == 410 and g.get("gone") is True, (gcode, g)
    assert "removed" in str(g.get("reason")), g
    code, r = house.route_post("/api/language/train", {})
    assert code in (404, 410), (code, r)
    assert "success" not in r, "a removed endpoint must not report success"

def test_agent_start_trains_language_and_reports(tmp_path, monkeypatch):
    import os
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from world.reasoning_agent import ReasoningAgent
    from organs.code_assembler import CodeAssembler
    from organs.memory import MemoryOrgan
    from organs.terminal import TerminalOrgan
    a = ReasoningAgent(
        {"code_assembler": CodeAssembler(), "filesystem": None,
         "terminal": TerminalOrgan(timeout_s=5), "memory": MemoryOrgan()},
        state_path=tmp_path / "s.json",
        config={"model": {"api_key": None, "provider": "zai"},
                "language": {"auto_train": True,
                             "state_path": str(tmp_path / "lang.json"),
                             "min_vocabulary": 50, "training_cycles": 2,
                             "words_per_cycle": 20},
                "connectome": {"project_root": str(tmp_path)},
                "sandbox": {"project_root": str(tmp_path)}})
    out = a.start(heartbeat=False, train_language=True)
    assert out["language"]["trained"] is False
    assert "SILENT" in out["language"]["reason"] or \
        "no API key" in out["language"]["reason"]
    assert a.language.vocabulary_size() == 0
    a.api_oracle.api_key = "zk-test"
    seen = {"n": 0}

    def transport(url, headers, payload):
        seen["n"] += 1
        return {"choices": [{"message": {"content": json.dumps(
            {"vocabulary": WORDS[:20]})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 100}}
    a.api_oracle.transport = transport
    out2 = a._maybe_train_language()
    assert out2["words_learned"] >= 20
    assert a.language.can_speak() is False or out2["vocabulary_size"] >= 20
    assert seen["n"] >= 1


def test_freshness_floor_ties_one_conversation_and_decays_across():
    """THE FLOOR. exp(-age/tau) on ages of a few seconds is an ordering with
    no meaning in it: the freshest-by-accident teaching won a question it
    could not answer (cross_session baseline 2026-10-25 22:41, accumulation
    how-ask). Ages under FRESH_FLOOR_S must tie at exactly 1.0 -- inside a
    conversation the answer-type and distinctiveness terms decide -- and
    decay must bite only past the floor, where the age is real information."""
    import math
    from organs.neural_language import (FRESH_FLOOR_S, FRESH_TAU_S,
                                        freshness_key)
    # Inside the floor: every age is the same conversation.
    assert freshness_key(0.0, "you") == 1.0
    assert freshness_key(10.0, "you") == 1.0
    assert freshness_key(FRESH_FLOOR_S, "you") == 1.0
    # Past the floor: decay bites, and only there.
    assert freshness_key(FRESH_FLOOR_S + 60.0, "you") < 1.0
    one_tau = freshness_key(FRESH_FLOOR_S + FRESH_TAU_S, "you")
    assert abs(one_tau - math.exp(-1.0)) < 1e-12, one_tau
    # Not testimony at all: his own echo, the corpus, an unknown mouth.
    for who in ("droso", "book", "", "parent"):
        assert freshness_key(0.0, who) == 0.0, who


def test_two_teachings_seconds_apart_tie_and_the_answer_type_decides(tmp_path):
    """The end-to-end shape of the floor's purpose: two user teachings heard
    seconds apart, then a question. Unfloored, the second teaching won on
    freshness alone even though it could not answer the question's type; the
    floor ties them and the answer-type term picks the teaching that can."""
    nl = make(tmp_path)
    nl.question_roles["how"] = {"3": 5}
    nl.answer_types["how"] = {"heavy": 5}
    nl.hear("the box is heavy", speaker="you")
    nl.hear("the box is red", speaker="you")  # heard last: fresher by accident
    r = nl.respond("how is the box")
    said = str(r.get("utterance") or r.get("response") or "")
    assert "heavy" in said, (said, r.get("retrieval"))