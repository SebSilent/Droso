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
from tools import electric_teach_mode, state_hygiene  # noqa: E402


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
    if getattr(server, "teach", False):
        # Teach mode's OWN telemetry, and a wire member a plain --electric run never had, so
        # the payload above stays byte-identical to what was measured. Two things a person
        # teaching pairs cannot see any other way: whether a pair actually LANDED (the
        # inventory counts tells, not pairs) and whether he is HOLDING their question, which
        # is the moment the protocol is easiest to lose -- an ask is answered by the NEXT
        # thing they say, and nothing on the wire said it was waiting.
        lang = server.session.lang
        store = getattr(lang, "qa_store", {}) or {}
        conv = [k for k, r in store.items()
                if str(((r or {}).get("prov") or {}).get("source") or "") == "conversation"]
        payload["choices"][0]["teach"] = {
            "pairs": len(store),
            "taught_pairs": len(conv),
            "ask_held": bool(getattr(lang, "_qa_pending", None)),
            "evidence": reply.get("ask_evidence"),
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
    ap.add_argument("--electric-ask-normalize", action="store_true",
                    help="Within --electric only: read an ask's FORM before giving up on "
                         "it. A copula ask that strands a preposition ('who is the lantern "
                         "with?') reaches the tell that strands it ('the lantern belongs to "
                         "Mira'); a passive ('what was the door opened by?') is looked up as "
                         "the active question the object-role path already answers. Function "
                         "words only, and only ever a lookup key -- the reply is still a "
                         "verbatim taught tell or nothing. OFF by default.")
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
                         "default: nothing is dropped (a row carrying `?` is tagged "
                         "either way -- the mark is evidence, not a switch).")
    ap.add_argument("--electric-ask-shape", action="store_true",
                    help="With --electric-ask-admissibility: decide an asking by its "
                         "SHAPE, not by whether the organ happened to know the word. "
                         "Tags unmarked interrogatives (`who pets the mouse`) and book "
                         "questions whose mark did not survive, and RECORDS the verdict "
                         "in the session delta so a replay keeps it (the tag is never "
                         "guessed from a row's tokens at read time: a window of a "
                         "statement can begin on 'who' and nothing in the row says so). "
                         "Reads the "
                         "arbiter's own question-word set, so nothing is dropped that "
                         "the arbiter could not have parsed as an ask. It also binds "
                         "such a question WHOLE -- a windowed question has no question "
                         "word in first position and could not be recognised as one by "
                         "anything. Read only under --electric-ask-admissibility, so "
                         "with it off which rows exist does not change. OFF by default: "
                         "the detector never runs.")
    ap.add_argument("--electric-ask-shape-store", action="store_true",
                    help="Shape authority at the OTHER store. --electric-ask-shape decides "
                         "what a ROW is called; `_taught_says` -- the taught-fact store that "
                         "is consulted before every other answer path -- is not a row, and "
                         "nothing there reaches it. Measured in the live house: teach ONE "
                         "pair, so the question word has one vote and is not yet learned, ask "
                         "`what rings the bell twice`, and that question is filed as a tell "
                         "under ('agent','rings'); ask `what rings the bell` and the house "
                         "answers with the other person's unanswered question. ON: a tell "
                         "whose shape is an ask is not filed. It is a NARROWING, not the "
                         "widening above: it never makes a new ask reachable, and it cannot "
                         "answer anything it did not answer before. It does NOT touch "
                         "`_absence_inv` -- the frame is still extracted and recorded, so the "
                         "E24 licence refuses exactly what it refuses today -- and it stands "
                         "off past the binder's max_roles, because a long line opening on "
                         "`who` is prose with a relative clause in it and declining a WRITE "
                         "loses a fact silently. Needs --electric, which is what files taught "
                         "facts at all. OFF by default, and included in --electric-teach.")
    ap.add_argument("--electric-ask-marks", action="store_true",
                    help="Carry the question marks a book actually printed. The "
                         "exposure path has always known which lines ended in `?` "
                         "(_book_is_q, read off the raw text) and used it only for "
                         "learn_qa, so 2,687 question lines were stored as quotable "
                         "statements. This passes their mark POSITIONS down to the row "
                         "so a book question is recognised as an asking. It changes no "
                         "token and no chunking -- a row's tokens stay exactly what the "
                         "tokenizer produced, and a long question still survives as "
                         "windows. The tag is only CONSULTED under "
                         "--electric-ask-admissibility, so marks alone change nothing "
                         "anyone can hear; marks + admissibility is the pair. OFF by "
                         "default: nothing is passed.")
    ap.add_argument("--electric-qa-store", action="store_true",
                    help="Remember the book questions he was READ an answer to. "
                         "learn_qa already judges, per pair, whether the next line is "
                         "the question with its question-word replaced, and then throws "
                         "the pair away keeping only the role vote. This keeps the "
                         "accepted pairs, tagged with the book and line they came from, "
                         "and answers an ask from them by EXACT key -- no retrieval, no "
                         "similarity, so it cannot answer a question it was never "
                         "paired. A pair with no provenance is not stored, and a "
                         "question whose next line was itself printed as a question is "
                         "refused (the only pair the 16 real novels yield is exactly "
                         "that: two Dickens rhetorical questions side by side). OFF by "
                         "default: the store stays empty and cannot answer anything.")
    ap.add_argument("--electric-qa-elicit", action="store_true",
                    help="Let a PERSON be a book, in conversation: an utterance ending in "
                         "`?` is held as a pending ask, and the very next thing that person "
                         "says is offered to learn_qa as its answer. The pair is stored with "
                         "provenance (source=conversation, speaker, turn, marked) and can "
                         "then be answered WITH or WITHOUT the mark -- without it, on the "
                         "evidence that a person typed the `?` at him once. Needs "
                         "--electric-qa-store to remember anything. Three routes, each "
                         "narrower than it needs to be: adjacency is the next utterance by "
                         "the SAME speaker and nothing older; an unmarked ask needs the "
                         "RECORD, not a learned question word, which is what makes a "
                         "one-vote word answerable; and respond() routes to answer() only "
                         "for a key the store holds a conversation pair under, so an ask he "
                         "has no pair for keeps the path it always took. OFF by default: "
                         "nothing is paired and nothing is routed.")
    ap.add_argument("--electric-qa-paraphrase", action="store_true",
                    help="Let a pair a PERSON taught answer when he is asked for it in "
                         "other words. Taught `who carries droso?` / `parent carries "
                         "droso` and asked `who carries the droso`, the store held the "
                         "pair and said nothing: the key is the exact characters that were "
                         "typed. This folds the ask through the two pieces of machinery the "
                         "ELECTRIC read path already runs for exactly this problem -- "
                         "organs/stemming.py, the project's one stemmer, and "
                         "normalize_ask_variants, the ask normalizer -- and consults the "
                         "store only when the exact key already missed. Bounded three ways: "
                         "candidates are only records whose provenance says a person typed "
                         "them with a `?` (a pair he was READ is never reached, at any "
                         "setting of --electric-qa-provenance); the fold keeps word order, "
                         "so `who droso carries` does not meet `who carries droso` and a "
                         "role-inverted ask is refused rather than answered; and two pairs "
                         "that fold onto one key answer NOTHING. It under-folds on purpose "
                         "-- `who carried droso` gets nothing, because the shared stemmer "
                         "will not bridge a vowel change it has not been told to -- and "
                         "those refusals are pinned by tests. A child of "
                         "--electric-qa-elicit, which is what routes such an ask to "
                         "answer() at all. OFF by default: the exact-key lookup is the code "
                         "that ran before this flag existed.")
    ap.add_argument("--electric-qa-provenance", action="store_true",
                    help="Make a pair's PROVENANCE govern the pair, not just its "
                         "storage. Two things the audit (tools/book_qa_store_audit.py) "
                         "measured are wrong with the order they happen in. (1) A pair "
                         "the store REFUSES -- no provenance, or a question answering a "
                         "question -- has already voted into question_roles, "
                         "interrogatives and answer_types and already counted in "
                         "qa_pairs_seen, because the vote runs before the refusal. The "
                         "corpus contains exactly one such pair and it taught an organ "
                         "that `what` asks role 5 and is answered by `whose`. Refused "
                         "means refused: it teaches nothing. (2) A stored pair is "
                         "reachable only by a typed `?`; asked without the mark, of 100 "
                         "pairs he holds with provenance, 0 reached the store, 38 produced "
                         "silence and 38 got the line from recall instead. "
                         "Under this flag an unmarked ask may hit the store, but only if "
                         "its tokens are exactly a marked book question AND the word that "
                         "pair teaches as the interrogative is one he learned from an "
                         "admissible pair. OFF by default: the path is byte-identical to "
                         "the audit.")
    ap.add_argument("--electric", action="store_true",
                    help="ELECTRIC demo mode: statements heard in chat are taught into "
                         "the keyed inventory and questions may be answered from it, "
                         "including an admitted ignorance for a relation never told. "
                         "OFF by default -- without it this server is byte-identical to "
                         "yesterday's, and every battery run stays ELECTRIC-free.")
    ap.add_argument("--electric-teach", action="store_true",
                    help="One switch for the TEACHABLE-QA stack: what --electric means, "
                         "plus the store, elicitation, the paraphrase fold, provenance, "
                         "the question marks, admissibility and the fragment guard, plus "
                         "the restart half (load_state) that only --electric runs today. "
                         "Those seven each exist for a measured reason and two of them are "
                         "INERT without another, so a single flag has to name the set rather "
                         "than guess it: the list lives in tools/electric_teach_mode.py, the "
                         "same table tools/electric_chat.py reads, so the two doors cannot "
                         "grow different ideas of what teach mode means. It WIDENS NOTHING: "
                         "--electric-reverse, --electric-object-role, "
                         "--electric-ask-normalize and --electric-ask-shape stay behind their "
                         "own flags, because each lets more asks reach more matchers and a run "
                         "that costs something has to be able to say which switch cost it. OFF "
                         "by default: with it off this server is the server that was measured.")
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
    # Shape authority is a WIDENING of admissibility, not a separate mouth: with
    # admissibility off it can tag rows but nothing reads the tag, so it is inert.
    agent.language.ELECTRIC_ASK_SHAPE = bool(args.electric_ask_shape)
    # The mark channel is read OUTSIDE the --electric block like the two above it: the
    # rows it tags come out of the recall path, and it writes positions into a row that
    # exists whether or not ELECTRIC is on. It does not touch tokenization, so it cannot
    # move a row's key, cue or vector -- only what the row is called.
    agent.language.ELECTRIC_ASK_MARKS = bool(args.electric_ask_marks)
    # Self-contained, so wired outside the --electric block: it WRITES while he reads a
    # book (a pair learn_qa already accepted) and READS in answer() by exact key. It
    # needs no taught inventory and no admissibility -- it never retrieves, so it cannot
    # recite a row, and with the flag off the store is empty and the branch cannot fire.
    agent.language.ELECTRIC_QA_STORE = bool(args.electric_qa_store)
    # Governs the SAME pair the store governs, in the two places the audit found the
    # order wrong: the vote that runs before the admission test, and the lookup that
    # demands a typed `?`. Off, the path is byte-identical to what was measured.
    agent.language.ELECTRIC_QA_PROVENANCE = bool(args.electric_qa_provenance)
    # The conversation half of the store, wired outside --electric like the two above it:
    # it lives in `respond`, the door every chat turn goes through, and it is inert while
    # the store is empty, so it cannot fire on a path the graded batteries touch.
    agent.language.ELECTRIC_QA_ELICIT = bool(args.electric_qa_elicit)
    # The paraphrase lookup is inert without the route its parent opens, so it is wired
    # beside it and not inside --electric: a folded ask still has to reach `answer`.
    agent.language.ELECTRIC_QA_PARAPHRASE = bool(args.electric_qa_paraphrase)
    # --electric-teach: the whole teachable stack, from the ONE table in
    # tools/electric_teach_mode.py that tools/electric_chat.py reads too. Applied AFTER the
    # individual switches above: each of those is store_true, so they can only ever add, and
    # applying the mode last means no combination of flags can leave it half-on.
    teach = bool(args.electric_teach)
    if teach:
        electric_teach_mode.enable(agent.language)
    # An INERT flag is worse than an off one: the symptom is that nothing happens and nothing
    # says so. The dependency rule lives with the flags, not in either caller.
    for line in electric_teach_mode.warnings(agent.language):
        print("[serve] " + line, flush=True)
    # The mode implies --electric, because the stack is pointless without it: elicitation writes
    # a pair into the store, the store is only consulted on a path that is answering, and the
    # restart half a few lines below is the only thing that makes a taught pair outlive the
    # window. Today a server started with the QA flags and NOT --electric saves everything and
    # comes back with nothing.
    if teach:
        # Recorded on the parsed args, not in a local condition, and the reason is a guard rail
        # rather than taste: five committed tests read this file as TEXT and anchor the wiring of
        # --electric-reverse, --electric-object-role, --electric-ask-normalize,
        # --electric-ask-marks and --electric-ask-admissibility on the literal line
        # `if args.electric:` below. They exist to prove those read paths cannot come on without
        # --electric; renaming the condition to a local would not be a tidy refactor, it would
        # delete that guarantee and leave the tests passing for the wrong reason.
        args.electric = True
        print("[serve] ELECTRIC teach mode on: " + ", ".join(electric_teach_mode.STACK_ATTRS),
              flush=True)
    electric = bool(args.electric)
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
        # Ask normalization is a FOURTH separate permission, for the same reason as the
        # other two: it changes which asks reach which matchers, and a run that shows it
        # costing something has to be able to say which switch did it.
        lang.ELECTRIC_ASK_NORMALIZE = bool(args.electric_ask_normalize)
        # The store-shape guard, wired HERE and not beside the other ELECTRIC_QA_* switches,
        # for two reasons that are both about order. It is inert without ELECTRIC_TEACH -- the
        # write it declines only happens under that flag -- and its parent is set four lines
        # above, so wiring it outside would make the inert-flag warning above fire on a run that
        # has its parent on. And `or teach` rather than a bare bool(): the mode's own table
        # already turned this on, several lines earlier, and a plain assignment would switch the
        # mode's fix back off for anyone who asked for the mode and not for this switch.
        lang.ELECTRIC_ASK_SHAPE_STORE = bool(args.electric_ask_shape_store) or teach
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
              f"reverse={args.electric_reverse} object_role={args.electric_object_role} "
              f"shape_store={lang.ELECTRIC_ASK_SHAPE_STORE}",
              flush=True)
    session = converse.Session(agent, beats=args.beats)
    print(f"[serve] loaded in {time.time() - t0:.1f}s: "
          f"{len(agent.language.word_patterns)} words, "
          f"{converse.snapshot(agent)['propositions']} propositions",
          flush=True)
    print(f"[serve] reading state from: "
          f"{args.state or 'the live tree (read-only)'}", flush=True)

    httpd = DrosoHTTPServer((args.host, args.port), Handler, session)
    httpd.electric = electric
    httpd.teach = teach
    # Seed the diff from what the organ ALREADY HAS, not from zero.  Without this a
    # restarted session reports its loaded inventory as if this turn taught it --
    # measured: the first ask after a restart printed taught_this_turn: 3 for 3 facts
    # it had loaded from disk and had not been told in that life at all.
    httpd.taught_seen = sum(len(v) for v in
                            session.lang._taught_says.values()) if electric else 0
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