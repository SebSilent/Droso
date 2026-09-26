"""Report an act to the living individual.

The tools run in their own processes and have no language organ; the being they are
exercising does. So an act is reported over the same endpoint the terminal already
uses -- the existing path, not a second record of the same event.

Why this exists at all: 27,455 propositions and only 239 of them were something he
DID (0.87%). Reading gives him sentences whose first word is "the", where role 0 is
not an agent. An act gives him a sentence whose first word is a doer, and role
recovery measures 0.834 against a 0.048 chance on acts and 1.6x on prose. Reasoning
is built out of acts and he had almost none.
"""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:7773"


def tell(verb: str, obj: str, agent: str = "droso",
         timeout: float = 6.0) -> bool:
    """Best-effort. A tool must never fail because the being is not running."""
    try:
        req = urllib.request.Request(
            BASE + "/api/world/experience",
            data=json.dumps({"agent": agent, "verb": str(verb),
                             "object": str(obj)[:80]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return bool(json.load(r).get("experienced"))
    except Exception:
        return False


def tries(task: str) -> bool:
    return tell("tries", task)


def outcome(task: str, passed: bool) -> bool:
    return tell("passes" if passed else "fails", task)


def ran(name: str, ok: bool) -> bool:
    return tell("runs" if ok else "breaks", name)
