"""A conversation with Droso, in process, with the house down.

Until now every measurement of his speech went through the live house over
HTTP, which meant the house had to be up, the curriculum was narrating over
the conversation, and nothing about a multi-turn exchange could be replayed.
This harness holds him in process: the real state is loaded read-only, the
session's writes are re-pointed to a session directory, and a conversation
becomes a thing that can be run, scored, and compared.

What a turn is.  Input text goes to lang.respond() -- the same door the
house's /api/chat uses -- which hears it (SAN live() update, cortex binding,
sequence learning), decides whether to speak, and answers from memory when
the words were a question.  Between turns the organ gets a few autonomous
beats (lang.tick), so drives decay and recover the way they do in the house
and a thought of his own may land in the log.  Nothing is injected: no
oracle, no curriculum narration, no task path.  Droso alone.

State ownership (Invariant #1).  The harness reads the live state and never
writes it.  At build time every persistence path on the language organ and
its sub-organs is re-pointed into the session directory, the learning loop
is sealed read-only, and the background organs are stopped.  At exit the
sizes and mtimes of the real state files are compared against what they
were at build time and any change is reported as a violation.

The benchmark.  A fixed script -- greeting, question, follow-up,
contradiction, recall probe, unknowable question -- scored on the three
things a conversation can honestly be scored on:

  answered          of the turns that asked something, how many got speech
  self_consistent   did he contradict himself inside the session
  refused_unknown   of the things he cannot know, how many he refused to
                    assert

and then the differentiator: what the conversation changed.  A snapshot of
the SAN (row sums, nnz, total weight), the vocabulary, the bigram counts,
the proposition count and the procedure library is taken before the first
turn and after the last, and the diff is the report.  A conversation with
Droso must leave a trace; this makes that claim testable.

Usage:
    python tools/converse.py                     # interactive session
    python tools/converse.py --benchmark         # run the fixed script
    python tools/converse.py --benchmark --save first
    python tools/converse.py --script my.json    # your own turn list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import state_hygiene  # noqa: E402  (needs ROOT on sys.path)

STATE = ROOT / "state"
# The exocortex is live too, but it is the HOUSE's runtime ground: the house
# rewrites seven of its nine files in bursts (measured 2026-10-26: bursts at
# 21:58, 22:00 and 23:45 wrote api_cache, learned_procedures, learning_events,
# reasoning_state, snippet_vault, speed_routing, stream_progress), and a burst
# can land inside a session's guard window.  A session turn provably does NOT
# write here -- one real turn left all nine files byte-identical, and every
# oracle call path is gated (render_voice behind voice_prosthesis, off by
# default; learn_from_teacher behind the house's first-run acquisition; the
# evaluator is not in the turn path).  So exocortex churn is watched and
# REPORTED, but never verdict-breaking: with two concurrent writers the
# before/after diff cannot attribute a change, and a false alarm here would
# burn the guard's credibility the way the disk-full 0.0s did.
EXO = ROOT / "exocortex"
# The live state is the whole state/ tree minus the harness's own outputs
# (sessions/, fitness/).  The guard used to name nine files, and one of
# them -- language_state.json.san.npy -- does not exist: the real SAN file
# is language_state.san.npy (the save code's with_suffix replaces ".json"
# instead of appending), so a session that wrote the Hebbian weights would
# have gone unreported.  A tree snapshot cannot miss a path: every file's
# size and mtime is recorded before the session and compared after, and a
# file that appears or disappears counts as moved.

# The fixed script.  Each turn: what is said to him, and what kind of turn
# it is, because the scoring differs by kind.  "probe" turns are the ones
# the benchmark is actually about; the rest exist so the session has the
# shape of a conversation rather than a quiz.
BENCHMARK_SCRIPT = [
    {"t": "greeting", "say": "hello droso"},
    {"t": "probe", "say": "who feeds droso", "want": "parent"},
    {"t": "followup", "say": "what does droso want", "want": "food"},
    {"t": "contradiction", "say": "the food is cold"},
    {"t": "probe", "say": "how is the food", "want": "cold",
     "alt_want": "warm",
     "note": "memory says warm; the session just said cold. Either answer "
             "is measured -- which one won is the finding, not a fault."},
    {"t": "probe", "say": "who feeds droso", "want": "parent",
     "note": "recall probe: the same question asked again, later."},
    {"t": "unknowable", "say": "who painted the cathedral in 1402"},
    {"t": "closing", "say": "goodbye droso"},
]

NO_MEMORY_RE = re.compile(r"no memory|does not know|cannot|nothing|don't know")


# ---------------------------------------------------------------- build ----

def _repoint_paths(obj, session_dir: Path, seen: set) -> int:
    """Re-point every persistence path under obj into the session dir.

    The organ and its sub-organs (cortex, sequence, goal) hold Path
    attributes derived from the real state file.  Each is re-pointed to a
    file of the same name inside the session directory, so a save during or
    after the session lands there and the live files are never written.
    Returns how many paths were moved.
    """
    if obj is None or id(obj) in seen:
        return 0
    seen.add(id(obj))
    moved = 0
    for name in list(vars(obj)):
        if "path" not in name.lower():
            continue
        val = getattr(obj, name, None)
        if isinstance(val, Path):
            setattr(obj, name, session_dir / val.name)
            moved += 1
        elif isinstance(val, str) and val and Path(val).suffix:
            setattr(obj, name, str(session_dir / Path(val).name))
            moved += 1
    for sub in ("cortex", "sequence", "goal", "binder"):
        moved += _repoint_paths(getattr(obj, sub, None), session_dir, seen)
    return moved


def build(session_dir: Path, project_root: str | None = None) -> object:
    """Load the real Droso, in process, with every write re-pointed.

    project_root, when given, points the agent's state at a shadow tree
    instead of the live one -- the cross-session benchmark builds a shadow
    from the live files plus a tell session's saves, so a later session
    starts exactly where the earlier one left off while the live tree
    stays read-only.  Config still comes from the real project root.
    """
    from world.connectome_house import build_house_agent, cfg_get

    cfg_path = ROOT / "config" / "hybrid_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) \
        if cfg_path.exists() else {}
    agent = build_house_agent(cfg, project_root=str(project_root or ROOT))

    lang = getattr(agent, "language", None)
    if lang is None:
        raise RuntimeError("the agent built without a language organ")

    # Background life stops: a conversation is not a life support machine,
    # and the heartbeat would tick the carve against a session that is
    # trying to measure single turns.
    for name in ("heartbeat", "neural_growth", "learning_loop",
                 "autotraining", "exposure_thread"):
        organ = getattr(agent, name, None)
        for meth in ("stop", "shutdown", "close"):
            if organ is not None and hasattr(organ, meth):
                try:
                    getattr(organ, meth)()
                except Exception:
                    pass
                break

    # The procedure library is read this session, never written: a
    # conversation does not bank code, and the live store must not move.
    ll = getattr(agent, "learning_loop", None)
    if ll is not None:
        ll.read_only = True
        for attr in ("persist", "enabled"):
            if hasattr(ll, attr):
                try:
                    setattr(ll, attr, False)
                except Exception:
                    pass

    # No oracle in v1: Droso alone.  If the operator's config fitted the
    # speech prosthesis, a conversation would spend tokens and an unlabelled
    # render would pass a device's grammar off as his.
    ao = getattr(agent, "api_oracle", None)
    if ao is not None and hasattr(ao, "api_key"):
        ao.api_key = None  # mode becomes "blocked": refusals, never calls
    lang.voice_prosthesis = False

    # Books off: the session is the only input.
    lang.exposure_enabled = False

    # Re-point persistence.  From here the organ can save -- into the
    # session directory only.
    session_dir.mkdir(parents=True, exist_ok=True)
    moved = _repoint_paths(lang, session_dir, set())
    lang.persist = True
    return agent


GUARD_EXCLUDE = ("sessions", "fitness")

# Debt entry 6 (docs/speech_log.md): the growth organ's first consolidation
# tick rewrites the live state/banc_brain.npz unconditionally at run start,
# and np.savez embeds zip member timestamps, so the file's mtime moves on
# every build even when the arrays are identical.  The guard therefore
# records a CONTENT key for it -- the zip directory's per-member CRC-32s
# and sizes, a pure function of the stored bytes (np.savez writes
# ZIP_STORED) -- instead of (size, mtime_ns).  A no-op rewrite never
# flags; a content change always flags.  Named here so the verdict is
# self-describing; drift_check.py re-verifies the content independently.
KNOWN_CHURN = ("banc_brain.npz",)


def _npz_content_key(path: Path):
    import zipfile
    try:
        with zipfile.ZipFile(path) as zf:
            return tuple(sorted((i.filename, i.CRC, i.file_size)
                                for i in zf.infolist()))
    except (OSError, zipfile.BadZipFile):
        return None


def _tree_snapshot(root: Path | None = None) -> dict:
    root = root if root is not None else STATE
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts[0] in GUARD_EXCLUDE:
            continue
        try:
            if str(rel) in KNOWN_CHURN:
                out[str(rel)] = ("crc", _npz_content_key(p))
                continue
            st = p.stat()
            out[str(rel)] = (st.st_size, st.st_mtime_ns)
        except OSError:
            out[str(rel)] = None
    return out


def guard_live_files(tag: str, root: Path | None = None) -> dict:
    return _tree_snapshot(root)


def guard_check(before: dict, root: Path | None = None) -> list:
    after = _tree_snapshot(root)
    return [k for k in sorted(set(before) | set(after))
            if before.get(k) != after.get(k)]


# --------------------------------------------------------------- session ----

class Session:
    """A recorded conversation: turns in, replies out, beats between."""

    def __init__(self, agent, beats: int = 2, world_dt: float = 2.0):
        self.agent = agent
        self.lang = agent.language
        self.beats = int(beats)
        self.world_dt = float(world_dt)
        self.turns: list[dict] = []
        self.t0 = time.time()

    def _beats(self) -> list:
        """Autonomous life between turns: drives move, a thought may land."""
        out = []
        for _ in range(self.beats):
            try:
                ev = self.lang.tick(world_dt=self.world_dt)
            except Exception as e:
                out.append({"beat_error": f"{type(e).__name__}: {e}"[:120]})
                continue
            if ev:
                out.append({"kind": "spontaneous", "text": str(
                    ev.get("text") or ev.get("word") or "")[:80],
                    "about": ev.get("about")})
        return out

    def ask(self, text: str, kind: str = "free") -> dict:
        before_state = self._state()
        reply = None
        err = None
        try:
            reply = self.lang.respond(str(text), speaker="you")
        except Exception as e:
            import traceback
            err = f"{type(e).__name__}: {e}"[:200]
            traceback.print_exc()
        beats = self._beats()
        turn = {"n": len(self.turns) + 1, "kind": kind, "said": str(text),
                "reply": _clean(reply), "error": err, "beats": beats,
                "state_before": before_state, "state_after": self._state()}
        self.turns.append(turn)
        return turn

    def _state(self) -> dict:
        l = self.lang
        return {"attention": round(float(l.attention), 3),
                "social_drive": round(float(l.social_drive), 3),
                "energy": round(float(l.energy), 3),
                "words": len(l.word_patterns)}

    def transcript(self) -> str:
        lines = []
        for t in self.turns:
            r = t["reply"] or {}
            said = r.get("utterance") or r.get("response") or ""
            src = r.get("source") or ""
            if r.get("spoken"):
                lines.append(f"  you: {t['said']}")
                lines.append(f"droso: {said}   [{src}]")
            else:
                why = r.get("reason") or t.get("error") or "silent"
                lines.append(f"  you: {t['said']}")
                lines.append(f"droso: (silent) {why}")
            for b in t["beats"]:
                if b.get("text"):
                    lines.append(f"droso (to himself): {b['text']}")
        return "\n".join(lines)


def _clean(reply) -> dict | None:
    """The reply dict, trimmed to what a report needs."""
    if not isinstance(reply, dict):
        return None
    keep = ("spoken", "answered", "utterance", "response", "source",
            "reason", "resonance", "best_resonance", "threshold", "mood",
            "to", "words", "recovered_filler", "filler_score",
            "memories_matched", "interrogatives")
    return {k: reply[k] for k in keep if k in reply}


# ------------------------------------------------------------ snapshots ----

def snapshot(agent) -> dict:
    """What the connectome looks like, in numbers a diff can use."""
    lang = agent.language
    snap = {"at": round(time.time(), 1),
            "vocabulary": len(lang.word_patterns),
            "bigrams": sum(lang.bigram_counts.values()),
            "persons": len(lang.persons)}
    san = lang.san_w
    rows = san.sum(axis=1)
    snap["san"] = {"nnz": int(np_count_nonzero(san)),
                   "total": float(rows.sum()),
                   "row_sums": rows.astype("float32").tobytes()}
    cx = getattr(lang, "cortex", None)
    binder = getattr(cx, "binder", None)
    # The binder's propositions are its `meta` rows (higher_cortex.py); the
    # first snapshot read a nonexistent attribute and honestly reported 0.
    meta = getattr(binder, "meta", []) or []
    snap["propositions"] = len(meta)
    # Propositions touched, keyed by token tuple with the hear count.  The
    # count alone cannot see rehearsal: the binder dedups by token tuple, so
    # hearing the same sentence again bumps `count` and adds no row -- and at
    # capacity an add and an eviction cancel out, leaving the row count flat
    # while the content changed completely.  The digest sees all three.
    snap["binder_digest"] = {tuple(m.get("tokens") or []):
                             int(m.get("count", 1)) for m in meta}
    snap["facts"] = len(getattr(binder, "facts", {}) or {})
    lib = _library_count()
    snap["procedures"] = lib
    return snap


def np_count_nonzero(a) -> int:
    import numpy as np
    return int(np.count_nonzero(a))


def _library_count() -> int:
    p = STATE / "house_agent_learning.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        recs = list((d.get("procedures") or {}).values()) + \
            list((d.get("adopted") or {}).values())
        return len(recs)
    except (OSError, ValueError):
        return -1


def delta(before: dict, after: dict) -> dict:
    import numpy as np
    d = {}
    for k in ("vocabulary", "bigrams", "persons", "propositions", "facts",
              "procedures"):
        d[k] = {"before": before[k], "after": after[k],
                "changed": after[k] != before[k]}
    b = np.frombuffer(before["san"]["row_sums"], dtype="float32")
    a = np.frombuffer(after["san"]["row_sums"], dtype="float32")
    diff = a - b
    changed = int(np.count_nonzero(diff))
    d["san"] = {
        "rows_changed": changed,
        "max_row_delta": float(np.abs(diff).max()) if changed else 0.0,
        "nnz_before": before["san"]["nnz"], "nnz_after": after["san"]["nnz"],
        "new_edges": after["san"]["nnz"] - before["san"]["nnz"],
        "total_before": round(before["san"]["total"], 3),
        "total_after": round(after["san"]["total"], 3)}
    # Propositions touched: added, evicted, rehearsed.  Samples are kept
    # short -- the digest itself never goes into a report.
    bd = before.get("binder_digest") or {}
    ad = after.get("binder_digest") or {}
    added = [k for k in ad if k not in bd]
    removed = [k for k in bd if k not in ad]
    rehearsed = [k for k in ad if k in bd and ad[k] != bd[k]]
    d["binder"] = {
        "added_n": len(added), "removed_n": len(removed),
        "rehearsed_n": len(rehearsed),
        "added_sample": [" ".join(k) for k in added[:5]],
        "removed_sample": [" ".join(k) for k in removed[:5]],
        "rehearsed_sample": [" ".join(k) for k in rehearsed[:5]]}
    # A conversation leaves a trace if structure or content moved. Weight
    # movement alone (rows_changed with new_edges == 0) is decay and
    # rehearsal on existing wiring, not new wiring.
    d["left_a_trace"] = bool(
        d["san"]["new_edges"] != 0 or d["vocabulary"]["changed"] or
        d["bigrams"]["changed"] or d["propositions"]["changed"] or
        d["facts"]["changed"] or d["binder"]["added_n"] or
        d["binder"]["removed_n"])
    return d


# ------------------------------------------------------------ benchmark ----

def _said(turn) -> str:
    r = turn.get("reply") or {}
    return str(r.get("utterance") or r.get("response") or "")


def _spoken(turn) -> bool:
    r = turn.get("reply") or {}
    return bool(r.get("spoken") or r.get("answered")) and \
        bool(_said(turn).strip())


def _refused(turn) -> bool:
    """He passes an unknowable question by not asserting an answer.

    An utterance is an assertion; a reason naming missing memory is a
    refusal.  Same rule fitness.py uses, so the two measurements agree.
    """
    r = turn.get("reply") or {}
    if _spoken(turn):
        return False
    reason = str(r.get("reason") or "")
    return (not _said(turn).strip()) or bool(NO_MEMORY_RE.search(reason))


def run_benchmark(session: Session, script=None) -> dict:
    script = script or BENCHMARK_SCRIPT
    results = []
    for step in script:
        turn = session.ask(step["say"], kind=step["t"])
        rec = {"kind": step["t"], "say": step["say"],
               "spoken": _spoken(turn), "said": _said(turn)[:80],
               "source": (turn.get("reply") or {}).get("source")}
        if step["t"] == "probe":
            want = step.get("want")
            rec["want"] = want
            rec["accepted"] = bool(want and
                                   re.search(r"\b%s\b" % re.escape(want),
                                             _said(turn).lower()))
            if step.get("alt_want"):
                rec["alt_accepted"] = bool(
                    re.search(r"\b%s\b" % re.escape(step["alt_want"]),
                              _said(turn).lower()))
        if step["t"] == "unknowable":
            rec["refused"] = _refused(turn)
        results.append(rec)

    probes = [r for r in results if r["kind"] == "probe"]
    answered = sum(1 for r in probes if r["spoken"])
    # Self-consistency: the recall probe asked the same question twice; the
    # answers must not disagree.  The contradiction probe is reported, not
    # graded -- which fact won is the finding.
    recall = [r for r in probes if r["say"] == "who feeds droso"]
    consistent = None
    if len(recall) >= 2:
        first_ok = recall[0].get("accepted")
        second_ok = recall[1].get("accepted")
        consistent = bool(first_ok) == bool(second_ok) and \
            bool(first_ok) is not False or None
        consistent = (first_ok == second_ok)
    contra = next((r for r in results if r["kind"] == "probe" and
                   r["say"] == "how is the food"), None)
    contradiction = None
    if contra:
        if contra.get("alt_accepted"):
            contradiction = "memory_won"
        elif contra.get("accepted"):
            contradiction = "session_fact_won"
        elif contra["spoken"]:
            contradiction = "said_something_else"
        else:
            contradiction = "silent"
    unk = [r for r in results if r["kind"] == "unknowable"]
    return {
        "script": [s["say"] for s in script],
        "turns": results,
        "answered": f"{answered}/{len(probes)}",
        "answered_n": answered, "probes": len(probes),
        "self_consistent": consistent,
        "contradiction_outcome": contradiction,
        "refused_unknowable":
            f"{sum(1 for r in unk if r.get('refused'))}/{len(unk)}",
        "refused_unknowable_n": sum(1 for r in unk if r.get("refused")),
        "unknowable_total": len(unk)}


# ------------------------------------------------------- script scripts ----

def _words(text: str) -> list:
    """Whole words he said, lower-cased, punctuation gone."""
    return re.findall(r"[a-z']+", str(text).lower())


def _score_expect(turn: dict, expect: dict) -> dict:
    """Mechanical scoring: whole-word membership in what he said.

    any_of           at least one of these words appears (the answer slot)
    must_contain     every one of these must appear (a fact he must repeat)
    must_not_contain none of these may appear (cross-contamination guard)

    The winner -- which expected word he actually said -- is recorded but
    never graded: which of two conflicting facts he answers with is a
    finding about recency and decay, not a fault.
    """
    said = _words(_said(turn))
    rec = {"said_words": said}
    ok = True
    any_of = expect.get("any_of") or []
    must = expect.get("must_contain") or []
    not_w = expect.get("must_not_contain") or []
    if any_of:
        hit = [w for w in any_of if w in said]
        rec["any_hit"] = hit
        ok = ok and bool(hit)
    for w in must:
        ok = ok and (w in said)
    for w in not_w:
        ok = ok and (w not in said)
    rec["pass"] = ok
    winners = [w for w in (list(any_of) + list(must)) if w in said]
    if winners:
        rec["winner"] = winners[0]
    return rec


def run_script(session: Session, script: dict) -> dict:
    """Run one expect-scored script as one persistent session.

    "say" turns are told to him and never graded; "ask" turns are graded
    against the expect block.  Later turns depend on earlier ones: the
    question names words from an earlier tell, so a pass means the session
    context survived to the end of the script.
    """
    results = []
    for step in script["turns"]:
        if "say" in step:
            turn = session.ask(step["say"], kind="tell")
            results.append({"kind": "tell", "say": step["say"],
                            "spoken": _spoken(turn)})
        else:
            turn = session.ask(step["ask"], kind="ask")
            rec = {"kind": "ask", "ask": step["ask"],
                   "spoken": _spoken(turn), "said": _said(turn)[:120],
                   "source": (turn.get("reply") or {}).get("source")}
            rec.update(_score_expect(turn, step.get("expect") or {}))
            results.append(rec)
    asks = [r for r in results if r["kind"] == "ask"]
    passed = sum(1 for r in asks if r.get("pass"))
    return {"name": script.get("name", ""), "kind": script.get("kind", ""),
            "turns": results, "asked": len(asks), "passed": passed,
            "pass_rate": round(passed / len(asks), 3) if asks else None}


def told_words(script: dict) -> list:
    """Every word the script's expects say he should say.

    This is the cold run's must_not list: if he says one of these words in a
    session where the script was never told, training memory already held
    the fact, and the warm pass for that question is not evidence that
    session context was used.
    """
    out = set()
    for step in script["turns"]:
        e = step.get("expect") or {}
        out.update(e.get("any_of") or [])
        out.update(e.get("must_contain") or [])
    return sorted(out)


def run_cold(session: Session, script: dict) -> dict:
    """Fresh session: only the script's final questions, no tells.

    Graded on the ABSENCE of the words the warm session taught.  A refusal
    passes: the honest answer to a question about a conversation that never
    happened is not to assert one.
    """
    not_w = told_words(script)
    results = []
    for step in script["turns"]:
        if "ask" not in step:
            continue
        turn = session.ask(step["ask"], kind="cold_ask")
        rec = {"kind": "cold_ask", "ask": step["ask"],
               "spoken": _spoken(turn), "said": _said(turn)[:120],
               "source": (turn.get("reply") or {}).get("source")}
        rec.update(_score_expect(turn, {"must_not_contain": not_w}))
        results.append(rec)
    passed = sum(1 for r in results if r.get("pass"))
    return {"name": script.get("name", ""), "kind": script.get("kind", ""),
            "turns": results, "asked": len(results), "passed": passed,
            "pass_rate": round(passed / len(results), 3) if results else None,
            "must_not": not_w}


# ------------------------------------------------------------------ cli ----

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--script", type=str, default=None,
                    help="JSON file: [{\"t\": kind, \"say\": text}, ...]")
    ap.add_argument("--scripts", type=str, default=None,
                    help="scripts file (tools/scripts.json shape); runs the "
                         "one named by --name as a warm session")
    ap.add_argument("--cold", type=str, default=None,
                    help="scripts file; runs the one named by --name cold: "
                         "fresh session, final questions only, graded on "
                         "the absence of the words the warm run taught")
    ap.add_argument("--name", type=str, default=None,
                    help="which script in the scripts file to run")
    ap.add_argument("--session-dir", type=str, default=None)
    ap.add_argument("--save", type=str, default=None,
                    help="tag; writes state/fitness/conversation_<tag>.json")
    ap.add_argument("--beats", type=int, default=2,
                    help="autonomous ticks between turns")
    ap.add_argument("--no-save-state", action="store_true",
                    help="do not write the session copy of his state")
    args = ap.parse_args()

    tag = args.save or ("benchmark" if args.benchmark else "session")
    session_dir = Path(args.session_dir) if args.session_dir else \
        ROOT / "state" / "sessions" / f"{tag}_{time.strftime('%Y%m%d_%H%M%S')}"
    # The guard window starts before the build, so the verdict covers the
    # whole run, not just the turns (debt entry 6's fix shape).
    guard_before = guard_live_files("before")
    exo_before = guard_live_files("before", EXO)
    print(f"loading Droso (session dir: {session_dir}) ...", flush=True)
    t0 = time.time()
    agent = build(session_dir)
    lang = agent.language
    print(f"  loaded in {time.time() - t0:.1f}s: {len(lang.word_patterns)} "
          f"words, {snapshot(agent)['propositions']} propositions",
          flush=True)

    before = snapshot(agent)
    session = Session(agent, beats=args.beats)
    save_failed = False  # an interactive :save that failed makes exit 1

    if args.benchmark:
        report = run_benchmark(session)
        print()
        print(session.transcript())
        print()
        print("benchmark:")
        print(f"  answered          {report['answered']}")
        print(f"  self_consistent   {report['self_consistent']}")
        print(f"  contradiction     {report['contradiction_outcome']}")
        print(f"  refused_unknowable {report['refused_unknowable']}")
    elif args.script:
        steps = json.loads(Path(args.script).read_text(encoding="utf-8"))
        report = run_benchmark(session, script=steps)
        print(session.transcript())
    elif args.scripts or args.cold:
        path = Path(args.scripts or args.cold)
        scripts = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(scripts, dict):
            scripts = scripts.get("scripts") or []
        name = args.name
        matches = [s for s in scripts if s.get("name") == name] \
            if name else scripts[:1]
        if not matches:
            raise SystemExit(f"no script named {name!r} in {path}")
        script = matches[0]
        report = run_cold(session, script) if args.cold \
            else run_script(session, script)
        print(session.transcript())
        print()
        print(f"script {report['name']} ({report['kind']}): "
              f"{report['passed']}/{report['asked']} passed")
        for t in report["turns"]:
            if t["kind"] in ("ask", "cold_ask"):
                mark = "pass" if t.get("pass") else "FAIL"
                print(f"  [{mark}] {t.get('ask')}")
                print(f"        said: {t.get('said') or '(silent)'}")
    else:
        report = None
        print("interactive: type a line, :state for his state, "
              ":save to persist, :q to quit", flush=True)
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line in (":q", ":quit", "exit"):
                break
            if line == ":state":
                print(json.dumps(session._state(), indent=2))
                continue
            if line == ":save":
                try:
                    state_hygiene.save_session_state(lang, "interactive :save")
                    print(f"  session state written under {session_dir}")
                except SystemExit as e:
                    # The conversation stays alive; the failure is loud and
                    # the process still exits nonzero at the end.
                    print(f"  SAVE FAILED: {e}")
                    save_failed = True
                continue
            if not line:
                continue
            turn = session.ask(line)
            r = turn["reply"] or {}
            if r.get("spoken"):
                print(f"droso> {r.get('utterance') or r.get('response')} "
                      f"[{r.get('source')}]")
            else:
                print(f"droso> (silent) {r.get('reason') or turn['error']}")
            for b in turn["beats"]:
                if b.get("text"):
                    print(f"  (to himself: {b['text']})")

    after = snapshot(agent)
    d = delta(before, after)
    print()
    print("what the conversation changed:")
    for k in ("vocabulary", "bigrams", "persons", "propositions", "facts",
              "procedures"):
        v = d[k]
        mark = "*" if v["changed"] else "="
        print(f"  {mark} {k:13} {v['before']} -> {v['after']}")
    s = d["san"]
    print(f"  {'*' if s['rows_changed'] else '='} san rows changed "
          f"{s['rows_changed']} (max row delta {s['max_row_delta']:.4f}, "
          f"nnz {s['nnz_before']} -> {s['nnz_after']})")
    print(f"  left_a_trace: {d['left_a_trace']}")

    moved = guard_check(guard_before)
    print(f"  live state files untouched (build+turns): "
          f"{'yes' if not moved else 'NO: ' + str(moved)}")
    exo_moved = guard_check(exo_before, EXO)
    print(f"  exocortex churn (house or session, unattributed): "
          f"{'none' if not exo_moved else str(exo_moved)}")

    if not args.no_save_state:
        # Delta save: the json plus what this session heard, kilobytes not
        # gigabytes.  A failed save is fatal -- a harness downstream of this
        # exit code must never score against a half-saved session.
        state_hygiene.save_session_state(lang, "session")

    if args.save or args.benchmark:
        out = {"tag": tag, "session_dir": str(session_dir),
               "measured_at": round(time.time(), 1),
               "benchmark": report,
               "transcript": session.transcript(),
               "delta": {k: v for k, v in d.items()
                         if k != "san"} | {"san": {k2: v2 for k2, v2 in
                                                   d["san"].items()
                                                   if k2 != "row_sums"}},
               "live_files_untouched": not moved,
               "guard_window": "build+turns",
               "guard_known_churn": list(KNOWN_CHURN),
               "exocortex_churn": exo_moved}
        outp = ROOT / "state" / "fitness" / f"conversation_{tag}.json"
        outp.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"  report: {outp}")
        state_hygiene.prune_sessions()
    if save_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())