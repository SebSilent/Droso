"""Why does the accumulation script's turn 3 go silent on the HTTP side?

The 05:00 drift report shows the suite's only CLI-vs-HTTP difference:
turn 3 ("the box is on the shelf") replies "vagabond pruned" on the CLI
path and "" on the HTTP path.  Both paths call the same Session.ask, so
the difference must come from process-level state.  This probe runs BOTH
paths and logs the full reply diagnostics per turn -- reason, mood,
resonance, threshold, attention, social_drive, RNG position -- so the
silent turn's why is on the record instead of guessed at.

Run:  python tools/probe_turn3_flip.py
"""

from __future__ import annotations

import json
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.converse as converse  # noqa: E402

SHADOW = ROOT / "state" / "sessions" / "drift_shadow_20261026_044855"
FITNESS = ROOT / "state" / "fitness"
OUT = FITNESS / "probe_turn3_out.txt"

SCRIPT = {
    "name": "accumulation",
    "kind": "warm",
    "turns": [
        {"say": "the box is heavy"},
        {"say": "the box is red"},
        {"say": "the box is on the shelf"},
        {"ask": "how is the box", "expect": {"any_of": ["heavy"]}},
        {"ask": "where is the box", "expect": {"any_of": ["shelf"]}},
    ],
}


def rng_fingerprint() -> dict:
    """Where the legacy global RNG stands: position plus the first words."""
    st = __import__("numpy").random.get_state()
    return {"pos": int(st[2]),
            "head": [int(x) for x in st[1][:3]]}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_for_models(port: int, timeout_s: float = 240.0) -> None:
    url = f"http://127.0.0.1:{port}/v1/models"
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(1.0)
    raise RuntimeError("serve did not answer /v1/models")


def post_turn(port: int, text: str) -> str:
    body = json.dumps({"messages": [{"role": "user", "content": text}]}
                      ).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


# ------------------------------------------------------- instrumented server --

def serve(port: int, session_dir: Path, log_path: Path) -> None:
    """serve.py's exact boot, plus one diagnostics line per turn."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlsplit

    agent = converse.build(session_dir, project_root=str(SHADOW))
    session = converse.Session(agent, beats=2)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if urlsplit(self.path).path == "/v1/models":
                self._send(200, {"object": "list", "data": [
                    {"id": "droso", "object": "model"}]})
            else:
                self._send(404, {"error": {"message": "unknown path",
                                           "type": "invalid_request_error"}})

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/v1/chat/completions":
                self._send(404, {"error": {"message": "unknown path",
                                           "type": "invalid_request_error"}})
                return
            length = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            content = [m.get("content") for m in req.get("messages", [])
                       if m.get("role") == "user"][-1]
            turn = session.ask(content, kind="free")
            reply = turn.get("reply") or {}
            said = str(reply.get("utterance") or reply.get("response") or "")
            body = {"id": "chatcmpl-droso", "object": "chat.completion",
                    "created": int(time.time()), "model": "droso",
                    "choices": [{"index": 0,
                                 "message": {"role": "assistant",
                                             "content": said},
                                 "finish_reason": "stop"}]}
            self._send(200, body)
            # the diagnostics line: everything the report cannot see
            diag = {"n": turn["n"], "said": turn["said"],
                    "reply": turn["reply"],
                    "state_before": turn["state_before"],
                    "state_after": turn["state_after"],
                    "beats": turn["beats"],
                    "rng": rng_fingerprint()}
            print("TURN " + json.dumps(diag), flush=True)

    class Server(HTTPServer):
        def __init__(self, addr, handler):
            super().__init__(addr, handler)

    httpd = Server(("127.0.0.1", port), Handler)
    print(f"[probe-serve] listening on {port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            agent.language.save_state()
        except Exception as e:
            print(f"[probe-serve] save failed: {e}", flush=True)


# ------------------------------------------------------------------- runner --

def main() -> int:
    lines = []

    def out(s: str) -> None:
        print(s)
        lines.append(s)

    # ---- HTTP side: this file in server mode, one POST per turn
    port = free_port()
    http_dir = ROOT / "state" / "sessions" / "probe_turn3_http"
    http_dir.mkdir(parents=True, exist_ok=True)
    log_path = FITNESS / "probe_turn3_http.log"
    cmd = [sys.executable, str(Path(__file__).resolve()), "--serve",
           "--port", str(port)]
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log,
                                stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                                if sys.platform == "win32" else 0)
        try:
            wait_for_models(port)
            http_replies = []
            for step in SCRIPT["turns"]:
                text = step.get("say") or step.get("ask") or ""
                http_replies.append(post_turn(port, text))
        finally:
            proc.send_signal(signal.CTRL_BREAK_EVENT
                             if sys.platform == "win32" else signal.SIGINT)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    http_diag = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TURN "):
            http_diag.append(json.loads(line[5:]))

    out("=== HTTP side (instrumented serve) ===")
    for i, (text, rep) in enumerate(zip(
            [s.get("say") or s.get("ask") for s in SCRIPT["turns"]],
            http_replies), 1):
        out(f"  turn {i}: said={text!r} -> reply={rep!r}")

    # ---- CLI side: build + Session + run_script in this process
    out("")
    out("=== CLI side (in-process run_script) ===")
    cli_dir = ROOT / "state" / "sessions" / "probe_turn3_cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    agent = converse.build(cli_dir, project_root=str(SHADOW))
    session = converse.Session(agent, beats=2)
    converse.run_script(session, SCRIPT)
    for t in session.turns:
        out(f"  turn {t['n']}: said={t['said']!r} kind={t['kind']} "
            f"reply={json.dumps(t['reply'])}")
        out(f"    state_before={t['state_before']} "
            f"state_after={t['state_after']} rng={rng_fingerprint()}")

    # ---- the turn-3 diagnostics, side by side
    out("")
    out("=== turn 3, side by side ===")
    if len(http_diag) >= 3:
        d = http_diag[2]
        out("HTTP turn 3 reply: " + json.dumps(d["reply"], indent=1))
        out("HTTP turn 3 state_before: " + json.dumps(d["state_before"]))
        out("HTTP turn 3 beats: " + json.dumps(d["beats"]))
        out("HTTP turn 3 rng: " + json.dumps(d["rng"]))
    if len(session.turns) >= 3:
        t = session.turns[2]
        out("CLI turn 3 reply: " + json.dumps(t["reply"], indent=1))
        out("CLI turn 3 state_before: " + json.dumps(t["state_before"]))
        out("CLI turn 3 beats: " + json.dumps(t["beats"]))

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out("")
    out(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    if "--serve" in sys.argv:
        i = sys.argv.index("--port")
        serve(int(sys.argv[i + 1]),
              ROOT / "state" / "sessions" / "probe_turn3_http",
              FITNESS / "probe_turn3_http.log")
    else:
        raise SystemExit(main())