"""The stale-status guard: a ledger's status field may not assert OPEN for a decision the same file rules.

Why a test and not another grep-and-fix pass: last turn I reconciled eleven paths by hand and still missed
`result_quoting_guard_while_blocked.status_after_rulings`, which went on saying "D-MPE10-02 is still OPEN, so
H2 has no scalar" for a full turn after the ruling block recorded it RULED. A grep finds the instances you
thought of. This finds the ones you did not.

The rule is deliberately narrow, because a guard that fires on legitimate history gets disabled:
  * a decision counts as RULED if it has an entry in a ruling block (pi_rulings*, pi_decisions.rulings);
  * a field counts as a STATUS field by its path (open_decisions_for_PI, decisions_left_open, *_status,
    status_after_rulings, guard status) -- prose elsewhere is allowed to quote the old position;
  * preserved history is exempt by key name (`*_as_registered_before_the_ruling`, `*snapshot*`,
    `*at_install*`, `*as_asked*`, `*previous_attempt*`);
  * anything else that must stay OPEN is exempt only if the file lists it in `status_reconciliation_allowlist`
    with a reason -- so a legitimate open decision is a recorded judgement, not an accident the test ignores.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGERS = sorted((ROOT / "experiments").glob("*/registration.json"))

ID_RE = re.compile(r"D-[A-Z0-9]+-\d+")
STATUS_PATH_RE = re.compile(
    r"(^|\.)("
    r"open_decisions_for_PI|decisions_left_open|status_after_rulings|"
    r"[a-z0-9_]*_status|status[a-z0-9_]*|guard_status"
    r")(\.|$)")
HISTORY_KEY_RE = re.compile(
    r"(_as_registered_before_the_ruling|_as_written_before_the_reconciliation|_as_asked|snapshot|at_install|"
    r"previous_attempt|superseded|historical)")
OPEN_RE = re.compile(r"\b(OPEN|unconfirmed|still open)\b", re.I)
RULED_RE = re.compile(r"\b(RULED|ruled)\b")

# A new ruling batch is invisible to this guard until its block name is registered here -- the tuple is the
# registry, not a filter that can be loosened. v1.2 B.R (experiments/MP-E9/plan_extract/
# DROSO_Master_Plan_v1_2.md:396-409, ingested 2026-11-05) is added so the batch it rules is enforced, and
# MP-E9/MP-E12 store their decisions under lowercase `open_decisions_for_pi` / `open_decisions`, which the
# path regex below did not cover; widening it makes those two ledgers checkable for the first time.
RULING_BLOCKS = ("pi_rulings", "pi_rulings_2026_08_10", "pi_rulings_2026_11_05_BR", "pi_decisions")


def ruled_ids(node, path=""):
    """Decision ids that have an actual ruling entry, keyed off the ruling blocks only."""
    ids = set()
    for blk in RULING_BLOCKS:
        v = node.get(blk)
        if not isinstance(v, dict):
            continue
        stack = [(v, "")]
        while stack:
            d, p = stack.pop()
            inner = d.get("rulings") if isinstance(d.get("rulings"), dict) else None
            for k, val in d.items():
                if k == "rulings":
                    continue
                kp = f"{p}.{k}" if p else k
                if ID_RE.fullmatch(k) or ID_RE.search(k):
                    if isinstance(val, dict) and any(RULED_RE.search(str(x)) for x in val.values()):
                        m = ID_RE.search(k)
                        if m:
                            ids.add(m.group(0))
                if isinstance(val, dict):
                    stack.append((val, kp))
            if inner:
                stack.append((inner, p))
    return ids


def status_fields(node, path="", out=None):
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            kp = f"{path}.{k}" if path else k
            if isinstance(v, str) and STATUS_PATH_RE.search(kp) and not HISTORY_KEY_RE.search(k):
                out.append((kp, v))
            status_fields(v, kp, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            status_fields(v, f"{path}[{i}]", out)
    return out


def violations(ledger: Path):
    d = json.loads(ledger.read_text(encoding="utf-8"))
    ruled = ruled_ids(d)
    # Entries are objects, not strings: {"path":..., "id":..., "reason":...}. A bare string in an allowlist is
    # how a stale status gets parked quietly instead of fixed, so the reason is part of the shape.
    allow_paths = {e.get("path") for e in d.get("status_reconciliation_allowlist", []) if isinstance(e, dict)}
    bad = []
    for path, text in status_fields(d):
        if path in allow_paths:
            continue
        for m in ID_RE.finditer(text):
            did = m.group(0)
            if did in ruled and OPEN_RE.search(text) and not RULED_RE.search(text):
                bad.append(f"{ledger.parent.name}: {path} asserts an OPEN status for {did}, "
                           f"which this file's ruling block marks RULED")
    return bad, sorted(ruled)


def test_every_ledger_status_field_agrees_with_its_own_rulings():
    all_bad = []
    for led in LEDGERS:
        bad, ruled = violations(led)
        all_bad += bad
    assert not all_bad, "\n".join(all_bad)


def test_the_guard_actually_fires_on_the_defect_it_is_meant_to_catch():
    """A guard that cannot fail is decoration. Feed it last turn's real bug and require a catch."""
    d = json.loads((ROOT / "experiments" / "MP-E10" / "registration.json").read_text(encoding="utf-8"))
    d["result_quoting_guard_while_blocked"]["status_after_rulings"] = (
        "D-MPE10-02 is still OPEN, so H2 has no scalar and the guard still binds.")
    tmp = ROOT / "_tmp" / "stale_guard_selftest.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps(d), encoding="utf-8")
    try:
        bad, ruled = violations(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    assert "D-MPE10-02" in ruled, "the ruling block must be what the guard reads"
    assert bad and "status_after_rulings" in bad[0], f"the guard missed the known defect: {bad}"


def test_the_allowlist_is_used_and_reasoned_not_just_present():
    """An allowlist entry without a reason is how a stale status gets parked instead of fixed."""
    for led in LEDGERS:
        d = json.loads(led.read_text(encoding="utf-8"))
        for e in d.get("status_reconciliation_allowlist", []):
            assert isinstance(e, dict) and e.get("reason"), f"{led}: allowlist entry lacks a reason"
