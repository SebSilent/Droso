"""ELECTRIC live demo -- teach facts in chat, survive a real restart, answer a
paraphrase, admit ignorance.

Why this exists.  Every ELECTRIC experiment so far (C1/C2/C3) drove the organ from a
script, in-process, over one interpreter.  That measures the mechanism but never
answers the question a person actually asks: *can I talk to it, and is it still there
after I close the window?*  This is that door, and it is deliberately small.

The intended door is ``respond()`` -- the same call the house's chat uses
(``tools/converse.py:288``), which routes by FORM: a sentence carrying an interrogative
returns from ``answer()`` (``organs/neural_language.py:4443``), a statement falls
through to ``hear()`` (``:4455``), and ``hear()`` is the ONLY write site of the taught
inventory (``:4347``).  One call, both jobs, classified by the organism.

It does not work on a bare organ, and that is a finding, not an obstacle.  A fresh
organ here has ``interrogatives == []`` and ``word_patterns == []`` -- both are learned,
from question/answer pairs (``:2440``) and from corpus exposure this demo does not load.
With no interrogatives the routing test at ``:4440`` never fires, the question falls
through to ``hear()``, and the organ replies "heard; no language learned yet".  Asking
it correctly once does not teach the interrogative (measured: still ``[]`` after a
correct ``answer()``).  So a bare organism genuinely does not know what a question is,
and a demo that quietly sorted statements from questions in Python would be performing
the very classification it is supposed to be testing.

Therefore the speaker declares the act: ``+`` = telling (-> ``hear()``), ``?`` = asking
(-> ``answer()``, the door C1/C2/C3 measured), unmarked = ``respond()``, the house door,
correct once the state carries language.  The marker is stripped before the organ sees
the text, so it enters neither the SAN, the binder, nor the stored tell.  Run against
the real house with ``tools/serve.py --electric``, no marker is needed.

Persistence is a RESTART, not a re-instantiation.  ``--say`` boots a process, loads
state from disk, serves one utterance, saves, and exits; two ``--say`` calls are two
lives of one organism with nothing but the file between them.  C2/C3 could only rebuild
an object inside one interpreter and said so; this is the version of the claim that
needs no caveat.  The server mode saves after every turn for the same reason: a demo
whose user kills the window mid-conversation must not lose what it was told.

ELECTRIC stays behind flags.  The three switches are set on the INSTANCE, never on
``NeuralLanguage`` itself, so importing or running this file cannot flip the defaults
that every battery run reads.  ``--no-electric`` is the control arm.
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import organs.neural_language as nl  # noqa: E402
from connectome.substrate import build_core_graph  # noqa: E402
from connectome.engine import HybridEngine  # noqa: E402
from organs.tokenizer import TokenizerOrgan  # noqa: E402

DEFAULT_STATE = ROOT / "state" / "electric_chat" / "neural_lang.json"


def build_organ(state_path, electric=True):
    """A bare language organ on its own state file -- no house, no corpus.

    Flags on the instance.  ``ELECTRIC_TEACH`` is a write permission,
    ``ELECTRIC_ANSWER`` a read permission, and ``ABSENCE_INVENTORY`` is what licenses
    the admission of ignorance at all (``:4354`` returns None without it, which would
    make silence the only "I don't know" the demo could show).
    """
    lang = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                             TokenizerOrgan(), state_path=str(state_path))
    lang.ELECTRIC_TEACH = bool(electric)
    lang.ELECTRIC_ANSWER = bool(electric)
    lang.ABSENCE_INVENTORY = bool(electric)
    lang.persist = True
    return lang


def _count(lang):
    return sum(len(v) for v in getattr(lang, "_taught_says", {}).values())


def turn(lang, text):
    """Say one thing.  Returns a plain dict, JSON-ready, describing what happened.

    THREE DOORS, AND WHY.  Unmarked text goes to ``respond()`` -- the door the house
    uses, which decides for itself whether it was asked or told.  That is the door the
    demo should use, and on a bare organ it does not work, MEASURED: a fresh organ here
    has ``interrogatives == []`` and ``word_patterns == []``, because both are learned
    from question/answer pairs and from corpus exposure that this demo does not load.
    ``respond()`` tests the interrogatives at :4440, finds none, falls through to the
    resonance path, and returns "heard; no language learned yet" -- silence.  Calling
    ``answer()`` first does not fix it either: answer() does not learn the interrogative
    (checked: still [] after a correct answer).  So on a bare organ the organism
    genuinely does not know what a question is.

    Rather than smuggle a classifier into this file and call it a demo, the act is
    declared by the speaker: ``+`` means I am telling you something (-> hear(), the only
    write site of the inventory), ``?`` means I am asking you something (-> answer(), the
    door C1/C2/C3 measured).  The marker is stripped before the organ sees the text, so
    it never enters the SAN, the binder or the taught tell.  Against the real house --
    ``tools/serve.py --electric``, 11,555 words and learned interrogatives -- no marker is
    needed and ``respond()`` classifies on its own.

    ``taught_this_turn`` is observed, not asserted: it diffs the inventory around the
    call.  A statement that parses into a subject and a relation grows it; a question
    must not.
    """
    raw = str(text)
    marker = raw[:1]
    body = raw[1:] if marker in ("+", "?") else raw
    door = {"+": "hear", "?": "answer"}.get(marker, "respond")
    before = _count(lang)
    if door == "hear":
        r = lang.hear(body, speaker="you")
        r = r if isinstance(r, dict) else {}
        r = {"spoken": False, "heard": True, "thought": r.get("thought")}
    elif door == "answer":
        r = lang.answer(body, speaker="you")
        r = r if isinstance(r, dict) else {"response": r}
    else:
        r = lang.respond(body, speaker="you")
        r = r if isinstance(r, dict) else {"response": r}
    after = _count(lang)
    said = str(r.get("utterance") or r.get("response") or "").strip()
    return {"text": body, "door": door,
            "reply": said,
            "spoken": bool(r.get("spoken")),
            "source": r.get("source"),
            "licensed_refusal": bool(r.get("licensed_refusal")),
            "reason": r.get("reason"),
            "heard": bool(r.get("heard")) or after > before,
            "inventory": after,
            "taught_this_turn": after - before}


def save(lang, force=False):
    # Per-turn saves are deltas: the json beside the delta is what carries the taught
    # inventory (save_state writes it at :5015-5017 even in delta mode), and the full
    # SAN rewrite is for the clean exit only.
    return lang.save_state(force=True) if force else lang.save_state(delta=True)


class ChatHTTPServer(HTTPServer):
    daemon_threads = False
    allow_reuse_address = True

    def __init__(self, addr, handler, lang, opts):
        super().__init__(addr, handler)
        self.lang = lang
        self.opts = opts
        self.turns = 0


class Handler(BaseHTTPRequestHandler):
    server: ChatHTTPServer

    def log_message(self, *a):            # silence: stdout is the protocol
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _last_user(self, messages):
        for m in reversed(list(messages or [])):
            if isinstance(m, dict) and m.get("role") == "user":
                return str(m.get("content") or "")
        return ""

    def do_GET(self):
        if self.path in ("/health", "/v1/models"):
            return self._send(200, {"status": "ok", "turns": self.server.turns,
                                    "inventory": _count(self.server.lang),
                                    "electric": self.server.opts["electric"]})
        return self._send(404, {"error": "unknown path"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:
            return self._send(400, {"error": f"bad json: {exc}"})
        if self.path == "/shutdown":
            # A clean stop that a test can drive and a person can use.  terminate()
            # on Windows kills the process without running finally blocks, so the save
            # cannot live in shutdown-only code and still be honest about persistence.
            res = save(self.server.lang, force=True)
            self._send(200, {"saved": bool(res.get("saved")), "turns": self.server.turns})
            # NOT self.server.shutdown() here.  This server is single-threaded, which
            # means the handler is running INSIDE the serve_forever loop, and shutdown()
            # blocks until that loop reports itself stopped -- a deadlock I hit in the
            # first version of this file, where the test hung for 180 s waiting on a
            # process that was politely waiting for itself.  Another thread can finish
            # this request and let the loop exit.
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        text = (req.get("text") if isinstance(req, dict) else None) \
            or self._last_user(req.get("messages") if isinstance(req, dict) else None)
        if not str(text).strip():
            return self._send(400, {"error": "no user message"})
        out = turn(self.server.lang, text)
        self.server.turns += 1
        if self.server.opts.get("autosave", True):
            out["saved"] = bool(save(self.server.lang).get("saved"))
        # OpenAI-shaped when asked through /v1, plain when asked through /chat.
        if self.path.startswith("/v1/"):
            return self._send(200, {"choices": [{"message": {
                "role": "assistant", "content": out["reply"] if out["spoken"] else ""},
                "electric": out}]})
        return self._send(200, out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", default=str(DEFAULT_STATE),
                    help="organ state file; the same path across runs IS the memory")
    ap.add_argument("--say", default=None,
                    help="one-shot: boot, load, answer this, save, exit (JSON on stdout)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--no-electric", action="store_true",
                    help="control arm: flags off, so nothing is taught and nothing is "
                         "recalled from the keyed inventory")
    ap.add_argument("--reset", action="store_true",
                    help="delete the state file first (a new organism, not amnesia)")
    ap.add_argument("--no-autosave", action="store_true",
                    help="server: save only at a clean shutdown, not every turn")
    args = ap.parse_args()

    state = Path(args.state)
    electric = not args.no_electric
    if args.reset:
        for p in (state, state.with_suffix(".json.tmp"),
                  Path(str(state) + ".cortex.delta.json")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    lang = build_organ(state, electric)
    loaded = lang.load_state()
    boot = {"loaded": bool((loaded or {}).get("loaded")),
            "inventory_at_boot": _count(lang),
            "electric": electric, "state": str(state)}

    if args.say is not None:
        out = turn(lang, args.say)
        out["boot"] = boot
        out["saved"] = bool(save(lang, force=True).get("saved"))
        print(json.dumps(out, ensure_ascii=False))
        return 0

    state.parent.mkdir(parents=True, exist_ok=True)
    httpd = ChatHTTPServer((args.host, args.port), Handler, lang,
                           {"electric": electric, "autosave": not args.no_autosave})
    # The bound port goes on stdout because port 0 means "whatever is free", and a
    # scripted client has to be able to find out what that was.
    print(f"[chat] ready port={httpd.server_address[1]} "
          f"electric={electric} inventory={boot['inventory_at_boot']}", flush=True)
    print(f"[chat] POST /chat {json.dumps({'text': 'the scarf is on the hook'})} "
          f"| POST /v1/chat/completions | POST /shutdown", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        res = save(lang, force=True)
        print(f"[chat] {httpd.turns} turns; saved={bool(res.get('saved'))} "
              f"inventory={_count(lang)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
