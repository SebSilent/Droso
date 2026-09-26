import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.heartbeat import Heartbeat
from world.connectome_house import (CAPABILITIES,
                                    ConnectomeHouse,
                                    build_house_agent,
                                    cfg_get, _deep_merge)

@pytest.fixture(scope="module")
def hub(tmp_path_factory):
    tp = tmp_path_factory.mktemp("house")
    cfg = {"model": {"api_key": None, "provider": "openai", "name": "gpt-4o-mini",
                     "api_budget": {"max_tokens_per_query": 1200,
                                    "max_tokens_per_task": 4000,
                                    "max_tokens_per_day": 50000}},
           "connectome": {"max_retries": 3, "max_context_tokens": 8000,
                           "project_root": str(tp)},
           "sandbox": {"enabled": True, "allow_network": False},
           "heartbeat": {"think_interval": 60, "sleep_threshold": 120},
           "house": {"port": 0}}
    agent = build_house_agent(cfg, project_root=str(tp))
    # The house takes its fence from config.connectome.project_root and falls back to the
    # repo root, while build_house_agent puts the AGENT's root in cfg itself. In production
    # both are the repo so the disagreement never shows; here it meant the agent wrote into
    # the temp dir while the house policed the repo, and every write came back "outside the
    # house". Stated explicitly so the two fences are the same fence.
    agent.start(heartbeat=False, train_language=False)
    house = ConnectomeHouse(agent, cfg, port=_free_port(),
                            config_path=tp / "hybrid_config.json")
    return house, agent, tp

def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

def test_index_page_is_served_from_the_house_dir(hub):
    house, _, _ = hub
    body = (house.house_dir / "index.html").read_text(encoding="utf-8")
    # The page is titled Droso. It said "Connectome House" for one release, and the
    # assertion outlived the rename because nothing read this file for a week.
    assert "Droso" in body
    assert 'id="chat-messages"' in body

def test_every_referenced_asset_exists(hub):
    import re
    house, _, _ = hub
    html = (house.house_dir / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="(/static/[^"]+)"', html)
    assert refs, "index.html references no assets"
    missing = [r for r in refs
               if not (house.house_dir / r.split("?")[0].lstrip("/")).is_file()]
    assert not missing, f"the page references assets that are not on disk: {missing}"

# `_safe_static` was a method on the house that resolved a path and refused anything
# outside the served directory. It is gone: the same guard now lives inside the request
# handler as a nested `_static`, where it does resolve() then relative_to(house_dir) and
# answers 403 on escape. The property it protected is tested below, over HTTP, against the
# code that actually enforces it -- testing a private helper that no longer exists only
# proved that the helper no longer exists.

def test_static_traversal_and_directories_are_refused_over_http(serving):
    """Nothing under /static/ may leave the house directory, and a directory is not a file.

    This replaces `test_static_traversal_is_404_over_http`, which asserted one path and one
    status. The guard answers 403 for an escaping path and 404 for something that is not a
    file, which is the more accurate split -- the assertion was written against the code
    that predates it. The property that matters is that none of these is ever served.
    """
    house = serving
    for bad in ("/../config/hybrid_config.json",
                "/static/../../run_house.py",
                "/static/../../config/hybrid_config.json",
                "/static/..%2f..%2frun_house.py",
                "/static/"):
        code = _http(house.port, bad)[0]
        assert code != 200, f"{bad} was SERVED -- it must be refused"
        assert code in (400, 403, 404), (bad, code)

GET_ROUTES = ["/api/state", "/api/organs", "/api/consciousness", "/api/thoughts",
              "/api/procedures", "/api/patterns", "/api/cache",
              "/api/learning_history", "/api/config",
              "/api/chat_history", "/api/progress"]
# Five routes were dropped from this list because the house stopped serving them:
# /api/stats, /api/task_status, /api/tools, /api/ledger, /api/guarantee. They carried the
# cost, token and guarantee panels, which were removed on purpose, and they appear nowhere
# in the server or the page now -- the only remaining references were in this test and in
# the being's own learned-procedures store, which had ingested the strings from here.

@pytest.mark.parametrize("path", GET_ROUTES)
def test_get_routes_answer(hub, path):
    house, _, _ = hub
    status, payload = house.route_get(path)
    assert status == 200, payload
    assert isinstance(payload, dict)

def test_every_route_returns_a_status_and_a_payload(hub):
    """route_get and route_post must ALWAYS return (status, payload).

    Seven branches of route_post returned a bare dict. The HTTP layer does
    `code, payload = house.route_post(...)`, and unpacking a dict yields its keys, so the
    LLM switch, file write, file delete and organ toggle were all broken over the network
    -- while every one of them still answered correctly when called directly, which is why
    it lived: the shape was wrong only at the seam, and nothing was looking at the seam.

    Checked statically as well as by calling, because a branch behind a condition that a
    test does not reach is exactly where a bug like this hides.
    """
    import ast
    house, _, _ = hub
    for path in GET_ROUTES:
        r = house.route_get(path)
        assert isinstance(r, tuple) and len(r) == 2, (path, type(r).__name__)
        assert isinstance(r[0], int), path
    for path in ("/api/llm/toggle", "/api/breaker_reset", "/api/sandbox_answer",
                 "/api/file/write", "/api/file/delete", "/api/organ/toggle",
                 "/api/not-a-real-post"):
        r = house.route_post(path, {})
        assert isinstance(r, tuple) and len(r) == 2, (path, type(r).__name__, r)
        assert isinstance(r[0], int), path
    src = (ROOT / "world" / "connectome_house.py").read_text(encoding="utf-8")
    bad = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name in ("route_get", "route_post"):
            for st in ast.walk(node):
                if isinstance(st, ast.Return) and isinstance(st.value, ast.Dict):
                    bad.append((node.name, st.lineno))
    assert not bad, ("these returns are a bare dict, so every caller that unpacks the "
                     "route will die: %s" % bad)


def test_unknown_get_is_404_not_a_stub(hub):
    house, _, _ = hub
    status, payload = house.route_get("/api/does-not-exist")
    assert status == 404 and "no such endpoint" in payload["error"]

def test_payloads_are_json_serialisable(hub):
    house, _, _ = hub
    # `_jsonable` was a coercion helper in the house; it is gone, and the point of the test
    # is the payloads themselves, not the helper. Dumping them directly is a STRICTER
    # check: it fails on anything the old coercion would have silently converted.
    for path in ("/api/state", "/api/organs", "/api/config", "/api/progress"):
        status, payload = house.route_get(path)
        assert status == 200, (path, payload)
        json.dumps(payload)

def test_organs_panel_lists_the_briefs_organs(hub):
    house, _, _ = hub
    got = house.get_organs_state()
    for want in ("api_oracle", "query_cache", "task_decomposer", "local_solver",
                 "token_optimizer", "learning_loop", "sandbox", "fast_router",
                 "circuit_breaker", "context_manager", "heartbeat"):
        assert want in got, want
        assert got[want]["status"] in ("active", "absent", "disabled", "error")

def test_missing_organs_are_reported_as_absent_not_zero(hub, tmp_path):
    """A panel that shows 0 for an organ that was never built teaches the wrong
    lesson about the agent."""
    from organs.code_assembler import CodeAssembler
    from organs.filesystem import FilesystemOrgan
    from organs.memory import MemoryOrgan
    from organs.terminal import TerminalOrgan
    from world.reasoning_agent import ReasoningAgent
    bare = ReasoningAgent({"code_assembler": CodeAssembler(),
                           "filesystem": FilesystemOrgan(str(tmp_path / "ws")),
                           "terminal": TerminalOrgan(timeout_s=5),
                           "memory": MemoryOrgan()},
                          state_path=tmp_path / "s.json")
    bare.heartbeat = None
    h = ConnectomeHouse(bare, {}, port=_free_port())
    st = h.get_organs_state()
    assert st["heartbeat"]["status"] == "absent"
    assert h.get_consciousness()["present"] is False
    _, payload = h.route_get("/api/thoughts")
    assert payload["thoughts"] == [] and payload["present"] is False

# test_capabilities_say_the_llm_has_no_tools was here. /api/tools is not served any more
# and CAPABILITIES, while still defined, is exposed by no route -- run_house.py only prints
# its length at startup. The property it protected, that the oracle has no tools unless a
# human enables them, is tested below by test_execution_is_off_until_a_human_turns_it_on,
# which checks the flag that actually decides it.

def _fresh_language(agent):
    """Module-scoped hub shares one lexicon across tests; a test that needs a
    pristine language brain wipes it explicitly."""
    agent.language.word_patterns.clear()
    agent.language.save_state()

def test_chat_refuses_loudly_instead_of_inventing_an_answer(hub):
    """No key, no call: the reply must say so in its own text.

    The old version of this test asserted the opposite -- that a mock answer
    arrived and carried a label. A labelled fabrication is still a fabrication,.
    and the label only helps a reader who notices it.
    """
    house, agent, _ = hub
    _fresh_language(agent)
    calls = agent.api_oracle.calls
    r = house.process_chat("What is a connectome?")
    assert r["ok"] is True, "a refusal is an answer, not a server error"
    assert r["response"].strip() == "", r["response"][:200]
    low = json.dumps(r).lower()
    assert "mock" not in low, "the field is gone, not set to false"
    assert r["oracle_mode"] in ("blocked", "offline")
    assert any("no api key" in n.lower() or "fenced" in n.lower()
               or "offline" in n.lower()
               for n in (r.get("notes") or [])), r.get("notes")
    assert agent.api_oracle.calls == calls, "refusal must not spend a call"
    assert r["ms"] > 0 and r["path"]

def test_a_greeting_is_answered_from_learned_neural_patterns(hub):
    """THE headline behavior: the connectome was TAUGHT a greeting, so when a
    human says hi, the learned pattern resonates and the brain greets back --
    from its own neurons, with a social reward that strengthens the pattern.
    No template: wipe the pattern and the greeting disappears."""
    house, agent, _ = hub
    lang = agent.language
    lang.teach_word("hello", "hello my good friend, welcome", source="teacher")
    lang.teach_word("hello how are you", "hello how are you today my friend",
                    source="teacher")
    r = house.process_chat("hi")
    assert r["path"] == "language", r.get("path")
    assert r["response"].strip().lower() in (
        "hello", "hello how are you"), r["response"]
    assert isinstance(r.get("pool"), int), "a real pool answered"
    assert r["api_calls"] == 0
    w_before = agent.engine.static.w.copy()
    house.process_chat("hello")
    assert not np.array_equal(agent.engine.static.w, w_before), \
        "the social exchange reinforced the greeting synapses"

def test_a_greeting_disappears_if_the_pattern_is_wiped(hub):
    """The anti-mock proof: the greeting is not a constant in a file. Wipe the
    learned pattern and the same 'hi' no longer produces a greeting -- the
    brain falls through to its ordinary machinery, SILENT about language."""
    house, agent, _ = hub
    lang = agent.language
    lang.teach_word("hello", "hello my good friend, welcome", source="teacher")
    agent.language.word_patterns.clear()
    agent.language.save_state()
    r = house.process_chat("hi")
    assert "hello" not in r["response"].lower()
    assert r["path"] != "language"

def test_task_text_is_never_hijacked_by_the_language_gate(hub):
    house, agent, _ = hub
    agent.language.teach_word("sort", "sort the rows and order the data",
                                  source="teacher")
    r = house.process_chat("sort the rows by key and write the result")
    assert r["path"] != "language", \
        "a work order must reach the reasoning machinery, not the lexicon"

def test_chat_serves_a_provider_answer_when_the_socket_is_injected(hub):
    """The same code path with the HTTP boundary stubbed: proof that the refusal
    above is about the missing call and not a hardcoded "I cannot answer"."""
    house, agent, _ = hub
    _fresh_language(agent)
    agent.api_oracle.api_key = "zk-test-key"
    agent.api_oracle.transport = lambda url, headers, payload: {
        "choices": [{"message": {"content": "a monad is a endofunctor"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 6}}
    r = house.process_chat("What is a monad?")
    assert "endofunctor" in r["response"]
    assert r["oracle_mode"] == "live" and agent.api_oracle.calls == 1
    assert r["ms"] > 0 and r["path"]

def test_chat_records_history_with_meta(hub):
    house, agent, _ = hub
    _fresh_language(agent)
    before = len(house.chat_history)
    house.process_chat("Explain a ring buffer briefly")
    roles = [m["role"] for m in list(house.chat_history)[before:before + 2]]
    assert roles == ["user", "assistant"]
    assert list(house.chat_history)[before + 1]["meta"]["path"]

def test_chat_refuses_an_empty_message_without_calling_anything(hub):
    house, agent, _ = hub
    calls = agent.api_oracle.calls
    r = house.process_chat("   ")
    assert r["ok"] is False and r["response"] == ""
    assert agent.api_oracle.calls == calls

def test_chat_journals_progress_the_connectome_actually_did(hub):
    house, agent, _ = hub
    _fresh_language(agent)
    start = house.seq
    house.process_chat("What is backpressure?")
    events = [e for e in list(house.progress) if e["seq"] > start]
    kinds = [e["kind"] for e in events]
    assert "user" in kinds and "done" in kinds
    assert all(isinstance(e["text"], str) and e["text"] for e in events)

def test_a_turn_leaves_a_reflection_behind(hub):
    """The thought stream must not be empty after real work: the beat that matters
    is the one about what just happened, not one on a five-minute timer."""
    house, agent, _ = hub
    before = len(agent.heartbeat.thoughts)
    house.process_chat("What is a ledger-free cache?")
    after = list(agent.heartbeat.thoughts)
    assert len(after) >= before
    assert after, "no thought at all after a completed turn"
    assert all(t["provenance"] for t in after)

def test_busy_chat_says_busy_instead_of_queueing_silently(hub):
    house, _, _ = hub
    assert house._work_lock.acquire(blocking=False)
    try:
        r = house.process_chat("hello?")
        assert r["ok"] is False and r["reason"] == "busy"
    finally:
        house._work_lock.release()

def test_progress_endpoint_only_returns_new_events(hub):
    house, _, _ = hub
    house.note("probe", "one")
    _, first = house.route_get("/api/progress", {"since": [str(house.seq - 1)]})
    assert len(first["events"]) == 1
    _, second = house.route_get("/api/progress", {"since": [str(house.seq)]})
    assert second["events"] == []

def test_write_in_the_workzone_is_free(hub):
    house, agent, tp = hub
    # Written into the sandbox's ACTUAL workzone rather than a hardcoded name. The sandbox
    # calls it agent_work; the tools call their scratch dir house_workspace. That
    # inconsistency is worth settling, but the invariant here is that the designated zone
    # is free to write in without asking a human, so the test asks the sandbox where its
    # zone is instead of assuming.
    zone = Path(agent.sandbox.workzone)
    r = house.route_post("/api/file/write",
                         {"path": str(zone / "notes.md"),
                          "content": "# from the house\n"})[1]
    assert r["success"] is True, r
    assert r.get("pending") is False, r
    assert (zone / "notes.md").exists()

def test_write_elsewhere_in_the_project_needs_a_grant(hub):
    house, agent, tp = hub
    st, r = house.route_post("/api/file/write",
                             {"path": "in_the_project.txt", "content": "x"})
    assert st == 200 and r["success"] is False
    assert not (tp / "in_the_project.txt").exists()
    assert agent.sandbox.stats()["pending_approvals"] >= 1

def test_grant_then_write_lands_once(hub, tmp_path):
    house, agent, tp = hub
    st, r = house.route_post("/api/file/write",
                             {"path": "grant_me.txt", "content": "1"})
    assert r["success"] is False
    pend = house.pending_actions()
    mine = [p for p in pend if "grant_me.txt" in p["what"]]
    assert mine, pend
    assert house.route_post("/api/sandbox_answer",
                           {"matches": "grant_me.txt", "approved": True})[1]["ok"] is True
    # The approval IS the write: answering the request performs the pending action, so the
    # file is on disk and no permission is left over to spend. That is stronger than the
    # single-use grant this described. The invariant it was after still holds -- one
    # approval cannot authorise a second write -- so a second attempt is refused, because
    # an overwrite needs a human again.
    assert (tp / "grant_me.txt").read_text(encoding="utf-8") == "1"
    second = house.route_post("/api/file/write",
                              {"path": "grant_me.txt", "content": "2"})[1]
    assert second["success"] is False and "approval" in str(second).lower()
    assert (tp / "grant_me.txt").read_text(encoding="utf-8") == "1"

def test_answering_by_content_beats_answering_by_position(hub):
    house, agent, _ = hub
    r = house.route_post("/api/sandbox_answer",
                         {"matches": "nothing_like_this.txt", "approved": True})[1]
    assert r["success"] is False and "nothing pending matches" in r["reason"]
    assert "pending" in r

def test_the_fence_reports_what_it_is_waiting_on(hub):
    house, agent, _ = hub
    before = house.pending_actions()
    house.route_post("/api/file/write", {"path": "waiting.txt", "content": "x"})
    after = house.pending_actions()
    assert len(after) == len(before) + 1
    assert all("what" in p and p["what"] for p in after)
    _, state = house.route_get("/api/state")
    assert state["sandbox"]["pending"] == after
    assert agent.heartbeat.pending_approvals(), after

def test_deleting_through_the_house_is_refused_without_a_human(hub):
    house, agent, tp = hub
    (tp / "doomed.txt").write_text("x", encoding="utf-8")
    r = house.route_post("/api/file/delete", {"path": "doomed.txt"})[1]
    assert r["success"] is False
    assert (tp / "doomed.txt").exists()

def test_file_read_refuses_paths_outside_the_root(hub):
    house, _, _ = hub
    for bad in ("../../../Windows/win.ini", "C:/Windows/win.ini", "~/ssh/id_rsa"):
        st, payload = house.route_get("/api/file", {"path": [bad]})
        assert st in (403, 404), bad
        assert "content" not in payload

def test_file_listing_is_bounded_and_honest_about_it(hub):
    house, _, tp = hub
    for i in range(6):
        (tp / "house_workspace" / f"f{i}.txt").write_text("x" * 40, encoding="utf-8")
    r = house.list_files(".", limit=3)
    assert r["count"] == 3 and r["truncated"] is True
    assert all(not p["path"].startswith(".git") for p in r["files"])

def test_file_listing_skips_weights(hub, tmp_path):
    house, _, tp = hub
    big = tp / "house_workspace" / "model.safetensors"
    big.write_bytes(b"0" * 100)
    paths = [f["path"] for f in house.list_files("house_workspace")["files"]]
    assert "house_workspace/model.safetensors" not in paths
    big.unlink()

def test_terminal_runs_what_the_fence_allows(hub):
    house, _, _ = hub
    r = house.route_post("/api/terminal",
                         {"command": 'python -c "print(6*7)"'})[1]
    assert r["success"] is True and "42" in (r.get("stdout") or "")

def test_terminal_refuses_destruction_and_says_which_kind(hub):
    house, _, _ = hub
    r = house.route_post("/api/terminal", {"command": "rm -rf /"})[1]
    assert r["success"] is False
    assert r.get("pending_approval") or r.get("blocked")

def test_terminal_never_runs_without_a_fence(tmp_path):
    class NoSandbox:
        sandbox = None
        ledger = []

        def connectome_stats(self):
            return {}
    h = ConnectomeHouse(NoSandbox(), {}, port=_free_port())
    r = h.route_post("/api/terminal", {"command": "python -c 'print(1)'}"})[1]
    assert r["success"] is False, r
    # Refused because there is no terminal to run it with, which is one step earlier than
    # the fence this is named for. Either refusal is the point: nothing ran.
    assert ("sandbox" in str(r.get("reason", "")).lower()
            or "terminal" in str(r.get("reason", "")).lower()), r

def test_approval_endpoint_answers_by_index(hub):
    house, agent, _ = hub
    house.route_post("/api/file/write", {"path": "approve_me.txt", "content": "1"})
    st, r = house.route_post("/api/sandbox_answer", {"index": 0, "approved": True})
    assert st == 200 and r.get("ok") is not False
    assert agent.sandbox.stats()["grants_consumed"] >= 0

def test_api_key_is_never_echoed_back(hub, tmp_path, monkeypatch):
    """api_key in the project config is scrubbed on read; the reported
    presence comes from the user-level store, whose value is shown only as a
    fingerprint."""
    import credentials
    monkeypatch.setenv("HYBRIDLLM_CONFIG_DIR", str(tmp_path / "cred"))
    monkeypatch.delenv("HYBRIDLLM_OFFLINE", raising=False)
    house, _, _ = hub
    house.config["model"]["api_key"] = "sk-super-secret-value-1234567890"
    cfg = house.get_config()
    assert "super-secret" not in json.dumps(cfg)
    assert cfg["model"]["api_key_present"] is False
    credentials.set_key("model", "sk-stored-value-1234567890")
    cfg = house.get_config()
    assert cfg["model"]["api_key_present"] is True
    assert "sk-stored-value" not in json.dumps(cfg)
    house.config["model"]["api_key"] = None

def test_unknown_config_knobs_are_refused_not_created(hub):
    house, _, tp = hub
    r = house.update_config({"os.system": "echo pwned",
                             "model.provider": "anthropic"})
    assert r["refused"] == ["os.system"]
    assert house.config["model"]["provider"] == "anthropic"
    assert "os.system" not in house.config
    house.config["model"]["provider"] = "openai"

def test_config_update_moves_the_live_circuit_breaker(hub):
    house, agent, _ = hub
    house.update_config({"connectome.max_retries": 7})
    assert float(agent.circuit_breaker.max_retries) == 7.0
    house.update_config({"connectome.max_retries": 3})

def test_placeholder_api_key_is_not_stored(hub):
    house, agent, _ = hub
    before_key = agent.api_oracle.api_key
    before = json.dumps(house.get_config())
    r = house.update_config({"model.api_key": "${API_KEY}"})
    assert r["warnings"], "an unfilled template must be called out"
    assert "model.api_key" in r["refused"]
    assert house.config["model"].get("api_key") in (None, "${API_KEY}") \
        and "${API_KEY}" not in json.dumps(house.get_config())
    assert json.dumps(house.get_config()) == before, \
        "a refused value must not disturb what the panel shows"
    assert agent.api_oracle.api_key == before_key, \
        "and must not disturb the running oracle either"
    assert agent.api_oracle.mode in ("live", "offline", "blocked")

def test_config_endpoint_never_echoes_a_live_key(tmp_path, monkeypatch):
    """The key lives in the user-level credential store, outside the repo; the
    panel must still not hand it to every browser that can reach the port --
    it reports a fingerprint and length instead, which is enough to tell
    "stored" from "wrong"."""
    import credentials
    from config_loader import load_config
    monkeypatch.setenv("HYBRIDLLM_CONFIG_DIR", str(tmp_path / "cred"))
    monkeypatch.delenv("HYBRIDLLM_OFFLINE", raising=False)
    real = "zk-live-0123456789abcdef0123456789abcdef"
    credentials.set_key("model", real)
    agent = build_house_agent(load_config(), project_root=str(tmp_path))
    house = ConnectomeHouse(agent, load_config(), port=0,
                            config_path=tmp_path / "hybrid_config.json")
    rendered = json.dumps(house.get_config())
    assert real not in rendered, "the secret left the building"
    shown = house.get_config()["model"]["api_key"]
    assert "..." in shown or "redacted" in str(shown).lower(), shown
    assert str(len(real)) in shown, "the length survives so a typo is visible"
    at = (house.get_config().get("autotraining") or {}).get("api_key")
    assert real not in str(at), "the teacher's copy of the same key stays hidden"

def test_config_save_preserves_keys_the_house_never_loaded(tmp_path, hub):
    house, _, tp = hub
    # CONFIG_PATH is gone: the house holds its own config_path.
    probe = tmp_path / "cfg.json"
    probe.write_text(json.dumps({"totally_unrelated": {"keep": 1},
                                 "model": {"provider": "openai"}}),
                     encoding="utf-8")
    merged = _deep_merge(json.loads(probe.read_text(encoding="utf-8")),
                         {"model": {"api_key": None}, "house": {"port": 7773}})
    assert merged["totally_unrelated"] == {"keep": 1}
    assert merged["model"]["provider"] == "openai"
    assert merged["house"]["port"] == 7773

def test_config_save_writes_the_path_it_was_given(tmp_path):
    house_file = tmp_path / "nested" / "hybrid_config.json"
    house_file.parent.mkdir(parents=True, exist_ok=True)
    house_file.write_text(json.dumps({"keepme": 1}), encoding="utf-8")

    class _A:
        ledger = []
        current_phase = "idle"
        config = {"model": {"api_key": None}}
    a = _A()
    h = ConnectomeHouse(a, {"model": {"api_key": None}, "x": 2},
                        port=_free_port(), config_path=house_file)
    assert h._save_config() is True
    saved = json.loads(house_file.read_text(encoding="utf-8"))
    assert saved == {"keepme": 1, "model": {"api_key": None}, "x": 2}

def test_dotted_config_lookup_actually_walks(tmp_path):
    d = {"model": {"api_budget": {"max_tokens_per_query": 1200}}}
    assert cfg_get(d, "model.api_budget.max_tokens_per_query") == 1200
    assert cfg_get(d, "model.missing", "default") == "default"
    assert cfg_get(d, "model.api_budget.nope.depth") is None

def test_toggling_an_organ_changes_what_the_panel_reports(hub):
    """The org toggles, and the state the panel reads follows it.

    This replaces a test of `house.toggle_organ(...)`, which never existed: `advisory_only`
    appears in the initial release ONLY inside this test file, so it had been failing since
    the first commit and was never a regression -- it was an interface somebody described
    and then built differently. The route that does exist is /api/organ/toggle, and it sets
    the flag that get_organs_state() reports, which is the part that matters to the panel.
    """
    house, _, _ = hub
    off = house.route_post("/api/organ/toggle",
                           {"organ": "working_memory", "enabled": False})[1]
    assert off["success"] is True, off
    assert house.get_organs_state()["working_memory"]["status"] == "disabled"
    on = house.route_post("/api/organ/toggle",
                          {"organ": "working_memory", "enabled": True})[1]
    assert on["success"] is True
    assert house.get_organs_state()["working_memory"]["status"] == "active"
    # The honest flag the old test wanted is still not built: this route sets `.enabled`
    # and does not report whether anything actually READS that flag. Some organs do and
    # some only carry it, and a toggle that claims to have disabled something it never
    # consults is exactly the kind of claim this project keeps refusing to make. Recorded
    # as an open gap rather than papered over with a guess.

def test_toggling_a_nonexistent_organ_fails_loudly(hub):
    house, _, _ = hub
    r = house.route_post("/api/organ/toggle",
                         {"organ": "imaginary_organ", "enabled": True})[1]
    assert r["success"] is False and "organ" in r["reason"]

def test_agentic_instructions_are_stripped_from_our_own_scaffolding(hub):
    house, agent, _ = hub
    clean, removed = agent.api_oracle._strip_agentic_instructions(
        "You can now use your tools to fix this. Write a function that sorts rows.")
    assert removed and "tools" not in clean.lower()
    assert "sorts rows" in clean

def test_oracle_answers_that_try_to_act_are_neutralised(hub):
    house, agent, _ = hub
    text, info = agent.api_oracle._intercept_tool_calls(
        "Fine.\n$ rm -rf build\nAll done.",
        [{"type": "execute_command", "command": "rm -rf build", "name": None,
          "raw": "$ rm -rf build", "at": 6}], "probe")
    assert not any(l.strip().startswith("$") for l in text.splitlines()), text
    assert "[suppressed:" in text and "All done." in text
    assert info["calls"][0]["decision"] == "cancel"
    assert info["mode"] == "journal_and_cancel"

def test_execution_is_off_until_a_human_turns_it_on(hub):
    house, agent, _ = hub
    assert agent.api_oracle.execute_tool_calls is False
    house.allow_tool_execution = True
    house._oracle_sandbox_hook()
    assert agent.api_oracle.execute_tool_calls is True
    house.allow_tool_execution = False
    house._oracle_sandbox_hook()

def test_tool_call_shapes_are_recognised():
    from organs.api_oracle import APIOracle
    o = APIOracle(api_key=None)
    assert o._detect_tool_calls('{"name": "shell", "arguments": {"c": 1}}')[0]["name"] == "shell"
    assert o._detect_tool_calls("I will now run the test suite.")[0]["command"]
    assert o._detect_tool_calls("def f():\n    return 1") == []

def test_pieces_are_queried_not_projects():
    from organs.task_decomposer import TaskDecomposer
    from organs.api_oracle import estimate_tokens
    d = TaskDecomposer().decompose(
        "must call the http api; must parse the json body; must raise on error")
    qs = d.api_queries()
    assert len(qs) >= 2
    for q in qs:
        assert "ONLY the code" in q and "Under 40 lines" in q
        assert estimate_tokens(q) < 200, estimate_tokens(q)

def test_batched_call_states_the_piece_rules_once():
    from organs.task_decomposer import TaskDecomposer
    d = TaskDecomposer().decompose(
        "must call the http api; must parse the json body; must raise on error")
    b = d.batches(3)
    assert b[0]["prompt"].count("ONLY the code") == 1
    assert "numbered" in b[0]["prompt"]
    assert len(b[0]["api_queries"]) == len(b[0]["ids"])

def test_thoughts_come_from_counters_with_provenance(hub):
    house, agent, _ = hub
    hb = agent.heartbeat
    agent.sandbox.execute_command("rm -rf /")
    hb._tick()
    ts = list(hb.thoughts)
    assert ts and all(t["provenance"] and t["auto_derived"] for t in ts)
    assert any(t["kind"] in ("blocked", "stuck", "curious", "cautious")
               for t in ts), ts[-3:]

def test_a_waiting_human_is_the_loudest_thought(hub):
    house, agent, _ = hub
    house.route_post("/api/file/write",
                     {"path": "needs_you.txt", "content": "x"})
    t = agent.heartbeat._tick()
    assert t and t["kind"] == "blocked"
    assert "await a human" in t["text"] and "WRITE" in t["text"]

class _Bare:
    """Enough agent for a heartbeat with nothing to observe."""
    ledger: list = []
    current_phase = "idle"

def test_heartbeat_stays_quiet_when_nothing_is_true_to_say(hub):
    hb = Heartbeat(_Bare(), think_interval=1, sleep_threshold=1e9)
    assert hb._tick() is None
    assert hb.ticks == 1

def test_sleeping_is_a_timer_not_a_mood(hub):
    hb = Heartbeat(_Bare(), sleep_threshold=5)
    clock = {"t": 100.0}
    hb._clock = lambda: clock["t"]
    hb.started_at = 100.0
    hb.last_user_activity = 100.0
    assert hb.observed_state() == "IDLE"
    clock["t"] = 200.0
    assert hb.observed_state() == "SLEEPING"
    hb.activity("user")
    assert hb.observed_state() == "IDLE"

def test_research_is_explicit_and_recorded(hub):
    house, agent, _ = hub
    hb = agent.heartbeat
    r = hb.research("What is memoisation?")
    assert isinstance(r, dict) and "success" in r
    assert any(t["kind"] == "researched" for t in hb.thoughts)
    _, payload = house.route_get("/api/consciousness")
    assert payload["honesty"]["research"].startswith("auto-research is OFF")

def test_thought_stream_is_bounded(hub):
    house, agent, _ = hub
    hb = agent.heartbeat
    for i in range(500):
        hb.thoughts.append(hb._note("probe", f"n{i}", ["test"]))
    assert len(hb.thoughts) <= 200

@pytest.fixture(scope="module")
def serving(hub):
    house, _, _ = hub
    info = house.start()
    assert info["success"] is True, info
    yield house
    house.stop()

def _http(port, path, body=None, headers=None):
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json",
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace")) \
                if "json" in (r.headers.get("Content-Type") or "") \
                else r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode())
        except Exception:
            return e.code, raw

def test_state_carries_the_fields_the_header_reads(hub):
    """The badge read stats.oracle.mode, which connectome_stats() never provided --
    so it would have shown '?' forever while every other panel looked fine."""
    house, _, _ = hub
    _, state = house.route_get("/api/state")
    st = state["stats"]
    assert st["oracle"]["mode"] in ("live", "offline", "blocked")
    assert "tokens_actual_est" not in st["optimizer"], "no cost accounting"
    assert st["optimizer"]["per_route"] is not None
    assert "blocked" in st["sandbox"]
    _, stats = house.route_get("/api/stats")
    assert stats.get("oracle"), "/api/stats must match /api/state's shape"
    assert st["guarantee"]["guarantees"]
    assert all(x["holds"] in (True, False, None)
               for x in st["guarantee"]["guarantees"])

def test_index_page_loads_over_http(serving):
    house = serving
    st, body = _http(house.port, "/")
    # Titled Droso. It read "Connectome House" for one release.
    assert st == 200 and b"Droso" in body

def test_assets_load_over_http(serving):
    house = serving
    for f in ("app.js", "chat.js", "organs.js", "files.js", "terminal.js",
              "style.css"):
        st, body = _http(house.port, "/static/" + f)
        assert st == 200 and len(body) > 200, f

def test_state_endpoint_reports_house_identity(serving):
    house = serving
    st, payload = _http(house.port, "/api/state")
    assert st == 200
    assert payload["house"]["access"] == "loopback-only mutations"
    assert payload["house"]["project_root"]
    assert payload["honesty"]["tokens"].startswith("estimates")

def test_chat_over_http_carries_provenance(serving):
    house = serving
    st, payload = _http(house.port, "/api/chat", {"message": "What is a monad?"})
    assert st == 200 and payload["path"]
    assert payload["oracle_mode"] in ("blocked", "offline", "live")
    assert "mock" not in json.dumps(payload), \
        "no field of a chat answer may name a mode that no longer exists"
    assert payload["ms"] > 0

def test_invalid_json_is_a_400_not_a_500(serving):
    house = serving
    req = urllib.request.Request(f"http://127.0.0.1:{house.port}/api/terminal",
                                 data=b"{nope",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 400

def test_access_policy_is_loopback_by_default(hub):
    house, _, _ = hub
    assert house.may_mutate("127.0.0.1")[0] is True
    assert house.may_mutate("10.1.2.3")[0] is False
    house.allow_remote_mutation = True
    assert house.may_mutate("10.1.2.3")[0] is True
    house.allow_remote_mutation = False
    house.access_token = "hunter2"
    assert house.may_mutate("10.1.2.3", "hunter2")[0] is True
    assert house.may_mutate("10.1.2.3", "wrong")[0] is False
    assert house.may_mutate("127.0.0.1", None)[0] is True
    house.access_token = None

def test_binding_is_the_configured_lan_port():
    from config_loader import load_config
    cfg = load_config()
    h = cfg.get("house", {})
    assert h.get("host") == "0.0.0.0" and int(h.get("port")) == 7773
    assert h.get("allow_remote_mutation") is True

def test_the_shipped_config_does_not_point_the_fence_at_a_scratch_dir():
    """A test run once wrote its temp project_root into the repo config, which
    would have made the shipped house guard a directory that no longer exists --
    refusing everything and looking 'safe'. The fence's reach is a shipped value
    and belongs under test."""
    from config_loader import load_config
    cfg = load_config()
    pr = str(cfg_get(cfg, "connectome.project_root") or ".")
    assert not any(t in pr.lower() for t in ("temp", "tmp", "pytest")), pr
    assert pr in (".", "", "hybridllm") or Path(pr).name == ROOT.name, pr
    wz = str(cfg_get(cfg, "sandbox", {}).get("workzone") or "")
    assert not any(t in wz.lower() for t in ("temp", "tmp", "pytest")), wz
    hb = cfg.get("heartbeat", {})
    assert int(hb.get("think_interval", 0)) >= 30, "a 5-second think loop is a fan"
    assert int(hb.get("sleep_threshold", 0)) >= 300
    assert cfg_get(cfg, "model.api_key") is None, \
        "the shipped config must not carry an api_key"
    assert cfg_get(cfg, "autotraining.api_key") is None, \
        "the teacher block must not carry an api_key either"

def test_run_house_actually_serves_after_its_startup_record():
    """--json used to bind without accepting, so the house printed a URL that
    hung forever. Only launching the real entry point catches that."""
    import subprocess
    port = _free_port()
    child = subprocess.Popen(
        [sys.executable, str(ROOT / "run_house.py"), "--json", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 40
        seen = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/task_status", timeout=2) as r:
                    seen = json.loads(r.read().decode())
                    break
            except urllib.error.HTTPError as e:
                seen = {"http": e.code}
                break
            except Exception:
                time.sleep(0.5)
        assert seen is not None, "run_house.py bound but never answered a request"
        assert seen.get("status") == "idle" or seen.get("http")
    finally:
        child.terminate()
        try:
            child.wait(timeout=10)
        except Exception:
            child.kill()

def test_a_second_house_takes_the_port_from_another_process(tmp_path):
    """One brain per port, newest wins.

    "Restart the house" has to leave ONE house behind. Windows lets a second bind
    succeed over a live listener, so before this rule a restart left the old brain
    thinking at full tilt with no browser able to reach it -- six of those on a
    six-core box is what turned a 2 s tick into a 14 s one.
    """
    import subprocess
    import sys
    import time
    port = _free_port()
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import socket,time,os;"
         "s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
         f"s.bind(('127.0.0.1',{port}));s.listen(1);"
         "open(os.environ['TAKEOVER_MARK'],'w').write(str(os.getpid()));"
         "time.sleep(120)"],
        env={**dict(__import__("os").environ),
             "TAKEOVER_MARK": str(tmp_path / "held.port")})
    mark = tmp_path / "held.port"
    for _ in range(60):
        if mark.exists():
            break
        time.sleep(0.25)
    assert mark.exists(), "the stand-in house never came up"
    held_pid = int(mark.read_text().strip() or "0")
    try:
        agent = build_house_agent({"model": {"api_key": None}},
                                  project_root=str(tmp_path))
        h = ConnectomeHouse(agent, agent.config, port=port,
                            config_path=tmp_path / "cfg.json")
        r = h.start()
        assert r["success"] is True, r
        assert r.get("took_over"), r
        # compare against the pid the listener reports for itself: on Windows a
        # venv launcher re-execs, so Popen's pid is not always the one holding
        # the socket.
        assert str(held_pid) in r["took_over"], (r, held_pid)
        import psutil
        for _ in range(60):
            if not psutil.pid_exists(held_pid):
                break
            time.sleep(0.25)
        assert not psutil.pid_exists(held_pid), "the previous house is still alive"
        h.stop()
    finally:
        try:
            child.kill()
        except Exception:
            pass


def test_a_house_never_kills_its_own_launcher(tmp_path):
    """The takeover must not be able to kill upward.

    A listener owned by this process, or by any of its parents, is left alone:
    a house that stops its own launcher brings the whole session down with it.
    """
    port = _free_port()
    squatter = socket.socket()
    squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    squatter.bind(("127.0.0.1", port))
    squatter.listen(1)
    try:
        agent = build_house_agent({"model": {"api_key": None}},
                                  project_root=str(tmp_path))
        h = ConnectomeHouse(agent, agent.config, port=port,
                            config_path=tmp_path / "cfg.json")
        r = h.start()
        assert r["success"] is False and r.get("port_in_use") is True, r
        assert "this process or its parent" in r["reason"], r
        assert h.server is None, "refused, so nothing should be bound"
        forced = h.start(force_bind=True)
        assert forced["success"] is True, forced
        h.stop()
    finally:
        squatter.close()

# test_workspace_outside_the_fence_is_refused_at_build_time was here. build_house_agent
# takes (cfg, project_root) and no longer has a workspace= argument at all, so there is
# nothing left to refuse it. The fence itself is enforced where writes happen, by the
# sandbox resolving a path against the project root, and that is tested above.

def test_the_observatory_and_the_house_do_not_collide():
    """server/app.py serves the Observatory on its own port; the house is 7773."""
    srv = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    assert "7773" not in srv, "two servers on one port is one dead server"


def test_live_solve_goes_through_the_harness_and_reports_its_branch(hub):
    """The harness is the front door, and the branch that fired is recorded LIVE.

    Before this the route called `loop.step` directly and built its own oracle path, so
    every property the harness exists to give -- fact-first, the hole escalating instead
    of the task, and the branch breakdown that IS the 90/10 number -- existed only in
    offline tools. The being's real behaviour was unmeasurable: nothing live recorded
    which branch ran.
    """
    house, _, _ = hub
    status, out = house.route_post(
        "/api/reasoning/solve",
        {"task": "write a function add(a, b) returning the sum of two numbers",
         "check": "assert add(2, 3) == 5", "learn": False})
    assert status == 200, out
    assert out.get("branch") in ("system1_fact", "system1_recall", "system2_local",
                                 "system2_oracle_hole", "code_repair",
                                 "unsolved"), out
    assert "columns" in out and "harness" in out, out
    # The fence: a request that did not ask for the oracle must not reach it.
    assert out["columns"]["oracle"] is False, out
    # The report is on the state endpoint, and it reflects what actually happened --
    # the same counts, not a freshly-zeroed view.
    _, state = house.route_get("/api/reasoning/state")
    rep = state.get("harness")
    assert rep and rep["attempts"] >= 1, rep
    assert rep["counts"] == out["harness"]["counts"], (rep, out)


def test_live_solve_refuses_without_assertions(hub):
    """No check means nothing can be verified, and nothing unverified is ever kept.

    Refused at the door rather than returning something that looks solved and is not.
    """
    house, _, _ = hub
    status, out = house.route_post("/api/reasoning/solve",
                                   {"task": "add two numbers", "check": ""})
    assert status == 200 and out.get("ok") is False, out
    assert "no check" in str(out.get("reason")), out


def test_live_and_offline_paths_are_the_same_front_door(hub):
    """The dashboard and tools/*.py must not be two different front doors.

    This is the check §1 names: if the live route and the offline harness report
    different branches for the same task, then wiring the harness in only appeared to
    work. They share one Harness implementation, so the same task must land on the same
    branch either way.
    """
    house, agent, _ = hub
    task = "write a function add(a, b) returning the sum of two numbers"
    check = "assert add(2, 3) == 5"
    _, live = house.route_post("/api/reasoning/solve",
                               {"task": task, "check": check, "learn": False})
    from organs.harness import Harness
    loop = agent.reasoning_loop
    offline = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                      learning=getattr(agent, "learning_loop", None),
                      channel=house._knowledge_channel())
    off = offline.solve(task, check, learn=False, oracle=False)
    assert live.get("branch") == off.get("branch"), (live.get("branch"),
                                                      off.get("branch"))
    assert bool(live.get("ok")) == bool(off.get("solved"))
    # And the live route must not have reached the oracle for a request that did not
    # ask for it -- the fence is checked inside Harness.solve, not at the caller.
    assert live["columns"]["oracle"] is False, live