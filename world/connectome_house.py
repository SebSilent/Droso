
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "world" / "house"

# The reasoning panel polls its state endpoint, and that endpoint read the curriculum
# jsonl and the reader's status off disk on EVERY call -- parsing 427 rows and stat-ing
# files several times a minute for numbers that change once an hour. Both are cached here
# for a short window.
#
# The TTL is the point: a stale figure for a few seconds is harmless and an unread disk
# is not, but caching indefinitely would make the panel lie about a curriculum that had
# just finished. So the window is short enough to notice and long enough to stop the
# repeated parse. Cached on failure too, but only for the same window, so a missing file
# is not re-stat-ed on every poll either.
_STATE_CACHE: dict = {}
_STATE_TTL_S = 15.0


def _cached_state(key: str, fn, ttl: float = _STATE_TTL_S):
    now = time.time()
    hit = _STATE_CACHE.get(key)
    if hit is not None and (now - hit[0]) < ttl:
        return hit[1]
    try:
        val = fn()
    except Exception as exc:
        # Both key spellings, because the reader reported `started` on failure and the
        # curriculum reported `present`, and the panel reads whichever it was given.
        val = {"present": False, "started": False, "why": str(exc)[:80]}
    _STATE_CACHE[key] = (now, val)
    return val


def _listener_pids(port: int) -> list:
    """Every process holding TCP `port`.

    Plural on purpose. With allow_reuse_address more than one process can be
    bound to the same port on Windows, and stopping only the first one leaves
    the port busy -- which is how a takeover once reported success while a
    45-minute-old brain kept serving the dashboard.
    """
    out = []
    try:
        import psutil
        for c in psutil.net_connections("tcp"):
            if c.status == "LISTEN" and c.laddr and c.laddr.port == int(port):
                if c.pid and c.pid not in out:
                    out.append(c.pid)
    except Exception:
        pass
    return out


def _port_busy(host: str, port: int, timeout: float = 0.4) -> bool:
    """Ask whether something is ANSWERING on (host, port).

    Binding is not the test. ThreadingHTTPServer sets allow_reuse_address, and on
    Windows a second bind over a live socket "succeeds" while the first listener
    keeps every connection -- the shape of a house that looks up and hangs while a
    second brain burns cores behind it. So the question is answered the way the
    world answers it: try to connect. A completed handshake means a listener is
    there, whether or not it will talk.
    """
    probe = "127.0.0.1" if host in (None, "", "0.0.0.0", "::") else host
    fam = socket.AF_INET6 if ":" in str(probe) else socket.AF_INET
    IN_PROGRESS = (10035, 115, 10063)      # WSAEWOULDBLOCK / EINPROGRESS
    try:
        with socket.socket(fam, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            rc = s.connect_ex((probe, int(port)))
            if rc == 0:
                return True
            if rc not in IN_PROGRESS:
                return False                      # refused: nothing listening
            import select
            ready, _, _ = select.select([], [s], [], timeout)
            return bool(ready) and \
                s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0
    except Exception:
        return False


def _process_lineage() -> set:
    """This pid and every parent above it."""
    pids = set()
    try:
        import psutil
        cur = psutil.Process()
        for _ in range(24):
            pids.add(cur.pid)
            parent = cur.parent()
            if parent is None or parent.pid in pids:
                break
            cur = parent
    except Exception:
        pids.add(os.getpid())
    return pids


def _take_over(host: str, port: int, timeout: float = 20.0):
    """Stop whoever holds the port, then wait until it is actually free.

    One brain per port and the newest one wins: that is the operator's rule, and
    it is what makes "restart the house" mean one thing instead of quietly
    meaning six. terminate() before kill() because a house saves its lived brain
    on the way out, and SIGKILL throws away the last minute of being alive.

    Two listeners are left alone: one whose pid cannot be named, and one that IS
    this process or one of its parents. A launcher must never be able to kill the
    thing that launched it.
    """
    pids = _listener_pids(port)
    if not pids:
        return False, "a listener holds the port but its pid is unknown"
    pid = ", ".join(str(p) for p in pids)
    mine = _process_lineage()
    if any(p in mine for p in pids):
        return False, ("the live listener is this process or its parent "
                       f"(pid {sorted(set(pids) & mine)})")
    procs = []
    for p in pids:
        try:
            import psutil
            proc = psutil.Process(p)
            procs.append(proc)
            # Its children as well. The accelerated life is a separate process,
            # and on Windows a daemon child outlives a terminated parent -- the
            # leaked workers, not the house, were what saturated the box.
            try:
                procs.extend(proc.children(recursive=True))
            except Exception:
                pass
        except Exception:
            pass
    if not procs:
        return False, f"could not open the listener processes (pid {pid})"
    for proc in procs:
        try:
            proc.terminate()
        except Exception:
            pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        alive = []
        for proc in procs:
            try:
                if proc.is_running():
                    alive.append(proc)
            except Exception:
                pass
        if not alive:
            break
        time.sleep(0.2)
    for proc in procs:
        try:
            if proc.is_running():
                proc.kill()
        except Exception:
            pass
    deadline = time.time() + 10.0
    while time.time() < deadline and _port_busy(host, port):
        time.sleep(0.2)
    if _port_busy(host, port):
        return False, f"pid {pid} was stopped but {port} is still busy"
    return True, f"stopped the previous house (pid {pid}) and took the port"

def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def cfg_get(cfg: dict, dotted: str, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

_BANC_REGIONS = None
_REGION_GROUPS = (
    ("mb", ("MB",)),
    ("al", ("AL",)),
    ("lh", ("LH",)),
    ("vnc", ("T1", "T2", "T3", "ABDNM", "ABD", "CV")),
    ("sez", ("GNG", "SAD", "FLA", "ANT")),
    ("ol", ("ME", "LO", "LOP", "LA")),
    ("lp", ("AVLP", "PVLP", "IVLP", "PLP", "WED", "AOTU", "BU", "LAL")),
    ("proto", ("SMP", "SLP", "SIP", "SCL", "ICL", "IPS", "VES", "EPA",
               "GOR", "PFL", "CAN", "IB", "INP", "ATM", "PRW", "POC",
               "CRE", "SNP", "PENP", "EL")),
    ("cx", ("PB", "FB", "EB", "NO")),
)

def _region_group(region: str) -> str:
    r = (region or "").upper()
    if r.startswith("NO_CONS"):
        return "other"
    head = r.split(".")[0].split("_")[0]
    for grp, heads in _REGION_GROUPS:
        if head in heads:
            return grp
    return "other"

def _banc_regions() -> dict:
    global _BANC_REGIONS
    if _BANC_REGIONS is None:
        import pandas as pd
        p = (Path(__file__).resolve().parent.parent / "connectome" / "data"
             / "neuron.csv.gz")
        n = pd.read_csv(p, usecols=["Root ID", "Top in/out region"])
        _BANC_REGIONS = dict(zip(n["Root ID"].astype("int64"),
                                 n["Top in/out region"].astype(str)))
    return _BANC_REGIONS

def build_house_agent(cfg: dict, project_root: str | None = None):
    """Assemble the body: organs, the neural core, and the config."""
    from organs.code_assembler import CodeAssembler
    from organs.memory import MemoryOrgan
    from organs.terminal import TerminalOrgan
    from organs.working_memory import WorkingMemoryOrgan
    from world.reasoning_agent import ReasoningAgent
    root = Path(project_root or cfg_get(cfg, "connectome.project_root")
                or ROOT)
    c = _deep_merge(cfg, {"connectome": {"project_root": str(root)}})
    return ReasoningAgent(
        {"code_assembler": CodeAssembler(),
         "filesystem": None,
         "terminal": TerminalOrgan(timeout_s=10),
         "memory": MemoryOrgan(),
         "working_memory": WorkingMemoryOrgan(capacity=7)},
        state_path=root / "state" / "house_agent.json",
        config=c)

CAPABILITIES = [
    {"name": "world", "verb": "POST /api/chat",
     "what": "speak into Droso's air; he hears, and decides whether to "
             "answer"},
    {"name": "world_clock", "verb": "GET+POST /api/world/speed",
     "what": "paused, 1x, or max: the pace of Droso's existence"},
    {"name": "care", "verb": "POST /api/world/care",
     "what": "feed, pet, praise -- grounding events with real dopamine"},
    {"name": "exposure", "verb": "GET+POST /api/language/exposure",
     "what": "books from /books read to Droso in world time; intensity, "
             "speed, reward dials"},
    {"name": "mind", "verb": "GET /api/language/stream",
     "what": "his thoughts, what he hears, and what he says, on one wire"},
    {"name": "approvals", "verb": "GET /api/state, POST /api/sandbox_answer",
     "what": "writes and deletes await a human; approve or refuse here"},
    {"name": "neural", "verb": "GET /api/neural/state",
     "what": "the carve's pulses, lived time and recent activity"},
    {"name": "research", "verb": "POST /api/research",
     "what": "record a question; auto-research stays off"},
    {"name": "config", "verb": "GET+POST /api/config/update",
     "what": "typed settings; unknown keys are refused, not absorbed"},
]

class ConnectomeHouse:
    """The body's world: doors, policy, and the chat-as-world channel."""

    ORGAN_REGISTRY = [
        ("api_oracle", "Oracle", "knowledge"),
        ("query_cache", "Cache", "knowledge"),
        ("task_decomposer", "Decomposer", "thought"),
        ("local_solver", "Local solver", "thought"),
        ("token_optimizer", "Token optimizer", "economy"),
        ("learning_loop", "Learning loop", "memory"),
        ("sandbox", "Sandbox", "safety"),
        ("fast_router", "Fast router", "economy"),
        ("circuit_breaker", "Circuit breaker", "safety"),
        ("context_manager", "Context manager", "safety"),
        ("heartbeat", "Heartbeat", "consciousness"),
        ("neural_growth", "Neural growth", "consciousness"),
        ("language", "Language", "consciousness"),
        ("working_memory", "Working memory", "memory"),
        ("exocortex", "Exocortex", "memory"),
        ("planner", "Planner", "thought"),
    ]

    CFG_KEY_TYPES = {
        "model.provider": str,
        "model.model": str,
        "model.base_url": str,
        "language.min_vocabulary": int,
        "language.auto_train": bool,
        "language.exposure_enabled": bool,
        "connectome.project_root": str,
        "connectome.background_drive": str,
        "connectome.neural_tick_interval": (int, float),
        "connectome.lived_time_save_interval": (int, float),
        "heartbeat.think_interval": (int, float),
        "heartbeat.sleep_threshold": (int, float),
        "heartbeat.neural_tick_interval": (int, float),
        "sandbox.project_root": str,
        "house.port": int,
        "house.allow_remote_mutation": bool,
    }

    def __init__(self, agent, config: dict | None = None, port: int = 7773,
                 config_path: str | None = None, host: str | None = None,
                 **_ignored):
        self.agent = agent
        self.config = config or {}
        self.port = int(port or 7773)
        self.host = host or str((self.config.get("house", {}) or {}).get(
            "host", "0.0.0.0"))
        self.config_path = Path(config_path) if config_path else None
        self.chat_history = deque(maxlen=200)
        self.progress = deque(maxlen=400)
        self.seq = 0
        self.errors: list[str] = []
        self._status = "idle"
        self._status_text = ""
        self._work_lock = threading.Lock()
        self._httpd = None
        self._server_thread = None
        self._started_at = None
        self._requests = 0
        self._refused = 0
        self.project_root = Path(
            (self.config.get("connectome", {}) or {}).get(
                "project_root", str(ROOT)))
        self.allow_remote_mutation = bool(
            (self.config.get("house", {}) or {}).get(
                "allow_remote_mutation", True))
        self.access_token = ((self.config.get("house", {}) or {})
                             .get("access_token") or None)
        self.allow_tool_execution = bool(
            (self.config.get("house", {}) or {}).get(
                "allow_tool_execution", False))

    TOOL_PATHS = ("/api/terminal", "/api/code", "/api/execute",
                  "/api/sandbox", "/api/shell")

    @staticmethod
    def is_loopback(peer: str) -> bool:
        p = str(peer or "")
        return p in ("127.0.0.1", "::1", "localhost") or p.startswith("127.")

    def may_mutate(self, peer: str, token: str | None = None):
        """Who may change the world through this house. Returns (ok, reason).

        Loopback is the operator's own seat. Anyone else is covered by the
        ruling in house.allow_remote_mutation, and if house.access_token is set
        a remote caller must present it. Until this method existed the config
        described all three knobs and nothing read them.
        """
        if self.is_loopback(peer):
            return True, "loopback"
        tok = str(token or "")
        if self.access_token and tok == str(self.access_token):
            return True, "access token"
        if self.access_token:
            return False, "remote peer without the access token"
        if self.allow_remote_mutation:
            return True, "allow_remote_mutation"
        return False, "remote mutation is not allowed"

    def may_execute(self, peer: str, path: str, token: str | None = None):
        """Tool execution is mutation with a bigger hammer: for a remote peer it
        needs house.allow_tool_execution, which is off by default. Loopback keeps
        working as it always has -- the operator's own browser is the tool."""
        ok, why = self.may_mutate(peer, token)
        if not ok:
            return ok, why
        if not self.is_loopback(peer) and not self.allow_tool_execution \
                and str(path).startswith(self.TOOL_PATHS):
            return False, "remote tool execution needs house.allow_tool_execution"
        return True, "allowed"

    @property
    def house_dir(self) -> Path:
        """Directory the web UI is served from (tests read index.html here)."""
        return STATIC_DIR

    def note(self, kind: str, text: str) -> dict:
        self.seq += 1
        ev = {"seq": self.seq, "kind": kind, "text": str(text),
              "t": time.time()}
        self.progress.append(ev)
        return ev

    def set_status(self, s: str, text: str = "") -> None:
        self._status = s
        self._status_text = text

    def _sandbox(self):
        return getattr(self.agent, "sandbox", None)

    def pending_actions(self) -> list[dict]:
        sb = self._sandbox()
        rows = list(getattr(sb, "pending_approvals", []) or [])
        return [{"id": a.get("id"), "op": a.get("op", "WRITE"),
                 "what": ("write " + str(a.get("path", ""))
                          if a.get("op") != "DELETE"
                          else "delete " + str(a.get("path", "")))}
                for a in rows]

    def process_chat(self, message: str) -> dict:
        """One turn, through the connectome. The human speaks into the
        world; Droso always hears; whether he answers is his own."""
        msg = str(message or "").strip()
        if not msg:
            return {"ok": False, "response": "", "reason": "empty message"}
        if not self._work_lock.acquire(blocking=False):
            return {"ok": False, "reason": "busy",
                    "response": "the connectome is already working on a "
                                "task; this one was not queued"}
        try:
            self.chat_history.append({"role": "user", "content": msg,
                                      "t": time.time()})
            hb = getattr(self.agent, "heartbeat", None)
            if hb is not None:
                try:
                    hb.begin_task(msg)
                    hb.activity("user")
                except Exception:
                    pass
            self.set_status("thinking", msg)
            self.note("user", msg)
            t0 = time.perf_counter()
            lang = getattr(self.agent, "language", None)
            if lang is not None and hasattr(lang, "respond") and \
                    len(msg) <= 80 and not self._looks_like_task(msg):
                reply = None
                try:
                    reply = lang.respond(msg, speaker=str(
                        data.get("speaker") or "you"))
                except Exception as e:
                    import traceback as _tb
                    self.errors.append(("language: " + _tb.format_exc())[:600])
                    print("LANGUAGE ERROR " + _tb.format_exc(), flush=True)
                if reply is None:
                    reply = {"spoken": False, "heard": True,
                             "reason": "the cortex errored; it heard anyway"}
                ms = round((time.perf_counter() - t0) * 1000, 1)
                self.set_status("idle")
                if reply.get("spoken"):
                    self.note("language",
                              f"it heard {msg[:30]!r} and said "
                              f"{reply['utterance']!r} "
                              f"(resonance {reply.get('resonance')})")
                    return {"ok": True, "heard": True, "spoken": True,
                            "response": reply["utterance"], "path": "world",
                            "ms": ms,
                            "oracle_mode": (self.agent.api_oracle.mode
                                            if self.agent.api_oracle
                                            else "absent"),
                            "api_calls": 0,
                            "notes": [reply.get("note", "")],
                            "pool": reply.get("pool"),
                            "resonance": reply.get("resonance"),
                            "mood": reply.get("mood"),
                            "kind": reply.get("kind"),
                            "source": reply.get("source")}
                return {"ok": True, "heard": True, "spoken": False,
                        "response": "", "path": "world", "ms": ms,
                        "oracle_mode": (self.agent.api_oracle.mode
                                        if self.agent.api_oracle
                                        else "absent"),
                        "api_calls": 0,
                        "notes": [reply.get("reason", "it chose not to "
                                            "speak")],
                        "mood": reply.get("mood"),
                        "best_resonance": reply.get("best_resonance"),
                        "pool": reply.get("pool")}
            route = {}
            router = getattr(self.agent, "fast_router", None)
            if router is not None:
                try:
                    route = dict(router.route(msg) or {})
                    self.note("route", f"path={route.get('path')} "
                                       f"why={route.get('why', '')}")
                except Exception as e:
                    self.errors.append(f"router: {type(e).__name__}"[:80])
            out = {}
            try:
                out = self.agent.solve_task(msg) or {}
            except Exception as e:
                self.errors.append(f"solve: {type(e).__name__}"[:80])
                out = {"success": False, "reason": f"{type(e).__name__}: {e}"}
            ms = round((time.perf_counter() - t0) * 1000, 1)
            answer = {"ok": bool(out.get("success", True)),
                      "response": str(out.get("response", "") or ""),
                      "path": route.get("path", "reasoning_loop"),
                      "ms": ms,
                      "oracle_mode": (self.agent.api_oracle.mode
                                      if self.agent.api_oracle else "absent"),
                      "api_calls": int(out.get("api_calls", 0) or 0),
                      "verified": out.get("verified"),
                      "notes": [str(out.get("reason", ""))]
                      if out.get("reason") else [],
                      "meta": {k: out[k] for k in out
                               if k not in ("response",)}
                      }
            if not answer["response"] and out.get("reason"):
                answer["reason"] = str(out.get("reason"))
            self.chat_history.append({"role": "assistant",
                                      "content": answer["response"],
                                      "t": time.time(),
                                      "meta": answer})
            self._teach_from_turn(msg, answer.get("response", ""))
            self.note("done", f"answered in {ms} ms via {answer.get('path')}")
            return answer
        finally:
            if hb is not None:
                try:
                    hb.end_task()
                    hb.tick()
                except Exception:
                    pass
            self.set_status("idle")
            self._work_lock.release()

    @staticmethod
    def _looks_like_task(msg: str) -> bool:
        m = msg.lower()
        if any(mk in m for mk in ("def ", "class ", "import ", ".py", ".js",
                                  "/", "\\", "http", "function", "script",
                                  "refactor", "implement", "debug",
                                  "compile")):
            return True
        return bool(re.search(r"\b(sort|write|create|build|parse|fix|run|"
                              r"make|generate|convert|deploy|install)\b", m))

    def _teach_from_turn(self, user_text: str, reply_text: str):
        lang = getattr(self.agent, "language", None)
        if lang is None:
            return
        try:
            if hasattr(lang, "observe_exchange"):
                lang.observe_exchange(user_text, reply_text)
        except Exception as e:
            self.errors.append(f"language: {type(e).__name__}"[:80])

    def get_mental(self) -> dict:
        hb = getattr(self.agent, "heartbeat", None)
        at = getattr(self.agent, "autotraining", None)
        lang = getattr(self.agent, "language", None)
        return {
            "llm_enabled": bool(getattr(self.agent, "llm_enabled", True)),
            "heartbeat": {"present": hb is not None,
                          "state": (hb.observed_state()
                                    if hb is not None else "UNKNOWN"),
                          "running": bool(getattr(hb, "_running", False)),
                          "thoughts": len(getattr(hb, "thoughts", []) or [])},
            "autotraining": {"present": at is not None,
                             "running": False,
                             "gone": True,
                             "reason": "autotraining removed: teachers are "
                                       "external and chosen by the "
                                       "administrator"},
            "language": {"present": lang is not None,
                         "vocabulary_size": (lang.vocabulary_size()
                                             if lang is not None else 0)}}

    def get_organs_state(self) -> dict:
        organs = {}
        for name, label, group in self.ORGAN_REGISTRY:
            organ = getattr(self.agent, name, None)
            if organ is None:
                organs[name] = {"label": label, "group": group,
                                "present": False, "status": "absent",
                                "status_name": "absent",
                                "note": "not attached"}
                continue
            stats = {}
            if hasattr(organ, "stats"):
                try:
                    stats = organ.stats() or {}
                except Exception as e:
                    stats = {"error": str(e)[:80]}
            enabled = getattr(organ, "enabled", True)
            organs[name] = {"label": label, "group": group,
                            "present": True, "stats": stats,
                            "status": "active" if enabled else "disabled",
                            "status_name": ("active" if enabled
                                            else "disabled")}
        organs["autotraining"] = {"label": "Autotraining",
                                  "group": "consciousness",
                                  "present": False, "status": "removed",
                                  "status_name": "removed",
                                  "note": "teachers are external now; "
                                          "exposure lives in Language"}
        return organs

    def neural_state(self) -> dict:
        eng = getattr(self.agent, "engine", None)
        core = getattr(eng, "static", None)
        g = getattr(core, "g", None)
        hb = getattr(self.agent, "heartbeat", None)
        out = {"graph_loaded": g is not None,
               "pools": int(getattr(g, "n_actions", 12) or 12),
               "neuron_count": int(getattr(g, "n_nodes", 0) or 0),
               "synapse_count": int((getattr(g, "meta", {}) or {})
                                    .get("n_static_edges", 0) or 0),
               "plastic_synapses": (int(len(core.w))
                                    if hasattr(core, "w") else 0),
               "recent_activity": (list(hb.neural_activity_log)[-20:]
                                   if hb is not None else []),
               "neural_ticks": (getattr(hb, "neural_ticks", 0)
                                if hb is not None else 0),
               "interval_s": (getattr(hb, "neural_tick_interval", None)
                              if hb is not None else None),
               "background_drive": (getattr(hb, "background_drive", None)
                                    if hb is not None else None),
               "world": hb.world_state() if hb is not None
               and hasattr(hb, "world_state") else None}
        code = getattr(eng, "last_code", None)
        if code is not None:
            lv = getattr(eng, "last_v", None)
            act = getattr(eng, "last_action", None)
            out["last_decision"] = {
                "cells": [int(i) for i in np.nonzero(code)[0][:16]],
                "n_cells": int((np.asarray(code) != 0).sum()),
                "pool": (int(act) if act is not None else None),
                "v": ([round(float(x), 3) for x in lv]
                      if lv is not None else [])}
        try:
            tot = hb.lived_time.totals()
            out["lived_time"] = {"decisions": tot.get("decisions", 0),
                                 "total_neural_seconds":
                                     tot.get("neural_seconds", 0.0),
                                 "neural_hours": tot.get("neural_hours", 0.0),
                                 "neural_days": tot.get("neural_days", 0.0),
                                 "neural_years": tot.get("neural_years", 0.0),
                                 "neuron_update_events": tot.get(
                                     "neuron_update_events", 0),
                                 "fly_days_equivalent": tot.get(
                                     "fly_days_equivalent", 0.0),
                                 "fly_lifetimes": tot.get(
                                     "fly_lifetimes_equivalent", 0.0),
                                 "beings": tot.get("beings", 0)}
            out["lived_time_path"] = (str(hb.lived_time.path)
                                      if hb.lived_time.path else None)
        except Exception as e:
            out["lived_time"] = {"error": str(e)[:120]}
        out["engine_static_pass"] = core is not None
        if hb is None:
            out["note"] = "no heartbeat attached: nothing pulses the core"
        return out

    def get_consciousness(self) -> dict:
        hb = getattr(self.agent, "heartbeat", None)
        if hb is None:
            return {"present": False, "state": "UNKNOWN",
                    "note": "no heartbeat attached; run_house.py attaches "
                            "one",
                    "recent_thoughts": [], "knowledge_gaps": [],
                    "research_queue": []}
        try:
            payload = dict(hb.get_consciousness())
        except Exception as e:
            return {"present": True, "state": "ERROR", "error": str(e)[:200]}
        # `present` has to be stated on BOTH branches. It was only set when there was no
        # heartbeat, so a caller could not tell "no organ attached" from "organ attached
        # and quiet" -- which is precisely the distinction this project keeps insisting on:
        # a missing organ is absent, never a confident zero.
        payload["present"] = True
        ll = getattr(self.agent, "learning_loop", None)
        vocab = getattr(self.agent, "language", None)
        payload["self_assessment"] = {
            "procedures_known": (ll.stats().get("procedures", 0)
                                 if ll is not None and hasattr(ll, "stats")
                                 else 0),
            "mean_confidence": (ll.stats().get("mean_confidence", 0)
                                if ll is not None and hasattr(ll, "stats")
                                else 0),
            "words_spoken": (vocab.vocabulary_size()
                             if vocab is not None else 0),
            "honest_gaps": len(payload.get("knowledge_gaps", []))}
        return payload

    def language_state(self) -> dict:
        lang = getattr(self.agent, "language", None)
        if lang is None:
            return {"present": False}
        s = {"present": True,
             "teacher": (lang.teacher_state()
                         if hasattr(lang, "teacher_state") else None),
             "oracle_present": getattr(self.agent, "api_oracle", None)
             is not None}
        if hasattr(lang, "stats"):
            s.update(lang.stats())
        s["inner"] = lang.inner_state() if hasattr(lang, "inner_state") \
            else None
        return s

    def language_store(self, section: str = "vocabulary", query: str = "",
                       limit: int = 100, known_only: bool = False) -> dict:
        lang = getattr(self.agent, "language", None)
        if lang is None:
            return {"present": False}
        words = getattr(lang, "word_patterns", {})
        rows, matched = [], 0
        for w, rec in sorted(words.items()):
            if query and query.lower() not in w.lower():
                continue
            matched += 1
            rows.append({"word": w, "pool": rec.get("pool"),
                         "kc": rec.get("kc", []),
                         "kc_count": len(rec.get("kc", [])),
                         "heard": (lang.exposure_counts.get(w, 0)
                                   if hasattr(lang, "exposure_counts") else 0),
                         "source": rec.get("source")})
        return {"section": section, "count": len(rows),
                "matched": matched, "total": len(words),
                "vocabulary": rows[:limit]}

    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def access_mode(self) -> str:
        return (f"open (allow_remote_mutation={self.allow_remote_mutation})"
                if self.allow_remote_mutation else
                "guarded (remote mutation needs approval)")

    def get_config(self) -> dict:
        import copy
        from credentials import get_key, fingerprint, store_path
        c = copy.deepcopy(self.config)
        for block in c.values():
            if isinstance(block, dict) and "api_key" in block:
                block["api_key"] = None
        c["provider_choices"] = ["zai", "zai-paas", "openai", "anthropic",
                                 "qwen", "groq", "openrouter", "ollama",
                                 "custom"]
        m = c.get("model", {})
        key = get_key("model")
        m["api_key_present"] = bool(key)
        m["api_key"] = fingerprint(key).get("hint") if key else None
        m["api_key_store"] = str(store_path())
        c["model"] = m
        return c

    def get_full_state(self) -> dict:
        hb = getattr(self.agent, "heartbeat", None)
        mental = self.get_mental()
        mental["activity"] = self._status or "idle"
        mental["house"] = {"access": self.access_mode(),
                           "url": self.url()}
        oracle = getattr(self.agent, "api_oracle", None)
        ostats = (oracle.stats() if oracle is not None
                  and hasattr(oracle, "stats") else {})
        opt = getattr(self.agent, "token_optimizer", None)
        ostats2 = (opt.stats() if opt is not None
                   and hasattr(opt, "stats") else {})
        out = {"house": {"port": self.port,
                         "host": self.host,
                         "url": self.url(),
                         "access": self.access_mode(),
                         "allow_remote_mutation":
                             self.allow_remote_mutation,
                         "project_root": str(self.project_root),
                         # The footer used to render "house down" while the page
                         # was being served by this very process, because nothing
                         # here answered. These are the process's own facts.
                         "running": self._httpd is not None,
                         "pid": os.getpid(),
                         "uptime_s": (round(time.time() - self._started_at, 1)
                                      if self._started_at else None),
                         "requests": self._requests,
                         "refused_remote": self._refused,
                         "errors": list(self.errors)[-6:]},
               "mental": mental,
               "task_status": self._status or "idle",
               "current_task": getattr(hb, "current_task", None),
               "seq": self.seq,
               "oracle": ostats,
               "stats": {"oracle": ostats,
                         "optimizer": ostats2,
                         "sandbox": (sb.stats() if (sb := getattr(self.agent,
                                        "sandbox", None)) is not None
                                     and hasattr(sb, "stats") else {}),
                         "circuit_breaker": (cb.stats() if (cb :=
                                        getattr(self.agent,
                                        "circuit_breaker", None)) is not None
                                        and hasattr(cb, "stats") else {}),
                         "fast_route": (fr.stats() if (fr := getattr(
                                        self.agent, "fast_router",
                                        None)) is not None
                                        and hasattr(fr, "stats") else {}),
                         "guarantee": {"verdict":
                                       "no cross-run claim is made",
                                       "rows": []}},
               "heartbeat": ("ticking"
                             if mental["heartbeat"]["running"]
                             else ("absent" if hb is None else "stopped")),
               "sandbox": {"pending": self.pending_actions()},
               "consciousness": self.get_consciousness(),
               "language": self.language_state(),
               "neural": self.neural_state(),
               "progress": list(self.progress)[-30:],
               "errors": list(self.errors)[-8:],
               "world": (hb.world_state() if hb is not None
                         and hasattr(hb, "world_state") else None)}
        return out

    API_KEY_ROLES = ("model", "autotraining")

    def update_config(self, changes: dict) -> dict:
        applied, refused, warnings = [], [], []
        hb = getattr(self.agent, "heartbeat", None)
        for key, value in (changes or {}).items():
            role = str(key).split(".")[0] if "." in str(key) else ""
            if str(key).endswith(".api_key") and role in self.API_KEY_ROLES:
                try:
                    from credentials import set_key, delete_key
                    from organs.api_oracle import placeholder_key
                    if value and isinstance(value, str):
                        if placeholder_key(value):
                            refused.append(key)
                            warnings.append(
                                f"{key}: looks like an unfilled template, not a "
                                f"credential -- nothing was stored")
                            continue
                        set_key(role, value.strip())
                    else:
                        delete_key(role)
                    oracle = getattr(self.agent, "api_oracle", None)
                    if role == "model" and oracle is not None:
                        oracle.api_key = (value.strip() if value
                                          and isinstance(value, str) else None)
                        oracle.key_placeholder = None
                    applied.append(key)
                except (OSError, ValueError) as e:
                    refused.append(f"{key} ({e})")
                continue
            want = self.CFG_KEY_TYPES.get(key)
            if want is None:
                refused.append(key)
                continue
            try:
                if isinstance(want, tuple):
                    ok = isinstance(value, want)
                    if want == (int, float) and isinstance(value, float) \
                            and float(value).is_integer():
                        value = int(value)
                elif want is bool:
                    ok = isinstance(value, bool)
                else:
                    ok = isinstance(value, want)
            except Exception:
                ok = False
            if not ok:
                refused.append(key)
                continue
            if key == "connectome.background_drive" and \
                    str(value).lower() not in ("noise", "replay", "context",
                                               "off"):
                refused.append(key)
                continue
            if key == "heartbeat.neural_tick_interval" and hb is not None:
                hb.neural_tick_interval = max(0.2, float(value))
            if key == "connectome.background_drive" and hb is not None:
                hb.background_drive = str(value).lower()
            if key == "connectome.lived_time_save_interval" and hb is not None:
                hb._lived_save_interval = max(5.0, float(value))
            applied.append(key)
        self._save_config()
        return {"applied": applied, "refused": refused,
                "warnings": warnings}

    def _save_config(self) -> None:
        if self.config_path is None:
            return
        try:
            self.config_path.write_text(
                json.dumps(self.config, indent=1), encoding="utf-8")
        except OSError as e:
            self.errors.append(f"config save: {e}"[:80])

    def _pend(self, op: str, path: Path, extra: dict | None = None) -> dict:
        sb = self._sandbox()
        entry = {"id": f"{op}:{path.name}:{int(time.time()*1000)}",
                 "op": op, "path": str(path)}
        if extra:
            entry.update(extra)
        if sb is not None and hasattr(sb, "pending_approvals"):
            sb.pending_approvals.append(entry)
        else:
            sb.pending_approvals = [entry]
        return entry

    def _resolve(self, rel: str) -> Path:
        p = Path(str(rel or ""))
        if not p.is_absolute():
            p = self.project_root / p
        return p.resolve()

    def _inside_root(self, p: Path) -> bool:
        try:
            p.relative_to(self.project_root.resolve())
            return True
        except ValueError:
            return False

    def answer_approval(self, data: dict) -> dict:
        answer = str(data.get("answer", data.get("decision", "")) or "")
        # `matches` is the older protocol and the better one: the human answers with the
        # NAME of the thing they are approving rather than an index, so an approval cannot
        # land on whichever request happened to be first in the queue. Answering by
        # position is the bug this shape exists to prevent. `approved: true/false` is a
        # decision too. Both are accepted, because a caller answering by content should not
        # be told its answer was not understood.
        match = str(data.get("matches", "") or "")
        if not answer and "approved" in data:
            answer = "approve" if data.get("approved") else "deny"
        want_id = str(data.get("id", "") or "")
        sb = self._sandbox()
        rows = list(getattr(sb, "pending_approvals", []) or [])
        pick = None
        for a in rows:
            if want_id and a.get("id") == want_id:
                pick = a
                break
            if want_id:
                continue
            if match and match not in str(a.get("path", "")):
                continue
            pick = a
            break
        if pick is None:
            return {"success": False, "ok": False, "reason": "nothing pending matches",
                    "pending": rows}
        if answer.lower() not in ("approve", "approved", "yes", "allow"):
            rows.remove(pick)
            return {"success": True, "ok": True, "approved": False, "action": pick}
        op = pick.get("op")
        path = Path(pick.get("path", ""))
        try:
            if op == "WRITE":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(pick.get("content", ""), encoding="utf-8")
                result = {"written": str(path)}
            elif op == "DELETE":
                if path.exists():
                    path.unlink()
                result = {"deleted": str(path)}
            else:
                result = {"note": f"unknown op {op}"}
            ok = True
        except OSError as e:
            ok = False
            result = {"error": str(e)[:120]}
        rows.remove(pick)
        return {"success": ok, "ok": ok, "result": result, "action": pick}

    def _knowledge_channel(self):
        """The knowledge channel, built once, in the only place the oracle is reachable.

        Lazily constructed and cached: the channel owns the call ledger, and two of them
        would mean two call counts for the same being.
        """
        ch = getattr(self, "_kchannel", None)
        if ch is not None:
            return ch
        oracle = getattr(self.agent, "api_oracle", None)
        loop = getattr(self.agent, "reasoning_loop", None)
        if oracle is None or loop is None:
            return None
        try:
            from organs.knowledge import KnowledgeChannel
        except Exception:
            return None
        self._kchannel = KnowledgeChannel(
            oracle=oracle, loop=loop,
            learning=getattr(self.agent, "learning_loop", None))
        return self._kchannel

    def _harness(self):
        """One harness per agent, and it is the front door.

        Before this the live route called `loop.step` directly and built its own oracle
        path, so every property the harness exists to give -- fact-first, the HOLE
        escalating instead of the task, and the branch breakdown that IS the 90/10
        number -- lived only in offline tools. The being's actual behaviour was
        unmeasured.

        It is wired to the SAME channel `_knowledge_channel()` already made: a second
        KnowledgeChannel would be a second ledger, and a second answer to "how much did
        the oracle do".
        """
        h = getattr(self, "_harness_obj", None)
        if h is not None:
            return h
        loop = getattr(self.agent, "reasoning_loop", None)
        if loop is None:
            return None
        try:
            from organs.harness import Harness
        except Exception:
            return None
        self._harness_obj = Harness(
            loop=loop, solver=getattr(loop, "solver", None),
            sandbox=getattr(loop, "sandbox", None),
            learning=getattr(self.agent, "learning_loop", None),
            channel=self._knowledge_channel())
        return self._harness_obj

    def route_get(self, path: str, query: dict | None = None) -> tuple:
        q = query or {}
        g = lambda k, d=None: (q.get(k) or [d])[0] if k in q else d
        if path in ("/api/state", "/api/full_state"):
            return 200, self.get_full_state()
        if path == "/api/organs":
            return 200, self.get_organs_state()
        if path == "/api/neural/state":
            return 200, self.neural_state()
        if path == "/api/neural/growth":
            ng = getattr(self.agent, "neural_growth", None)
            if ng is None:
                return 200, {"present": False,
                             "note": "no growth organ attached"}
            return 200, {"present": True, **ng.get_state()}
        if path == "/api/language/curriculum":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            pos = getattr(lang, "_cur_pos", 0)
            return 200, {"done": lang.curriculum_done,
                         "lesson": min(pos, len(lang.lessons)),
                         "total": len(lang.lessons),
                         "attention": round(lang.attention, 3),
                         "reward": lang.curriculum_reward,
                         "groundings": lang.known_groundings(),
                         "care_actions": sorted(lang.CARE_ACTIONS),
                         "narration": {
                             "phase": lang._phase(),
                             "world_clock": round(lang.world_clock, 1),
                             "cooldown_world_s": lang.REPEAT_COOLDOWN_WORLD_S,
                             "event_window_world_s": lang.EVENT_WINDOW_WORLD_S,
                             "care_active": lang._active_care(),
                             "recent_events": [
                                 {"kind": e.get("kind"),
                                  "detail": e.get("detail", ""),
                                  "age_world_s": round(
                                      lang.world_clock
                                      - float(e.get("at", 0.0)), 1),
                                  "narrated": e.get("narrated", 0)}
                                 for e in list(lang._events)[-8:]]},
                         "lessons": lang.curriculum_list()}
        if path == "/api/persons":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            return 200, lang.persons_state()
        if path == "/api/language/voice":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            return 200, {"enabled": bool(lang.voice_prosthesis),
                         "max_sentence_words": int(lang.max_sentence_words),
                         "note": "the prosthesis only articulates; the words are "
                                 "his and are always reported beside the render"}
        if path == "/api/language/probe":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            sent = [s for s in (g("sentences", "") or "").split("|") if s.strip()]
            return 200, lang.comprehension_probe(sent or None)
        if path == "/api/memory":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            return 200, lang.memory_state(q=g("q", ""),
                                          limit=int(g("limit", 12) or 12))
        if path == "/api/modulation":
            mod = getattr(self.agent, "modulation", None)
            if mod is None:
                return 200, {"present": False}
            return 200, mod.state_report()
        if path == "/api/compartment":
            core = getattr(getattr(self.agent, "engine", None), "static", None)
            if core is None or not hasattr(core, "compartment_stats"):
                return 200, {"present": False}
            rows = core.compartment_stats()
            return 200, {"present": True,
                         "rule": "per-compartment lr / tau_e / rpe-gain / cap",
                         "declared_model_choice": True,
                         "plasticity": core.plasticity_report(),
                         "compartments": rows}
        if path == "/api/language/questions":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            return 200, {"pairs_seen": lang.qa_pairs_seen,
                         "interrogatives": sorted(lang.interrogatives),
                         # What actually counts as a question word when he is
                         # asked something: a word demoted for appearing in
                         # ordinary statements is still listed above, because it
                         # was voted for, but it is no longer used.
                         "effective_interrogatives": sorted(
                             w for w in lang.interrogatives
                             if lang.is_interrogative(w)),
                         "role_votes": lang.role_votes_report(),
                         "role_used": {w: lang.role_for(w)
                                       for w in sorted(lang.interrogatives)
                                       if lang.is_interrogative(w)},
                         "answer_types": {
                             w: sorted(lang.answer_types.get(w, {}),
                                       key=lambda k: -lang.answer_types[w][k])[:6]
                             for w in sorted(lang.interrogatives)
                             if lang.is_interrogative(w)}}
        if path == "/api/cortex":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"present": False}
            st = lang.cortex.stats()
            st["algebra_self_test"] = lang.cortex.binder.self_test()
            st["role_recovery_on_own_memory"] = lang.cortex.self_evaluate()
            return 200, st
        if path == "/api/language/exposure":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            if getattr(lang, "books_dir", None) is None:
                lang.set_books_dir(ROOT / "books")
            return 200, lang.exposure_state()
        if path == "/api/neural/map":
            if getattr(self, "_brain_map", None) is not None:
                return 200, self._brain_map
            eng = getattr(self.agent, "engine", None)
            core = getattr(eng, "static", None)
            g = getattr(core, "g", None)
            if g is None:
                return 200, {"present": False}
            region_of = _banc_regions()
            zones = {}
            for nid in g.node_ids:
                grp = _region_group(region_of.get(int(nid), ""))
                zones[grp] = zones.get(grp, 0) + 1
            pools = []
            for mpos in g.mbon_pools:
                dist = {}
                for pos in mpos:
                    grp = _region_group(
                        region_of.get(int(g.node_ids[int(pos)]), ""))
                    dist[grp] = dist.get(grp, 0) + 1
                tot = sum(dist.values()) or 1
                pools.append({k: round(v / tot, 3) for k, v in
                              sorted(dist.items(), key=lambda kv: -kv[1])})
            self._brain_map = {"present": True, "zones": zones,
                               "pools": pools,
                               "n_actions": int(g.n_actions)}
            return 200, self._brain_map
        if path == "/api/world/state":
            hb = getattr(self.agent, "heartbeat", None)
            if hb is None or not hasattr(hb, "world_state"):
                return 200, {"speed": "unknown"}
            return 200, hb.world_state()
        if path == "/api/language/stream":
            lang = getattr(self.agent, "language", None)
            since = float(g("since", 0) or 0)
            events = lang.recent_events(since) if lang is not None \
                and hasattr(lang, "recent_events") else []
            return 200, {"events": events, "now": time.time(),
                         "ticks": getattr(lang, "ticks", 0)}
        if path == "/api/language/state":
            return 200, self.language_state()
        if path == "/api/language/store":
            return 200, self.language_store(
                str(g("section", "vocabulary") or "vocabulary"),
                query=str(g("q", "") or ""),
                limit=int(g("limit", 100) or 100),
                known_only=str(g("known", "") or "") in ("1", "true", "yes"))
        if path == "/api/language/overnight":
            return 410, {"gone": True,
                         "reason": "autotraining removed: this being is "
                                   "taught by teachers its administrator "
                                   "connects, not by a cron job"}
        if path == "/api/language/speak":
            lang = getattr(self.agent, "language", None)
            ctx = str(g("context", "") or "")
            return 200, (lang.speak(ctx) if lang is not None
                         and hasattr(lang, "speak")
                         else {"spoken": False, "reason": "no language"})
        if path == "/api/language/train":
            return 410, {"gone": True,
                         "reason": "cron teaching removed; teachers are "
                                   "connected by the administrator"}
        if path == "/api/consciousness":
            return 200, self.get_consciousness()
        if path == "/api/thoughts":
            hb = getattr(self.agent, "heartbeat", None)
            # Same distinction as get_consciousness: absent is reported as absent, not as
            # an empty list that reads like a working organ with nothing to say.
            return 200, {"thoughts": (list(getattr(hb, "thoughts", []))[-50:]
                                       if hb is not None else []),
                         "present": hb is not None}
        if path == "/api/chat_history":
            return 200, {"history": list(self.chat_history)}
        if path == "/api/progress":
            since = int(g("since", 0) or 0)
            return 200, {"events": [e for e in self.progress
                                    if e["seq"] > since]}
        if path == "/api/files":
            root = self.project_root
            base = self._resolve(g("path", ".") or ".")
            if not self._inside_root(base):
                return 200, {"files": [], "count": 0}
            rows, total = [], 0
            for f in sorted(base.rglob("*")):
                if f.is_dir() or f.suffix in (".pyc", ".npz", ".dmp", ".bin"):
                    continue
                rel = f.relative_to(root)
                if any(part.startswith(".") or part == "__pycache__"
                       for part in rel.parts):
                    continue
                rel = rel.as_posix()
                if len(rows) < 600:
                    try:
                        rows.append({"path": rel,
                                     "size": f.stat().st_size})
                    except OSError:
                        continue
                total += 1
            return 200, {"files": rows, "count": total, "root": str(root)}
        if path == "/api/file":
            p = self._resolve(g("path", ""))
            if not self._inside_root(p) or not p.exists():
                return 404, {"error": "no such file"}
            if any(part.startswith(".") or part == "__pycache__"
                   for part in p.relative_to(
                       self.project_root.resolve()).parts):
                return 403, {"error": "forbidden"}
            return 200, {"path": str(p), "content": p.read_text(
                encoding="utf-8", errors="replace")}
        if path == "/api/research":
            hb = getattr(self.agent, "heartbeat", None)
            if hb is None:
                return 200, {"success": False, "reason": "no heartbeat"}
            return 200, hb.research(str(g("q", "") or ""))
        if path == "/api/config":
            return 200, self.get_config()
        if path == "/api/procedures":
            ll = getattr(self.agent, "learning_loop", None)
            if ll is None:
                return 200, {"present": False,
                             "note": "no learning loop attached"}
            qq = str(g("q", "") or "").lower()
            limit = int(g("limit", 40) or 40)
            rows = []
            for sig, rec in getattr(ll, "store", {}).items():
                if qq and qq not in sig.lower() and \
                        qq not in str(rec.get("task", "")).lower():
                    continue
                rows.append({"signature": sig,
                             "task": rec.get("task", ""),
                             "tries": rec.get("tries", 0),
                             "successes": rec.get("successes", 0),
                             "confidence": rec.get("confidence", 0),
                             "verified": (rec.get("successes", 0) or 0) > 0,
                             "discarded": bool(rec.get("discarded"))})
            return 200, {"present": True, "procedures": rows[:limit]}
        if path == "/api/patterns":
            ll = getattr(self.agent, "learning_loop", None)
            mem = getattr(ll, "patterns", None) if ll is not None else None
            facts = getattr(mem, "facts", {}) if mem is not None else {}
            qq = str(g("q", "") or "").lower()
            limit = int(g("limit", 40) or 40)
            rows = []
            for key, fact in sorted(facts.items()):
                if qq and qq not in str(key).lower():
                    continue
                rows.append({"key": str(key), "name": str(key),
                             "confidence": fact.get("confidence", 0),
                             "hits": fact.get("last_accessed", 0)})
            return 200, {"present": mem is not None,
                         "patterns": rows[:limit]}
        if path == "/api/cache":
            qc = getattr(self.agent, "query_cache", None)
            if qc is None:
                return 200, {"present": False,
                             "note": "no query cache attached"}
            stats = qc.stats() if hasattr(qc, "stats") else {}
            entries = []
            con = getattr(qc, "_con", None)
            limit = int(g("limit", 40) or 40)
            if con is not None:
                try:
                    for row in con.execute(
                            "SELECT question, mode, verified, tokens_in, "
                            "tokens_out, hits FROM entries "
                            "ORDER BY created DESC LIMIT ?", (limit,)):
                        entries.append({"question": row[0], "mode": row[1],
                                        "verified": bool(row[2]),
                                        "tokens_in": row[3],
                                        "tokens_out": row[4], "hits": row[5]})
                except Exception:
                    pass
            return 200, {"present": True, "stats": stats, "entries": entries}
        if path == "/api/learning_history":
            ll = getattr(self.agent, "learning_loop", None)
            n = int(g("n", 30) or 30)
            events = []
            if ll is not None:
                ep = getattr(ll, "events_path", None)
                try:
                    if ep and Path(ep).exists():
                        for line in Path(ep).read_text(
                                encoding="utf-8",
                                errors="replace").splitlines()[-n:]:
                            try:
                                events.append(json.loads(line))
                            except Exception:
                                pass
                except OSError:
                    pass
            return 200, {"present": True, "events": events}
        if path == "/api/patterns_legacy":
            lang = getattr(self.agent, "language", None)
            return 200, {"patterns": list(
                getattr(lang, "word_patterns", {}).items())[:200]}
        if path == "/api/procedures":
            ll = getattr(self.agent, "learning_loop", None)
            proc = getattr(ll, "procedures", None) or {}
            try:
                rows = list(proc.keys())[:200]
            except Exception:
                rows = []
            return 200, {"procedures": rows}
        if path == "/api/learning_history":
            ll = getattr(self.agent, "learning_loop", None)
            hist = getattr(ll, "history", []) if ll is not None else []
            return 200, {"history": list(hist)[-100:]}
        if path == "/api/cache":
            qc = getattr(self.agent, "query_cache", None)
            if qc is None:
                return 200, {"present": False}
            entries = getattr(qc, "cache", {})
            return 200, {"entries": len(entries)}
        if path == "/api/reasoning/state":
            # Everything the reasoning panel needs, in one call: the loop's own
            # numbers, what is in the library and on what evidence, whether an
            # oracle is reachable, and the curriculum and reader that feed it.
            loop = getattr(self.agent, "reasoning_loop", None)
            ll = getattr(self.agent, "learning_loop", None)
            store = getattr(ll, "store", {}) or {}
            kinds: dict = {}
            for r in store.values():
                k = str((r or {}).get("last_evidence") or "none")
                kinds[k] = kinds.get(k, 0) + 1
            oracle = getattr(self.agent, "api_oracle", None)
            out = {
                "loop_present": loop is not None,
                "loop_error": getattr(self.agent, "last_loop_error", None),
                "loop": (loop.stats() if loop is not None else None),
                "library": {
                    "procedures": len(store),
                    "trusted": sum(1 for r in store.values()
                                   if float((r or {}).get("confidence", 0)) >= 0.70),
                    "evidence": kinds},
                "oracle": {"provider": getattr(oracle, "provider", None),
                           "model": getattr(oracle, "model", None),
                           "mode": getattr(oracle, "mode", None),
                           "key": bool(getattr(oracle, "has_key", False))},
            }
            from tools.make_curriculum import status as _cs
            out["curriculum"] = _cached_state("curriculum", _cs)
            from tools.reader import status as _rs
            out["reader"] = _cached_state("reader", _rs)
            # THE 90/10 NUMBER, LIVE. Offline tools could report it; the dashboard could
            # not, because the branch that fired was never recorded on the live path.
            _h = self._harness()
            out["harness"] = _h.report() if _h is not None else None
            return 200, out
        return 404, {"error": f"no such endpoint: {path}"}

    def route_post(self, path: str, data: dict | None = None) -> tuple:
        """Answer a POST. ALWAYS returns (status, payload).

        Seven branches returned a bare dict here instead, and the HTTP layer does
        `code, payload = house.route_post(u.path, data)` -- so unpacking a dict yields its
        KEYS and the request dies with a ValueError. The LLM switch, file write, file
        delete and organ toggle were all broken over the network because of it, and each
        one still returned the right thing when called directly in a test, which is why it
        survived: the shape was only wrong at the seam. `test_every_route_returns_a_status
        _and_a_payload` now guards it.
        """
        data = data or {}
        if path == "/api/chat":
            return 200, self.process_chat(str(data.get("message", "")))
        if path == "/api/terminal":
            term = getattr(self.agent, "terminal", None)
            if term is None:
                return 200, {"success": False,
                             "reason": "no terminal organ"}
            try:
                lang = getattr(self.agent, "language", None)
                if lang is not None and hasattr(lang, "ground"):
                    # The command he is about to run becomes something he can
                    # feel, so words said during it wire to the act itself.
                    lang.ground("command", str(data.get("command", ""))[:60])
                r = term.run(str(data.get("command", "")))
                if isinstance(r, dict):
                    r["command"] = str(data.get("command", ""))
                    r["success"] = (r.get("returncode") == 0)
                # The outcome becomes an act he remembers, not only a percept he
                # feels. A grounded command is something happening now; a
                # proposition is something that happened, with a doer attached, and
                # only the second kind can be asked about afterwards.
                if lang is not None and hasattr(lang, "experience"):
                    head = " ".join(str(data.get("command", "")).split()[:4])
                    lang.experience(
                        "droso",
                        "runs" if isinstance(r, dict) and r.get("success")
                        else "breaks",
                        head)
                return 200, r
            except Exception as e:
                return 200, {"success": False, "stderr": str(e)[:200]}
        if path == "/api/world/speed":
            hb = getattr(self.agent, "heartbeat", None)
            if hb is None or not hasattr(hb, "set_world_speed"):
                return 200, {"success": False, "reason": "no heartbeat"}
            return 200, hb.set_world_speed(str(data.get("mode", "")))
        if path == "/api/language/forget":
            lang = getattr(self.agent, "language", None)
            if lang is None or not hasattr(lang, "forget_word"):
                return 200, {"success": False, "reason": "no language organ"}
            return 200, lang.forget_word(str((data or {}).get("word", "")))
        if path == "/api/world/care":
            lang = getattr(self.agent, "language", None)
            if lang is None or not hasattr(lang, "care"):
                return 200, {"success": False, "reason": "no language organ"}
            return 200, lang.care(str(data.get("action", "")))
        if path == "/api/language/curriculum/edit":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            op = str(data.get("op", ""))
            if op == "add":
                return 200, lang.curriculum_add(data.get("sentence", ""),
                                                data.get("tag", "custom"),
                                                data.get("care"))
            if op == "update":
                return 200, lang.curriculum_update(data.get("index", -1),
                                                   data.get("sentence", ""),
                                                   data.get("tag"),
                                                   data.get("care"))
            if op == "delete":
                return 200, lang.curriculum_delete(data.get("index", -1))
            if op == "dials":
                return 200, lang.curriculum_dials(
                    attention=data.get("attention"),
                    reward=data.get("reward"))
            return 200, {"success": False, "reason": "unknown op"}
        if path == "/api/language/curriculum":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            if str(data.get("op", "")) == "reset":
                return 200, lang.start_curriculum()
            return 200, lang.narrate_now()
        if path == "/api/language/voice":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            if data.get("enabled") is not None:
                lang.voice_prosthesis = bool(data.get("enabled"))
            mw = data.get("max_sentence_words")
            if mw is not None:
                lang.max_sentence_words = max(1, min(16, int(mw)))
            return 200, {"success": True,
                         "enabled": bool(lang.voice_prosthesis),
                         "max_sentence_words": int(lang.max_sentence_words)}
        if path == "/api/world/ground":
            lang = getattr(self.agent, "language", None)
            if lang is None or not hasattr(lang, "ground"):
                return 200, {"success": False, "reason": "no language organ"}
            return 200, lang.ground(str(data.get("kind", "thing")),
                                    str(data.get("name", "")),
                                    data.get("seconds"))
        if path == "/api/world/experience":
            lang = getattr(self.agent, "language", None)
            if lang is None or not hasattr(lang, "experience"):
                return 200, {"success": False, "reason": "no language organ"}
            return 200, lang.experience(
                str(data.get("agent", "droso") or "droso"),
                str(data.get("verb", "") or ""),
                str(data.get("object", "") or ""),
                data.get("seconds"))
        if path == "/api/goal":
            lang = getattr(self.agent, "language", None)
            goal = getattr(lang, "goal", None) if lang is not None else None
            if goal is None:
                return 200, {"present": False, "reason": "no goal organ"}
            txt = data.get("goal") or data.get("text")
            if data.get("release"):
                return 200, {"present": True, **goal.release(),
                             "state": goal.report()}
            if txt is not None:
                out = goal.hold(str(txt), float(data.get("strength", 1.0) or 1.0))
                return 200, {"present": True, **out, "state": goal.report()}
            return 200, {"present": True, **goal.report()}
        if path == "/api/world/adversity":
            lang = getattr(self.agent, "language", None)
            if lang is None or not hasattr(lang, "adversity"):
                return 200, {"success": False, "reason": "no language organ"}
            return 200, lang.adversity(
                str(data.get("kind", "bad")), str(data.get("detail", "")),
                float(data.get("severity", 0.5)))
        if path == "/api/language/answer":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            q = str(data.get("question", "") or "")
            if not q.strip():
                return 200, {"answered": False, "reason": "no question"}
            return 200, lang.answer(q, speaker=str(data.get("speaker") or "you"))
        if path == "/api/cortex/ask":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            cue = [w for w in str(data.get("cue", "") or "").lower().split() if w]
            if not cue:
                return 200, {"success": False, "reason": "no cue word"}
            return 200, lang.cortex.ask(cue, role=int(data.get("role", 0) or 0),
                                        candidates=data.get("candidates"),
                                        k=int(data.get("k", 1) or 1))
        if path == "/api/language/sentence":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            out = lang.speak_sentence(
                str(data.get("context", "") or ""),
                max_words=int(data.get("max_words",
                                       lang.max_sentence_words) or 6),
                scent=lang.person_scent(data.get("speaker") or "you"))
            if data.get("render") and out.get("spoken"):
                out["voice"] = lang.render_voice(
                    out.get("words"), context=str(data.get("context", "")))
            return 200, out
        if path == "/api/language/exposure":
            lang = getattr(self.agent, "language", None)
            if lang is None:
                return 200, {"success": False, "reason": "no language organ"}
            if getattr(lang, "books_dir", None) is None:
                lang.set_books_dir(ROOT / "books")
            if hasattr(lang, "set_oracle"):
                lang.set_oracle(getattr(self.agent, "api_oracle", None))
            allowed = ("enabled", "speed_s", "intensity_words",
                       "assimilation_threshold", "reward_exposure",
                       "reward_social", "reward_babble", "reward_teach")
            kw = {k: data[k] for k in allowed if k in data}
            bd = data.get("books_dir")
            if bd:
                # Which shelf he reads from is the parent's choice, and it matters:
                # the reader walks the shelf in order, so reaching a late book
                # means reading every earlier one first. A word is only assimilated
                # after twelve hearings, and a book whose words appear five times
                # each needs three passes before it teaches anything -- being able
                # to put one book on the shelf is the difference between that
                # taking minutes and taking an hour.
                try:
                    lang.set_books_dir(Path(str(bd)))
                except Exception as e:
                    return 200, {"success": False,
                                 "reason": f"books_dir: {e}"[:160]}
            return 200, lang.configure_exposure(**kw)
        if path == "/api/neural/grow":
            eng = getattr(self.agent, "engine", None)
            core = getattr(eng, "static", None)
            if core is None or not hasattr(core, "grow_plastic"):
                return 200, {"success": False, "reason": "no carve"}
            out = {}
            if data.get("synapses"):
                out["grown_synapses"] = core.grow_plastic(
                    int(data["synapses"]), float(data.get("w0", 0.01)))
            if data.get("prune_below") is not None:
                out["pruned_synapses"] = core.prune_plastic(
                    float(data["prune_below"]))
            if data.get("pool"):
                out["grown_pool"] = core.grow_pool(
                    int(data.get("pool_nodes", 6)),
                    int(data.get("pool_fanin", 40)))
            self.note("growth", json.dumps(out)[:120])
            return 200, {"success": True, **out}
        if path == "/api/neural/consult":
            oracle = getattr(self.agent, "api_oracle", None)
            core = getattr(getattr(self.agent, "engine", None),
                           "static", None)
            if oracle is None or core is None:
                return 200, {"success": False,
                             "reason": "no oracle or no carve"}
            try:
                oracle.require_key("neural.consult")
            except Exception as e:
                return 200, {"success": False, "reason": str(e)[:120]}
            ll = getattr(self.agent, "learning_loop", None)
            lst = ll.stats() if ll is not None and hasattr(ll, "stats") else {}
            vocab_n = len(getattr(self.agent.language,
                                  "word_patterns", {}))
            prompt = (
                "You are the growth architect of a drosophila-connectome AI "
                "called Droso. Current brain: "
                f"{int(core.g.n_nodes)} neurons, "
                f"{int(core.g.n_actions)} concept pools, "
                f"{len(core.w)} plastic synapses, "
                f"{lst.get('procedures', 0)} procedures known, mean "
                f"confidence {lst.get('mean_confidence', 0)}, "
                f"vocabulary {vocab_n} words. "
                "Reply with EXACTLY ONE JSON object, no prose: "
                '{"grow_synapses": <int 0-400>, "prune": <true|false>, '
                '"grow_pool": <true|false>, "reason": "<one sentence>"}'
                "-- decide like an engineer: grow capacity if confidence is "
                "high (saturating), prune if synapses are slack, grow a pool "
                "only if it truly needs a new concept space.")
            r = oracle.query(prompt, max_tokens=300, temperature=0.4,
                             purpose="neural_growth")
            directive = {}
            try:
                txt = str(r.get("text", ""))
                s, e2 = txt.find("{"), txt.rfind("}") + 1
                directive = json.loads(txt[s:e2])
            except Exception:
                directive = {}
            applied = {}
            if directive.get("grow_synapses"):
                n = max(0, min(400, int(directive["grow_synapses"])))
                if n:
                    applied["grow_synapses"] = core.grow_plastic(n, 0.01)
            if directive.get("prune") is True:
                applied["pruned"] = core.prune_plastic(0.004)
            if directive.get("grow_pool") is True and \
                    int(core.g.n_actions) < 24:
                applied["grown_pool"] = core.grow_pool(6, 30)
            self.note("consult", json.dumps(directive)[:120])
            return 200, {"success": True, "directive": directive,
                         "applied": applied}
        if path == "/api/llm/toggle":
            self.agent.llm_enabled = bool(data.get("enabled", True))
            mode = getattr(self.agent.api_oracle, "mode", "absent") \
                if self.agent.api_oracle else "absent"
            return 200, {"success": True, "llm_enabled": self.agent.llm_enabled,
                         "oracle_mode": mode}
        if path == "/api/breaker_reset":
            cb = getattr(self.agent, "circuit_breaker", None)
            if cb is not None and hasattr(cb, "reset"):
                cb.reset()
                return 200, {"success": True,
                             "result": {"action": "continue",
                                        "reason": "reset by house"}}
            return 200, {"success": False, "reason": "no circuit breaker"}
        if path == "/api/sandbox_answer":
            return 200, self.answer_approval(data)
        if path == "/api/file/write":
            if not self.allow_remote_mutation:
                return 200, {"success": False,
                             "reason": "remote mutation is disabled"}
            p = self._resolve(data.get("path", ""))
            if not self._inside_root(p):
                return 200, {"success": False, "reason": "outside the house"}
            content = str(data.get("content", ""))
            sb = self._sandbox()
            # THE SANDBOX ALREADY KNOWS THIS POLICY AND THE ROUTE WAS OVERRIDING IT. The
            # sandbox frees writes inside its workzone and gates everything else; this
            # branch pended EVERY write, which quietly took the workspace away -- there
            # was no file he could touch through the house without asking a human first.
            # One policy, in one place, and the sandbox is where it lives.
            #
            # It also stops the route claiming success for a write that did not happen.
            # `success: True, pending: True` reads as "done, and also queued"; nothing
            # was done, and a caller that checks `success` would believe otherwise.
            if sb is not None and hasattr(sb, "write_file"):
                res = sb.write_file(str(p), content, reason="house: /api/file/write")
                if res.get("success"):
                    return 200, {"success": True, "pending": False, "path": str(p),
                                 "result": res}
                # The sandbox records its OWN pending request before refusing, so the house
                # must not add a second one -- that double-pend is why the fence queue grew
                # by two for every attempted write and the count never lined up.
                pend = [a for a in (getattr(sb, "pending_approvals", []) or [])
                        if str(p) in str(a.get("path", "")) and not a.get("answered")]
                return 200, {"success": False, "pending": bool(pend), "path": str(p),
                             "action": pend[-1] if pend else None,
                             "reason": str(res.get("reason") or res.get("error")
                                           or "awaits a human approval")}
            entry = self._pend("WRITE", p, {"content": content})
            return 200, {"success": False, "pending": True, "action": entry,
                         "reason": "awaits a human approval"}
        if path == "/api/file/delete":
            p = self._resolve(data.get("path", ""))
            if not self._inside_root(p):
                return 200, {"success": False, "reason": "outside the house"}
            sb = self._sandbox()
            # Same as write: the sandbox owns the policy and records its own pending
            # request. The route used to answer success: True for a delete that had not
            # happened and would not until a human said so, which is the exact claim the
            # test below exists to prevent.
            if sb is not None and hasattr(sb, "delete_file"):
                res = sb.delete_file(str(p))
                if res.get("success"):
                    return 200, {"success": True, "pending": False, "path": str(p),
                                 "result": res}
                pend = [a for a in (getattr(sb, "pending_approvals", []) or [])
                        if str(p) in str(a.get("path", "")) and not a.get("answered")]
                return 200, {"success": False, "pending": bool(pend), "path": str(p),
                             "action": pend[-1] if pend else None,
                             "reason": str(res.get("reason") or res.get("error")
                                           or "awaits a human approval")}
            entry = self._pend("DELETE", p)
            return 200, {"success": False, "pending": True, "action": entry,
                         "reason": "awaits a human approval"}
        if path == "/api/config/update":
            return 200, self.update_config(data.get("config")
                                           if isinstance(
                                               data.get("config"), dict)
                                           else data)
        if path == "/api/language/overnight/start" or \
                path == "/api/language/overnight/stop":
            return 410, {"gone": True,
                         "reason": "autotraining removed: teaching is the "
                                   "administrator's hand, not a timer"}
        if path == "/api/organ/toggle":
            name = str(data.get("organ", ""))
            organ = getattr(self.agent, name, None)
            if organ is None:
                return 200, {"success": False, "reason": "no such organ"}
            enabled = bool(data.get("enabled", True))
            try:
                setattr(organ, "enabled", enabled)
                return 200, {"success": True, "organ": name, "enabled": enabled}
            except Exception as e:
                return 200, {"success": False, "reason": str(e)[:120]}
        if path == "/api/research":
            hb = getattr(self.agent, "heartbeat", None)
            if hb is None:
                return 200, {"success": False, "reason": "no heartbeat"}
            return 200, hb.research(str(data.get("q", "")))
        if path == "/api/reasoning/solve":
            loop = getattr(self.agent, "reasoning_loop", None)
            if loop is None:
                return 200, {"ok": False,
                             "reason": "no reasoning loop on this agent"}
            task = str(data.get("task", "") or "")
            check = str(data.get("check", "") or "")
            if not task.strip():
                return 200, {"ok": False, "reason": "a task needs words"}
            if not check.strip():
                # Refused on purpose. The gate is the task's own assertions, so a
                # task with no check is a task that cannot be verified, and a
                # candidate that is never verified cannot be kept. Accepting it
                # would mean returning something that looks solved and is not.
                return 200, {"ok": False,
                             "reason": "no check: without assertions nothing "
                                       "can be verified, and nothing "
                                       "unverified is ever kept"}
            out = self._solve_via_harness(loop, task, check, data)
            return 200, out
        return 404, {"error": f"no such endpoint: {path}"}

    def _solve_via_harness(self, loop, task: str, check: str, data: dict) -> dict:
        """The live solve path, through the harness, shape-compatible with the frontend.

        The panel reads the loop's own fields flat off the response (`outcome`, `attempt`,
        `candidate`, `stored`), so the harness's `loop` payload is re-flattened underneath
        and the harness keys win. The oracle only fires when the request asks for it --
        the harness is told, rather than deciding.
        """
        want_oracle = bool(data.get("oracle"))
        h = self._harness()
        if h is None:
            # No harness (no solver/channel): the loop alone, as before.
            out = loop.step(task, check, learn=bool(data.get("learn", True)))
            out["ok"] = out.get("outcome") == "solved"
            out["columns"] = {"local": out["ok"], "oracle": False}
            out["branch"] = "system2_local" if out["ok"] else "unsolved"
            return out
        r = h.solve(task, check, learn=bool(data.get("learn", True)),
                    oracle=want_oracle)
        out = dict(r.get("loop") or {})
        out.update({k: v for k, v in r.items() if k != "loop"})
        branch = r.get("branch")
        out["branch"] = branch
        out["outcome"] = "solved" if r.get("solved") else "refused"
        out["ok"] = bool(r.get("solved"))
        out["columns"] = {
            "local": branch in ("system1_fact", "system1_recall",
                                "system2_local", "code_repair"),
            "oracle": branch == "system2_oracle_hole"}
        if not want_oracle and not r.get("solved"):
            out.setdefault("reason", r.get("reason") or r.get("hole"))
        out["harness"] = h.report()
        return out

    def start(self, force_bind: bool | None = None) -> dict:
        if self._httpd is not None:
            return {"success": False, "running": True,
                    "reason": "this house is already serving"}
        if force_bind is None:
            force_bind = bool((self.config.get("house", {}) or {})
                              .get("force_bind", False))
        took_over = None
        force_bound = None
        blocker = ""
        if _port_busy(self.host, self.port):
            done, note = _take_over(self.host, self.port)
            blocker = note
            if not done:
                if not force_bind:
                    return {"success": False, "port_in_use": True,
                            "reason": f"{self.host}:{self.port} is held and could "
                                      f"not be taken over: {note}. Start with "
                                      "force_bind to bind over it anyway."}
                force_bound = note
            else:
                took_over = note
        house = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _static(self, path: str):
                import os
                if path in ("/", "/index.html"):
                    fp = STATIC_DIR / "index.html"
                elif path.startswith("/static/"):
                    fp = STATIC_DIR / path.lstrip("/")
                else:
                    fp = STATIC_DIR / path.lstrip("/")
                try:
                    fp = fp.resolve()
                    fp.relative_to(STATIC_DIR.resolve())
                except Exception:
                    self._json(403, {"error": "forbidden"})
                    return
                if not fp.is_file():
                    self._json(404, {"error": "not found"})
                    return
                ctype = {".html": "text/html", ".js":
                         "application/javascript",
                         ".css": "text/css", ".png": "image/png",
                         ".svg": "image/svg+xml"}.get(fp.suffix,
                                                      "text/plain")
                body = fp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, payload: dict):
                house._requests += 1
                if code == 403:
                    house._refused += 1
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                from urllib.parse import urlparse, parse_qs
                u = urlparse(self.path)
                if u.path == "/" or not u.path.startswith("/api/"):
                    return self._static(u.path)
                q = parse_qs(u.query)
                try:
                    code, payload = house.route_get(u.path, q)
                except Exception as e:
                    code, payload = 500, {"error": str(e)[:200]}
                self._json(code, payload)

            def do_POST(self):
                from urllib.parse import urlparse
                u = urlparse(self.path)
                peer = (self.client_address[0]
                        if self.client_address else "")
                tok = self.headers.get("X-House-Token")
                allowed, why = house.may_execute(peer, u.path, tok)
                if not allowed:
                    self._json(403, {"error": "forbidden", "reason": why,
                                     "peer": peer})
                    return
                n = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(n) if n else b"{}"
                try:
                    data = (json.loads(raw.decode("utf-8"))
                            if raw and raw.strip() else {})
                except Exception as e:
                    self._json(400, {"error": "invalid json body",
                                     "reason": str(e)[:160]})
                    return
                if not isinstance(data, dict):
                    self._json(400, {"error": "json body must be an object"})
                    return
                try:
                    code, payload = house.route_post(u.path, data)
                except Exception as e:
                    code, payload = 500, {"error": str(e)[:200]}
                self._json(code, payload)

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._server_thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True)
        self._server_thread.start()
        self._started_at = time.time()
        return {"success": True, "port": self.port, "host": self.host,
                "took_over": took_over, "force_bound": force_bound,
                "note": blocker}

    def stop(self) -> dict:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd = None
        return {"success": True}

    @property
    def server(self):
        """The live HTTP server, or None while nothing is bound."""
        return self._httpd