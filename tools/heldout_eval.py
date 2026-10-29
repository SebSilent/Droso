r"""Held-out hard evaluation: a gate that can actually see a capability gain.

WHY THIS EXISTS.  The only capability gate in the house reads 32/32 at
1.00/1.00 (tools/scripts.json, six scripts).  A saturated instrument cannot
register an improvement of any size, so five consecutive cuts produced
knowledge and zero capability.  This harness measures the other end: tasks
Droso fails today that a language model would pass.  A LOW SCORE IS THE POINT;
a 1.00 here means the tasks are too easy and must be replaced.

NO JUDGE.  Every check is mechanical over the words he actually said:
  answer            at least one of these whole words must appear (the slot)
  must_contain      every one must appear (exact repetition)
  order             these must appear as a strictly increasing subsequence
  forbid            NONE may appear -- this is what makes it ungameable, since
                    blurting a related word cannot pass
  require_refusal   he must NOT assert: a spoken answer, or any forbidden word,
                    fails it.  This is the state invariant ("did i ever mention
                    the moon") graded without asking anyone's opinion.
Nothing here consults a model, a threshold, or a human.  A task with no answer
slot, no must_contain and no require_refusal is a BUG and is reported as one.

STAGE ATTRIBUTION.  For every failure, which stage refused it, from the trace
fields the reply already carries (reason / source / parser.verdict /
recovered_filler / memories_matched / join / band_walk):
  recall         nothing reached the arbiter -- coverage floor, no memory,
                 or a join that never assembled (join and band-walk refusals
                 are recall-side: the shape question was never asked)
  shape_arbiter  a candidate existed and the shape veto/recovered filler chose
  mouth          he answered from the sequence organ -- the words he has
  other          spoke, wrong content, none of the above
The raw trace strings ride along, so the map is evidence and not interpretation.

Live state is read-only: every organ is re-pointed into a session copy under
state/sessions/ by converse.build(), and each script gets a FRESH copy, so no
task is contaminated by an earlier one.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.converse import Session, build, _clean, _said, _spoken, _words  # noqa: E402

TASKS = ROOT / "tools" / "scripts_heldout.json"

RECALL_RE = re.compile(
    r"cover|no memor|nothing he rememb|remembers no|no trace|not heard|"
    r"never heard|no witness|no record|empty|no candidate|nothing to answer|"
    r"did not hear|no join|no path", re.I)
ARB_RE = re.compile(r"shape|verdict|veto|filler|no such slot|form", re.I)
MOUTH_RE = re.compile(r"mouth|sequence|meaning resonance", re.I)
# "it understood but did not feel like speaking" is the REPLY GATE refusing, not
# memory failing -- recall succeeded and said so.  Counting those as recall misses
# would aim the next cut at the wrong organ, which is the whole point of the map.
GATING_RE = re.compile(
    r"did not feel like speaking|not feel like|did not want to speak|"
    r"chose not|no urge|reluctan", re.I)


def grade(said_words: list, spoken: bool, expect: dict) -> tuple[bool, str]:
    """Mechanical pass/fail.  Returns (passed, why)."""
    if not expect:
        return False, "UNGRADED: no expect block (harness bug)"
    answer = expect.get("answer") or []
    forbid = expect.get("forbid") or []
    must = expect.get("must_contain") or []
    order = expect.get("order") or []
    refusal = bool(expect.get("require_refusal"))
    if not (answer or must or order or refusal):
        return False, "UNGRADED: task has no check (harness bug)"

    hits = [w for w in answer if w in said_words]
    for w in forbid:
        if w in said_words:
            return False, f"forbidden word said: {w}"
    if refusal:
        if spoken and hits:
            return False, "asserted an answer where the invariant is silence"
        if spoken and any(_said_content(said_words)):
            return False, "spoke where the invariant is silence"
        return True, "refused, as the invariant requires"
    missing = [w for w in must if w not in said_words]
    if missing:
        return False, f"missing: {missing}"
    if order:
        pos, cur = -1, -1
        for w in order:
            try:
                i = said_words.index(w, cur + 1)
            except ValueError:
                return False, f"order broken: {w} not after {order}"
            pos, cur = i, i
        _ = pos
    if answer and not hits:
        return False, f"answer slot empty: wanted {answer}"
    return True, "ok"


def _said_content(words: list) -> list:
    return [w for w in words if w not in ("the", "a", "is", "are", "of", "to")]


def stage_of(turn: dict, why: str) -> str:
    r = turn.get("reply") or {}
    if why.startswith("UNGRADED"):
        return "harness-bug"
    # Session.ask keeps an exception as turn["error"] and an empty reply, so a
    # crash looks EXACTLY like a silent recall miss: no reason, no source.
    # Two of the first baseline's "recall" items were crashes (KeyError
    # 'proposition' in answer(), organs/neural_language.py:2803) -- calling
    # those a memory miss would have aimed the next cut at recall.
    if turn.get("error"):
        return "engine_error"
    reason = str(r.get("reason") or "")
    src = str(r.get("source") or "")
    par = r.get("parser") or {}
    verdict = str(par.get("verdict") or par) if isinstance(par, dict) else str(par)
    if not _spoken(turn):
        if GATING_RE.search(reason):
            return "gating"          # he understood and declined: not a memory miss
        if "veto" in verdict.lower():
            return "shape_arbiter"
        if ARB_RE.search(reason) and not RECALL_RE.search(reason):
            return "shape_arbiter"
        if RECALL_RE.search(reason):
            return "recall"
        if r.get("join") or r.get("band_walk"):
            return "recall"          # the join never assembled: recall-side
        # Silence with NO reason string at all.  Attributed recall because a
        # refusal with no candidate is the usual shape of a recall miss -- but
        # the reply carries no evidence either way, so this is a DEFAULT, not a
        # measurement, and it is counted separately below.
        return "recall_untraced" if not reason else "recall"
    if MOUTH_RE.search(src):
        return "mouth"
    if r.get("recovered_filler"):
        return "shape_arbiter"
    return "other"


def run_one(script: dict, keep_copies: bool) -> dict:
    sd = ROOT / "state" / "sessions" / f"heldout_{script['name']}"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    recs = []
    for step in script["turns"]:
        if "say" in step:
            t = sess.ask(step["say"], kind="tell")
            recs.append({"kind": "tell", "say": step["say"],
                         "spoken": _spoken(t)})
            continue
        recs.append(ask_record(sess, step))
    if not keep_copies:
        shutil.rmtree(sd, ignore_errors=True)
    asks = [x for x in recs if x["kind"] == "ask"]
    return {"name": script["name"], "kind": script.get("kind"),
            "asked": len(asks), "passed": sum(1 for x in asks if x["pass"]),
            "turns": recs}


def ask_record(sess, step) -> dict:
    """Grade one ask against the session it is put to.

    Shared by the sequential and the independent mode on purpose: the two
    numbers have to come off the same checker or comparing them is meaningless.
    """
    t = sess.ask(step["ask"], kind="ask")
    r = t.get("reply") or {}
    words = _words(_said(t))
    ok, why = grade(words, _spoken(t), step.get("expect") or {})
    return {
        "kind": "ask", "ask": step["ask"], "said": _said(t)[:120],
        "words": words[:24], "spoken": _spoken(t), "pass": ok, "why": why,
        "stage": None if ok else stage_of(t, why),
        "expect": step.get("expect"),
        "trace": {"reason": r.get("reason"), "source": r.get("source"),
                  "parser": r.get("parser"), "vote": r.get("vote"),
                  "join": r.get("join"), "band_walk": r.get("band_walk"),
                  "recovered_filler": r.get("recovered_filler"),
                  "filler_score": r.get("filler_score"),
                  "memories_matched": r.get("memories_matched")}}


def run_one_independent(script, keep_copies, journal) -> dict:
    """Every ask scored against a FRESHLY BUILT house.

    The tells that PRECEDE the ask are replayed into a new copy, then that one
    ask and no other is put to it. So nothing an earlier ask did -- speaking,
    spending, writing the ledger, changing what he feels like saying -- can move
    this number. It is the measurement future cuts should be judged against:
    an unrelated fix inside ask 1 cannot change ask 3's score, which is exactly
    how the KeyError fix moved `is the coat dry or wet` in the sequential run.

    Cost is one build per ask, so this runs in chunks and journals each result
    as it lands (a turn boundary kills the process; the journal keeps the work).
    """
    turns = script["turns"]
    idxs = [i for i, s in enumerate(turns) if "ask" in s]
    recs = []
    for n, i in enumerate(idxs, 1):
        sd = (ROOT / "state" / "sessions"
              / f"heldoutind_{script['name']}_{n}")
        if sd.exists():
            shutil.rmtree(sd)
        agent = build(sd)
        sess = Session(agent, beats=0)
        for st in turns[:i]:
            if "say" in st:
                sess.ask(st["say"], kind="tell")
        rec = ask_record(sess, turns[i])
        recs.append(rec)
        with journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "id": f"{script['name']}::{rec['ask']}",
                "script": script["name"], "ask": rec["ask"],
                "pass": bool(rec["pass"]),
                "stage": rec["stage"], "said": rec["said"],
                "why": rec["why"]}) + "\n")
        print(f"   [{script['name'][:16]:16s}] {n}/{len(idxs)} "
              f"{'PASS' if rec['pass'] else 'fail'}  {rec['ask'][:46]}  "
              f"stage={rec['stage'] or '-'}", flush=True)
        if not keep_copies:
            shutil.rmtree(sd, ignore_errors=True)
    return {"name": script["name"], "kind": script.get("kind"),
            "asked": len(recs), "passed": sum(1 for x in recs if x["pass"]),
            "turns": recs}


def compare(paths) -> int:
    """Print two campaign journals side by side and list every ask whose
    outcome or stage differs between them.

    The bar is reproducible in aggregate and NOT in membership: 5/24 held
    across campaigns while two asks left the pass set and two entered it, on an
    unchanged tree. So a score delta cannot, by itself, tell a cut from drift,
    and the standing rule -- only movement verified on both trees in the same
    hour counts -- was a process promise. This makes it a field: the two columns
    are the two trees (or the tree and its control), and any row that differs is
    named.
    """
    def load(p):
        d = {}
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            key = r.get("id") or f"{r['script']}::{r['ask']}"
            d[key] = ("PASS" if r.get("pass")
                      else (r.get("stage") or "unknown"))
        return d

    A, B = (load(p) for p in paths)
    label = [Path(p).name for p in paths]
    print(f"\n=== PASS-SET COMPARISON ===\n  A = {label[0]}\n  B = {label[1]}")
    print(f"\n  {'A':14s} {'B':14s}  ask")
    moved = []
    for k in sorted(set(A) | set(B)):
        a, b = A.get(k, "--absent--"), B.get(k, "--absent--")
        if a == b:
            print(f"  {a:14s} {b:14s}  {k}")
        elif k in A and k in B:
            moved.append((k, a, b))
            print(f"  {a:14s} {b:14s}  {k}   << MOVED")
        else:
            # Present on one side only: a chunked campaign covers fewer asks
            # than a whole one, so this is coverage, not movement.
            print(f"  {a:14s} {b:14s}  {k}   (coverage, not movement)")
    only_a = sorted(k for k in A if k not in B)
    only_b = sorted(k for k in B if k not in A)
    if only_a or only_b:
        # A chunked campaign covers fewer asks than a whole one, so a missing
        # row is coverage, not movement. Say so before the diff, or a partial
        # journal against a full one reads as dozens of changed asks.
        print(f"\n  NOTE the two journals cover different ask sets: "
              f"{len(only_a)} only in A, {len(only_b)} only in B. Those rows "
              f"are coverage, not movement -- compare the {len(set(A) & set(B))} "
              f"shared asks.")
    pa = sum(1 for v in A.values() if v == "PASS")
    pb = sum(1 for v in B.values() if v == "PASS")
    print(f"\n  A {pa}/{len(A)} = {pa / max(1, len(A)):.3f}   "
          f"B {pb}/{len(B)} = {pb / max(1, len(B)):.3f}   "
          f"score delta {pb - pa:+d}")
    print(f"  asks whose outcome or stage differs: {len(moved)}")
    for k, a, b in moved:
        print(f"     {a} -> {b}   {k}")
    if pa == pb and moved:
        print("\n  SAME SCORE, DIFFERENT MEMBERSHIP: the bar moved without the "
              "score moving. Treat any single-script shift here as drift until "
              "both trees have been run.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="run scripts whose name matches")
    ap.add_argument("--compare", nargs=2, metavar=("JOURNAL_A", "JOURNAL_B"),
                    help="print two independent-mode journals side by side "
                         "(ask id + outcome in each) and name every difference")
    ap.add_argument("--keep-copies", action="store_true")
    ap.add_argument("--independent", action="store_true",
                    help="score every ask against a freshly built house (one "
                         "build per ask, no shared session state), so an "
                         "unrelated fix cannot move a later ask's number")
    ap.add_argument("--journal", default=None,
                    help="where the independent mode appends one line per ask "
                         "(default state/fitness/heldout_independent.jsonl)")
    a = ap.parse_args()
    if a.compare:
        return compare(a.compare)
    scripts = json.loads(TASKS.read_text(encoding="utf-8"))["scripts"]
    if a.only:
        scripts = [s for s in scripts if a.only in s["name"]]
    journal = Path(a.journal) if a.journal else (
        ROOT / "state" / "fitness" / "heldout_independent.jsonl")
    if a.independent and not a.only and journal.exists():
        # A whole-campaign run starts fresh; a chunked run (--only) appends,
        # because 24 builds will not fit inside one turn's wall clock.
        journal.unlink()
    journal.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    out = []
    for s in scripts:
        r = (run_one_independent(s, a.keep_copies, journal) if a.independent
             else run_one(s, a.keep_copies))
        out.append(r)
        print(f"[{r['name']:24s}] {r['passed']}/{r['asked']}"
              f"   ({time.time() - t0:.0f}s)", flush=True)

    asked = sum(r["asked"] for r in out)
    passed = sum(r["passed"] for r in out)
    print("\n=== HELD-OUT BASELINE ===")
    print(f"SCORE {passed}/{asked} = {passed / max(1, asked):.3f}")
    by_kind = {}
    stages = {}
    for r in out:
        for x in r["turns"]:
            if x["kind"] != "ask":
                continue
            k = r["kind"] or "?"
            d = by_kind.setdefault(k, [0, 0])
            d[1] += 1
            d[0] += 1 if x["pass"] else 0
            if not x["pass"]:
                stages[x["stage"]] = stages.get(x["stage"], 0) + 1
    for k, (p, n) in sorted(by_kind.items()):
        print(f"  {k:12s} {p}/{n}")
    print("\nFAILURE MAP -- which stage refused it:")
    for k, n in sorted(stages.items(), key=lambda kv: -kv[1]):
        print(f"  {k:14s} {n}")
    # The composition, not just the count. 5/24 held across campaigns while two
    # asks left the pass set and two entered it, on an unchanged tree -- so a
    # score alone cannot tell a cut from drift. Emit which ask went where, every
    # campaign, and let --compare diff two of them.
    attribution = {}
    for r in out:
        for x in r["turns"]:
            if x["kind"] != "ask":
                continue
            attribution[f"{r['name']}::{x['ask']}"] = (
                "PASS" if x["pass"] else (x["stage"] or "unknown"))
    print("\nPASS SET AND STAGES (ask id -> outcome):")
    for k in sorted(attribution):
        print(f"  {attribution[k]:14s} {k}")
    print("\nFAILURES IN FULL:")
    for r in out:
        for x in r["turns"]:
            if x["kind"] == "ask" and not x["pass"]:
                print(f"  [{r['name']}] {x['ask']}")
                print(f"      said : {x['said']!r}  spoken={x['spoken']}")
                print(f"      want : {x['expect']}")
                print(f"      why  : {x['why']}   STAGE={x['stage']}")
                tr = x["trace"]
                print(f"      trace: reason={tr['reason']!r} source={tr['source']!r} "
                      f"verdict={(tr['parser'] or {}).get('verdict') if isinstance(tr['parser'], dict) else tr['parser']!r} "
                      f"filler={tr['recovered_filler']!r} mem={tr['memories_matched']}")
    ts = time.strftime("%Y%m%d_%H%M%S")
    tag = "ind_" if a.independent else ""
    rep = ROOT / "state" / "fitness" / f"heldout_{tag}{ts}.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps({"at": ts, "score": f"{passed}/{asked}",
                               "rate": round(passed / max(1, asked), 3),
                               "by_kind": by_kind, "stages": stages,
                               "pass_set": sorted(k for k, v in attribution.items()
                                                  if v == "PASS"),
                               "attribution": attribution,
                               "scripts": out}, indent=1, default=str),
                   encoding="utf-8")
    print(f"\nreport: {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
