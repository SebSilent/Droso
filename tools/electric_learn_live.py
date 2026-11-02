"""LIVE-HOUSE check of the FULL teach/learn mode: three arms, one script, in the real Droso.

`--electric-learn` turns on fifteen switches at once. `tests/test_electric_learn_mode.py` proves
the SET is the set and that the answer path behaves on a bare organ; this file is the only place
that says what the combination does in a house with a corpus behind it, because a bare organ
cannot speak an inventory answer at all (`respond` returns `heard; no language learned yet` for an
ask `answer()` resolves perfectly) -- so a unit test that asserted the speaking would be asserting
nothing, and a live check that asserted only the answer path would be a unit test in a costume.

Three arms run the SAME script, so every difference is attributable to a switch:

  control  ELECTRIC off entirely -- the house every number in this repo was measured in
  teach    the stack that can only ever refuse (tools/electric_teach_mode.py: STACK + BASE)
  learn    teach plus the four widenings (LEARN + BASE)

and each arm is asked twice: once in the life it was taught in, once after a real restart through
the saved session files.

What is asserted, and why those four:
  * the three shapes the widenings exist for (object-role, stranded reverse, the stemmer's fold)
    come back VERBATIM in learn -- a sentence the person said, not a word lifted out of one;
  * no arm ever says a sentence nobody told it. That is the invariant four widenings could break
    and the reason the mode is allowed to exist;
  * the fragment (`to?`) never leaves any arm's mouth, taught life or restarted;
  * an untaught ask is refused in every arm, and the refusal is not an answer anywhere.

What is NOT asserted: that the widenings are free. The evidence file records, per arm and per ask,
which store answered -- including the cases where teach mode answers with a single arbiter word
and learn mode answers with the whole tell, which is the trade the mode flag is asking you to make.

Writes docs/evidence/electric_learn_live.json. Run:  python tools/electric_learn_live.py
"""
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.converse as converse                    # noqa: E402
import tools.electric_teach_mode as tm               # noqa: E402

TMP = Path("_tmp/electric_learn_live")
EVIDENCE = Path("docs/evidence/electric_learn_live.json")

# Facts a person tells. `hear` is the write door for the keyed inventory.
TELLS = ["the dog bites the latch",
         "the lantern belongs to Mira",
         "the copper bell rings",
         "the latch holds the door"]

# Pairs a person teaches: ask, then say the answer. The marked form is the protocol.
PAIRS = [("what rings the bell?", "the copper bell rings"),
         ("what holds the door?", "the latch holds the door")]

# The asks, in the form that reaches the answer path. Marked asks are HELD when elicitation is on
# -- that is the teaching protocol, not a miss -- so every probe here is unmarked, and the shape
# detector is what still lets the house tell them from statements.
PROBES = [
    ("fold", "what ring the bell", "the copper bell rings"),
    ("exact", "what rings the bell", "the copper bell rings"),
    ("object-role", "what bites the latch", "the dog bites the latch"),
    ("reverse", "who does the lantern belong to", "the lantern belongs to Mira"),
    ("untaught", "where is the moon", None),
    ("untaught2", "who does the bell report to", None),
]

# The leak's own two lines, kept here because the full mode contains the guard that closes it.
STRANDED = "who does the mouse chase to"
BARE = "who does the mouse chase"
FRAGMENTS = {"to?", "to", ""}

SPOKEN = set(TELLS) | {a for _q, a in PAIRS}


def boot(tag, mode, root):
    """One real house, flags wired from the TABLE, in the order serve.py uses.

    The timing knobs go on BEFORE the tells, copied from tools/qa_elicit_live.py for exactly the
    reason it says: set after, which tells produced a row depends on wall-clock, and the arms then
    differ by a row for a reason that has nothing to do with a flag.
    """
    agent = converse.build(TMP / "sess" / tag, project_root=str(root))
    lang = agent.language
    if mode != "control":
        for attr in tm.BASE_ATTRS:
            setattr(lang, attr, True)
    if mode == "teach":
        tm.enable(lang)
    elif mode == "learn":
        tm.enable_learn(lang)
    lang.exposure_enabled = False
    lang.social_drive = 1.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang.exposure_speed_s = 0.0
    lang.cortex.MIN_HEAR_INTERVAL_S = 0.0
    # Persistence on, exactly as the shipped door turns it on (electric_chat.build_organ sets it
    # after the flags). Without it the organ answers beautifully in one process and leaves nothing
    # on disk, and a "restart" that boots from an empty state dir proves nothing about a mode --
    # which is precisely what the first two runs of this tool did, and reported as the mode losing
    # every fact across a restart.
    lang.persist = True
    return lang


def teach(lang):
    for t in TELLS:
        lang.hear(t, speaker="you")
    for ask, ans in PAIRS:
        lang.respond(ask, speaker="you")
        lang.respond(ans, speaker="you")
        lang._qa_pending = None
    return lang


def ask_all(lang):
    """Every probe, plus the fragment pair, through the ANSWER door."""
    out = {}
    for label, q, _want in PROBES:
        r = lang.answer(q) or {}
        out[label] = {"ask": q,
                      "answered": bool(r.get("answered")),
                      "said": str(r.get("utterance") or "").strip(),
                      "src": str(r.get("source") or ""),
                      "reason": str(r.get("reason") or "")[:120]}
    lang.hear(STRANDED, speaker="you")
    lang._qa_pending = None
    r = lang.answer(BARE) or {}
    out["fragment"] = {"ask": BARE, "answered": bool(r.get("answered")),
                       "said": str(r.get("utterance") or "").strip(),
                       "src": str(r.get("source") or ""),
                       "reason": str(r.get("reason") or "")[:120]}
    return out


def run(mode):
    tag = mode
    root = TMP / "root" / tag
    for p in (root, TMP / "sess" / tag):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    (root / "state").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    lang = boot(tag, mode, root)
    flags = tm.state(lang)
    teach(lang)
    live = ask_all(lang)
    # restart: save, copy the session files into the house's state dir, boot again
    sdir = TMP / "sess" / tag
    sv = lang.save_state(force=True) or {}
    saved = (sdir / "language_state.json").exists()
    session_files = sorted(f.name for f in sdir.iterdir() if f.is_file())
    for f in sdir.iterdir():
        if f.is_file():
            shutil.copy2(f, root / "state" / f.name)
    lang2 = boot(tag, mode, root)
    # THE RESTART HALF, and the reason this line is here rather than assumed: `converse.build`
    # comes up amnesiac. The saved language state is applied by `load_state()`, which tools/serve.py
    # runs inside its `--electric` block -- so a house booted from a session without that call has
    # the files on disk and nothing in its head. The first run of this tool found exactly that, and
    # reported the full mode as losing every taught fact across a restart: the harness was not
    # loading, not the mode.
    # Every arm, control included. The first version of this line skipped `load_state()` for the
    # control arm on the reasoning that a house with no ELECTRIC flags has no language state to
    # load -- but the cortex rows come back off the .npz at build time regardless, so the skipped
    # call made control's "restart" a different experiment from the other two arms, and its
    # post-restart column was not a restart at all.
    loaded = lang2.load_state() or {}
    restarted = ask_all(lang2)
    res = {"mode": mode,
           "flags_on": sorted(a for a, v in flags.items() if v),
           "seconds": round(time.time() - t0, 1),
           "saved_files_seen": bool(saved),
           "session_files": session_files,
           "save_result_keys": sorted(str(k) for k in sv.keys()),
           "restart_loaded": bool((loaded or {}).get("loaded")),
           "restart_state_keys": sorted((loaded or {}).keys()),
           "taught_pairs_before_restart": sum(
               1 for r in (getattr(lang, "qa_store", {}) or {}).values()
               if ((r or {}).get("prov") or {}).get("source") == "conversation"),
           "inventory_before_restart": sum(len(v) for v in
                                           (getattr(lang, "_taught_says", {}) or {}).values()),
           "rows": len(lang2.cortex.binder.meta),
           "qa_pairs": len(getattr(lang2, "qa_store", {}) or {}),
           "taught_says": {k: v for k, v in (lang2._taught_says or {}).items()},
           "inventory_at_restart": sum(len(v) for v in
                                       (getattr(lang2, "_taught_says", {}) or {}).values()),
           "live": live, "restarted": restarted}
    print(f"  [{mode:7}] {res['seconds']}s flags={len(res['flags_on'])} "
          f"answered={sum(1 for v in live.values() if v['answered'])} "
          f"after_restart={sum(1 for v in restarted.values() if v['answered'])}", flush=True)
    return res


# Lower-cased on purpose. The rows are stored lower-cased, so the arbiter answers `mira` while the
# person said `Mira` -- and a check that called that an invention would be a check with a case bug,
# not a finding about the mode. The first run of this file found it in the CONTROL arm, where no
# ELECTRIC flag is on at all, which is the only reason it was obvious.
SPOKEN_L = {s.lower() for s in SPOKEN}
WORDS = {w.lower() for s in SPOKEN for w in s.split()}


def check(res):
    """Per-arm invariants. Returns a list of failures -- empty means the arm held.

    `answered` with a one-word filler is NOT an invention and is not treated as one: the shape
    arbiter speaks `dog` for `what bites the latch` in the narrow arms, which is a word it was
    told, out of a sentence it was told. The line this file draws is the one that matters -- no
    arm may say a SENTENCE nobody said, and no arm may answer an untaught ask with a taught one.
    """
    bad = []
    for phase, tab in (("live", res["live"]), ("restarted", res["restarted"])):
        for label, got in tab.items():
            said = got["said"]
            if label == "fragment":
                if said in FRAGMENTS - {""}:
                    bad.append(f"{res['mode']}/{phase}: the fragment spoke ({said!r})")
                continue
            low = said.lower()
            if got["answered"] and low not in SPOKEN_L and low not in WORDS:
                bad.append(f"{res['mode']}/{phase}/{label}: invented {said!r}")
            if label.startswith("untaught") and low in SPOKEN_L:
                bad.append(f"{res['mode']}/{phase}/{label}: answered what it was never told")
    # The harness invariant, and the only reason this tool found its own bug instead of reporting
    # a mode that loses facts: a restart that loaded nothing cannot convict anything, so it fails
    # loudly rather than printing empty cells. It applies to EVERY arm, control included -- the
    # first version exempted the one arm whose boot was wrong, which is precisely where a wrong
    # boot can hide: an arm nobody checks is an arm that cannot fail.
    if not res["restart_loaded"]:
        bad.append(f"{res['mode']}: the restarted house loaded no state (load_state said "
                   f"{res['restart_state_keys']}) -- the restart arm proves nothing")
    if res["inventory_before_restart"] and not res["inventory_at_restart"]:
        bad.append(f"{res['mode']}: {res['inventory_before_restart']} keyed tells before the "
                   f"restart, {res['inventory_at_restart']} after")
    return bad


def main():
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    print("[learn-live] three arms, one script, the real house", flush=True)
    arms = {}
    for mode in ("control", "teach", "learn"):
        arms[mode] = run(mode)

    fails = []
    for mode, res in arms.items():
        fails += check(res)

    # The buy, arm by arm: what each mode says to the three widening probes.
    table = {m: {k: (r["live"][k]["said"], r["live"][k]["src"],
                     r["restarted"][k]["said"]) for k in
                 ("fold", "object-role", "reverse", "untaught")}
             for m, r in arms.items()}
    learn = arms["learn"]
    for label, _q, want in (("fold", *PROBES[0][1:]),
                            ("object-role", *PROBES[2][1:]),
                            ("reverse", *PROBES[3][1:])):
        for phase in ("live", "restarted"):
            got = learn[phase][label]["said"]
            if want is not None and got != want:
                fails.append(f"learn/{phase}/{label}: expected {want!r}, got {got!r}")

    out = {"arms": arms, "say_what_each_answered": table,
           "taught": sorted(SPOKEN), "probes": [p[1] for p in PROBES],
           "failures": fails,
           "note": ("control has no ELECTRIC at all; teach is the stack that can only refuse; "
                    "learn is teach plus the four widenings. Every answer in every arm is a "
                    "sentence from `taught` or silence -- the widenings change which asks REACH "
                    "an answer, never what an answer may say.")}
    EVIDENCE.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(table, indent=1, sort_keys=True), flush=True)
    if fails:
        print(f"[learn-live] FAILURES ({len(fails)}):", flush=True)
        for f in fails:
            print("   - " + f, flush=True)
        return 1
    print(f"[learn-live] clean: 3 arms, {len(arms['learn']['flags_on'])} flags in the full mode, "
          f"evidence -> {EVIDENCE}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
