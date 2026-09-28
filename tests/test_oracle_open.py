"""The fence has only ever been tested for BLOCKING. It is now tested for OPENING.

Three separate failures came from the same shape: a tool popped HYBRIDLLM_OFFLINE, a later
step re-armed it or the key had already been resolved while it was up, and a report showed a
zero that looked like a real measurement. The generator said `generated: 0`, the probe said a
15% solve rate, the knowledge ledger said `asked: 0`.

So the two directions are pinned here: the fence still closes by default, and an explicitly
opened oracle really does have its credential and really does reach the wire.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.api_oracle import APIOracle, OFFLINE_ENV, oracle_open  # noqa: E402


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-placeholder")


def _oracle(**kw):
    return APIOracle(provider="openai", model="gpt-4o-mini", usage_path=Path(os.devnull), **kw)


def test_an_oracle_built_under_the_fence_is_not_permanently_keyless(monkeypatch, keyed):
    """THE BUG THIS FILE EXISTS FOR.

    `api_key` used to be read once, in __init__, and `_env_key()` returns None while the fence
    is up. So an oracle constructed after any local agent had armed the fence stayed keyless
    forever -- and popping the fence afterwards changed nothing. That produced 20 of 20
    NoAPIKeyError on the §2 probe, which is one line away from being read as "the oracle
    cannot solve these problems".
    """
    monkeypatch.setenv(OFFLINE_ENV, "1")
    o = _oracle()                      # built WHILE the fence is up
    assert o.has_key is False, "the fence must still hide the key"

    with oracle_open():
        assert o.has_key is True, "opening the fence must re-evaluate the key"


def test_an_opened_oracle_reaches_the_endpoint(monkeypatch, keyed):
    """Opening is not enough: the credential must survive all the way to the call."""
    seen = {}

    def transport(url, headers, payload):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "42"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setenv(OFFLINE_ENV, "1")
    o = _oracle(transport=transport)
    with oracle_open():
        out = o.query("what is the answer", max_tokens=8, purpose="test")
    assert out.get("ok") is True, out
    assert seen.get("auth", "").startswith("Bearer sk-test"), "the key must be sent"


def test_the_fence_still_closes_by_default(monkeypatch, keyed):
    """The blocking direction, unchanged -- an open fence would mix the three columns.

    No transport is injected here: injecting one is the sanctioned way to make an oracle
    live, so an oracle with `transport is None` is the one that must stay fenced.
    """
    monkeypatch.setenv(OFFLINE_ENV, "1")
    o = _oracle()
    assert o.transport is None
    out = o.query("anything", purpose="test")
    assert out.get("ok") is False
    assert out.get("mode") == "offline"
    assert "offline_mode" in str(out.get("reason")), \
        "fenced and keyless are different conditions and must not share an error"
    assert o.calls == 0, "a fenced oracle must not reach the wire"


def test_the_fence_is_rearmed_on_exit(monkeypatch, keyed):
    """A tool that forgets to close it must not be able to leave the fence open.

    The contract is FALSY, not ABSENT. Inside the block the key is present and empty, which is
    what stops a nested `setdefault` from re-arming it; asserting absence here would be
    asserting the old mechanism rather than the thing that matters.
    """
    monkeypatch.setenv(OFFLINE_ENV, "1")
    with oracle_open():
        assert not os.environ.get(OFFLINE_ENV)
    assert os.environ.get(OFFLINE_ENV) == "1", "the previous state must be restored"

    monkeypatch.delenv(OFFLINE_ENV, raising=False)
    with oracle_open():
        assert not os.environ.get(OFFLINE_ENV)
    assert not os.environ.get(OFFLINE_ENV), "an open fence must stay open when it was open"


def test_a_nested_local_agent_cannot_re_arm_the_fence(monkeypatch, keyed):
    """THE BUG THIS CONTEXT MANAGER EXISTS FOR.

    `seeds()` builds a tool agent, and `_loop_agent` arms the fence with `os.environ.setdefault`.
    A plain pop leaves the key absent, so that setdefault re-arms it from inside an
    `oracle_open()` block -- which is how a generation run came back `offline_mode` on every
    call while looking like a provider that had stopped answering.
    """
    monkeypatch.delenv(OFFLINE_ENV, raising=False)
    with oracle_open():
        os.environ.setdefault(OFFLINE_ENV, "1")   # what a nested tool agent does
        assert not os.environ.get(OFFLINE_ENV), \
            "a nested setdefault must not be able to close the fence again"


def test_an_opened_oracle_reports_offline_rather_than_raising(monkeypatch, keyed):
    """A fenced oracle explains itself; it does not look like a missing credential."""
    monkeypatch.setenv(OFFLINE_ENV, "1")
    o = _oracle()
    out = o.query("anything", purpose="test")
    assert out.get("mode") == "offline"
    assert "offline_mode" in str(out.get("reason"))
