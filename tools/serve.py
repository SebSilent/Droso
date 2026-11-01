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
import threading
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
    payload = {
        "id": f"chatcmpl-droso-{server.turns_served}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "droso",
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
    }
    if getattr(server, "electric", False):
        # The demo's telemetry.  respond() returns no such keys -- the inventory is
        # state on the organ, so it is read there -- and `taught_this_turn` is a
        # DIFF against what this server saw before the turn, which is the only way to
        # know a fact entered on THIS utterance rather than sometime earlier.
        # Gated on the flag: without --electric this payload is byte-identical to
        # yesterday's, which is what "ELECTRIC off for battery runs" has to mean for
        # the wire format too, not just for the organ.
        says = getattr(server.session.lang, "_taught_says", {}) or {}
        inv = sum(len(v) for v in says.values())
        before = getattr(server, "taught_seen", 0)
        server.taught_seen = inv
        payload["choices"][0]["electric"] = {
            "spoken": reply.get("spoken"),
            "source": reply.get("source"),
            "reason": reply.get("reason"),
            "licensed_refusal": reply.get("licensed_refusal"),
            "inventory": inv,
            "subjects": len(says),
            "taught_this_turn": inv - before,
        }
    return payload


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
        if path == "/shutdown":
            # DEMO MODE ONLY: without --electric this 404s, so the route is not a new
            # door on the production server.  A person closing the demo and a test that
            # restarts it both need an exit that runs main()'s finally -- the session
            # save lives there -- because terminate() on Windows skips it, and a
            # persistence claim resting on a killed process would be testing nothing.
            if not getattr(self.server, "electric", False):
                self._error(404, f"unknown path {path!r}", "invalid_request_error")
                return
            try:
                state_hygiene.save_session_state(self.server.session.lang,
                                                 "serve session (demo shutdown)")
            except Exception as exc:   # never report a save that did not happen
                self._error(500, f"shutdown save failed: {type(exc).__name__}: {exc}",
                            "droso_internal_error")
                return
            self._send(200, {"saved": True, "turns": self.server.turns_served})
            # Another thread, always.  This server is single-threaded, so this handler
            # is running INSIDE serve_forever, and shutdown() blocks until that loop
            # reports itself stopped -- I hit exactly that deadlock in
            # tools/electric_chat.py and a test hung 180 s on a process waiting for
            # itself.
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
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
    ap.add_argument("--electric-reverse", action="store_true",
                    help="Within --electric only: let a reverse-role ask like 'who does X "
                         "belong to?' reach the keyed inventory. Requires the ask to strand a "
                         "preposition, which is what proves the noun in the middle of the "
                         "question is the tell's own subject. OFF by default, and inert without "
                         "--electric.")
    ap.add_argument("--electric-object-role", action="store_true",
                    help="Within --electric only: let an ask that names a tell's OBJECT and "
                         "wants its SUBJECT ('what bites the latch?') reach that tell. "
                         "C4d measured that --electric-reverse does NOT cover this shape and "
                         "that the subject path mis-binds it, so this is a THIRD, separate "
                         "permission. It only ever runs after the subject path has found "
                         "nothing. OFF by default, and inert without --electric.")
    ap.add_argument("--electric-fragment-guard", action="store_true",
                    help="Independent of --electric: when nothing he remembers answers "
                         "the ask, do not let the house speak a fragment of the ask "
                         "itself (measured: `to?`). Repairs a licensed absence "
                         "falling through to fragment speech. OFF by default; the leak "
                         "reproduces with --electric off, so this is not gated by it.")
    ap.add_argument("--electric-ask-admissibility", action="store_true",
                    help="Independent of --electric: a question someone asked is "
                         "remembered as an ASKING, tagged at storage, and dropped from "
                         "the recall hits before the arbiter -- so no read path can "
                         "answer from a remembered question (the `to?` fragment and the "
                         "whole-question read-back are both its symptoms). OFF by "
                         "default: nothing is tagged, nothing is dropped.")
    ap.add_argument("--electric", action="store_true",
                    help="ELECTRIC demo mode: statements heard in chat are taught into "
                         "the keyed inventory and questions may be answered from it, "
                         "including an admitted ignorance for a relation never told. "
                         "OFF by default -- without it this server is byte-identical to "
                         "yesterday's, and every battery run stays ELECTRIC-free.")
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
    # NOT an ELECTRIC feature.  Measured with ELECTRIC entirely off, the house still
    # speaks `to?` for `who does the mouse chase?` once it has remembered the stranded
    # variant of that ask -- the fragment comes out of the recall path, not out of
    # ELECTRIC.  So this switch is read outside the --electric block: off by default,
    # and when set it applies to the house path whatever else is on.
    agent.language.ELECTRIC_FRAGMENT_GUARD = bool(args.electric_fragment_guard)
    # Both switches are read OUTSIDE the --electric block: the leak they address
    # reproduces with ELECTRIC off entirely, because the branch is in the recall path.
    agent.language.ELECTRIC_ASK_ADMISSIBILITY = bool(args.electric_ask_admissibility)
    if args.electric:
        # Flags on the INSTANCE, never on the class: if this flipped
        # NeuralLanguage.ELECTRIC_*, a demo run in a shared interpreter would leak into
        # whatever battery run came after it.  ELECTRIC_TEACH is a write permission,
        # ELECTRIC_ANSWER a read permission, and ABSENCE_INVENTORY is what licenses the
        # admission at all -- without it an untaught relation produces silence, not "I
        # don't know", which would make the demo's honesty invisible.
        lang = agent.language
        lang.ELECTRIC_TEACH = True
        lang.ELECTRIC_ANSWER = True
        lang.ABSENCE_INVENTORY = True
        # Reverse-role asks are a separate permission (see NeuralLanguage.
        # ELECTRIC_REVERSE): a miss there can return the wrong fact about the right
        # noun instead of nothing, so it is not folded into --electric.
        lang.ELECTRIC_REVERSE = bool(args.electric_reverse)
        # Object-role asks get their own switch for the same reason, and because
        # ELECTRIC_REVERSE already turned out to do more than its name says (C4d) --
        # folding a third behaviour into it would make the flag un-analysable.
        lang.ELECTRIC_OBJECT_ROLE = bool(args.electric_object_role)
        # THE RESTART HALF. converse.build() repoints writes into the session dir and
        # never reads them back, so a second serve.py over the same --session-dir would
        # come up amnesiac even though the state is on disk.  load_state() is a no-op
        # returning {"loaded": False} when the file is absent (:5082), so the first life
        # of a session is untouched.  The save at exit is already a delta save, and
        # save_state writes the json -- which carries taught_says -- even in delta mode
        # (:5015-5017, :4995).
        lres = lang.load_state()
        print(f"[serve] ELECTRIC on: loaded={bool((lres or {}).get('loaded'))} "
              f"taught facts={sum(len(v) for v in lang._taught_says.values())} "
              f"subjects={len(lang._taught_says)} "
              f"reverse={args.electric_reverse} object_role={args.electric_object_role}",
              flush=True)
    session = converse.Session(agent, beats=args.beats)
    print(f"[serve] loaded in {time.time() - t0:.1f}s: "
          f"{len(agent.language.word_patterns)} words, "
          f"{converse.snapshot(agent)['propositions']} propositions",
          flush=True)
    print(f"[serve] reading state from: "
          f"{args.state or 'the live tree (read-only)'}", flush=True)

    httpd = DrosoHTTPServer((args.host, args.port), Handler, session)
    httpd.electric = bool(args.electric)
    # Seed the diff from what the organ ALREADY HAS, not from zero.  Without this a
    # restarted session reports its loaded inventory as if this turn taught it --
    # measured: the first ask after a restart printed taught_this_turn: 3 for 3 facts
    # it had loaded from disk and had not been told in that life at all.
    httpd.taught_seen = sum(len(v) for v in
                            session.lang._taught_says.values()) if args.electric else 0
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
        # With the snapshot keyed by CONTENT at every depth, a churn name in
        # `moved` means its BYTES changed -- that is not "known no-op churn" and must
        # not be excused, so the bare-filename exclusion below is gone rather than
        # extended. It never worked anyway: these keys are relative paths
        # ("live_learner/current/banc_brain.npz"), so `m == "banc_brain.npz"` matched
        # nothing, `known` stayed empty, and every life printed "live files untouched:
        # False" over mtime-only rewrites while being equally blind to a real write.
        churn = {Path(m).name for m in converse.KNOWN_CHURN}
        changed = sorted(m for m in moved if Path(m).name in churn)
        unexpected = sorted(m for m in moved if Path(m).name not in churn)
        print(f"[serve] {httpd.turns_served} turns served; "
              f"live files untouched: {not moved}", flush=True)
        if changed:
            print(f"[serve] LIVE FILES CONTENT CHANGED (churn files, NOT no-op): "
                  f"{changed}", flush=True)
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