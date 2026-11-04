#!/usr/bin/env python
"""ELECTRIC_LEARN_BENCH -- how much of a 40-item curriculum a learn-mode house actually keeps.

`tools/electric_learn_live.py` answers one question: does the full mode reach the asks the narrow
mode refuses. It does that with four tells and two pairs, which is enough to prove a wiring and
nowhere near enough to find a bottleneck. This asks the scale question instead: teach a real
curriculum -- 24 tells and 16 question-answer pairs (40 items, 136 probes), in three sessions, with
a restart between every session -- then ask everything back in every shape the mode claims to
handle, and count what comes out as the right sentence, the wrong sentence, one word, or silence.

THE NUMBERS, and why they are separate. A benchmark that reports "82% correct" hides the only thing
that matters, which is the SHAPE of the failures:
  retention      per ITEM, not per probe: kept = every way of asking it still gets its own tell
  correct        per probe SHAPE, at the last checkpoint -- the widenings' report card
  refusal        of the things it was NEVER told, how many it leaves alone. The number that makes
                 the other two mean anything: a mode that answers everything scores 100% on
                 retention by answering the distractors too.
  confabulation  not one number, because it is not one fault. MISATTRIBUTION is a sentence it WAS
                 told, in answer to a question it was not. ECHO is the question handed back, folded
                 or framed (`where does the bell hang` -> `where the bell hang`), and includes the
                 bare interrogative: control answers `what the dog guard` with `what`, which is the
                 question word falling out of a parse, not a fabricated fact. CROSS_ECHO is a
                 DIFFERENT question out of the remembered pool -- the pool chose the sentence, not
                 the ask. INVENTION is a sentence nobody said in any form, the only class that fails
                 this tool's exit code. ABSENCE is the licensed refusal SPEAKING (`i don't know,
                 bell was told but no place was ever told for bell`) and ENTAILED is a not-yet-taught
                 item answered correctly from a tell the house does have: neither is a failure, and
                 the first draft of this file scored both of them as inventions, which is how a
                 benchmark reports 16 confabulations in an arm that has no ELECTRIC at all. PARTIAL
                 is one word out of a tell -- a reach problem, not a truth problem.

WHAT IT MEASURED (`docs/evidence/electric_learn_bench.json`). The clean restarted house at the end
of the curriculum, 124 probes about things the house was told:
    control   0 correct  83 partial  26 echo  9 refused  6 cross-echo  0 misattrib  0 invented
    teach    39 correct  43 partial 34 refused 4 absence  3 misattrib  1 cross-echo  0 invented
    learn    79 correct   7 partial 30 refused 4 absence  3 misattrib  1 cross-echo  0 invented
  Of the 12 probes about things it was NEVER told, learn refused 11; at depth 1, where 97 of the 136
  probes ask about items it will be taught two sessions later, it refused 89, answered 4 of them
  correctly from a tell it did already have, handed a question back 3 times, and mis-answered 1. No arm said a sentence nobody said, at any depth, in any phase: the
  floor holds at scale, and the widenings bought retention (0 -> 39 -> 79) without buying false
  acceptance. **The restart itself cost nothing: probes gained on restart 0, probes lost on restart
  0, at every depth, in both ELECTRIC arms** -- every failure in this table was a failure before the
  house went down. That is the number `--electric-learn` needed, and it is a different number from
  the one the previous task was chasing: the remembered-question artifact is real, but it is not
  forgetting, and at this scale it moved one probe.

THE BOTTLENECK THIS FINDS, and `shadow()` is its proof rather than a paragraph: a `what V the N`
ask binds N to the SUBJECT slot of whichever tell carries V, so the house answers the OPPOSITE
question. `what holds the shelf` in a house told `the rope holds the shelf` is answered
`the shelf holds the lamp` as soon as that second tell is in the house -- and in a house where the
competitor is the ONLY tell, the same wrong sentence still comes back, which rules out "the tell
beat the pair" and leaves "the pair was never reached". The store holds the right answer under an
exact key in all three houses. `answer()` consults the keyed inventory one step before the store,
and the inventory returned, so the record the person taught by the protocol is dead code on the path
the protocol exists to feed. Same mechanism, one notch worse, on the distractor `what chases the
mouse`: answered `the mouse chases the dog` in both ELECTRIC arms, at every depth, in every phase --
a wrong sentence for a question nobody taught, stable enough to be a signature.

SECOND, behind it: PAIR ADMISSION. `learn_qa` admits a pair only when the answer differs from the
ask by exactly one word on each side, and the QA store inherits that test -- it is the grammar's
role-learning rule, doing store duty. 10 of 16 curriculum pairs reached the store, and 0 of the 3
whose answer sentence no tell carries, which are the only three the store is FOR. Spot check on
pairs a person would actually say: `where does the bell hang? / the bell hangs on the wall` refused
(3 missing, 3 new), `who fed the mouse? / Mira fed the mouse last night` refused (3 missing). An
answer that tells you something new is, by construction, unteachable here.

THE DESIGN TRAP, handled explicitly. Asking a question writes a row, and the previous task
established that a pool of remembered question rows changes what a narrow house answers -- so a
benchmark that probes the same house six times measures its own probing. Three defusings:
  * the state is saved BEFORE the live probe round, so the restarted house loads the taught state
    with NO probe rows in it. The restart number is retention of teaching, not of asking.
  * the restarted house is then probed a SECOND time, after its own 136 probe rows have accumulated.
    The delta between those two columns is the measurement artifact, quantified, rather than a
    finding nobody notices: in learn at depth 3 it moved exactly one probe (a refusal became an
    echo), and the 79 correct did not move at all -- so the headline number is not an artifact of
    the asking, and the asking is not free either.
  * every depth is a FRESH house (boot, teach sessions 1..d, restart). Depth 1 therefore asks about
    97 probes the house has not been taught yet, which is the largest false-acceptance sample
    available anywhere in this repo: the future curriculum, asked back before it was told.

NOTHING HERE IS A GRADER. It prints, and it writes docs/evidence/electric_learn_bench.json, and it
exits non-zero if a house says a sentence nobody said. The guarded absence contract is untouched:
this file only ever sets attributes on an instance, through tools/electric_teach_mode.py.

Run:  .venv/Scripts/python.exe tools/electric_learn_bench.py [--arms learn] [--depth 3]
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.converse as converse                    # noqa: E402
import tools.electric_teach_mode as tm               # noqa: E402
from organs.neural_language import NeuralLanguage     # noqa: E402  (qa_key / qa_paraphrase_key)

TMP = Path("_tmp/electric_learn_bench")

# MP-E9 treatment arms turned on for THIS process, parsed from --flag-on in main(). Module-level
# because boot() reads it and boot() is reached from run_arm() deep inside the harness. Empty by
# default, which is what makes a run without the flag the pre-treatment house.
FLAG_ON: set = set()
# Which arms a --flag-on treatment can actually reach. control is the untouched house and never
# carries a treatment, so if a control row moves the cause is not the flag. Hoisted out of seals()
# into a constant because D-MPE8-01 requires the same fact stated PER ARM inside each arm's own
# record: a reader looking only at arms.learn must be able to see that its zero is flag-conditional,
# which is precisely the confusion MP-E9 decision.md 7.1 registered.
FLAG_BEARING_ARMS = ("learn", "teach")
EVIDENCE = Path("docs/evidence/electric_learn_bench.json")


def svo(tell, q, subj, verb, stem, obj):
    return dict(kind="svo", tell=tell, q=q, subj=subj, verb=verb, stem=stem, obj=obj)


def obl(tell, subj, verb, stem, tail, q, prep):
    return dict(kind="obl", tell=tell, q=q, subj=subj, verb=verb, stem=stem, tail=tail, prep=prep)


def intr(tell, subj, verb, stem):
    return dict(kind="intr", tell=tell, q="what", subj=subj, verb=verb, stem=stem)


# THE CURRICULUM, three sessions. Words are introduced by the tells themselves -- the house has no
# seed vocabulary, so a probe can only ever use a word this file already taught, and a refusal can
# never be blamed on a missing noun unless the reason string says exactly that.
SESSIONS = [
    [svo("the dog bites the latch", "what", "dog", "bites", "bite", "latch"),
     svo("the mouse chases the dog", "what", "mouse", "chases", "chase", "dog"),
     svo("Nora carries the lantern", "who", "nora", "carries", "carry", "lantern"),
     intr("the copper bell rings", "copper bell", "rings", "ring"),
     obl("the lantern belongs to Mira", "lantern", "belongs", "belong", "to Mira", "who", "to"),
     svo("the key opens the door", "what", "key", "opens", "open", "door"),
     svo("the rope holds the shelf", "what", "rope", "holds", "hold", "shelf"),
     svo("the kettle warms the water", "what", "kettle", "warms", "warm", "water")],
    [svo("the dog guards the gate", "what", "dog", "guards", "guard", "gate"),
     svo("Mira feeds the mouse", "who", "mira", "feeds", "feed", "mouse"),
     obl("the bell hangs on the wall", "bell", "hangs", "hang", "on the wall", "where", "on"),
     svo("the rain fills the bucket", "what", "rain", "fills", "fill", "bucket"),
     svo("the socket powers the lamp", "what", "socket", "powers", "power", "lamp"),
     svo("the thread binds the button", "what", "thread", "binds", "bind", "button"),
     svo("the gate blocks the road", "what", "gate", "blocks", "block", "road"),
     svo("the shelf holds the lamp", "what", "shelf", "holds", "hold", "lamp")],
    [svo("the collar fits the dog", "what", "collar", "fits", "fit", "dog"),
     svo("the bridge crosses the river", "what", "bridge", "crosses", "cross", "river"),
     svo("the lamp lights the door", "what", "lamp", "lights", "light", "door"),
     svo("the net catches the mouse", "what", "net", "catches", "catch", "mouse"),
     svo("the moon pulls the tide", "what", "moon", "pulls", "pull", "tide"),
     svo("the tide floods the road", "what", "tide", "floods", "flood", "road"),
     svo("the wind wakes the dog", "what", "wind", "wakes", "wake", "dog"),
     svo("the boy mends the net", "who", "boy", "mends", "mend", "net")],
]

# Question-answer pairs, taught by the protocol (marked ask, then the answer). Most repeat a tell,
# which is the normal case -- a person asks about something they were told. The last three are
# PAIR-ONLY: nothing else in the house carries that sentence, so those three measure the QA store
# by itself, with no keyed inventory underneath it.
PAIRS = [
    [("what bites the latch?", "the dog bites the latch"),
     ("who carries the lantern?", "Nora carries the lantern"),
     ("what rings in the tower?", "the copper bell rings"),
     ("who does the lantern belong to?", "the lantern belongs to Mira"),
     ("what opens the door?", "the key opens the door")],
    [("where does the bell hang?", "the bell hangs on the wall"),
     ("what holds the shelf?", "the rope holds the shelf"),
     ("what warms the water?", "the kettle warms the water"),
     ("who feeds the mouse?", "Mira feeds the mouse"),
     ("what fills the bucket?", "the rain fills the bucket")],
    [("what powers the lamp?", "the socket powers the lamp"),
     ("what binds the button?", "the thread binds the button"),
     ("what crosses the river?", "the bridge crosses the river"),
     # pair-only: the answer is a sentence this house was never TOLD, only answered with
     ("what does Mira love most?", "she loves the lantern most"),
     ("when does the bell toll?", "it tolls at dusk"),
     ("how many dogs sleep?", "two dogs sleep")],
]

# Never taught, in every case. The first six are ROLE SWAPS and near-misses built entirely out of
# words the house knows -- if a widening reaches into a tell to answer one of these, that is the
# failure this benchmark exists to catch. The rest are question words the mode makes no claim on.
DISTRACTORS = [
    ("role_swap", "what chases the mouse", "the mouse chases the dog is the other direction"),
    ("role_swap", "who does the dog carry", "Nora carries the lantern, not the reverse"),
    ("role_swap", "what bites the bell", "no such tell"),
    ("role_swap", "who does the kettle belong to", "no such tell"),
    ("role_swap", "what floods the bridge", "the tide floods the road"),
    ("role_swap", "what crosses the dog", "no such tell"),
    ("qword", "why does the dog bite the latch", "no why path claimed"),
    ("qword", "how does the rope hold the shelf", "no how path claimed"),
    ("qword", "which bell rings", "no which path claimed"),
    ("qword", "where is the harbor", "harbor was never taught"),
    ("qword", "who mends the latch", "no such tell"),
    ("qword", "what sleeps at dusk", "answerable only by the pair-only item, and not this way"),
]


def probes_for(f):
    """Every way this fact can be asked. The answer to all of them is the tell, verbatim -- that is
    the mode's whole contract, and it is why PARTIAL (one word) is scored separately rather than
    rounded up into correct."""
    k = f["kind"]
    if k == "svo":
        yield "subject", f'{f["q"]} {f["verb"]} the {f["obj"]}'
        yield "subject_fold", f'{f["q"]} {f["stem"]} the {f["obj"]}'
        yield "object", f'what does the {f["subj"]} {f["stem"]}'
        yield "object_fold", f'what the {f["subj"]} {f["stem"]}'
    elif k == "obl":
        yield "subject", f'what {f["verb"]} {f["tail"]}'
        if f["q"] == "where":
            yield "reverse", f'where does the {f["subj"]} {f["stem"]}'
            yield "reverse_fold", f'where the {f["subj"]} {f["stem"]}'
        else:
            yield "reverse", f'who does the {f["subj"]} {f["stem"]} {f["prep"]}'
            yield "reverse_fold", f'who the {f["subj"]} {f["stem"]} {f["prep"]}'
    else:
        yield "subject", f'what {f["verb"]}'
        yield "subject_fold", f'what {f["stem"]}'


def probes_for_pair(ask, ans):
    a = ask.rstrip("?")
    yield "pair_exact", a
    # The fold the widening is named for: the auxiliary goes, the content words stay.
    yield "pair_fold", a.replace("does ", "").replace(" is ", " ").replace("does", "")


# The whole probe set, built once: (item_id, shape, ask, tell_or_None). tell is None for anything
# this file does not intend the house to answer.
def build_probes():
    out = []
    for d, facts in enumerate(SESSIONS):
        for i, f in enumerate(facts):
            iid = f"tell{d}.{i}"
            for shape, ask in probes_for(f):
                out.append((iid, shape, ask, f["tell"], d))
    for d, ps in enumerate(PAIRS):
        for i, (ask, ans) in enumerate(ps):
            iid = f"pair{d}.{i}"
            # The key the STORE would hold this pair under, computed with the organ's own key
            # function -- the same one `_qa_keep` writes with and `_qa_store_answer` reads with.
            # Without it the mechanism split below is guesswork: "key not found" and "pair never
            # admitted" are different faults with the same symptom, and only the store says which.
            PAIR_KEYS[iid] = NeuralLanguage.qa_key(ask)
            for shape, a in probes_for_pair(ask, ans):
                out.append((iid, shape, a, ans, d))
    for i, (shape, ask, _why) in enumerate(DISTRACTORS):
        out.append((f"dist{i}", shape, ask, None, 99))
    return out


PAIR_KEYS = {}
PROBES = build_probes()
# What the house is allowed to say, in total. Anything else out of its mouth is an invention.
TOLD = {f["tell"].lower() for s in SESSIONS for f in s} | {a.lower() for s in PAIRS for _q, a in s}
ALL_ITEMS = sum(len(s) for s in SESSIONS) + sum(len(s) for s in PAIRS)

# ---------------------------------------------------------------------------
# --curriculum PATH: run the bench against a committed tier manifest
# (experiments/MP-E8/curriculum_tier120.json / ..._tier300.json, authored under D-MPE8-03).
#
# This is an INSTRUMENT CHANGE, so it is built to be provably inert at tier 40 rather than assumed
# so: with no --curriculum in sys.argv, nothing below executes. The literals above remain the
# curriculum and the tier-40 proof is a row-for-row diff against armA_tier40_newenv.json.
#
# A manifest records each tell as the CONSTRUCTION CALL arm A's own builder emits --
# "svo('the dog bites the latch', 'what', 'dog', 'bites', 'bite', 'latch')" -- not as a finished
# dict. Deliberate: frames are rebuilt by the bench's own svo/obl/intr, so a tier cannot smuggle in
# a frame shape the shape arbiter has never seen. Constraint (a) of the D-MPE8-03 ruling then holds
# by construction instead of by review.
CURRICULUM = None                              # None => the module literals above (sealed tier 40)
_ALLOWED_FRAME_BUILDERS = ("svo", "obl", "intr")


def _frame_from_recorded_call(call):
    """Rebuild one tell frame from its recorded construction call.

    The call text arrives from a file, so it is parsed and whitelisted BEFORE anything runs: only a
    bare svo/obl/intr call over literals is admissible. An attribute, a subscript, a nested call, a
    keyword argument or any name outside the builders raises instead of executing. A curriculum file
    must not be an arbitrary code path wearing a data file's clothes.
    """
    node = ast.parse(call, mode="eval").body
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _ALLOWED_FRAME_BUILDERS):
        raise SystemExit(f"--curriculum: tell is not a bare {'/'.join(_ALLOWED_FRAME_BUILDERS)} "
                         f"call: {call!r}")
    if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
        raise SystemExit(f"--curriculum: tell uses keyword or starred arguments: {call!r}")
    for sub in ast.walk(node):
        if sub is not node and isinstance(sub, ast.Call):
            raise SystemExit(f"--curriculum: tell nests a call: {call!r}")
        if isinstance(sub, (ast.Attribute, ast.Subscript)):
            raise SystemExit(f"--curriculum: tell reaches into an object: {call!r}")
        if isinstance(sub, ast.Name) and sub.id not in _ALLOWED_FRAME_BUILDERS:
            raise SystemExit(f"--curriculum: tell names something outside the frame builders: "
                             f"{call!r}")
    return eval(compile(ast.Expression(body=node), "<curriculum tell>", "eval"),
                {"svo": svo, "obl": obl, "intr": intr, "__builtins__": {}}, {})


def apply_curriculum(path):
    """Replace the module-literal curriculum with a committed manifest, then rebuild everything
    derived from it (PAIR_KEYS, PROBES, TOLD, ALL_ITEMS) through the bench's own functions."""
    global CURRICULUM, SESSIONS, PAIRS, DISTRACTORS, PAIR_KEYS, PROBES, TOLD, ALL_ITEMS
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"--curriculum: no such manifest: {p}")
    raw = p.read_bytes()
    man = json.loads(raw.decode("utf-8"))
    # Re-derive the curriculum hash the way tier 40's is derived -- sha256 over the canonical
    # {sessions, pairs} form, distractors excluded -- and refuse the file if its own claim is false.
    canon = json.dumps({"sessions": [s["tell_frames"] for s in man["sessions"]],
                        "pairs": [s["qa_pairs"] for s in man["sessions"]]}, sort_keys=True)
    derived = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    if man.get("curriculum_sha256") != derived:
        raise SystemExit(f"--curriculum: {p.name} declares curriculum_sha256 "
                         f"{man.get('curriculum_sha256')} but its content hashes to {derived}. The "
                         f"manifest was edited after it was sealed.")
    sessions = [[_frame_from_recorded_call(c) for c in s["tell_frames"]] for s in man["sessions"]]
    pairs = [[tuple(q) for q in s["qa_pairs"]] for s in man["sessions"]]
    # Distractors ride outside the curriculum hash by design, and the SEALED tier-40 manifest was
    # emitted before they were recorded in it -- so tier 40 legitimately has no "distractors" key and
    # the harness's own registered set is the right fallback. For any other tier the manifest must
    # carry them: silently running tier 120 against tier 40's 12 distractors would understate the
    # refusal denominators and nobody would see it. Measured, not assumed: KeyError was what this
    # file actually did before, which is a crash where a refusal belongs.
    if "distractors" in man:
        distractors = [tuple(d) for d in man["distractors"]]
    elif man.get("tier") == 40:
        distractors = [tuple(d) for d in DISTRACTORS]
    else:
        raise SystemExit(f"--curriculum: tier {man.get('tier')} manifest carries no distractors. "
                         f"Only the sealed tier-40 file may omit them, because tier 40's are the "
                         f"harness's own registered set.")
    n_items = sum(len(s) for s in sessions) + sum(len(p) for p in pairs)
    if n_items != man["n_items"]:
        raise SystemExit(f"--curriculum: manifest says {man['n_items']} items, its sessions hold "
                         f"{n_items}.")
    if len(sessions) != 3:
        raise SystemExit(f"--curriculum: {len(sessions)} session groups, expected 3 -- the "
                         f"interference curve is defined over exactly three sessions.")
    SESSIONS, PAIRS, DISTRACTORS = sessions, pairs, distractors
    PAIR_KEYS = {}
    PROBES = build_probes()
    TOLD = {f["tell"].lower() for s in SESSIONS for f in s} | {a.lower() for s in PAIRS for _q, a in s}
    ALL_ITEMS = n_items
    # The registered probe count is enforced here, not just at emit time: if the bench's own probe
    # construction disagrees with the number registered in D-MPE8-03, the run stops.
    reg_probes = (man.get("measured") or {}).get("n_probes")
    if reg_probes is not None and reg_probes != len(PROBES):
        raise SystemExit(f"--curriculum: {p.name} registers {reg_probes} probes, arm A's own "
                         f"probes_for()/probes_for_pair() produce {len(PROBES)} from the same "
                         f"frames. One of the two is wrong and no number should be made from it.")
    CURRICULUM = {
        "mode": "manifest",
        "path": str(p).replace("\\", "/"),
        "file_sha256_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "curriculum_sha256": derived,
        "tier": man.get("tier"),
        "seed": (man.get("construction") or {}).get("seed"),
        "n_items": n_items,
        "n_probes_built_by_this_bench": len(PROBES),
        "n_probes_registered_in_manifest": reg_probes,
        "n_distractors": len(DISTRACTORS),
        "note": "frames rebuilt by this file's own svo/obl/intr from the recorded construction calls",
    }
    print(f"[bench] curriculum <- {p.name}: tier {man.get('tier')}, {n_items} items, "
          f"{len(PROBES)} probes, sha {derived[:16]}", flush=True)
    return CURRICULUM


def _literal_curriculum_identity():
    """Identity of the module-literal curriculum, hashed in the SAME canonical form a manifest uses.

    tools/mp_e8_curriculum.py parses this file's SESSIONS/PAIRS literals to produce tier 40's
    curriculum_sha256; calling it here keeps the sealed baseline comparable to the authored tiers
    instead of leaving tier 40 as the one run whose curriculum has no hash. Lazy import inside a
    try, because the tool moving must not take the sealed tier-40 path down with it -- but the
    failure is written into the artifact rather than hidden behind a None.
    """
    try:
        import mp_e8_curriculum as mc
        base = mc.load()
        return {"mode": "module_literals",
                "path": "tools/electric_learn_bench.py (SESSIONS/PAIRS/DISTRACTORS literals)",
                "curriculum_sha256": base["curriculum_sha256"], "tier": 40,
                "n_items": base["n_items"], "n_probes_built_by_this_bench": len(PROBES),
                "n_distractors": len(DISTRACTORS),
                "note": "the sealed baseline curriculum; no --curriculum was passed"}
    except Exception as exc:
        return {"mode": "module_literals", "curriculum_sha256": None,
                "hash_error": f"{type(exc).__name__}: {exc}"}


def _curriculum_arg(argv):
    for i, a in enumerate(argv):
        if a == "--curriculum":
            return argv[i + 1] if i + 1 < len(argv) else ""
    return None


# Runs at import because PROBES/TOLD/ALL_ITEMS are computed at import: a swap inside main() would
# leave the probe matrix built from the literals. Absent the flag, this branch is never entered.
#
# __main__-only, and that is a bug fix rather than a nicety: tools/mp_e8_arm_b.py takes --curriculum
# for its OWN curriculum file and imports this module to reuse classify()/probes_for(). Scanning
# sys.argv unconditionally made the bench read the IMPORTER's command line, so arm B's --curriculum
# was applied inside the bench, by the bench's rules, before arm B could validate it -- measured as
# 2 failures and 8 errors in tests/test_mp_e8_arm_b.py. An importing process must call
# apply_curriculum() itself, explicitly, and know it did.
if __name__ == "__main__":
    if "--replay" in sys.argv[1:]:
        # Set here, in the __main__ guard, so it can only ever be the person running the bench who asks for
        # replay -- never an importer, never an argument a caller can pass by accident.
        global REPLAY_REQUESTED
        REPLAY_REQUESTED = True
        print("[bench] --replay: episodic replay WILL run at each restart boundary, "
              "gain = LEARN_LR by identity, passes = the registered schedule", flush=True)
    _cur_arg = _curriculum_arg(sys.argv[1:])
    if _cur_arg is not None:
        if not _cur_arg:
            raise SystemExit("--curriculum needs a path to a committed tier manifest")
        apply_curriculum(_cur_arg)


def boot(tag, mode, root):
    """One real house, flags wired in the order serve.py uses, timing knobs set BEFORE the tells
    (set after, and which tells produced a row depends on wall-clock -- tools/electric_learn_live.py
    carries the reason)."""
    agent = converse.build(TMP / "sess" / tag, project_root=str(root))
    lang = agent.language
    if mode != "control":
        for attr in tm.BASE_ATTRS:
            setattr(lang, attr, True)
    if mode == "teach":
        tm.enable(lang)
    elif mode == "learn":
        tm.enable_learn(lang)
    # MP-E9 treatment arms, applied LAST and only to the arms that already carry the electric stack.
    # control is deliberately excluded, and this is the point PRE-1 makes about BASE: the arms must
    # differ by exactly the flags, and control is the reference that says what the house does with no
    # treatment at all. Give control the flag and the invariant "the control arm, byte for byte"
    # stops being a check on the treatment and becomes a second treatment -- 727 arbiter-head rows
    # in the pre-treatment census would move, and there would be nothing left to compare against.
    # Writing every candidate explicitly -- on or off, never absent -- is the E25 rule: a missing key
    # must not be indistinguishable from a deliberate off.
    if mode != "control":
        for attr in tm.CANDIDATE_ATTRS:
            setattr(lang, attr, attr in FLAG_ON)
    lang.exposure_enabled = False
    lang.social_drive = 1.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang.exposure_speed_s = 0.0
    lang.cortex.MIN_HEAR_INTERVAL_S = 0.0
    lang.persist = True
    return lang


def teach(lang, depth):
    """Sessions 1..depth, tells by `hear`, pairs by the elicitation protocol."""
    for d in range(depth):
        for f in SESSIONS[d]:
            lang.hear(f["tell"], speaker="you")
        for ask, ans in PAIRS[d]:
            lang.respond(ask, speaker="you")
            lang.respond(ans, speaker="you")
            lang._qa_pending = None


def probe(lang, taught_depth):
    """Ask everything. An item taught at a LATER depth is, right now, a distractor -- which is the
    free sample on purpose."""
    rows = []
    store = {str(k) for k in (lang.qa_store or {})}
    for iid, shape, ask, tell, d in PROBES:
        want = tell if (tell is not None and d < taught_depth) else None
        r = lang.answer(ask) or {}
        row = dict(item=iid, shape=shape, ask=ask,
                   own=(tell or "").lower() or None,
                   taught=(want or "").lower() or None,
                   answered=bool(r.get("answered")),
                   said=str(r.get("utterance") or "").strip(),
                   src=str(r.get("source") or ""),
                   reason=str(r.get("reason") or "")[:90])
        row["mech"] = mechanism(row, store)
        rows.append(row)
    return rows


NORM_DROP = ("does", "did", "is", "are", "was", "the", "a", "an")

# The house's own narration frame, in ONE place. `tools/word_provenance.py` imports this list rather
# than restating it, because a word-level grader that does not strip the frame first fires on all
# 23 `droso says ...` rows of the committed evidence -- 23 false aborts under R9, which makes
# "one untraceable word aborts" unusable and would read as a capability collapse.
#
# The strip is POSITIONAL (prefix only), and that is the whole distinction the says gap turns on:
# in `droso says where the bell hang` the word `says` is the frame of a report about speaking; in
# `says`, spoken as the entire answer to `what the dog guard`, there is no frame and no residue, and
# the word is the assertion. `says` is in no told sentence (measured: 61 taught content words,
# `says`/`say`/`told`/`droso` absent) and in no ask, so the positional rule flags exactly the 16
# rows and none of the 23.
REPORT_FRAMES = ("droso says ", "droso said ", "droso answers ")


def strip_report_frame(s):
    """Drop the house's narration frame when it is in frame position. Nothing else is dropped.

    `says` alone is NOT a frame -- it does not start with `droso says `, so it survives to be graded.
    """
    s = (s or "").lower().strip()
    for p in REPORT_FRAMES:
        if s.startswith(p):
            return s[len(p):]
    return s


def norm(s):
    """An ask and an answer compared on the same ground: lower, no punctuation, no report frame,
    no auxiliary or article.

    The house says `droso says where the bell hang`. With the frame left on, every echo looks like
    an invention. And WITHOUT the aux dropped, a question handed back folded does not match the
    question it came from -- `where does the bell hang` vs `where the bell hang` -- so it lands in
    CROSS_ECHO, the class reserved for a sentence the POOL chose rather than the ask. That would
    overstate the pool leak in exactly the column this benchmark is read for, so the two forms are
    one string here.

    G0-prime note: the frame list moved to REPORT_FRAMES so the word-level grader and this function
    cannot drift apart. The refactor is behaviour-preserving and is pinned as such -- `norm()` output
    is asserted byte-identical over all 3,675 rows of the committed evidence
    (tests/test_word_provenance.py). R3 freezes what a suite ASKS; this changes no question, no
    class and no threshold.
    """
    # Order preserved exactly from the pre-G0-prime implementation: lower, strip, drop a trailing
    # '?', THEN drop the frame. Reversing the last two would change the result on a string ending
    # "? " (space after the mark), because the '?' would survive into the token list.
    s = strip_report_frame((s or "").lower().strip().rstrip("?"))
    return " ".join(w for w in s.split() if w not in NORM_DROP)


ASK_NORMS = {norm(a) for _i, _s, a, _t, _d in PROBES}


QWORDS = {"what", "who", "where", "when", "why", "how", "which", "whose", "whether"}


def classify(row):
    """One of: correct / partial / refused / absence / entailed / echo / cross_echo / misattrib /
    invented.

    `taught` is None for anything this file does not expect an answer to, and for those the only
    passing classes are refused and absence. The classes that are NOT failures of truthfulness, and
    the first draft of this file scored as inventions, are the ones worth naming:

      ABSENCE    the licensed refusal speaking (`i don't know, bell was told but no place was ever
                 told for bell`). A sentence nobody told, said AS A REFUSAL. Counted apart so the
                 invention rate means fabrication. When it fires on an item whose tell IS in the
                 house, that is its own finding, and `absence_on_told` counts it.
      ECHO       handing the question back, folded or framed (`where does the bell hang` -> `where
                 the bell hang`), including the bare interrogative: control answers `what the dog
                 guard` with `what`, which is the question word falling out of the parse, not a
                 fabricated fact.
      CROSS_ECHO the same, with some OTHER question out of the remembered pool. Worse than an echo:
                 the pool, not the ask, chose the sentence.
      ENTAILED   an item not yet taught at this depth, answered with the right sentence because a
                 TELL it does have carries it. At depth 1 the future curriculum is a distractor
                 set, and a house that answers `what holds the shelf` from the rope sentence in
                 hand is not wrong -- the first version of this file called that a false
                 acceptance, which is a benchmark bug, not a capability.
      PARTIAL    one word lifted out of a tell. The shape arbiter saying `dog` where the keyed
                 inventory says `the dog bites the latch`: a reach problem, not a truth problem.

    INVENTED is a sentence nobody said in any form, and the only class that fails the exit code.
    """
    said = row["said"].lower().strip()
    want = row["taught"]
    n = norm(said)
    if row["src"] == "electric_absence":
        return "absence"
    if said and n == norm(row["ask"]):
        return "echo"
    if said and len(said.split()) == 1 and said in QWORDS:
        return "echo"
    if said and n in ASK_NORMS:
        return "cross_echo"
    if want is None:
        if not said:
            return "refused"
        if row.get("own") and said == row["own"]:
            return "entailed"
        if said in TOLD:
            return "misattrib"
        if len(said.split()) == 1:
            return "partial"
        return "invented"
    if not said:
        return "refused"
    if said == want:
        return "correct"
    if said in TOLD:
        return "misattrib"
    if len(said.split()) == 1:
        return "partial"              # the right tell or the wrong one, one word of it
    return "invented"


def reason_family(r):
    t = (r["reason"] or "").lower()
    for key, fam in (("only the asking", "ask-only"), ("asking itself", "ask-only"),
                     ("no word", "unknown-word"), ("no content", "no-content"),
                     ("nothing remembered", "nothing-matched"),
                     ("nothing he remembers has that shape", "no-shape"),
                     ("closest memory", "near-miss"),
                     ("was told but no", "absence-claim"), ("told but no", "absence-claim")):
        if key in t:
            return fam
    return t[:40] or ("answered" if r["answered"] else "empty")


MECH = ("answered", "key_shadowed", "key_found_store_silent", "pair_never_admitted",
        "paraphrase_mismatch", "fold_not_taken", "ask_not_recognized", "fallback_fragment",
        "wrong_fact_reached", "invented", "refusal_silence")


def mechanism(row, store_keys):
    """WHY this probe did not get its own sentence back, in the machinery's terms.

    `cls` says what came out; this says which part of the pipeline did not do its job, and the two
    are not the same split. A refusal is one class and four mechanisms: the pair was never admitted
    to the store (a WRITE loss, upstream of every read-path flag), it was admitted and this
    phrasing does not fold onto the stored key (a READ loss the paraphrase flag owns), it was
    admitted and does fold but the fold was not taken (the ambiguity bound, or the flag), or the
    ask was never recognised as a question at all. Only the first of those is fixed by touching the
    store's admission test, and picking the fix is exactly the question this function answers.

    Every branch is an observable recorded in the evidence -- the store's own keys, the organ's own
    key function and its own paraphrase key -- so the decomposition is reproducible from the file,
    not from a reading of the organ.
    """
    cls = classify(row)
    if cls == "correct":
        return "answered"
    ask_key = NeuralLanguage.qa_key(row["ask"])
    pair_key = PAIR_KEYS.get(row["item"])
    is_pair = pair_key is not None
    exact_in = ask_key in store_keys
    pair_in = bool(pair_key) and pair_key in store_keys
    folds = (is_pair and pair_in
             and NeuralLanguage.qa_paraphrase_key(row["ask"])
             == NeuralLanguage.qa_paraphrase_key(pair_key))
    if cls in ("partial", "echo", "cross_echo"):
        return "fallback_fragment"      # a word, or a question, came out instead of an answer
    if exact_in and cls in ("misattrib", "invented"):
        return "key_shadowed"           # the store held THIS ask, and something else spoke
    if cls == "misattrib":
        return "wrong_fact_reached"     # a sentence it was told, for a different fact
    if cls == "invented":
        return "invented"
    if exact_in:
        return "key_found_store_silent"  # the key matched and the store still said nothing
    if is_pair and not pair_in:
        return "pair_never_admitted"    # WRITE side: the lesson was heard and not kept
    if is_pair and not folds:
        return "paraphrase_mismatch"    # kept, but this phrasing is not the key and does not fold
    if is_pair and folds:
        return "fold_not_taken"         # kept, and it folds -- the read path did not use it
    if reason_family(row) in ("no-shape", "no-content", "unknown-word"):
        return "ask_not_recognized"     # never reached a question path at all
    return "refusal_silence"


# ---------------------------------------------------------------------------
# MP-E10 B.4 step 2: episodic replay at the restart boundary. DEFAULT OFF, and off is not a value that
# happens to behave like the old code -- the flag is read at ONE place, inside run_arm, and when it is False
# no line of the replay path executes at all. Same shape as --curriculum above (:264-269): "with no
# --curriculum in sys.argv, nothing below executes".
#
# It is a module constant rather than an argument because tools/mp_e8_arm_b.py imports this bench and calls
# run_arm() directly; an added keyword would let an importer pass replay=True by accident, and a sys.argv scan
# inside run_arm is the exact bug documented at :411-413 (the bench once read the IMPORTER's command line).
# An importer therefore gets the unwired path, which is what it has always got.
# ---------------------------------------------------------------------------
REPLAY_REQUESTED = False
REPLAY_PASSES = None          # None -> the organ's registered REPLAY_PASSES_PER_TIER (2)


def run_arm(mode, depths):
    """One arm, every depth, in a fresh house each time. Returns {depth: {phase: rows}} plus the
    wiring facts a reader needs to distrust or trust the numbers."""
    root = TMP / "root" / mode
    res = {"mode": mode, "depths": {}, "runs": []}
    t0 = time.time()
    for depth in depths:
        tag = f"{mode}-d{depth}"
        for p in (root, TMP / "sess" / tag):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        (root / "state").mkdir(parents=True, exist_ok=True)
        lang = boot(tag, mode, root)
        teach(lang, depth)
        # SAVE FIRST. Everything the live probe round writes after this line stays in RAM, so the
        # restarted house loads the taught state with no question rows in it.
        sv = lang.save_state(force=True)
        live = probe(lang, depth)
        sdir = TMP / "sess" / tag
        for f in sdir.iterdir():
            if f.is_file():
                shutil.copy2(f, root / "state" / f.name)
        lang2 = boot(tag, mode, root)
        loaded = lang2.load_state() or {}
        # ---- THE RESTART BOUNDARY. Registered as the place replay runs (interference_protocol_step2 /
        # replay_gain_ruling.2): three sessions per tier with a real restart between them, replay at the
        # boundaries, 2 passes, gain = LEARN_LR by identity, guard live per pass.
        #
        # This bench restarts ONCE per depth (save -> boot -> load), not twice, so the two registered passes
        # run at the one boundary this instrument has. That discrepancy is recorded in the artifact rather
        # than smoothed over, because "the schedule was executed as registered" is a claim about the
        # instrument, not about the plan.
        replay_report = None
        if REPLAY_REQUESTED:
            seq = getattr(lang2, "sequence", None)
            if seq is None or not hasattr(seq, "replay_tier"):
                # Loud, not silent: a run that skipped replay and still called itself a replay run is the
                # substitution every ledger in this project was built to refuse.
                raise SystemExit(f"--replay: the house at {tag} carries no replay entry on its sequence "
                                 f"organ (sequence={seq!r}); refusing to report a replay run that replayed "
                                 f"nothing")
            replay_report = seq.replay_tier(passes=REPLAY_PASSES)
            if replay_report["void_for_H3"]:
                print(f"  [{mode:7}] depth {depth}: REPLAY CEILING-LIMITED -> void for H3 "
                      f"({replay_report['reason_void']})", flush=True)
        restarted = probe(lang2, depth)     # clean: never asked anything
        reasked = probe(lang2, depth)       # same house, second pass, its own rows now in the pool
        # THE TEACHING CHANNEL, counted separately from the answering channel. A pair that never
        # reaches the store was not forgotten by a restart -- it was never learned, and no widening
        # downstream can reach a record that was not written. `pair_only` is the sharp subset: pairs
        # whose ANSWER sentence no tell in this house carries, so the store is the only place that
        # sentence could possibly live.
        told_now = {f["tell"].lower() for dd in range(depth) for f in SESSIONS[dd]}
        kept_keys = {str(k).lower() for k in (lang2.qa_store or {})}
        taught_pairs = [p for dd in range(depth) for p in PAIRS[dd]]
        pair_only = [(a, ans) for a, ans in taught_pairs if ans.lower() not in told_now]
        res["runs"].append(dict(depth=depth,
                                flags=sorted(a for a, v in tm.state(lang2).items() if v),
                                save=sorted(str(k) for k in (sv or {})),
                                loaded=bool(loaded.get("loaded")),
                                rows=len(lang2.cortex.binder.meta),
                                inventory=sum(len(v) for v in
                                              (lang2._taught_says or {}).values()),
                                qa=len(getattr(lang2, "qa_store", {}) or {}),
                                qa_keys=sorted(kept_keys),
                                pairs_taught=len(taught_pairs),
                                pairs_in_store=sum(1 for a, _ in taught_pairs
                                                   if a.lower().rstrip("?") in kept_keys),
                                pair_only=len(pair_only),
                                pair_only_in_store=sum(1 for a, _ in pair_only
                                                       if a.lower().rstrip("?") in kept_keys),
                                pair_only_lost=[a for a, _ in pair_only
                                                if a.lower().rstrip("?") not in kept_keys]))
        # Recorded only when replay was asked for. An always-present key would make the OFF path write a
        # different artifact from the run it is being compared against, and "byte-identical when off" has to
        # mean the artifact too, not just the answers.
        if replay_report is not None:
            res["runs"][-1]["replay"] = replay_report
        res["depths"][depth] = {"live": live, "restarted": restarted, "reasked": reasked}
        print(f"  [{mode:7}] depth {depth}: rows={res['runs'][-1]['rows']} "
              f"inv={res['runs'][-1]['inventory']} "
              f"pairs={res['runs'][-1]['pairs_in_store']}/{res['runs'][-1]['pairs_taught']} "
              f"correct={sum(1 for r in restarted if classify(r) == 'correct')}"
              f"/{sum(1 for r in restarted if r['taught'])} "
              f"invented={sum(1 for r in restarted if classify(r) == 'invented')}", flush=True)
    res["seconds"] = round(time.time() - t0, 1)
    return res


def tally(rows):
    c = {}
    for r in rows:
        c[classify(r)] = c.get(classify(r), 0) + 1
    return c


def by_shape(rows):
    out = {}
    for r in rows:
        d = out.setdefault(r["shape"], {"n": 0, "correct": 0, "partial": 0, "refused": 0,
                                        "absence": 0, "entailed": 0, "misattrib": 0,
                                        "echo": 0, "cross_echo": 0, "invented": 0})
        d["n"] += 1
        d[classify(r)] += 1
    return out


def retention(rows):
    """Per ITEM (not per probe): kept = every probe for it answered with its own tell; part = some;
    lost = none. An item with no probes taught yet is not counted."""
    per = {}
    for r in rows:
        if not r["taught"]:
            continue
        d = per.setdefault(r["item"], dict(kept=0, n=0))
        d["n"] += 1
        d["kept"] += classify(r) == "correct"
    kept = sum(1 for v in per.values() if v["kept"] == v["n"])
    part = sum(1 for v in per.values() if 0 < v["kept"] < v["n"])
    lost = sum(1 for v in per.values() if v["kept"] == 0)
    return dict(items=len(per), kept=kept, part=part, lost=lost,
                probes=sum(v["n"] for v in per.values()),
                probes_correct=sum(v["kept"] for v in per.values()))


def shadow():
    """THE MECHANISM, three houses and one ask, so the bottleneck claim is a reproducible sub-experiment
    of this file rather than something a temp script once printed.

    The ask is `what holds the shelf`, and the house is taught the pair that answers it. House A has
    one tell. House B has that tell PLUS `the shelf holds the lamp`, a sentence about a different
    thing. House C has only the competitor -- so the rope sentence exists in C nowhere but the pair.

    A answers correctly. B answers `the shelf holds the lamp`, which is the answer to `what does the
    shelf hold`: the noun the person asked ABOUT was bound to the subject slot of a tell it only
    ever sat in the object slot of. C answers the same way as B, which rules out the tell being
    preferred over the pair -- the pair is simply never reached, and in C the pair is the ONLY place
    the right sentence is. The store is consulted one step after the inventory in `answer()`, and the
    inventory returned, so the exact key `what holds the shelf` -> `the rope holds the shelf` that
    all three houses hold is dead code on this path.
    """
    SH_ASK = "what holds the shelf"
    SH_PAIR = [("what holds the shelf?", "the rope holds the shelf")]
    houses = (("A_pair_and_its_own_tell", ["the rope holds the shelf"]),
              ("B_plus_a_competing_tell", ["the rope holds the shelf", "the shelf holds the lamp"]),
              ("C_competing_tell_only", ["the shelf holds the lamp"]))
    out = []
    for tag, tells in houses:
        root = TMP / "root" / f"shadow-{tag}"
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        (root / "state").mkdir(parents=True, exist_ok=True)
        lang = boot(tag, "learn", root)
        for t in tells:
            lang.hear(t, speaker="you")
        for q, a in SH_PAIR:
            lang.respond(q, speaker="you")
            lang.respond(a, speaker="you")
            lang._qa_pending = None
        r = lang.answer(SH_ASK) or {}
        s = lang._qa_store_answer(SH_ASK) or {}
        out.append(dict(house=tag, tells=tells, ask=SH_ASK,
                        said=str(r.get("utterance") or "").strip(),
                        src=str(r.get("source") or ""),
                        store_holds=str(s.get("utterance") or "").strip()))
        print(f"  [shadow {tag[:1]}] tells={len(tells)} -> {out[-1]['said']!r} "
              f"(src={out[-1]['src']})  while the store holds {out[-1]['store_holds']!r}", flush=True)
    out.append(dict(flipped=out[0]["said"] != out[1]["said"],
                    right_in_store=all(o["store_holds"] == "the rope holds the shelf" for o in out[:3])))
    return out


CLS = ("correct", "partial", "refused", "absence", "entailed", "echo", "cross_echo",
       "misattrib", "invented")


def report(res):
    """One arm, the deepest depth, the CLEAN restarted house -- the column that measures teaching
    rather than probing. Everything else in this file exists to make this table trustworthy."""
    depth = max(res["depths"])
    rows = res["depths"][depth]["restarted"]
    print(f"\n[report] {res['mode']} at depth {depth}: a house that has been restarted and never "
          f"asked anything", flush=True)
    print("   shape             n  " + "  ".join(f"{c[:6]:>6}" for c in CLS))
    for shape, d in sorted(by_shape(rows).items()):
        print(f"   {shape:<16}{d['n']:>3}  " + "  ".join(f"{d.get(c, 0):>6}" for c in CLS))
    for tag, sub in (("taught  ", [r for r in rows if r["taught"]]),
                     ("untaught", [r for r in rows if not r["taught"]])):
        t = tally(sub)
        print(f"   {tag} ({len(sub):>3} probes): " +
              "  ".join(f"{c}={t.get(c, 0)}" for c in CLS if t.get(c, 0)))
    for label, sub in (("taught probes", rows),
                       ("QA-store probes", [r for r in rows if r["item"].startswith("pair")])):
        sub = [r for r in sub if r["taught"]]
        mq = {}
        for r in sub:
            mq[r["mech"]] = mq.get(r["mech"], 0) + 1
        order = sorted((k for k in mq if k != "answered"), key=lambda k: -mq[k])
        print(f"   mechanism, {label} ({len(sub)}): answered={mq.get('answered', 0)}  "
              + "  ".join(f"{k}={mq[k]}" for k in order))
    ret = retention(rows)
    print(f"   items: {ret['items']} asked about, {ret['kept']} kept on EVERY probe, "
          f"{ret['part']} part, {ret['lost']} lost -- probes correct "
          f"{ret['probes_correct']}/{ret['probes']}")
    per = {}
    for r in rows:
        if r["taught"]:
            per.setdefault(r["item"], []).append(classify(r))
    lost = sorted(i for i, cl in per.items() if "correct" not in cl)
    print(f"   items with no correct probe at all: {len(lost)} {lost}")
    rec = [x for x in res["runs"] if x["depth"] == depth][-1]
    print(f"   teaching channel: {rec['pairs_in_store']}/{rec['pairs_taught']} taught pairs are in "
          f"the store; of the {rec['pair_only']} whose answer NO tell carries, "
          f"{rec['pair_only_in_store']} reached it -- lost: {rec['pair_only_lost']}")
    fa = sorted({r["ask"] for r in rows if classify(r) == "absence" and r["taught"]})
    print(f"   licensed refusal spoken where the tell IS in the house: {len(fa)} {fa}")
    reasons = {}
    for r in rows:
        if classify(r) in ("refused", "partial", "echo", "cross_echo"):
            f = reason_family(r)
            reasons[f] = reasons.get(f, 0) + 1
    print("   why it did not answer: " + ", ".join(
        f"{k}={v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]))
    a = tally(res["depths"][depth]["restarted"])
    b = tally(res["depths"][depth]["reasked"])
    print("   the probing artifact (restarted -> reasked): " +
          ", ".join(f"{c} {a.get(c, 0)}->{b.get(c, 0)}" for c in CLS))


def torch_version():
    """torch imported lazily: this harness ran for the whole of MP-E9 without it, and a top-level
    import would make every arm-A run depend on a package only arm B needs."""
    try:
        import torch
        return torch
    except Exception:
        return None


def torch_threads():
    t = torch_version()
    return None if t is None else t.get_num_threads()


def torch_build_info():
    """Version alone does not identify a build: the +cpu wheel and a cu12x wheel of the same version
    are different machines, and H4's cost claim depends on telling them apart. Returns plain values
    only -- getattr(torch, "cuda") is the cuda MODULE and is not JSON-serializable, which is the first
    version of this function and it killed the run at the write step, eight minutes in."""
    t = torch_version()
    if t is None:
        return None
    return {"version": t.__version__,
            "cuda_version": t.version.cuda,
            "cuda_available": bool(t.cuda.is_available()),
            "threads": t.get_num_threads()}


def _requirements_pinned():
    """True only if every named line in requirements.txt carries an exact version."""
    try:
        req = Path(__file__).resolve().parents[1] / "requirements.txt"
        named = [x.strip() for x in req.read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.strip().startswith("#")]
        return bool(named) and all("==" in x for x in named)
    except Exception:
        return False


def arm_flag_provenance(mode):
    """The flag state of ONE arm, written inside that arm's own record (D-MPE8-01, condition 1).

    The run-level block already says which flags were passed. It does not survive being read alone:
    someone quoting arms.learn.learn_correct_live out of a file has no flag information next to the
    number. MP-E9 decision.md 7.1 is the case study -- a proven flag-conditional zero, if it travels
    without its condition, gets read as a property of the organism.
    """
    reaches = mode in FLAG_BEARING_ARMS
    return {
        "flags": {a: bool(a in FLAG_ON) for a in tm.CANDIDATE_ATTRS},
        "flags_reach_this_arm": reaches,
        "flag_state_meaning": (
            "these flags were passed on this arm's configuration" if reaches else
            "this arm carries no treatment: a change in its rows is not attributable to a flag"),
        "zero_is_flag_conditional": bool(reaches and any(FLAG_ON)),
        "read_this_before_quoting_any_number_from_this_arm": (
            "a flag-conditional 0 is a property of THIS configuration, not of the shipped organism; "
            "the shipped house runs none of these flags -- see experiments/MP-E9/decision.md 7.1"),
    }


def seals(argv):
    """Per-run provenance, in the shape the battery's journals already use: git, interpreter,
    harness. G0-prime cannot close on unsealed bench rows -- the plan's own standard is that every
    journal row can be re-derived or discarded on the strength of its seals.

    Additive only. No existing key of the evidence schema is renamed or removed, so every row
    published before this change still verifies against its own record -- the same rule the repo
    applied when it put `cause` beside `stage` instead of rewriting `stage`.
    """
    import hashlib
    import os
    import platform
    import subprocess

    def git(*a):
        try:
            return subprocess.run(["git", *a], capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except Exception:
            return ""

    def pkg(name):
        try:
            return __import__(name).__version__
        except Exception:
            return None

    here = os.path.abspath(__file__)
    return {
        "git_head": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "interpreter": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        # sysconfig.get_paths()["environment"] was the first attempt and it raised KeyError on this
        # venv -- get_paths() here exposes data/include/platinclude/platlib/platstdlib/purelib/
        # scripts/stdlib and no 'environment'. A seal field that can kill an eight-minute measurement
        # is worse than a seal field that is one level coarser, so the prefix is recorded directly:
        # prefix != base_prefix is exactly the fact "this ran in a virtualenv".
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "in_venv": sys.prefix != sys.base_prefix,
        "platform": platform.platform(),
        # torch is in the list because D-MPE8-02 put it in the environment: H4 compares arm A's cost
        # against arm B's "on identical hardware", and that has to mean identical software too, so a
        # cost row that cannot say which torch (if any) was loaded is not comparable. pkg() returns
        # None when the package is absent, so an arm-A-only environment records torch: null rather
        # than omitting the key.
        "packages": {p: pkg(p) for p in ("numpy", "pandas", "scipy", "psutil", "pytest", "pyarrow",
                                         "torch")},
        # The +cpu build and the cu12x build of the same version are different machines. Recording the
        # version alone would let a GPU run and a CPU run claim the same environment.
        "torch_build": torch_build_info(),
        # Derived, not asserted. requirements.txt was unpinned for every number published before
        # D-MPE8-02; a hardcoded False would now be a lie and a hardcoded True would be worse.
        "requirements_pinned": _requirements_pinned(),
        "harness": os.path.relpath(here, os.getcwd()).replace("\\", "/"),
        "harness_sha256": hashlib.sha256(open(here, "rb").read()).hexdigest(),
        "argv": list(argv),
        # Which treatment arms this artifact was produced with, stated by the artifact rather than
        # inferred from the filename. Every candidate is written, on or off, so an absent key is
        # never read as a deliberate off -- and the flag-OFF reproduction test reads this field to
        # prove the census it pins has no treatment in it.
        "electric_flags": {a: bool(a in FLAG_ON) for a in tm.CANDIDATE_ATTRS},
        # Which arms the flags above actually reach. control never carries a treatment arm, so an
        # artifact whose control rows moved is describing something other than the flag.
        "electric_flags_apply_to": list(FLAG_BEARING_ARMS),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    args = sys.argv[1:]
    modes = ["control", "teach", "learn"]
    if "--arms" in args:
        modes = args[args.index("--arms") + 1].split(",")
    depths = [1, 2, 3]
    if "--depth" in args:
        depths = [int(args[args.index("--depth") + 1])]
    # --out: a clone run must not clobber the committed baseline. The default is unchanged, so the
    # shipped command in docs/HANDOVER.md still writes docs/evidence/electric_learn_bench.json.
    out_path = EVIDENCE
    if "--out" in args:
        out_path = Path(args[args.index("--out") + 1])
    # --flag-on ATTR[,ATTR]: opt into an MP-E9 treatment arm. The name is validated against
    # tools/electric_teach_mode.CANDIDATE_ATTRS, because an unrecognised name would otherwise
    # produce exactly the thing this whole gate exists to prevent: an ordinary pre-treatment run
    # that believes itself a treatment run, and a typo that costs eight minutes to discover.
    global FLAG_ON
    FLAG_ON = set()
    if "--flag-on" in args:
        for name in args[args.index("--flag-on") + 1].split(","):
            name = name.strip()
            if not name:
                continue
            attr = name.upper().replace("-", "_")
            if attr not in tm.CANDIDATE_ATTRS:
                raise SystemExit(f"--flag-on: {name!r} is not a registered treatment arm. "
                                 f"Known: {', '.join(tm.CANDIDATE_ATTRS)}")
            FLAG_ON.add(attr)
    write = "--no-write" not in args
    # --workdir: the scratch tree this run teaches into. It defaults to the shipped path, but two
    # runs sharing it would rmtree each other's session state -- which is exactly the failure mode a
    # noise-floor clone run must not have, because a clone that lost its own taught state would still
    # print a clean number. The runner gives every clone its own.
    global TMP
    if "--workdir" in args:
        TMP = Path(args[args.index("--workdir") + 1])
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    print(f"[bench] {ALL_ITEMS} items, {len(PROBES)} probes, depths {depths}, arms {modes}",
          flush=True)
    arms = {}
    for m in modes:
        arms[m] = run_arm(m, depths)

    # The floor this whole thing stands on: a house may not say a sentence nobody said, at any
    # depth, in any phase, in any arm. Everything else on this page is a rate.
    fails = []
    for m, res in arms.items():
        for run in res["runs"]:
            if not run["loaded"]:
                fails.append(f"{m}/d{run['depth']}: the restarted house loaded no state -- its "
                             f"retention number is a boot number, not a memory number")
        for depth, ph in res["depths"].items():
            for phase, rows in ph.items():
                for r in rows:
                    if classify(r) == "invented":
                        fails.append(f"{m}/d{depth}/{phase}/{r['item']}/{r['shape']}: "
                                     f"{r['ask']!r} -> {r['said']!r} (nobody said that)")

    summary = {}
    for m, res in arms.items():
        summary[m] = {}
        for depth, ph in res["depths"].items():
            summary[m][depth] = {p: dict(tally(ph[p]),
                                         retention=retention(ph[p]),
                                         by_shape=by_shape(ph[p]))
                                 for p in ph}
    sh = shadow() if "learn" in arms else []
    if sh:
        v = sh[-1]
        print(f"[shadow] one more tell in the house changed the answer to a question the person "
              f"explicitly taught: {v['flipped']}; the store held the right sentence in every "
              f"house: {v['right_in_store']}", flush=True)
    for m in arms:
        report(arms[m])
    last = {m: {p: summary[m][max(summary[m])][p] for p in ("live", "restarted", "reasked")}
            for m in summary}
    print(json.dumps(last, indent=1, sort_keys=True), flush=True)

    out = dict(shadow=sh,
               arms={m: dict(seconds=r["seconds"], runs=r["runs"],
                             arm_provenance=arm_flag_provenance(m),
                             probes={str(d): {p: [dict(x, cls=classify(x)) for x in rows]
                                              for p, rows in ph.items()}
                                     for d, ph in r["depths"].items()})
                          for m, r in arms.items()},
               items=ALL_ITEMS, probes=len(PROBES), told=sorted(TOLD),
               # `told` is the set of sentences the house was TOLD. A taught QA pair's QUESTION side
               # is also taught material -- the teacher said it out loud -- but it is not a sentence
               # the house may answer with, so it never entered TOLD. G0-prime found that a word-level
               # provenance grader reading only `told` fires on `tower`, a word from the taught pair
               # `what rings in the tower? / the copper bell rings`. Additive field, so the artifact is
               # self-describing instead of depending on a reader importing PAIRS.
               # Which curriculum this artifact stands on, recorded rather than inferred. With a
               # --curriculum manifest this is the manifest's own identity; without one it is the
               # literal tier-40 baseline, hashed by the same canonical form tools/mp_e8_curriculum.py
               # uses so a tier-40 artifact and a tier-120 artifact carry comparable curriculum hashes.
               # A failed hash is recorded as a failure, not papered over with a None.
               curriculum=CURRICULUM or _literal_curriculum_identity(),
               taught_questions=sorted({q.lower() for s in PAIRS for q, _a in s}),
               distractors=[d[1] for d in DISTRACTORS],
               summary={m: {str(d): s for d, s in sum_.items()} for m, sum_ in summary.items()},
               failures=fails,
               provenance=seals(args))
    if not write:
        print("[bench] --no-write: nothing written", flush=True)
        return 1 if fails else 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"[bench] evidence -> {out_path}", flush=True)
    if fails:
        print(f"[bench] {len(fails)} INVENTIONS (a sentence nobody said):", flush=True)
        for f in fails[:30]:
            print("   - " + f, flush=True)
        return 1
    print("[bench] no invention in any arm at any depth", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
