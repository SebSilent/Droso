#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ACTIVE_DIRS = ("organs", "world", "server", "core", "connectome")
ARCHIVED_MODULES = {
    "moe_expert_streamer", "weight_reader", "dense_expert_loader", "moe_mlp",
    "attention_engine", "forward_kernels", "token_pipeline",
    "generation_engine", "kv_cache", "moe_knowledge_library", "moe_generator",
    "mock_bf16_model", "gpu_expert_streamer", "nvfp4_fast",
}
PATH_A_ORGANS = {"api_oracle": "APIOracle", "query_cache": "QueryCache",
                 "task_decomposer": "TaskDecomposer",
                 "local_solver": "LocalSolver",
                 "token_optimizer": "TokenOptimizer",
                 "learning_loop": "LearningLoop"}
BAD_SUBSTRINGS = ("models/qwen3.8-flash-next", "organs/moe_expert_streamer",
                  "organs/weight_reader", "organs/attention_engine",
                  "organs/generation_engine", "exocortex/moe_experts",
                  ".safetensors", "nvfp4", "bf16", "kernels/nvfp4_fused")
EXEMPT = {"organs/safetensors_library.py", "organs/exocortex.py",
          "organs/layer_expertise.py", "organs/ffn_expertise.py",
          "organs/error_expertise.py", "organs/sparse_inference.py",
          "organs/streaming_inference.py"}

def active_files():
    for d in ACTIVE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p

def _imported_names(tree) -> list[tuple[str, int]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.module, node.lineno))
            for a in node.names:
                out.append((f"{node.module}.{a.name}", node.lineno))
        elif isinstance(node, ast.Import):
            for a in node.names:
                out.append((a.name, node.lineno))
    return out

def _strings(tree) -> list[tuple[str, int]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.value, getattr(node, "lineno", 0)))
    return out

def check_no_archived_imports():
    bad = []
    for p in active_files():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad.append(f"{p.relative_to(ROOT)}: syntax error {e}")
            continue
        for mod, line in _imported_names(tree):
            leaf = mod.rsplit(".", 1)[-1]
            if leaf in ARCHIVED_MODULES or "organs_archive" in mod or \
                    "tools_archive" in mod:
                bad.append(f"{p.relative_to(ROOT)}:{line}: imports {mod}")
    return bad

def check_no_dynamic_loads():
    bad = []
    for p in active_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for s, line in _strings(tree):
            leaf = str(s).replace("/", ".").rsplit(".", 1)[-1]
            if leaf in ARCHIVED_MODULES and ("organs" in s or "import" in s):
                bad.append(f"{p.relative_to(ROOT)}:{line}: loads {s}")
    return bad

def check_no_local_model_paths():
    bad = []
    for p in active_files():
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel in EXEMPT:
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for s, line in _strings(tree):
            low = str(s).lower()
            for pat in BAD_SUBSTRINGS:
                if pat.lower() not in low:
                    continue
                if pat in EXTENSION_ONLY and not _path_shaped(low):
                    break
                bad.append(f"{rel}:{line}: string {s[:60]!r} mentions "
                           f"{pat!r}")
                break
    return bad

EXTENSION_ONLY = {".safetensors"}

def _path_shaped(s: str) -> bool:
    return any(sep in s for sep in ("/", "\\", ":")) or s.startswith("~")

def check_organs_import():
    import importlib
    bad = []
    for p in sorted((ROOT / "organs").glob("*.py")):
        if p.name == "__init__.py":
            continue
        mod = f"organs.{p.stem}"
        try:
            importlib.import_module(mod)
        except Exception as e:
            bad.append(f"{mod}: {type(e).__name__}: {e}")
    return bad

def check_agent_wiring():
    """Construct the Path A agent and make it answer something, with no model
    file and no API key. Anything less would certify the imports, not the
    architecture."""
    notes = []
    try:
        from world.reasoning_agent import ReasoningAgent
    except Exception as e:
        return [f"import failed: {type(e).__name__}: {e}"], notes
    organs = {}
    try:
        import tempfile
        from organs.code_assembler import CodeAssembler
        from organs.filesystem import FilesystemOrgan
        from organs.memory import MemoryOrgan
        from organs.terminal import TerminalOrgan
        organs = {"code_assembler": CodeAssembler(),
                  "filesystem": FilesystemOrgan(tempfile.mkdtemp()),
                  "terminal": TerminalOrgan(timeout_s=10),
                  "memory": MemoryOrgan()}
        ag = ReasoningAgent(organs, state_path=Path(tempfile.mkdtemp()) /
                            "state.json")
    except Exception as e:
        return [f"ReasoningAgent(...) raised {type(e).__name__}: {e}"], notes
    bad = []
    for attr, clsname in (("api_oracle", "APIOracle"),
                          ("query_cache", "QueryCache"),
                          ("local_solver", "LocalSolver"),
                          ("decomposer", "TaskDecomposer"),
                          ("learning_loop", "LearningLoop"),
                          ("token_optimizer", "TokenOptimizer")):
        got = getattr(ag, attr, None)
        if got is None:
            bad.append(f"agent.{attr} is None (organ not initialised)")
        elif type(got).__name__ != clsname:
            bad.append(f"agent.{attr} is {type(got).__name__}, expected "
                       f"{clsname}")
    if ag.api_oracle is not None:
        ag.api_oracle.api_key = None
    try:
        r = ag.ask_api("Sort a list of dicts by a key in python")
        notes.append({"route": r.get("route"), "api_calls": r.get("api_calls"),
                      "tokens_used": r.get("tokens_used"),
                      "oracle_mode": (ag.api_oracle.mode if ag.api_oracle
                                      else "off"),
                      "reasons": r.get("reasons") or []})
        if r.get("route") not in ("learned", "local", "cache", "none"):
            bad.append(f"keyless oracle produced route {r.get('route')!r}")
        if r.get("route") == "none" and not (r.get("reasons") or []):
            bad.append("refusal carried no reason: an empty 'none' is invisible")
        for k in ("mock", "synthetic"):
            if k in json.dumps(r, default=str).lower():
                bad.append(f"answer record mentions {k!r}")
    except Exception as e:
        bad.append(f"ask_api raised {type(e).__name__}: {e}")
    import inspect
    import organs.api_oracle as ao
    src = inspect.getsource(ao)
    for gone in ("allow_mock", "_mock_answer", "serve_mock", 'mode = "mock"',
                 "mock_calls"):
        if gone in src:
            bad.append(f"organs/api_oracle.py still contains {gone!r}")
    if "NoAPIKeyError" not in src:
        bad.append("api_oracle has no NoAPIKeyError: nothing raises when it "
                   "cannot ask")
    notes.append({"oracle_constructors": sorted(
        p for p in __import__("inspect").signature(
            ao.APIOracle).parameters)}),
    return bad, notes

def check_safety_layer():
    """The 'always better' layer must be present AND armed.

    An organ that exists but is not wired into the agent is decoration, so this
    checks the live agent's instances, then asks each layer to prove its own
    headline claim with the cheapest real test available.
    """
    bad, notes = [], []
    import tempfile
    from organs.code_assembler import CodeAssembler
    from organs.filesystem import FilesystemOrgan
    from organs.memory import MemoryOrgan
    from organs.sandbox import Sandbox
    from organs.terminal import TerminalOrgan
    from organs.fast_router import FastRouter
    from organs.circuit_breaker import CircuitBreaker
    from organs.context_manager import ContextManager
    from world.reasoning_agent import ReasoningAgent
    tp = Path(tempfile.mkdtemp())
    try:
        ag = ReasoningAgent({"code_assembler": CodeAssembler(),
                             "filesystem": FilesystemOrgan(str(tp / "sb")),
                             "terminal": TerminalOrgan(timeout_s=10),
                             "memory": MemoryOrgan()},
                            state_path=tp / "state.json")
    except Exception as e:
        return [f"ReasoningAgent(...) raised {type(e).__name__}: {e}"], notes
    want = {"sandbox": Sandbox, "fast_router": FastRouter,
            "circuit_breaker": CircuitBreaker,
            "context_manager": ContextManager}
    for attr, cls in want.items():
        got = getattr(ag, attr, None)
        if not isinstance(got, cls):
            bad.append(f"agent.{attr} is {type(got).__name__}, expected {cls.__name__}")
    if bad:
        return bad, notes
    st = ag.sandbox.self_test()
    if st.get("passed") is not True:
        bad.append("sandbox self_test failed: " +
                   str({k: v for k, v in st.items() if v is not True})[:220])
    if ag.sandbox.check_command("rm -rf /")["allow"]:
        bad.append("sandbox allows rm -rf /")
    if ag.sandbox.check_command("python _rt_check.py")["allow"] is not True:
        bad.append("sandbox blocks the agent's own test runner")
    for risky in ("rename x and test it", "must parse csv; must handle quotes"):
        if ag.fast_router.route(risky)["path"] != "reasoning_loop":
            bad.append(f"fast router bypasses verification for {risky!r}")
    cb = CircuitBreaker(max_retries=2, repeat_limit=99)
    cb.begin_task("probe")
    cb.record_attempt(1, error="a")
    if cb.record_attempt(1, error="b")["action"] != "escalate":
        bad.append("circuit breaker did not trip at its retry limit")
    cm = ContextManager(max_context_tokens=200, response_reserve=50)
    o = cm.build("task", relevant_files=[("big.py", "x = 1\n" * 5000)],
                 previous_attempts=[{"error": "boom"}] * 9)
    if o["tokens_est"] > cm.budget:
        bad.append(f"context manager exceeded its own budget "
                   f"({o['tokens_est']} > {cm.budget})")
    g = ag.always_better()
    if "unmeasured" not in g["verdict"] and g["unmeasured"]:
        bad.append("guarantee verdict hides unmeasured rows")
    if not g["limits"]:
        bad.append("guarantee reported without its limits")
    notes.append({"sandbox_root": str(ag.sandbox.project_root),
                  "workzone": str(ag.sandbox.workzone),
                  "network": ag.sandbox.allow_network,
                  "guarantee": {x["id"]: x["holds"] for x in g["guarantees"]}})
    return bad, notes

def check_house():
    """The house must be openable, fenced, and honest about who may knock.

    Deliberately no socket: this script runs on a box that may already be
    serving, and a verifier that steals a port is a verifier people stop running.
    """
    bad, notes = [], []
    import tempfile
    from world.connectome_house import ConnectomeHouse, build_house_agent
    tp = Path(tempfile.mkdtemp())
    try:
        # No project_root means the repo root, which means the being's own language
        # state path -- so this verifier could save over his memory exactly as
        # curriculum_run did. Reading his state to check the architecture is fine;
        # writing it is not.
        agent = build_house_agent({"model": {"api_key": None}},
                                  project_root=str(tp))
        house = ConnectomeHouse(agent, agent.config,
                                port=0, config_path=tp / "cfg.json")
    except Exception as e:
        return [f"build_house_agent/ConnectomeHouse raised {type(e).__name__}: {e}"], notes
    html = (house.house_dir / "index.html")
    if not html.exists():
        bad.append("world/house/index.html is missing")
    else:
        import re
        refs = re.findall(r'(?:src|href)="(/static/[^"]+)"',
                          html.read_text(encoding="utf-8"))
        missing = [r for r in refs
                   if house._safe_static(r.split("?")[0].lstrip("/")) is None]
        if missing:
            bad.append(f"index.html references missing assets: {missing[:4]}")
    for sneaky in ("../config/hybrid_config.json", "static/../../run.py", ""):
        if house._safe_static(sneaky) is not None:
            bad.append(f"static serving escapes the house dir via {sneaky!r}")
    routes = ["/api/state", "/api/organs", "/api/consciousness",
              "/api/procedures", "/api/patterns", "/api/cache", "/api/config",
              "/api/stats", "/api/tools", "/api/progress", "/api/thoughts",
              "/api/learning_history", "/api/guarantee", "/api/ledger",
              "/api/chat_history", "/api/task_status", "/api/file"]
    silent = []
    for r in routes:
        status, payload = house.route_get(r, {"path": ["__none__"]})
        if status != 200 and r != "/api/file":
            silent.append(f"{r} -> {status}")
    if silent:
        bad.append("endpoints not answering: " + ", ".join(silent[:5]))
    if house.may_mutate("10.0.0.9")[0]:
        bad.append("a remote peer may mutate state by default")
    if not house.may_mutate("127.0.0.1")[0]:
        bad.append("loopback cannot mutate: the house could not be used")
    o = getattr(agent, "api_oracle", None)
    if o is None or getattr(o, "sandbox", None) is None:
        bad.append("the oracle is not attached to the fence, so interception "
                   "has no policy to consult")
    if getattr(o, "execute_tool_calls", True):
        bad.append("tool execution is on by default; a model's command would run "
                   "without a human opting in")
    _, tools = house.route_get("/api/tools")
    if tools.get("llm_has_tools") is not False:
        bad.append("the capability catalogue claims the LLM has tools")
    st, conf = house.route_get("/api/config")
    from credentials import get_key
    if get_key("model"):
        bad.append("/api/config echoed an API key")
    _, cons = house.route_get("/api/consciousness")
    if cons.get("state") not in ("IDLE", "ACTIVE", "THINKING", "RESEARCHING",
                                 "SLEEPING"):
        bad.append(f"consciousness state is {cons.get('state')!r}")
    notes.append({"assets": len(list((house.house_dir / "static").glob("*"))),
                  "organs": len(house.get_organs_state()),
                  "access": house.access_mode(),
                  "oracle_mode": getattr(o, "mode", "?")})
    house.stop()
    return bad, notes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    checks = [("no imports of archived organs", check_no_archived_imports),
              ("no dynamic loads of archived organs", check_no_dynamic_loads),
              ("no local-model paths in active code", check_no_local_model_paths),
              ("every active organ imports standalone", check_organs_import),
              ("safety layer present and armed", check_safety_layer),
              ("connectome house is wired and fenced", check_house),
              ("reasoning agent wired for Path A and answering", None)]
    report, ok = {}, True
    for name, fn in checks:
        if fn is None:
            bad, notes = check_agent_wiring()
        else:
            res = fn()
            bad, notes = res if isinstance(res, tuple) else (res, [])
        report[name] = {"ok": not bad, "violations": bad[:24],
                        "count": len(bad), "notes": notes}
        ok = ok and not bad
    archives = [d for d in ("organs_archive", "tools_archive", "tests_archive",
                            "kernels_archive") if (ROOT / d).exists()]
    report["archive folders present"] = {
        "ok": len(archives) == 4, "violations": [],
        "count": 0, "notes": [{"dir": a, "files": len(
            list((ROOT / a).glob("*.py")))} for a in archives]}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, r in report.items():
            mark = "ok  " if r["ok"] else "FAIL"
            extra = ""
            if name == "archive folders present":
                extra = " | " + ", ".join(
                    f"{n['dir']}={n['files']} py" for n in r["notes"])
            print(f"  [{mark}] {name}{extra}")
            for n in r.get("notes") or []:
                if name.startswith("reasoning agent"):
                    print(f"         agent: {json.dumps(n)[:200]}")
            for v in r["violations"]:
                print(f"         - {v}")
        print("\nverdict:", "ARCHITECTURE CLEAN" if ok else
              "PHANTOM REFERENCES REMAIN")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()