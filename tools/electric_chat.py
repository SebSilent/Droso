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

``--electric-teach`` changes that, and the reason is a fact about the mechanism rather than a
user-interface choice.  The pairing that makes a question and the next sentence ONE QA pair lives
at the top of ``respond()`` (``neural_language.py:5427``) and nowhere else, so a ``?`` sent
straight to ``answer()`` is never held as a question and a ``+`` sent straight to ``hear()`` can
never be heard as the answer to a held one -- the held question would sit waiting and pair with
some unrelated turn much later, which is exactly the false adjacency the adjacency rule exists to
prevent.  So under the mode every turn goes through ``respond()``, the door the house uses
anyway: an ask the store holds a pair for still reaches ``answer()`` (``:5473``), keyed on the
RECORD rather than on punctuation, and a statement still reaches ``hear()`` (``:5495``), which
stays the only write site of the taught inventory.  The stack itself is defined once, in
``tools/electric_teach_mode.py``, the same table ``tools/serve.py`` reads.

Persistence is a RESTART, not a re-instantiation.  ``--say`` boots a process, loads
state from disk, serves one utterance, saves, and exits; two ``--say`` calls are two
lives of one organism with nothing but the file between them.  C2/C3 could only rebuild
an object inside one interpreter and said so; this is the version of the claim that
needs no caveat.  The server mode saves after every turn for the same reason: a demo
whose user kills the window mid-conversation must not lose what it was told.

ELECTRIC stays behind flags.  The three switches are set on the INSTANCE, never on
``NeuralLanguage`` itself, so importing or running this file cannot flip the defaults
that every battery run reads.  ``--no-electric`` is the control arm.

One of those switches is a no-op on purpose.  ``--electric`` was never an option of this
file: argparse resolved it as a PREFIX of ``--electric-teach``, so a person typing the
ELECTRIC switch got the whole teach stack and had no say in it, and once a second
``--electric-*`` option existed the prefix became ambiguous and the same typing was a hard
error.  Declaring the exact name fixes both: it affirms the default, changes nothing, and
loses to ``--no-electric`` in a conflict, because an affirmation of what is already on
carries no information and the control arm is the one request that does.
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
from tools import electric_teach_mode  # noqa: E402

DEFAULT_STATE = ROOT / "state" / "electric_chat" / "neural_lang.json"


def build_organ(state_path, electric=True, teach=False, guard=False):
    """A bare language organ on its own state file -- no house, no corpus.

    Flags on the instance.  ``ELECTRIC_TEACH`` is a write permission,
    ``ELECTRIC_ANSWER`` a read permission, and ``ABSENCE_INVENTORY`` is what licenses
    the admission of ignorance at all (``:4354`` returns None without it, which would
    make silence the only "I don't know" the demo could show).

    ``teach`` turns on the whole teachable-QA stack through the SAME table
    ``tools/serve.py`` reads, so "teach mode" is one definition and not two that can drift.

    ``guard`` is the store-shape guard alone, so the hole it closes can be measured with the
    mode OFF. It is set BEFORE ``enable`` because the mode's table includes it: an individual
    switch can only ever add to the mode, never take it back off.
    """
    lang = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                             TokenizerOrgan(), state_path=str(state_path))
    lang.ELECTRIC_TEACH = bool(electric)
    lang.ELECTRIC_ANSWER = bool(electric)
    lang.ABSENCE_INVENTORY = bool(electric)
    lang.ELECTRIC_ASK_SHAPE_STORE = bool(guard)
    if teach:
        electric_teach_mode.enable(lang)
    lang.persist = True
    return lang


def _pairs(lang):
    """How many QA pairs he holds, and how many of those a PERSON taught him. The store is
    the teach mode's whole point, and nothing in the demo's output counted it before."""
    store = getattr(lang, "qa_store", {}) or {}
    conv = sum(1 for r in store.values()
               if str((((r or {}).get("prov") or {}).get("source") or "")) == "conversation")
    return len(store), conv


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
    if getattr(lang, "ELECTRIC_QA_ELICIT", False):
        # TEACH MODE takes over the declared door, and has to.  The pairing that turns an ask
        # and the next sentence into a QA pair sits at the TOP of `respond`
        # (neural_language.py:5427) and nowhere else: a `?` sent straight to answer() is never
        # held as a question, and a `+` sent straight to hear() cannot be heard as the answer to
        # a held ask -- so the held one would sit waiting and pair with some unrelated turn much
        # later, which is the false adjacency the adjacency rule exists to prevent.  `respond`
        # is not a weaker door: an ask the store holds a pair for still goes to answer() (:5473),
        # and a statement still reaches hear() (:5495), which stays the only write site of the
        # taught inventory.
        door = "respond"
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
    out = {"text": body, "door": door,
           "reply": said,
           "spoken": bool(r.get("spoken")),
           "source": r.get("source"),
           "licensed_refusal": bool(r.get("licensed_refusal")),
           "reason": r.get("reason"),
           "heard": bool(r.get("heard")) or after > before,
           "inventory": after,
           "taught_this_turn": after - before}
    if getattr(lang, "ELECTRIC_QA_ELICIT", False):
        # The mode's own members, added only while it is on, so a plain --electric turn keeps
        # the exact JSON shape that was measured. `ask_held` is the one that matters: an ask is
        # answered by the NEXT thing the person says, and without this nothing on the wire told
        # them he was holding the question.
        pairs, conv = _pairs(lang)
        out.update({"qa_pairs": pairs, "taught_pairs": conv,
                    "ask_held": bool(getattr(lang, "_qa_pending", None)),
                    "ask_evidence": r.get("ask_evidence")})
    return out


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
            health = {"status": "ok", "turns": self.server.turns,
                      "inventory": _count(self.server.lang),
                      "electric": self.server.opts["electric"]}
            if self.server.opts.get("teach"):
                # A script driving the demo has to be able to ask "is the mode on, and did the
                # pair land?" without reading a turn for it. Gated on the mode, so /health is
                # the response it always was for every run that did not ask for teach mode.
                pairs, conv = _pairs(self.server.lang)
                health.update({"teach": True, "qa_pairs": pairs, "taught_pairs": conv})
            return self._send(200, health)
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
    ap.add_argument("--electric", action="store_true",
                    help="affirm the ELECTRIC flags explicitly. This tool has always started "
                         "with them ON, so it changes nothing -- it exists because typing "
                         "`--electric` used to resolve as an ABBREVIATION of --electric-teach, "
                         "which meant the person who typed the ELECTRIC switch got the whole "
                         "teach stack and had no say in it. Naming it exactly makes that "
                         "abbreviation impossible. With --no-electric the control wins, because "
                         "an affirmation of the default carries no information.")
    ap.add_argument("--no-electric", action="store_true",
                    help="control arm: flags off, so nothing is taught and nothing is "
                         "recalled from the keyed inventory")
    ap.add_argument("--electric-ask-shape-store", action="store_true",
                    help="do not file a tell whose SHAPE is an ask as a taught fact. "
                         "`_taught_says` is read before every other store, so a question the "
                         "house has not learned to classify used to answer itself: teach one "
                         "pair, ask `what rings the bell twice`, then ask `what rings the bell` "
                         "and get the first question back. This closes that without widening "
                         "anything -- the frame still lands in the inventory the absence licence "
                         "reads, and a line longer than the binder's cap is left alone, because "
                         "a relative clause that opens a line is a fact. Needs --electric, "
                         "which is what files taught facts at all. Included in "
                         "--electric-teach.")
    ap.add_argument("--electric-teach", action="store_true",
                    help="the teachable-QA stack in one switch -- the store, elicitation, the "
                         "paraphrase fold, provenance, the question marks, admissibility, "
                         "the fragment guard and the store-shape guard, from the same table "
                         "tools/serve.py reads. Teach "
                         "a pair by asking a question and saying the answer next; ask it again "
                         "in other words later. Implies --electric. It WIDENS NOTHING beyond "
                         "that: --electric-reverse, --electric-object-role and "
                         "--electric-ask-normalize have no switch here at all, and a bare organ "
                         "has no learned question words, so a pair he holds is answered by the "
                         "RECORD, not by punctuation.")
    ap.add_argument("--reset", action="store_true",
                    help="delete the state file first (a new organism, not amnesia)")
    ap.add_argument("--no-autosave", action="store_true",
                    help="server: save only at a clean shutdown, not every turn")
    args = ap.parse_args()

    state = Path(args.state)
    if args.reset:
        for p in (state, state.with_suffix(".json.tmp"),
                  Path(str(state) + ".cortex.delta.json")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    teach = bool(args.electric_teach)
    # `--electric` is deliberately absent from this expression. It affirms the default, so it
    # carries no information, and letting it flip `electric` would mean a person who typed both
    # switches could lose the control arm by accident. The conflict is announced instead.
    electric = not args.no_electric or teach
    if args.electric and args.no_electric:
        print("[chat] --electric with --no-electric: ELECTRIC is what this tool does on its own, "
              "so the affirmation adds nothing and the CONTROL arm stands. Say one of them.",
              file=sys.stderr, flush=True)
    if teach and args.no_electric:
        # A contradictory pair of switches has to be announced, not resolved quietly: --no-electric
        # is the CONTROL arm, and teach mode sits on top of the flags it turns off, so this run is
        # not the control it thinks it asked for.
        print("[chat] --no-electric with --electric-teach: teach mode implies the ELECTRIC "
              "flags underneath it, so this is not the control arm. Drop --electric-teach to "
              "measure the control.", file=sys.stderr, flush=True)
    lang = build_organ(state, electric, teach,
                       guard=bool(args.electric_ask_shape_store))
    for line in electric_teach_mode.warnings(lang):
        print("[chat] " + line, flush=True)
    loaded = lang.load_state()
    pairs, conv = _pairs(lang)
    boot = {"loaded": bool((loaded or {}).get("loaded")),
            "inventory_at_boot": _count(lang),
            "electric": electric, "state": str(state),
            "teach": teach, "qa_pairs_at_boot": pairs, "taught_pairs_at_boot": conv,
            "ask_shape_store": bool(lang.ELECTRIC_ASK_SHAPE_STORE)}

    if args.say is not None:
        out = turn(lang, args.say)
        out["boot"] = boot
        out["saved"] = bool(save(lang, force=True).get("saved"))
        if out.get("ask_held"):
            # Measured, not guessed at: two `--say` calls are two lives of one organism, the
            # pair was never formed, and the user typed an answer into a void.  A HELD ASK is
            # memory-only by design -- a question from a previous life must not pair with an
            # unrelated sentence in this one, which is the false adjacency the adjacency rule
            # exists to prevent -- so the fix is to say the answer in the same session, not to
            # persist the question.  Silence about it would look like the feature is broken.
            print("[chat] he is holding your question, and a held ask does not survive the "
                  "restart this process is about to make: teach the pair inside one session "
                  "(server mode, or a script) -- ask, then say the answer.",
                  file=sys.stderr, flush=True)
        print(json.dumps(out, ensure_ascii=False))
        return 0

    state.parent.mkdir(parents=True, exist_ok=True)
    httpd = ChatHTTPServer((args.host, args.port), Handler, lang,
                           {"electric": electric, "autosave": not args.no_autosave,
                            "teach": teach})
    # The bound port goes on stdout because port 0 means "whatever is free", and a
    # scripted client has to be able to find out what that was.
    ready = (f"[chat] ready port={httpd.server_address[1]} electric={electric} "
             f"inventory={boot['inventory_at_boot']}")
    if teach:
        ready += f" teach=on pairs={boot['qa_pairs_at_boot']}"
    print(ready, flush=True)
    if teach:
        # Say what is on, and say the protocol, because the protocol is the part a person
        # cannot infer: an ask is not answered until the NEXT thing they say arrives.
        for line in electric_teach_mode.describe():
            print(f"[chat]   {line}", flush=True)
        print("[chat]   teach a pair: `what rings the bell?` then `the copper bell rings`"
              " -- ask it again in other words and it answers", flush=True)
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
