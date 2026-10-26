"""Droso over the OpenAI chat-completions format.

One utterance in, one reply out, through the same door every other
measurement uses: converse.build() for the agent, Session.ask() for the
turn.  The server adds no machinery of its own: no streaming, no system
prompt, no token counting, no temperature.  Of a request's messages,
only the last one with role "user" is the utterance; its content goes
through the door as speaker "you"; the reply's utterance comes back as
choices[0].message.content.  When he stays silent the content is an
empty string: silence is a true report, and an internal reason must not
be passed off as his words.

The server is single-threaded: one request at a time, one session for
the server's lifetime, HTTP/1.0 so a connection cannot hold the server.
Writes are re-pointed into a session directory under state/sessions/ as
in every harness run, so the tree it reads is never written.  --state
points the reads at a shadow tree (the cross-session harness's
build_shadow), which keeps a server and the suite from ever sharing a
tree.

Usage:
    python tools/serve.py                       # live tree, read-only
    python tools/serve.py --state <shadow>      # reads a shadow tree
    python tools/serve.py --port 8000 --host 127.0.0.1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.converse as converse  # noqa: E402
from tools import state_hygiene  # noqa: E402


# ------------------------------------------------------------- payloads ----

def last_user_message(messages) -> tuple[str | None, str | None]:
    """The last message with role "user", or why there is none.

    Returns (content, error); exactly one is truthy.  Only the selected
    message is validated: a system or assistant message with an exotic
    content shape is ignored, not an error, because it is never the
    utterance.
    """
    if not isinstance(messages, list):
        return None, "messages must be an array"
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            return None, "every message must be an object"
        if msg.get("role") == "user":
            content = msg.get("content")
            if not isinstance(content, str):
                return None, "the user message's content must be a string"
            return content, None
    return None, "no user message in the request"


def completion_payload(turn: dict, server: "DrosoHTTPServer") -> dict:
    """The standard chat-completion shape, nothing else.

    A spoken reply's utterance is the content; a silent turn is an empty
    content.  usage is omitted: he counts words, not tokens, and a
    fabricated number would be worse than a missing field.
    """
    reply = turn.get("reply") or {}
    said = reply.get("utterance") or reply.get("response") or ""
    content = str(said) if reply.get("spoken") else ""
    server.turns_served += 1
    return {
        "id": f"chatcmpl-droso-{server.turns_served}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "droso",
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
    }


def models_payload(server: "DrosoHTTPServer") -> dict:
    return {"object": "list",
            "data": [{"id": "droso", "object": "model",
                      "created": server.booted_at, "owned_by": "droso"}]}


# --------------------------------------------------------------- server ----

class DrosoHTTPServer(HTTPServer):
    """An HTTPServer (one request at a time) carrying the one session."""

    def __init__(self, addr, handler, session):
        super().__init__(addr, handler)
        self.session = session
        self.turns_served = 0
        self.booted_at = int(time.time())


class Handler(BaseHTTPRequestHandler):
    """One utterance in, one reply out.  Errors use OpenAI's shape."""

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str, err_type: str) -> None:
        self._send(code, {"error": {"message": message, "type": err_type,
                                    "code": code}})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/v1/models":
            self._send(200, models_payload(self.server))
        elif path == "/v1/chat/completions":
            self._error(405, "chat completions are POST; GET is only for "
                             "/v1/models", "invalid_request_error")
        else:
            self._error(404, f"unknown path {path!r}", "invalid_request_error")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/v1/models":
            self._error(405, "models are GET", "invalid_request_error")
            return
        if path != "/v1/chat/completions":
            self._error(404, f"unknown path {path!r}", "invalid_request_error")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            req = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self._error(400, f"request body is not valid JSON: {exc}",
                        "invalid_request_error")
            return
        if not isinstance(req, dict):
            self._error(400, "request body must be a JSON object",
                        "invalid_request_error")
            return
        content, err = last_user_message(req.get("messages"))
        if err:
            self._error(400, err, "invalid_request_error")
            return
        try:
            turn = self.server.session.ask(content, kind="free")
        except Exception as exc:  # the organ raised; say so, never fake a reply
            self._error(500, f"{type(exc).__name__}: {exc}",
                        "droso_internal_error")
            return
        self._send(200, completion_payload(turn, self.server))


# ------------------------------------------------------------------ cli ----

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--state", default=None,
                    help="project root to read state from (a shadow tree); "
                         "default: the live tree, read-only")
    ap.add_argument("--beats", type=int, default=2,
                    help="autonomous ticks between turns (as in the harness)")
    ap.add_argument("--session-dir", default=None)
    args = ap.parse_args()

    try:
        import numpy  # noqa: F401
    except ImportError as exc:
        print(f"[serve] interpreter has no numpy ({exc}); refusing to run\n"
              f"[serve] interpreter: {sys.executable}")
        return 2

    session_dir = Path(args.session_dir) if args.session_dir else \
        converse.STATE / "sessions" / f"serve_{time.strftime('%Y%m%d_%H%M%S')}"
    # The guard window starts before the build, so the verdict covers the
    # whole run, not just the turns (debt entry 6's fix shape).
    guard_before = converse.guard_live_files("serve")
    print(f"[serve] loading Droso (session dir: {session_dir}) ...", flush=True)
    t0 = time.time()
    agent = converse.build(session_dir, project_root=args.state)
    session = converse.Session(agent, beats=args.beats)
    print(f"[serve] loaded in {time.time() - t0:.1f}s: "
          f"{len(agent.language.word_patterns)} words, "
          f"{converse.snapshot(agent)['propositions']} propositions",
          flush=True)
    print(f"[serve] reading state from: "
          f"{args.state or 'the live tree (read-only)'}", flush=True)

    httpd = DrosoHTTPServer((args.host, args.port), Handler, session)
    print(f"[serve] listening on http://{args.host}:{args.port}/v1 "
          f"(model: droso, single-threaded)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        moved = converse.guard_check(guard_before)
        # banc_brain.npz churns on every run start (debt entry 6): a no-op
        # rewrite whose mtime moves while the arrays stay identical.  Named
        # here, excluded from the verdict; the drift check re-verifies its
        # content on every run.
        known = sorted(m for m in moved if m == "banc_brain.npz")
        unexpected = sorted(m for m in moved if m != "banc_brain.npz")
        print(f"[serve] {httpd.turns_served} turns served; "
              f"live files untouched: {not unexpected}", flush=True)
        if known:
            print(f"[serve] known no-op churn (debt entry 6): {known}",
                  flush=True)
        if unexpected:
            print(f"[serve] LIVE FILES TOUCHED: {unexpected}", flush=True)
        # Delta save, fatal on failure: a smoke test that half-saved its
        # session must exit nonzero, not print and pass.
        state_hygiene.save_session_state(agent.language, "serve session")
        print(f"[serve] session state written under {session_dir}",
              flush=True)
        state_hygiene.prune_sessions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())