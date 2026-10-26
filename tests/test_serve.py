"""The HTTP layer adds nothing between a client and the door.

tools/serve.py is one more front end on the same door every other
measurement uses.  These tests hold two invariants: the ingest rule
(the last user message's content is the utterance, verbatim, and
everything else in the request is ignored) and the reply rule (a spoken
reply's utterance is the content, a silent turn is an empty content, an
internal reason is never passed off as his words).  The end-to-end
round trips run against a stub session, so no state is loaded: the
layer under test is HTTP, not Droso.
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer, ThreadingHTTPServer

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.serve as serve  # noqa: E402


# ------------------------------------------------------------- stub session

class StubLang:
    def __init__(self):
        self.seen = []

    def respond(self, text, speaker="you"):
        self.seen.append((text, speaker))
        return {"spoken": True, "utterance": f"echo: {text}",
                "source": "stub"}


class StubAgent:
    def __init__(self, lang):
        self.language = lang


class StubSession:
    """The part of converse.Session the handler touches, nothing more."""

    def __init__(self):
        self.lang = StubLang()
        self.agent = StubAgent(self.lang)
        self.kinds = []

    def ask(self, text, kind="free"):
        self.kinds.append(kind)
        reply = self.lang.respond(text, speaker="you")
        return {"n": len(self.kinds), "kind": kind, "said": text,
                "reply": reply}


class SilentSession(StubSession):
    def ask(self, text, kind="free"):
        self.kinds.append(kind)
        return {"n": len(self.kinds), "kind": kind, "said": text,
                "reply": {"spoken": False, "reason": "no memory of this"}}


# ------------------------------------------------------------------ helpers

@pytest.fixture
def server():
    httpd = serve.DrosoHTTPServer(("127.0.0.1", 0), serve.Handler,
                                  StubSession())
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def silent_server():
    httpd = serve.DrosoHTTPServer(("127.0.0.1", 0), serve.Handler,
                                  SilentSession())
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def url(server, path="/v1/chat/completions"):
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


def post(server, payload, path="/v1/chat/completions"):
    req = urllib.request.Request(
        url(server, path), data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def post_raw(server, raw: bytes):
    req = urllib.request.Request(url(server), data=raw,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ----------------------------------------------------------- ingest rule

def test_last_user_message_selects_the_last_user_turn():
    messages = [{"role": "system", "content": "be brief"},
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "a reply"},
                {"role": "user", "content": "second"}]
    content, err = serve.last_user_message(messages)
    assert (content, err) == ("second", None)


def test_no_user_message_is_an_error():
    content, err = serve.last_user_message(
        [{"role": "system", "content": "s"}, {"role": "assistant", "content": "a"}])
    assert content is None and err == "no user message in the request"


def test_messages_not_an_array_is_an_error():
    content, err = serve.last_user_message({"role": "user", "content": "hi"})
    assert content is None and err == "messages must be an array"


def test_non_string_user_content_is_an_error():
    content, err = serve.last_user_message(
        [{"role": "user", "content": [{"type": "text", "text": "hi"}]}])
    assert content is None and err == "the user message's content must be a string"


def test_non_dict_message_is_an_error():
    content, err = serve.last_user_message(["hello"])
    assert content is None and err == "every message must be an object"


def test_exotic_content_on_ignored_messages_is_tolerated():
    """Only the selected utterance is validated; the rest is never the door."""
    messages = [{"role": "system", "content": [{"type": "text", "text": "s"}]},
                {"role": "user", "content": "hi"}]
    content, err = serve.last_user_message(messages)
    assert (content, err) == ("hi", None)


# --------------------------------------------------------- reply rule

def test_say_then_ask_round_trip_over_http(server):
    """Two turns through the real HTTP layer: both utterances arrive
    verbatim, in order, as speaker "you"; both replies come back as
    choices[0].message.content in the standard shape."""
    for text in ("i keep my keys in the blue drawer", "where are my keys"):
        status, payload = post(server, {"model": "droso",
                                        "messages": [{"role": "user",
                                                      "content": text}]})
        assert status == 200
        assert payload["object"] == "chat.completion"
        assert payload["model"] == "droso"
        assert payload["id"].startswith("chatcmpl-droso-")
        choice = payload["choices"][0]
        assert choice["index"] == 0 and choice["finish_reason"] == "stop"
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == f"echo: {text}"
    assert server.session.lang.seen == [
        ("i keep my keys in the blue drawer", "you"),
        ("where are my keys", "you")]
    assert server.session.kinds == ["free", "free"]
    assert server.turns_served == 2


def test_silent_turn_is_an_empty_content_not_a_reason(silent_server):
    status, payload = post(silent_server, {"messages": [
        {"role": "user", "content": "what did we say about the moon"}]})
    assert status == 200
    assert payload["choices"][0]["message"]["content"] == ""


def test_everything_but_the_last_user_message_is_ignored(server):
    """model, temperature, system and assistant turns: none of it reaches
    the door; the last user message is the whole ingest."""
    status, payload = post(server, {
        "model": "whatever", "temperature": 0.7, "stream": False,
        "messages": [{"role": "system", "content": "you are helpful"},
                     {"role": "user", "content": "first"},
                     {"role": "assistant", "content": "ok"},
                     {"role": "user", "content": "second"}]})
    assert status == 200
    assert payload["choices"][0]["message"]["content"] == "echo: second"
    assert server.session.lang.seen == [("second", "you")]


# ------------------------------------------------------------- errors

def test_invalid_json_body_is_a_400(server):
    status, payload = post_raw(server, b"{not json")
    assert status == 400
    assert payload["error"]["type"] == "invalid_request_error"


def test_missing_user_message_is_a_400(server):
    status, payload = post(server, {"messages": [
        {"role": "assistant", "content": "alone"}]})
    assert status == 400
    assert "no user message" in payload["error"]["message"]


def test_unknown_path_is_a_404(server):
    status, payload = post(server, {"messages": []}, path="/v1/nope")
    assert status == 404
    assert payload["error"]["type"] == "invalid_request_error"


def test_get_on_completions_is_a_405(server):
    try:
        urllib.request.urlopen(url(server), timeout=10)
        status, payload = 200, {}
    except urllib.error.HTTPError as e:
        status, payload = e.code, json.loads(e.read().decode("utf-8"))
    assert status == 405
    assert payload["error"]["type"] == "invalid_request_error"


def test_models_lists_droso(server):
    req = urllib.request.Request(url(server, "/v1/models"))
    with urllib.request.urlopen(req, timeout=10) as r:
        payload = json.loads(r.read().decode("utf-8"))
    assert payload["object"] == "list"
    assert payload["data"][0]["id"] == "droso"
    assert payload["data"][0]["object"] == "model"


# ------------------------------------------------------- single-threaded

def test_the_server_is_not_threaded():
    """One request at a time is the invariant: HTTPServer, not its
    threaded subclass, so two clients can never interleave turns in his
    one session."""
    assert issubclass(serve.DrosoHTTPServer, HTTPServer)
    assert not issubclass(serve.DrosoHTTPServer, ThreadingHTTPServer)