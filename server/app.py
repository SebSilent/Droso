
import asyncio
import json
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.action_space import ACTION_INDEX, ACTIONS

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

def create_app(agent) -> FastAPI:
    app = FastAPI(title="HybridLLM Observatory")
    state_lock = threading.Lock()

    class TaskIn(BaseModel):
        text: str
        expected_action: str | None = None

    class StepIn(BaseModel):
        n: int = 1

    class RunIn(BaseModel):
        on: bool

    _exo: dict = {}

    def exo_agent():
        if "a" not in _exo:
            _exo["a"] = None
            _exo["err"] = ("removed: the grown-colony fleet was archived to "
                           "legacy_archive/; the brain is the BANC carve")
        return _exo["a"]

    @app.get("/api/exo_state")
    def exo_state():
        a = exo_agent()
        return a.state_snapshot() if a else {"error": _exo.get("err", "unavailable")}

    @app.post("/api/exo_step")
    def exo_step(payload: dict):
        a = exo_agent()
        if a is None:
            return {"ok": False}
        n = min(max(int(payload.get("n", 1)), 1), 25)
        done = [a.step() for _ in range(n)]
        return {"ok": True, "steps": sum(1 for d in done if d)}

    @app.post("/api/exo_task")
    def exo_task(payload: dict):
        a = exo_agent()
        if a is None:
            return {"ok": False}
        a.inject(str(payload.get("text", "")))
        return {"ok": True}

    import re as _re
    _SAFE = _re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_. /-]{0,120}$")

    def _exo_a():
        a = exo_agent()
        if a is None:
            raise HTTPException(404, "exocortex unavailable")
        return a

    def _in_dir(root: Path, name: str) -> Path:
        if not _SAFE.match(name) or ".." in name:
            raise HTTPException(400, "bad file name")
        p = (root / name).resolve()
        if root.resolve() not in p.parents or not p.is_file():
            raise HTTPException(404, "no such file")
        return p

    @app.get("/api/exo_files")
    def exo_files():
        a = _exo_a()
        sandbox = Path(a.world.sandbox)
        files = []
        if sandbox.is_dir():
            for f in sorted(sandbox.iterdir()):
                if f.is_file():
                    st = f.stat()
                    files.append({"name": f.name, "size": st.st_size,
                                  "mtime": st.st_mtime})
        return {"sandbox": sandbox.name, "files": files,
                "recent_writes": [
                    {k: w[k] for k in ("path", "n_chars", "ts", "truncated")}
                    for w in list(a.filesystem.journal)[-12:]],
                "write_log": list(a.filesystem.journal)[-12:],
                "artifacts": exo_artifact_list()}

    def exo_artifact_list() -> list[dict]:
        root = FRONTEND.parent.parent / "exocortex"
        out = []
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix in (".json", ".md", ".db", ".txt"):
                if "__pycache__" in f.parts:
                    continue
                out.append({"name": f.relative_to(root).as_posix(),
                            "size": f.stat().st_size})
        return out[:60]

    @app.get("/api/exo_file")
    def exo_file(name: str):
        a = _exo_a()
        p = _in_dir(Path(a.world.sandbox), name)
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = "<binary>"
        return {"name": name, "size": p.stat().st_size, "content": body[:200_000]}

    @app.get("/api/exo_download")
    def exo_download(name: str):
        a = _exo_a()
        p = _in_dir(Path(a.world.sandbox), name)
        return FileResponse(str(p), filename=name)

    @app.get("/api/exo_artifact_download")
    def exo_artifact_download(name: str):
        _exo_a()
        p = _in_dir(FRONTEND.parent.parent / "exocortex", name)
        return FileResponse(str(p), filename=name)

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket):
        await ws.accept()
        cursor = -1
        try:
            await ws.send_json({"type": "hello", "actions": ACTIONS,
                                "submit": ACTION_INDEX["SUBMIT_ANSWER"]})
            while True:
                for rec in agent.thought_stream_list(500):
                    if rec["tick"] > cursor:
                        cursor = rec["tick"]
                        await ws.send_json({"type": "thought", **rec})
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=0.3)
                except asyncio.TimeoutError:
                    pass
        except (WebSocketDisconnect, RuntimeError):
            pass

    @app.get("/")
    def index():
        return FileResponse(FRONTEND)

    _reasoning = {}

    def reasoning_agent():
        if "a" not in _reasoning:
            _reasoning["a"] = None
            _reasoning["err"] = ("removed: this endpoint drove the archived "
                                 "colony benchmark; the house is run_house.py")
        return _reasoning["a"]

    @app.get("/api/reasoning_state")
    def reasoning_state():
        root = FRONTEND.parent.parent
        try:
            st = json.loads((root / "exocortex" / "reasoning_state.json")
                            .read_text(encoding="utf-8"))
        except Exception:
            st = {"phase": "idle"}
        try:
            st["chains"] = sum(
                1 for f in (root / "exocortex" / "procedures").glob("*.json")
                if json.loads(f.read_text(encoding="utf-8")).get("type")
                == "REASONING_CHAIN")
        except Exception:
            st["chains"] = 0
        try:
            from world.reasoning_benchmark import TASKS as RT
            st["benchmark_tasks"] = [t["id"] for t in RT]
        except Exception:
            st["benchmark_tasks"] = []
        return st

    @app.post("/api/reasoning_task")
    def reasoning_task(payload: dict):
        a = reasoning_agent()
        if a is None:
            return {"ok": False, "error": _reasoning.get("err", "n/a")}
        task = dict(payload or {})
        if not task.get("text"):
            return {"ok": False, "error": "text required"}
        from world.parity_benchmark import grade
        graded = bool(task.get("path")) and bool(task.get("run"))
        res = a.solve_task(task, grade_fn=grade if graded else None)
        return {"ok": True, "result": res}

    @app.get("/api/api_state")
    def api_state():
        """PATH A dashboard: four panels, all measured.

        api_usage / local_vs_api / learning_progress / cache. `mode`
        says whether the oracle is live, blocked (no credential) or offline (the
        test fence), because a run that never dialled must never resemble a
        billable one. There is deliberately no money panel: a price table for
        someone else's models is a guess dressed as a measurement, so nothing
        here claims a cost.
        """
        out: dict = {"mode": "off", "panels": {}}
        try:
            a = reasoning_agent()
            st = a.api_stats() if a is not None else {"enabled": False}
        except Exception as exc:
            st = {"enabled": False, "error": str(exc)[:120]}
        opt = (st or {}).get("optimizer") or {}
        oracle = opt.get("oracle") or (st or {}).get("oracle") or {}
        out["enabled"] = bool((st or {}).get("enabled"))
        out["mode"] = oracle.get("mode", "off")
        out["panels"] = {
            "api_usage": {
                "calls": oracle.get("calls"),
                "has_key": oracle.get("has_key"),
                "errors": oracle.get("errors"),
                "provider": oracle.get("provider"),
                "model": oracle.get("model"),
                "tokens_prompt_est": oracle.get("tokens_prompt_est"),
                "tokens_completion_est": oracle.get("tokens_completion_est"),
                "token_source": oracle.get("token_source"),
                "budget_remaining": oracle.get("budget")},
            "local_vs_api": {
                "per_route": opt.get("per_route"),
                "solved_without_api": opt.get("solved_without_api"),
                "local_solve_share": opt.get("local_solve_share"),
                "tasks": opt.get("tasks"), "partial": opt.get("partial"),
                "local_solver": (st or {}).get("local")},
            "learning_progress": (st or {}).get("learning"),
            "cache": opt.get("cache")}
        return out

    @app.get("/api/connectome_state")
    def connectome_state():
        """PATH A final layer: sandbox, circuit breaker, fast route, context.

        Read-only, and it must stay that way -- the dashboard is not allowed to
        approve its own destructive operations, so approval is a separate
        endpoint a human has to press.
        """
        try:
            a = reasoning_agent()
            cs = a.connectome_stats() if a is not None else {}
        except Exception as exc:
            cs = {"error": f"{type(exc).__name__}: {exc}"[:200]}
        box = dict(cs.get("sandbox") or {})
        try:
            pending = [dict(p, index=i) for i, p in enumerate(
                reasoning_agent().sandbox.pending_approvals[-10:])]
        except Exception:
            pending = []
        box["pending_requests"] = pending
        return {"sandbox": box,
                "circuit_breaker": cs.get("circuit_breaker"),
                "breaker_stats": cs.get("breaker_stats"),
                "fast_route": cs.get("fast_route"),
                "context": cs.get("context"),
                "guarantee": cs.get("guarantee"),
                "ledger_tail": cs.get("ledger_tail"),
                "init_error": cs.get("init_error")}

    @app.post("/api/sandbox_answer")
    def sandbox_answer(index: int, approve: bool = False):
        """The human half of the safety layer. Approving grants exactly one
        matching action; it does not open the gate generally."""
        try:
            a = reasoning_agent()
            return a.sandbox.answer(int(index), bool(approve))
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}

    @app.get("/api/state")
    def state():
        return agent.state()

    @app.get("/api/thought_stream")
    def thought_stream(n: int = 50):
        return {"stream": agent.thought_stream_list(min(max(n, 1), 200))}

    @app.get("/api/memory_top")
    def memory_top():
        mem = agent.memory
        sem = sorted(mem.semantic.to_list(), key=lambda f: -f.get("last_accessed", 0))[:10]
        proc = sorted(mem.procedural.to_list(),
                      key=lambda p: -p.get("last_used", 0))[:10]
        return {"semantic": [{"key": f["key"], "value": str(f["value"])[:120],
                              "accessed": int(f.get("last_accessed", 0))} for f in sem],
                "procedural": [{"trigger": p["trigger_pattern"][:60],
                                "seq": p["action_sequence"],
                                "rate": p.get("success_rate", 0.0)} for p in proc]}

    @app.post("/api/task")
    def inject(payload: TaskIn):
        if payload.expected_action and payload.expected_action.upper() not in ACTIONS:
            return {"ok": False, "error": f"unknown action {payload.expected_action}"}
        task = agent.inject_task(payload.text, payload.expected_action)
        return {"ok": True, "task_id": task.task_id,
                "expected_action": ACTIONS[task.expected_action]
                if task.expected_action is not None else None}

    @app.post("/api/step")
    def step(payload: StepIn):
        with state_lock:
            done = agent.run(min(max(payload.n, 1), 100))
        return {"ok": True, "steps": len(done)}

    @app.post("/api/run")
    def run_continuous(payload: RunIn):
        agent.running = bool(payload.on)
        if agent.running:
            def _loop():
                while agent.running:
                    with state_lock:
                        agent.step()
                    agent.paused = False
                agent.paused = False
            threading.Thread(target=_loop, daemon=True, name="agent-loop").start()
        return {"ok": True, "running": agent.running}

    @app.post("/api/user_reply")
    def user_reply(payload: dict):
        agent.set_user_reply(str(payload.get("reply", "")))
        return {"ok": True}

    return app

def start_server(agent, host: str = "0.0.0.0", port: int = 8123) -> threading.Thread:
    """Run the observatory in a daemon thread; the simulation continues.
    host=0.0.0.0 makes it LAN-accessible (http://<this-machine-ip>:<port>)."""
    app = create_app(agent)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True, name="observatory")
    thread.start()
    return thread

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from world.hybrid_agent import HybridAgent
    agent = HybridAgent()
    start_server(agent, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8123)
    print(f"Observatory on http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8123} - Ctrl-C to stop")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        pass