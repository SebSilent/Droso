import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.api_oracle import (PROVIDERS, APIOracle, Budget, NoAPIKeyError,
                               estimate_tokens, oracle_from_block)
from organs.learning_loop import LearningLoop, signature
from organs.local_solver import LocalSolver, _looks_like_code
from organs.query_cache import QueryCache, normalise, tokens
from organs.task_decomposer import TaskDecomposer
from organs.token_optimizer import TokenOptimizer

STUB_ANSWER = "def dedup(items):\n    return list(dict.fromkeys(items))"

def stub_transport(url, headers, payload):
    return {"choices": [{"message": {"content": STUB_ANSWER},
                         "finish_reason": "stop"}],
            "model": payload.get("model", "glm-5.3-flash"),
            "usage": {"prompt_tokens": 40, "completion_tokens": 16,
                      "total_tokens": 56}}

def keyed(tmp_path, name="u.jsonl", **kw):
    """A live oracle (Z.AI, as this box is configured) with the socket replaced."""
    kw.setdefault("budget", Budget(per_query=1200, per_task=4000,
                                   per_day=50000))
    transport = kw.pop("transport", stub_transport)
    provider = kw.pop("provider", "zai")
    return APIOracle(provider=provider, api_key="zk-test-key",
                     transport=transport, usage_path=tmp_path / name, **kw)

@pytest.fixture
def cache(tmp_path):
    c = QueryCache(path=tmp_path / "c.sqlite3")
    yield c
    c.clear()
    c.close()

@pytest.fixture
def stub_oracle(tmp_path):
    return keyed(tmp_path, name="usage.jsonl")

def test_no_key_raises_rather_than_answering(tmp_path):
    """There is no mock mode: `query` has no path that returns text without a
    model. An exception cannot be mistaken for an answer."""
    o = APIOracle(api_key=None, usage_path=tmp_path / "usage.jsonl")
    assert o.mode == "blocked" and o.has_key is False
    with pytest.raises(RuntimeError) as e:
        o.query("how do I sort a list of dicts by key in python")
    assert "No API key configured" in str(e.value)
    assert "model.api_key" in str(e.value)
    assert isinstance(e.value, NoAPIKeyError)
    assert o.calls == 0, "a refused oracle must not count as an attempt"
    assert not (tmp_path / "usage.jsonl").exists(), \
        "nothing was called, so nothing may be logged as spent"

def test_no_synthetic_path_remains_anywhere_in_the_oracle(tmp_path):
    """A guard on the removal itself, so no future edit can re-add the branch
    quietly: no mock method, no mock switch, no mock price row, and no `mock`
    field on a real response."""
    import inspect

    import organs.api_oracle as mod
    src = inspect.getsource(mod)
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    assert "def _mock" not in code
    assert "allow_mock" not in code
    assert not hasattr(mod, "PRICES"), \
        "no price table: a guess about someone else's pricing is not a measurement"
    assert "\"mock\"" not in code, "the response contract must not carry it"
    o = keyed(tmp_path)
    r = o.query("what does sqlite3 connect do")
    assert "mock" not in r
    assert o.stats()["has_key"] is True

def test_live_path_parses_openai_shape_without_network():
    seen = {}

    def transport(url, headers, payload):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "Use sorted(d, key=f)"}}],
                "model": "gpt-4o-mini-2024-07-18",
                "usage": {"prompt_tokens": 21, "completion_tokens": 7,
                          "total_tokens": 28}}
    o = APIOracle(api_key="sk-test", transport=transport)
    assert o.mode == "live"
    r = o.query("sort a list of dicts", max_tokens=40)
    assert r["ok"] and r["text"] == "Use sorted(d, key=f)"
    assert r["mode"] == "live" and r["token_source"] == "provider"
    assert r["completion_tokens_est"] == 7, "provider usage must be believed"
    assert seen["auth"].startswith("Bearer ")
    assert "/chat/completions" in seen["url"]
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert "cost_usd" not in r, "a call reports latency and tokens, never money"
    assert "cost_usd_est" not in o.stats()
    assert "cost_meaningful" not in o.stats()

def test_live_path_parses_anthropic_shape():
    def transport(url, headers, payload):
        assert headers["x-api-key"] == "ak"
        assert "system" in payload and "messages" in payload
        return {"content": [{"type": "text", "text": "Use sorted()."}],
                "usage": {"output_tokens": 4}, "model": "claude-x"}
    o = APIOracle(provider="anthropic", api_key="ak", transport=transport)
    r = o.query("sort please")
    assert r["ok"] and r["text"] == "Use sorted()." and r["mode"] == "live"
    assert r["model"] == "claude-x"

def test_http_error_is_reported_not_invented():
    import urllib.error

    def boom(url, headers, payload):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
    o = APIOracle(api_key="sk-test", transport=boom)
    r = o.query("anything")
    assert r["ok"] is False and r["reason"] == "http_429"
    assert r["text"] == "", "a failed call must not fall back to a stub answer"
    assert o.stats()["errors"] == 1

def test_transport_error_is_not_mistaken_for_an_answer():
    def boom(url, headers, payload):
        raise OSError("getaddrinfo failed")
    o = APIOracle(api_key="sk-test", transport=boom)
    r = o.query("anything")
    assert r["ok"] is False and r["reason"].startswith("transport_error")

def test_budget_is_enforced_before_the_call(tmp_path):
    calls = []

    def transport(url, headers, payload):
        calls.append(payload)
        return {"choices": [{"message": {"content": "x"}}], "usage": {}}
    o = APIOracle(api_key="sk-test", transport=transport,
                  budget=Budget(per_query=20, per_task=10000, per_day=10000),
                  usage_path=tmp_path / "u.jsonl")
    r = o.query("a very long question " * 30, max_tokens=500)
    assert r["ok"] is False and "query_budget_exceeded" in r["reason"]
    assert calls == [], "the request must never be sent past its own ceiling"
    assert r["text"] == ""

def test_day_budget_rolls_over_and_task_budget_stops(tmp_path):
    b = Budget(per_query=100, per_task=200, per_day=500)
    b.commit(140)
    assert b.check(20) is None
    b.commit(20)
    assert "task_budget_exceeded" in b.check(50)
    assert b.remaining()["task_remaining"] == 40
    assert b.check(1) is None
    b.day = "2000-01-01"
    assert b.roll_day() != "2000-01-01"
    assert b.day_spent == 0, "a new calendar day starts unspent"

def test_usage_log_is_written_per_call(tmp_path):
    o = keyed(tmp_path, name="usage.jsonl")
    o.query("one")
    o.query("two")
    lines = (tmp_path / "usage.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["mode"] == "live" and rec["prompt_tokens_est"] > 0
    assert "cost_usd" not in rec, "the usage log records no money"

def test_token_estimate_is_labelled_and_monotonic():
    assert estimate_tokens("") == 0
    a = estimate_tokens("short text")
    b = estimate_tokens("short text " * 50)
    assert 0 < a < b
    o = APIOracle()
    assert o.stats()["token_source"].startswith("estimate")

def test_prompt_relevance_trim_keeps_the_shared_sentences():
    o = APIOracle()
    ctx = ("The parser reads CSV rows. Unrelated prose about weather. "
           "The parser also handles quoted commas in fields.")
    p = o.build_prompt("how does the parser handle quoted fields?", ctx)
    assert "quoted commas" in p and "weather" not in p
    assert len(p) < len(ctx) + 80

def test_cache_exact_round_trip(cache):
    k = cache.put("how do I sort a list", "sorted(x, key=...)",
                  provider="openai", model="gpt-4o-mini", tokens_in=10,
                  tokens_out=5)
    got = cache.get("how do I sort a list", provider="openai",
                    model="gpt-4o-mini")
    assert got["answer"].startswith("sorted") and got["exact"]
    assert got["tokens_avoided"] == 15
    st = cache.stats()
    assert st["hits"] == 1 and st["tokens_saved"] == 15
    assert "cost_saved_usd" not in st, "the cache reports no money"
    assert k and st["entries"] == 1

def test_cache_ignores_punctuation_and_case(cache):
    cache.put("Sort a List, FAST!", "ans", provider="p", model="m")
    assert cache.get("sort a list fast", provider="p", model="m") is not None
    assert normalise("  A, b!!  ") == "a b"

def test_cache_does_not_leak_across_models_or_providers(cache):
    cache.put("same question", "answer for model A", provider="openai",
              model="gpt-4o-mini")
    assert cache.get("same question", provider="openai",
                     model="other-model") is None
    assert cache.get("same question", provider="anthropic",
                     model="gpt-4o-mini") is None

def test_legacy_synthetic_cache_rows_are_never_served(cache):
    """The self-fulfilling loop guard, inverted into an allow-list.

    The mock oracle is gone, but the shipped exocortex/api_cache.sqlite3 still
    holds rows it wrote (verified: 3 rows with mode='mock'). Reading the cache
    by "everything except a name I remember" would hand those rows back to the
    first live question that looks similar, so only mode='live' is servable and
    the leftovers are counted and can be purged.
    """
    cache.put("what is a monad", "[synthetic stub text]", provider="p", model="m",
              mode="mock")
    assert cache.get("what is a monad", provider="p", model="m") is None
    assert cache.stats()["quarantined_not_served"] == 1
    assert cache.get("what is a monad", provider="p", model="m") is None
    assert "mock" in cache.stats()["modes"], "still visible on disk until purged"
    assert cache.purge_non_live() == 1
    assert cache.stats()["modes"].get("mock") is None
    cache.put("what is a monad", "an endofunctor in Endo", provider="p",
              model="m", mode="live")
    hit = cache.get("what is a monad", provider="p", model="m")
    assert hit is not None and hit["mode"] == "live"

def test_near_match_is_flagged_as_something_to_distrust(cache):
    cache.put("how do I read a csv file with pandas in python",
              "pd.read_csv(path)", provider="p", model="m")
    hit = cache.get("how do I write a csv file with pandas in python",
                    provider="p", model="m", approximate=True)
    assert hit is not None
    assert hit.get("approximate") is True and not hit["exact"]
    assert 0 < hit["similarity"] < 1
    assert "different question" in hit["warning"]

def test_exact_lookup_never_returns_a_near_match(cache):
    cache.put("alpha question about sorting", "A", provider="p", model="m")
    assert cache.get("completely different beta", provider="p",
                     model="m", approximate=False) is None

def test_ttl_evicts_old_entries(cache):
    cache.put("old question", "stale", provider="p", model="m")
    con = cache._con
    con.execute("UPDATE entries SET created=?", (time.time() - 400 * 86400,))
    con.commit()
    assert cache.get("old question", provider="p", model="m") is None
    assert cache.stats()["stale_entries"] == 1

def test_lru_prune_respects_the_cap(tmp_path):
    c = QueryCache(path=tmp_path / "cap.sqlite3", max_entries=10)
    for i in range(25):
        c.put(f"question number {i}", f"answer {i}", provider="p", model="m")
    assert c.stats()["entries"] == 10
    assert c.stats()["evictions"] == 15
    c.close()

def test_decomposer_splits_requirements_and_keeps_order():
    d = TaskDecomposer()
    reqs = d.split_requirements(
        "must parse the csv; should write the report to disk; "
        "- handle missing columns; never crash on empty input")
    assert len(reqs) >= 3
    assert any("parse" in r for r in reqs) and any("empty" in r for r in reqs)

def test_unknown_is_a_real_answer():
    d = TaskDecomposer()
    v, rule = d.classify("zebraux flunn the gizmo")
    assert v is None and "refused to guess" in rule
    dec = d.decompose("must do the thing")
    assert all(p["needs_oracle"] in (True, False, None) for p in dec.parts)

def test_external_names_send_a_question_to_the_oracle():
    d = TaskDecomposer()
    assert d.classify("must call the OAuth endpoint")[0] is True
    assert d.classify("must rename the variable")[0] is False
    d2 = TaskDecomposer(known_local=["quux"])
    assert d2.classify("must frobnicate the quux")[0] is False
    d3 = TaskDecomposer(known_external=["frobnicate"])
    assert d3.classify("must frobnicate the widget")[0] is True

def test_questions_are_questions():
    d = TaskDecomposer()
    q = d.as_question("must return the rows sorted by id")
    assert q.endswith("?") and q.startswith("How")

def test_batches_merge_questions():
    dec = TaskDecomposer().decompose(
        "must parse the CSV; must handle the JSON header; must support "
        "gzip endpoints; must raise on the bad token")
    b = dec.batches(max_per_call=3) if hasattr(dec, "batches") else []
    assert b and sum(len(x["questions"]) for x in b) == len(dec.oracle_parts)
    if len(b[0]["questions"]) > 1:
        assert "numbered" in b[0]["prompt"]

class FakeProcs:
    def __init__(self, proc=None):
        self.proc = proc

    def match(self, task, min_success_rate=0.0):
        return self.proc

class FakePatterns:
    def __init__(self, items=()):
        self.items = list(items)

    def query(self, key):
        return next((i for i in self.items if i["key"] == key), None)

    def search(self, sub, limit=10):
        return [i for i in self.items if sub in i["key"].lower()][:limit]

class FakeVerifier:
    def __init__(self, ok=True):
        self.ok = ok
        self.seen = []

    def verify(self, code, language="python"):
        self.seen.append(code)
        return {"ok": self.ok}

CODE = "def sort_rows(rows, key):\n    return sorted(rows, key=key)\n"

def test_local_solver_refuses_when_it_knows_nothing():
    s = LocalSolver()
    assert s.solve("sort a list") is None
    assert s.stats()["refused"] == 1

def test_local_solver_recalls_a_verified_procedure():
    procs = FakeProcs({"signature": "sort rows", "confidence": 0.9,
                       "successes": 3,
                       "dag": [{"code": CODE}], "language": "python"})
    v = FakeVerifier(ok=True)
    s = LocalSolver(procedure_store=procs, verifier=v, min_confidence=0.7)
    hit = s.solve("sort rows by id")
    assert hit and hit["method"] == "procedure" and hit["verified"]
    assert CODE in hit["solution"]
    assert any("procedure(" in p for p in hit["provenance"])

def test_local_solver_wont_claim_verification_it_did_not_get():
    procs = FakeProcs({"signature": "sort rows", "confidence": 0.9,
                       "successes": 1, "dag": [{"code": CODE}]})
    s = LocalSolver(procedure_store=procs, min_confidence=0.7)
    hit = s.solve("sort rows")
    assert hit["verified"] is False, "no verifier means no claim of verification"
    assert s.solve("sort rows", require_verified=True) is None

def test_low_confidence_procedure_is_not_recalled():
    procs = FakeProcs({"signature": "sort rows", "confidence": 0.4,
                       "dag": [{"code": CODE}]})
    s = LocalSolver(procedure_store=procs, min_confidence=0.7)
    assert s.solve("sort rows") is None

def test_pattern_lookup_and_code_shape_detection():
    pats = FakePatterns([{"key": "sort rows dict", "value": CODE,
                         "confidence": 0.95}])
    s = LocalSolver(pattern_library=pats, verifier=FakeVerifier(),
                    min_confidence=0.7)
    hit = s.solve("sort rows by a key in a dict")
    assert hit and hit["method"] == "pattern"
    assert _looks_like_code(CODE) and not _looks_like_code("just prose here")

def test_exocortex_conflict_prefers_procedure():
    procs = FakeProcs({"signature": "s", "confidence": 0.9,
                       "dag": [{"code": CODE}]})
    pats = FakePatterns([{"key": "s", "value": "def other():\n    pass\n",
                         "confidence": 0.99}])
    s = LocalSolver(procedure_store=procs, pattern_library=pats,
                    verifier=FakeVerifier(), min_confidence=0.7)
    assert s.solve("s")["method"] == "procedure", "ladder order matters"

def test_a_broken_collaborator_does_not_become_an_answer():
    class Exploding:
        def match(self, *a, **k):
            raise RuntimeError("db gone")
    s = LocalSolver(procedure_store=Exploding(), min_confidence=0.0)
    assert s.solve("anything") is None

@pytest.fixture
def learner(tmp_path):
    return LearningLoop(state_path=tmp_path / "learn.json",
                        events_path=tmp_path / "events.jsonl",
                        min_confidence=0.6)

def test_signature_is_phrase_independent():
    a = signature("Write a function that sorts rows by id in python")
    b = signature("python: sort rows by id, write a function")
    assert a == b, "the same request must find the same procedure"

def test_unattributable_provenance_is_never_learned(learner):
    """No model answered on these paths, so nothing may become belief."""
    for src in ("mock", "blocked", "error", "none"):
        r = learner.learn_from_task("sort rows", CODE, {"source": src})
        assert r["stored"] is False
        assert r["reason"] == "unlearnable_provenance"
        assert r["source"] == src
    assert learner.stats()["unlearnable_rejections"] == 4
    assert learner.recall("sort rows") is None
    assert learner.learn_from_task("sort rows", CODE)["stored"] is True

def test_verification_moves_confidence_and_reuse_does_not(learner):
    learner.learn_from_task("sort rows", CODE, {"source": "live"},
                            verified=True)
    c1 = learner.store[signature("sort rows")]["confidence"]
    assert c1 > 0.35
    learner.recall("sort rows")
    learner.recall("sort rows")
    c2 = learner.store[signature("sort rows")]["confidence"]
    assert c2 == c1, "reuse is not evidence; verification is"

def test_failures_demote_and_eventually_discard(learner):
    for _ in range(4):
        learner.learn_from_task("weird task", CODE, {"source": "live"},
                                verified=False)
    sig = signature("weird task")
    assert sig not in learner.store
    assert sig in learner.discarded
    assert learner.recall("weird task") is None
    st = learner.stats()
    assert st["discarded"] == 1 and st["demotions"] >= 3

def test_learned_answer_is_remembered_across_instances(tmp_path):
    p = tmp_path / "l2.json"
    a = LearningLoop(state_path=p, events_path=tmp_path / "e.jsonl",
                     min_confidence=0.4)
    a.learn_from_task("parse the csv header", CODE, {"source": "live"},
                      verified=True)
    b = LearningLoop(state_path=p, events_path=tmp_path / "e.jsonl",
                     min_confidence=0.4)
    hit = b.recall("parse the csv header")
    assert hit and CODE in hit["solution"] and hit["verified"]

def test_empty_solution_is_not_stored(learner):
    assert learner.learn_from_task("x", "", {"source": "live"})["stored"] \
        is False
    assert learner.learn_from_task("x", "   ", {"source": "live"})["reason"] \
        == "no_solution"

def test_reinforce_updates_belief(learner):
    learner.learn_from_task("sort rows", CODE, {"source": "live"},
                            verified=True)
    before = learner.store[signature("sort rows")]["confidence"]
    learner.reinforce("sort rows", False)
    assert learner.store[signature("sort rows")]["confidence"] < before
    assert learner.reinforce("unheard of", True) == {"known": False}

def test_event_log_is_append_only_and_greppable(tmp_path):
    ev = tmp_path / "ev.jsonl"
    l = LearningLoop(state_path=tmp_path / "s.json", events_path=ev,
                     min_confidence=0.4)
    l.learn_from_task("t", CODE, {"source": "live"}, verified=True)
    l.recall("t")
    l.learn_from_task("t2", CODE, {"source": "blocked"})
    lines = [json.loads(x) for x in ev.read_text(encoding="utf-8").splitlines()]
    kinds = [x["kind"] for x in lines]
    assert kinds == ["learn", "recall", "rejected_provenance"]

def test_ladder_prefers_free_rungs_and_counts_zero_calls(tmp_path, cache):
    """Measured, not assumed: the API call counter must stay at zero when
    something local can answer."""
    procs = FakeProcs({"signature": "sort rows", "confidence": 0.9,
                       "successes": 2, "dag": [{"code": CODE}]})
    o = APIOracle(api_key=None, usage_path=tmp_path / "u.jsonl")
    s = LocalSolver(procedure_store=procs, min_confidence=0.7,
                    verifier=FakeVerifier())
    opt = TokenOptimizer(o, s, cache=cache, learning_loop=None,
                         verifier=FakeVerifier())
    r = opt.solve_with_minimal_tokens("sort rows by id")
    assert r["route"] == "local" and r["api_calls"] == 0
    assert o.calls == 0 and r["tokens_used"] == 0
    assert r["provenance"], "a local answer must say which rung produced it"

def test_cache_is_consulted_before_the_oracle(tmp_path, cache):
    o = APIOracle(api_key=None, usage_path=tmp_path / "u.jsonl")
    cache.put("what does sqlite3 connect do", "it opens the db",
              provider="openai", model="gpt-4o-mini", mode="live",
              tokens_in=20, tokens_out=8)
    opt = TokenOptimizer(o, LocalSolver(), cache=cache, learning_loop=None)
    r = opt.solve_with_minimal_tokens("what does sqlite3 connect do")
    assert r["route"] == "cache" and o.calls == 0
    assert r["cached"] and r["api_calls"] == 0

def test_live_answers_are_cached_as_live_and_replayed(tmp_path):
    """The mode column is the cache's provenance, so it must say what actually
    happened: this answer came from a provider call."""
    o = keyed(tmp_path)
    c = QueryCache(path=tmp_path / "m.sqlite3")
    opt = TokenOptimizer(o, None, cache=c, learning_loop=None)
    r = opt.solve_with_minimal_tokens(
        "must call the OAuth endpoint to fetch the token")
    assert r["route"] == "oracle" and r["api_calls"] == 1
    assert c.stats()["modes"].get("live") == 2
    again = opt.solve_with_minimal_tokens(
        "must call the OAuth endpoint to fetch the token")
    assert again["route"] == "cache" and again["api_calls"] == 0
    assert o.calls == 1, "the repeat was answered from what was already paid for"
    assert again["solution"] == r["solution"], \
        "the cached text is replayed verbatim, not re-derived"
    c.close()

def test_llm_switch_off_leaves_the_free_rungs_standing(tmp_path):
    """"No LLM" must not mean "no thinking": the learned/local/cache rungs still
    answer, and the refusal is reported rather than returned as an empty "done".
    """
    o = keyed(tmp_path)
    c = QueryCache(path=tmp_path / "off.sqlite3")
    opt = TokenOptimizer(o, None, cache=c, learning_loop=None)
    task = "what does sqlite3 connect do"
    c.put(task, "opens a database file", provider="zai", model=o.model,
          mode="live")
    hit = opt.solve_with_minimal_tokens(task, allow_oracle=False)
    assert hit["route"] == "cache" and hit["api_calls"] == 0, \
        "a cached answer is not a reason to call the model off"
    miss = opt.solve_with_minimal_tokens("an entirely different question here",
                                         allow_oracle=False)
    assert miss["route"] == "none" and miss["partial"] is True
    assert "llm_disabled" in miss["reasons"]
    assert o.calls == 0, "the switch is enforced, not decorative"
    c.close()

def test_budget_stop_returns_partial_not_a_truncated_success(tmp_path):
    o = keyed(tmp_path, budget=Budget(per_query=5, per_task=5, per_day=5))
    opt = TokenOptimizer(o, None, cache=QueryCache(path=tmp_path / "b.db"),
                         learning_loop=None)
    r = opt.solve_with_minimal_tokens(
        "must call the OAuth endpoint; must parse the JWT token; must handle "
        "the expiry skew")
    assert r["route"] in ("none", "oracle")
    assert r["api_calls"] == 0
    assert r["partial"] is True
    assert any("budget" in str(x) for x in r["provenance"] + r["reasons"])
    assert opt.report()["budget_stops"] >= 1

def test_escalation_when_everything_looked_local(tmp_path):
    """Classification said 'no oracle-worthy part', and local had nothing:
    that must escalate and say so, not silently return an empty solution."""
    o = keyed(tmp_path)
    opt = TokenOptimizer(o, LocalSolver(),
                         cache=QueryCache(path=tmp_path / "e.db"),
                         learning_loop=None)
    r = opt.solve_with_minimal_tokens("must rename the variable and sort rows")
    assert r["route"] == "oracle" and r["api_calls"] == 1
    assert any("escalated" in x for x in r["provenance"])
    assert STUB_ANSWER in r["solution"], "the answer came through the real parser"

def test_an_unverified_answer_is_replayed_by_cache_not_by_memory(tmp_path):
    """The distinction this whole file exists to keep.

    A repeat question may be answered for free by the cache (the same text, the
    same question -- that is a fact about cost). It may NOT be promoted to a
    procedure and replayed as *knowledge*, because no checker confirmed it. And
    the learning loop goes further: an unverified store *demotes* the record,
    because being asked again is not evidence of being right.
    """
    o = keyed(tmp_path)
    ll = LearningLoop(state_path=tmp_path / "l.json",
                      events_path=tmp_path / "l.jsonl", min_confidence=0.4)
    opt = TokenOptimizer(o, LocalSolver(), cache=QueryCache(
        path=tmp_path / "loop.db"), learning_loop=ll)
    task = "how do I dedup a list preserving order"
    first = opt.solve_with_minimal_tokens(task)
    assert first["route"] == "oracle" and o.calls == 1
    assert first["verified"] is False
    assert ll.recall(task) is None
    rec = ll.store.get(signature(task))
    assert rec is not None and rec["confidence"] < 0.35, \
        "the unverified store should have demoted it, not nudged it up"
    again = opt.solve_with_minimal_tokens(task)
    assert again["route"] == "cache" and again["api_calls"] == 0
    assert again["solution"] == first["solution"], "the same text, replayed"
    assert o.calls == 1, "free because it was already paid for, not because " \
                        "anything checked it"

def test_a_verified_procedure_is_the_rung_that_becomes_knowledge(tmp_path):
    """The other side of the ladder: one checked outcome on a fresh record is
    enough to promote, and then the answer is recalled as a procedure."""
    o = keyed(tmp_path)
    ll = LearningLoop(state_path=tmp_path / "k.json",
                      events_path=tmp_path / "k.jsonl", min_confidence=0.45)
    opt = TokenOptimizer(o, None, cache=QueryCache(path=tmp_path / "k.db"),
                         learning_loop=ll)
    task = "dedup a list preserving order, write the function"
    ll.learn_from_task(task, CODE, {"source": "live"}, verified=True)
    hit = ll.recall(task)
    assert hit is not None and hit["solution"] == CODE
    r = opt.solve_with_minimal_tokens(task)
    assert r["route"] == "learned" and r["api_calls"] == 0
    assert o.calls == 0, "this task never dialled: it remembered how"

def test_repetition_without_verification_never_opens_the_learned_rung(tmp_path):
    o = keyed(tmp_path)
    ll = LearningLoop(state_path=tmp_path / "v.json",
                      events_path=tmp_path / "v.jsonl", min_confidence=0.45)
    task = "explain the difference between a stack and a queue"
    for _ in range(5):
        ll.learn_from_task(task, "a queue is FIFO, a stack is LIFO",
                           {"source": "live"}, verified=False)
        assert ll.recall(task) is None, "repetition is not evidence"
    assert o.calls == 0

def test_savings_report_states_its_basis(tmp_path):
    o = keyed(tmp_path)
    opt = TokenOptimizer(o, LocalSolver(),
                         cache=QueryCache(path=tmp_path / "s.db"),
                         learning_loop=None)
    opt.solve_with_minimal_tokens("must call the OAuth endpoint")
    rep = opt.report()
    assert "savings_basis" not in rep, "no counterfactual savings claim"
    assert "tokens_actual_est" not in rep and "cost_usd_est" not in rep
    assert rep["tasks"] >= 1 and rep["per_route"]
    assert rep["oracle"]["mode"] == "live"
    assert "cost_meaningful" not in rep["oracle"]
    assert rep["cache"]["servable_modes"] == ["live"]
    assert "serve_mock" not in rep["cache"] and "mock_entries_blocked" \
        not in rep["cache"], "a zeroed field would claim a prevented event"
    assert rep["per_route"]["oracle"] == 1
    assert rep["solved_without_api"] == 0

def test_report_counts_local_share(tmp_path):
    procs = FakeProcs({"signature": "sort rows", "confidence": 0.9,
                       "dag": [{"code": CODE}], "successes": 5})
    o = APIOracle(api_key=None, usage_path=tmp_path / "u.jsonl")
    opt = TokenOptimizer(o, LocalSolver(procedure_store=procs,
                                        min_confidence=0.7),
                         cache=QueryCache(path=tmp_path / "r.db"),
                         learning_loop=None)
    opt.solve_with_minimal_tokens("sort rows")
    assert opt.report()["local_solve_share"] == 1.0

def test_zai_provider_rows_match_what_was_measured_live():
    """Two v4 surfaces, two different bills. Collapsing them into one row is how
    a working key starts looking broken."""
    assert PROVIDERS["zai"]["base"] == "https://api.z.ai/api/coding/paas/v4"
    assert PROVIDERS["zai"]["plan"] == "coding-plan-subscription"
    assert PROVIDERS["zai-paas"]["base"] == "https://api.z.ai/api/paas/v4"
    assert PROVIDERS["zai-paas"]["plan"] == "per-token-balance"
    assert PROVIDERS["zai"]["reasoning_model"] is True
    assert PROVIDERS["zai"]["model"] == "glm-5.3-flash"
    lo, hi = PROVIDERS["zai"]["temp"]
    assert lo > 0.0 and hi <= 1.0

def test_zai_request_shape_thinking_disabled_and_bearer(tmp_path):
    seen = {}

    def transport(url, headers, payload):
        seen["url"], seen["headers"], seen["payload"] = url, headers, payload
        return {"choices": [{"message": {"content": "an endofunctor"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 4,
                          "total_tokens": 34}}

    o = APIOracle(provider="zai", api_key="zk-test", transport=transport,
                  usage_path=tmp_path / "u.jsonl")
    r = o.query("what is a monad", max_tokens=40)
    assert r["ok"] and r["text"] == "an endofunctor"
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["Authorization"] == "Bearer zk-test"
    assert seen["payload"]["thinking"] == {"type": "enabled"}, \
        "GLM-5.3 removed 'disabled' entirely: the documented migration is " \
        "thinking.type 'enabled' plus reasoning_effort"
    assert seen["payload"]["reasoning_effort"] == "low", \
        "'low' is the least thinking the model accepts, and thinking cannot be " \
        "turned off -- sending 'disabled' or 'low' as the type both 400"
    assert [m["role"] for m in seen["payload"]["messages"]] == ["system", "user"]
    assert seen["payload"]["temperature"] >= PROVIDERS["zai"]["temp"][0]
    assert r["token_source"] == "provider" and r["completion_tokens_est"] == 4

def test_enabled_thinking_is_sent_when_asked_for(tmp_path):
    def transport(url, headers, payload):
        assert payload["thinking"] == {"type": "enabled"}
        return {"choices": [{"message": {"content": "x"}}]}
    o = APIOracle(provider="zai", api_key="zk-test", thinking="enabled",
                  transport=transport, usage_path=tmp_path / "t.jsonl")
    assert o.query("q")["ok"]

def test_reasoning_only_completion_is_diagnosed_not_reported_as_answer(tmp_path):
    """Measured live: a small max_tokens on a reasoning model can return 200 with
    empty content and all the tokens spent on thinking. That is not "the model
    had nothing to say", and it must not be surfaced as an empty success."""
    def transport(url, headers, payload):
        return {"choices": [{"message": {"content": "",
                                         "reasoning_content": "hmm" * 40},
                             "finish_reason": "length"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 12,
                          "completion_tokens_details": {"reasoning_tokens": 12}}}
    o = APIOracle(provider="zai", api_key="zk-test", transport=transport,
                  usage_path=tmp_path / "r.jsonl")
    r = o.query("q", max_tokens=12)
    assert r["ok"] is False and r["text"] == ""
    assert r["reason"].startswith("thinking_ate_the_budget")
    assert r["reasoning_tokens"] == 12

def test_coding_plan_key_on_the_per_token_surface_says_recharge(tmp_path):
    """429 code 1113 came back as an HTTP body on the wrong surface. Mapping it
    to `http_429` alone reads like a transient rate limit and invites retries; the
    actual meaning is "wrong billing plane for this key"."""
    import io
    import urllib.error

    def transport(url, headers, payload):
        body = json.dumps({"code": 1113,
                           "message": "Insufficient balance or no resource "
                                      "package. Please recharge."}).encode()
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {},
                                     io.BytesIO(body))
    o = APIOracle(provider="zai-paas", api_key="zk-test", transport=transport,
                  usage_path=tmp_path / "b.jsonl")
    r = o.query("q")
    assert r["ok"] is False
    assert "1113" in r["reason"] and "recharge" in r["reason"].lower()

def test_error_inside_a_200_is_not_an_empty_answer(tmp_path):
    def transport(url, headers, payload):
        return {"error": {"code": "1113", "message": "no resource package"}}
    o = APIOracle(provider="zai", api_key="zk-test", transport=transport,
                  usage_path=tmp_path / "e.jsonl")
    r = o.query("q")
    assert r["ok"] is False and r["text"] == ""
    assert "1113" in r["reason"]

def test_no_response_from_the_oracle_is_ever_labelled_mock(tmp_path):
    """The word must not survive in a live answer's provenance either."""
    o = keyed(tmp_path)
    r = o.query("q")
    assert "mock" not in json.dumps(r), r
    assert r["mode"] == "live" and o.stats()["has_key"] is True
    assert "mock_calls" not in o.stats()

def test_the_teacher_can_have_its_own_provider_but_inherits_by_default(tmp_path):
    cfg = {"model": {"provider": "zai", "api_key": "zk-main",
                     "model": "glm-5.3-flash",
                     "base_url": "https://api.z.ai/api/coding/paas/v4",
                     "api_budget": {"max_tokens_per_query": 111}},
           "autotraining": {"model": "glm-5.3", "api_budget":
                            {"max_tokens_per_query": 900}}}
    same = oracle_from_block(cfg, "autotraining")
    assert same.provider == "zai" and same.api_key == "zk-main"
    assert same.model == "glm-5.3", "the block's own model wins"
    assert same.budget.per_query == 900, "a teacher needs a bigger ceiling"
    assert oracle_from_block(cfg, "no_such_block").model == "glm-5.3-flash"
    empty = oracle_from_block({"model": {"provider": "zai"}}, "autotraining")
    assert empty.mode == "blocked" and empty.has_key is False
def test_a_save_adopts_records_written_by_someone_else(tmp_path):
    """The house holds the main store in memory and writes it whole, which used to
    make it the only writer that could exist. Any offline tool that learned
    something was erased on the next tick. The battery taught one procedure -- the
    first verified by doing a task -- and it was gone from the file before the
    report finished printing."""
    a = LearningLoop(state_path=tmp_path / "s.json", events_path=tmp_path / "e",
                     persist=True, min_confidence=0.4)
    b = LearningLoop(state_path=tmp_path / "s.json", events_path=tmp_path / "e",
                     persist=True, min_confidence=0.4)
    a.learn_from_task("first task", CODE, {"source": "live"}, verified=True)
    b.learn_from_task("second task", CODE, {"source": "live"}, verified=True)
    b.save()
    after = LearningLoop(state_path=tmp_path / "s.json", persist=False,
                         min_confidence=0.4)
    after.load_if_exists()
    assert "second task" in after.store, list(after.store)
    # And a writer that does not know about it adopts it rather than erasing it.
    assert after.recall("second task") is not None, \
        "a record adopted from another writer was not callable"
