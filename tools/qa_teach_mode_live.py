"""LIVE-HOUSE check for `--electric-teach`: one switch, the real Droso, two pairs taught in chat,
a real restart, a paraphrase asked of each, and an ask nobody taught -- which must still be
refused.

Run:  .venv\\Scripts\\python.exe tools/qa_teach_mode_live.py

Three arms, because the claim a bundle flag has to answer is not one but three:

  T0  BASE only -- ELECTRIC_TEACH / ELECTRIC_ANSWER / ABSENCE_INVENTORY, which is what plain
      `--electric` means today. The control for "does the mode do anything at all".
  T1  `--electric-teach`, applied through tools/electric_teach_mode.enable() -- the shipped
      code path, not a copy of it.
  T2  the seven flags spelled out one by one, as the CLI documents them, WITHOUT reading the
      module's table.

T1 vs T2 is the bundle's own claim: a single switch must be the LIST, not a new configuration
nobody measured. Their rows, store keys and every probe reply are compared byte for byte,
before and after a restart. T0 is the arm that shows what the mode buys: it holds the same
tells and the same conversation and forms no pair at all.

What has to hold, and is asserted:

  * the mode turns on exactly the stack and the base, and NOTHING ELSE -- the four switches
    that widen which asks reach which matchers (shape, reverse, object role, ask-normalize)
    stay off, so a run that costs something can still say which one cost it;
  * teaching works: the ask is held, the next sentence from the same speaker pairs with it,
    and the pair is a CONVERSATION pair (the only kind the fold may reach);
  * the exact ask and the paraphrases of it answer from the store, with the line the person
    gave and the evidence named; T0 answers none of them from a store it never filled;
  * a phrasing that is NOT the pair's (word order, an added content word) is not answered
    from the store in any arm;
  * an ask nobody taught is not answered from the store in any arm, is never answered with
    its own text, and the leak count does not rise -- the mode's own admissibility and
    fragment guard are the two switches that keep that true, which is why they are in it;
  * the guard still refuses, from `electric_absence`, with the same words in every arm: the
    bundle changes nothing about the graded absence path;
  * probing teaches nothing: the pair count after the probes is the count before them;
  * after a real restart the pair is still there, the paraphrases still answer, and the held
    ask is GONE -- a question from a previous life must not pair with an unrelated sentence
    in this one.

And one thing that does NOT hold, asserted as broken on purpose so it stays visible (section 6):
a question the house cannot classify is HEARD as a statement, and `_absence_note` files its
frame in `_taught_says`, the one store that answers before the QA store does. The filing happens
in every arm. Being CAUGHT by it happens only in a house that has since learned the word -- which
is the mode, in its one-pair state, where it repeats the person's own question back at them. The
second elicited pair earns the word and closes it. Not fixed here: the repair is a narrowing at a
write site the graded E24 work owns, and `question_shape` mis-fires on relative clauses, where
declining the write would silently lose a fact.

Writes docs/evidence/qa_teach_mode_live.json.
"""
import importlib.util as _u
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.converse as converse                       # noqa: E402
import tools.electric_teach_mode as tm                  # noqa: E402
import tools.qa_elicit_live as q                        # noqa: E402

q.TMP = Path("_tmp/qa_teach_mode_live")   # not the committed tools' scratch dir

# The seven, spelled out the way the CLI documents them. Deliberately NOT read from the
# module: T2 exists to compare against it, and a comparison that reads the same table proves
# nothing.
HAND_LIST = ("ELECTRIC_QA_STORE", "ELECTRIC_QA_ELICIT", "ELECTRIC_QA_PARAPHRASE",
             "ELECTRIC_QA_PROVENANCE", "ELECTRIC_ASK_MARKS",
             "ELECTRIC_ASK_ADMISSIBILITY", "ELECTRIC_FRAGMENT_GUARD")

ARMS = (("T0", "base only -- what plain --electric means today", "base"),
        ("T1", "--electric-teach", "mode"),
        ("T2", "the seven flags set one by one", "hand"))

# Two taught pairs, both starting with `what`, and the second one is not decoration: an ask
# reaches answer() by ROUTE (3) (the record) or by `is_interrogative` (the learned word), and
# the word needs two role votes. Two elicited `what` pairs earn them, which is what stops a
# THIRD phrasing of the same question -- one the store holds no pair for -- from being heard as
# a statement and filed as a tell. Measured at the bottom of this file, in both arms.
PAIRS = [("what rings the bell?", "the copper bell rings"),
         ("what holds the door?", "the latch holds the door")]
CONV = [u for pair in PAIRS for u in pair]
PAIR_KEY = PAIRS[0][0].rstrip("?").strip()
PAIR_ANSWER = PAIRS[0][1]
PAIR2_KEY = PAIRS[1][0].rstrip("?").strip()
PAIR2_ANSWER = PAIRS[1][1]

# Told the lantern BELONGS to Mira, never told where it is: the relation whose absence this
# house is licensed to admit. (NOT the scarf -- the tells say where the scarf is, so refusing
# that ask would itself be the bug.)
GUARD_ASK = "where did i say the lantern is?"

# (what is asked, kind, the line the store should give back -- None means it must say nothing)
PROBES = [
    (PAIR_KEY, "exact", PAIR_ANSWER),
    ("what ring the bell", "folded", PAIR_ANSWER),
    ("what is ringing the bell", "folded", PAIR_ANSWER),
    (PAIR_KEY + "?", "exact_marked", PAIR_ANSWER),
    (PAIR2_KEY, "exact", PAIR2_ANSWER),
    ("what hold the door", "folded", PAIR2_ANSWER),
    ("what rings the bell twice", "refused", None),      # a content word added
    ("who droso carries", "refused", None),              # word order
    ("where is the moon", "unpaired", None),
    ("what bites the latch", "unpaired", None),
    ("who carries the droso", "unpaired", None),
    ("is the kettle warm?", "unpaired", None),
    (GUARD_ASK, "guard_chat", None),
]


def apply_arm(lang, arm):
    """The arm's flag policy, on the INSTANCE. T1 goes through the shipped function."""
    if arm == "mode":
        tm.enable(lang)
    elif arm == "hand":
        for attr in HAND_LIST + tm.BASE_ATTRS:
            setattr(lang, attr, True)


def boot(arm, tag, root):
    """One real house, wired the way tools/serve.py wires it, in the same order."""
    agent = converse.build(q.TMP / "sess" / tag, project_root=str(root))
    lang = agent.language
    for attr in tm.BASE_ATTRS:          # --electric is implied by every arm, T0 included
        setattr(lang, attr, True)
    apply_arm(lang, arm)
    # Timing knobs BEFORE the tells: a row that depends on wall-clock makes the arms differ
    # for a reason that has nothing to do with the flag (measured, the hard way, in the
    # committed elicitation tool).
    lang.exposure_enabled = False
    lang.social_drive = 1.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang.exposure_speed_s = 0.0
    lang.cortex.MIN_HEAR_INTERVAL_S = 0.0
    for t in q._m.TELLS:
        lang.hear(t, speaker="you")
    return lang


def fresh(arm, tag, conv=None):
    root = q.TMP / "root" / tag
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    (root / "state").mkdir(parents=True)
    sess = q.TMP / "sess" / tag
    if sess.exists():
        shutil.rmtree(sess, ignore_errors=True)
    lang = boot(arm, tag, root)
    for u in (CONV if conv is None else conv):
        lang.respond(u, speaker="you")
    lang._house_root = root
    lang._house_tag = tag
    return lang


def restart(arm, tag):
    sdir, root = q.TMP / "sess" / tag, q.TMP / "root" / tag
    sv = (sdir / "language_state.json").exists()
    for f in sdir.iterdir():
        if f.is_file():
            shutil.copy2(f, root / "state" / f.name)
    lang = boot(arm, tag, root)
    print(f"      [restart saved={sv}  rows={len(lang.cortex.binder.meta)} "
          f"pairs={len(lang.qa_store)} conv={len(q.conv_keys(lang))}]", flush=True)
    return lang


def probe(lang, leak_keys):
    """Every ask goes through `respond`, the door a chat turn actually uses."""
    out = {}
    for text, kind, expect in PROBES:
        r = lang.respond(text, speaker="you") or {}
        lang._qa_pending = None        # probes are independent questions, not a dialogue
        said = str(r.get("utterance") or r.get("response") or "").strip()[:70]
        src = str(r.get("source") or "")
        out[text] = {"kind": kind, "expect": expect,
                     "spoken": bool(r.get("spoken")), "said": said,
                     "src": src, "evidence": str(r.get("ask_evidence") or ""),
                     "from_store": src == "electric_qa_store",
                     "refused": bool(r.get("licensed_refusal")),
                     "reason": str(r.get("reason") or "")[:60],
                     "leaked": bool(r.get("spoken")) and said in leak_keys}
    return out


def guard_probe(lang):
    """The admitted ignorance, measured through `answer()`, the way the committed elicitation
    and paraphrase checks measure it -- and that is not laziness, it is a finding. The licence
    to ADMIT an absence lives behind answer(), and this shadow house boots with no learned word
    patterns at all (its state dir is empty), so `respond()` reaches answer() for an ask only by
    the routes the stack itself opens: the RECORD (the store holds a pair for that key) or a
    question word it has EARNED. Two elicited `what` pairs earn `what`; nothing here earns
    `where`, and GUARD_ASK is a `where` ask, so through the chat door it falls through to the
    resonance path and the house says nothing, `heard; no language learned yet` -- which is why
    the door is asserted separately, below: an untaught ask is never answered from a pair, never
    echoed, never a fragment. In the real tree, with 11,555 words loaded, `where` is learned and
    the same ask reaches the licence directly."""
    r = lang.answer(GUARD_ASK, speaker="you") or {}
    r = r if isinstance(r, dict) else {"response": r}
    return {"spoken": bool(r.get("spoken")),
            "said": str(r.get("utterance") or r.get("response") or "").strip()[:70],
            "src": str(r.get("source") or ""),
            "refused": bool(r.get("licensed_refusal")),
            "reason": str(r.get("reason") or "")[:60]}


def flag_state(lang):
    return {attr: bool(getattr(lang, attr, False)) for attr in tm.ALL_ATTRS}


# The hole this check found, and which this check does NOT fix. `ask` is a phrasing no pair
# covers; it is asked, gets no answer, and then the REAL pair is asked again.
HOLE_ASK = "what rings the bell twice"


def hole(arm, pairs, tag):
    """How many elicited pairs does a house need before an unanswerable question stops being
    filed as a tell? Measured in BOTH arms, because the claim that the mode caused it is false
    and the claim that the mode fixes it is also false."""
    lang = fresh(arm, tag, CONV[:2 * pairs])
    rec = {"arm": arm, "pairs": pairs,
           "votes_for_what": dict(lang.question_roles.get("what") or {}),
           "min_votes": lang.INTERROGATIVE_MIN_VOTES,
           "what_is_a_question_word": lang.is_interrogative("what")}
    lang.respond(HOLE_ASK, speaker="you")
    lang._qa_pending = None
    # The write site is `_absence_note` (neural_language.py:5365): a tell whose words yield a
    # frame is filed under that frame's subject, and a question's words do yield a frame.
    rec["question_filed_as_tell"] = "rings" in lang._taught_says
    r = lang.respond(PAIR_KEY, speaker="you") or {}
    lang._qa_pending = None
    said = str(r.get("utterance") or r.get("response") or "").strip()
    rec.update({"said": said[:60], "src": str(r.get("source") or ""),
                "polluted": said == HOLE_ASK,
                "answered_from_store": str(r.get("source")) == "electric_qa_store"})
    print(f"      [{arm}, {pairs} pair{'s' if pairs != 1 else ''}] "
          f"votes={rec['votes_for_what']}/{rec['min_votes']} "
          f"question_word={rec['what_is_a_question_word']} "
          f"filed_as_tell={rec['question_filed_as_tell']} -> asked {PAIR_KEY!r} and it said "
          f"{said[:40]!r} ({rec['src']}){'  POLLUTED' if rec['polluted'] else ''}", flush=True)
    return rec


def main():
    print("=== ELECTRIC teach mode, live house: teach a pair, restart, ask it in other words ===",
          flush=True)
    res = {"arms": {}, "flags": {}}
    for name, what, arm in ARMS:
        tag = f"{name}_{int(time.time())}"
        print(f"\n--- {name}: {what} ---", flush=True)
        lang = fresh(arm, tag)
        st = flag_state(lang)
        res["flags"][name] = st
        print(f"      on: {sorted(a for a, v in st.items() if v)}", flush=True)
        print(f"      off: {sorted(a for a, v in st.items() if not v)}", flush=True)
        rows = len(lang.cortex.binder.meta)          # counted BEFORE probing
        lk = q.row_keys(lang, ask=True)
        pairs_before = len(lang.qa_store)
        conv_before = q.conv_keys(lang)
        out = probe(lang, lk)
        for text, r in out.items():
            print(f"      {r['kind']:13} {text:32} src={r['src']:20} "
                  f"ev={r['evidence']:20} said={r['said'][:30]!r:34} "
                  f"ref={r['refused']!s:5} {'LEAK' if r['leaked'] else ''}", flush=True)
        g = guard_probe(lang)
        print(f"      guard via answer(): refused={g['refused']} src={g['src']!r} "
              f"said={g['said'][:34]!r} reason={g['reason'][:40]!r}", flush=True)
        saved = lang.save_state(delta=True)
        lang2 = restart(arm, tag)
        out2 = probe(lang2, q.row_keys(lang2, ask=True))
        g2 = guard_probe(lang2)
        res["arms"][name] = {"rows": rows, "rows_after": len(lang2.cortex.binder.meta),
                             "store_keys": sorted(lang.qa_store),
                             "store_keys_after": sorted(lang2.qa_store),
                             "conv": conv_before, "conv_after": q.conv_keys(lang2),
                             "pairs_before_probes": pairs_before,
                             "pairs_after_probes": len(lang.qa_store),
                             "saved": bool((saved or {}).get("saved")),
                             "pending_after_restart": bool(lang2._qa_pending),
                             "probes": out, "probes_after": out2,
                             "guard": g, "guard_after": g2,
                             "leaks": sum(1 for r in out.values() if r["leaked"])
                                     + sum(1 for r in out2.values() if r["leaked"])}

    A = res["arms"]
    F = res["flags"]

    # ---- 1. what the mode turns on, and what it leaves alone -------------------------
    want = set(tm.STACK_ATTRS) | set(tm.BASE_ATTRS)
    assert set(a for a, v in F["T1"].items() if v) == want, \
        f"the mode is not the stack it claims: {sorted(F['T1'].items())}"
    assert not any(F["T1"][a] for a in tm.EXCLUDED_ATTRS), \
        "the mode turned on a switch that widens which asks reach which matchers"
    assert F["T1"] == F["T2"], "the bundle is NOT the list: the flags differ arm to arm"
    assert not any(F["T0"][a] for a in tm.STACK_ATTRS), "the control arm has the stack on"

    # ---- 2. the bundle IS the list, measured, not just in flags ----------------------
    for key in ("rows", "store_keys", "conv", "probes", "probes_after"):
        assert A["T1"][key] == A["T2"][key], f"mode and hand-list differ in {key}"
    print("\n    T1 (mode) == T2 (the seven flags set one by one): rows, store, every probe "
          "reply, before and after restart", flush=True)

    # ---- 3. teaching works, and only in the arms that hold a store ------------------
    for name in ("T1", "T2"):
        # sorted: `conv_keys` hands back keys, and keys have no teaching order -- asserting the
        # order here would be asserting a property of the store that does not exist.
        assert sorted(A[name]["conv"]) == sorted([PAIR_KEY, PAIR2_KEY]), \
            f"{name} did not teach both pairs: {A[name]['conv']}"
    assert A["T0"]["conv"] == [], "the control arm formed a pair with the stack off"
    answered = 0
    for name in ("T1", "T2"):
        for text, kind, expect in PROBES:
            r = A[name]["probes"][text]
            if kind in ("exact", "exact_marked", "folded"):
                assert r["from_store"] and r["said"] == expect, f"{name} lost {text}: {r}"
                assert r["evidence"], f"{name} answered {text} with no evidence named: {r}"
                answered += 1
            if kind == "folded":
                assert "paraphrase" in r["evidence"], \
                    f"{name} answered a paraphrase as if it were the exact key: {r}"
            if kind in ("refused", "unpaired", "guard_chat"):
                assert not r["from_store"], f"{name} answered {text} from a pair: {r}"
    for text, kind, _e in PROBES:
        r0 = A["T0"]["probes"][text]
        if kind in ("exact", "exact_marked", "folded"):
            assert not r0["from_store"], f"T0 answered {text} from a store it never filled"
    print(f"    T1/T2: {answered // 2} phrasings of the two taught pairs answered from the store "
          f"with the line the person gave; T0 answered 0 of them from a store it never filled",
          flush=True)

    # ---- 4. nothing leaks, nothing echoes, the guard is untouched --------------------
    for name in A:
        assert A[name]["leaks"] == 0, f"{name} leaked a remembered question"
        for text, r in list(A[name]["probes"].items()) + list(A[name]["probes_after"].items()):
            assert r["said"] != text.rstrip("?").strip(), f"{name} echoed the ask: {text}"
        # The absence licence is the graded path, and a bundle must not move it: same
        # refusal, same source, same words, in every arm, before and after a restart.
        for key in ("guard", "guard_after"):
            g = A[name][key]
            assert g["refused"] and g["src"] == "electric_absence", \
                f"{name} {key} stopped refusing: {g}"
    assert A["T0"]["guard"] == A["T1"]["guard"] == A["T2"]["guard"], \
        "the mode changed what the guard SAYS, not just whether it refuses"
    # Through the CHAT door the same ask has nothing to answer it with, and all three arms
    # agree: silence. Not a fragment of the ask, not a line from a pair that does not exist.
    chat = {name: A[name]["probes"][GUARD_ASK] for name in A}
    assert chat["T0"] == chat["T1"] == chat["T2"], f"the chat door differs by arm: {chat}"
    assert not chat["T1"]["spoken"], \
        f"the chat door now says something about an untaught relation -- re-measure this: {chat}"
    print("    guard refuses from electric_absence in every arm, in the same words, before and "
          "after a restart; through the chat door the untaught ask is silent in every arm; "
          "leaks 0; no ask echoed", flush=True)

    # ---- 5. the mode is not a memory writer, and probes teach nothing ----------------
    # Measured EQUAL here -- elicitation hears the ask turn and only then captures it, so the
    # pair forms without writing anything the control did not write. `<=` rather than `==`
    # because the direction that could ever move is down, never up: a turn the house has learned
    # to classify as a question can route to answer() instead of being heard.
    assert A["T1"]["rows"] <= A["T0"]["rows"], \
        f"the mode wrote rows the control did not: {A['T0']['rows']} vs {A['T1']['rows']}"
    for name in A:
        assert A[name]["pairs_before_probes"] == A[name]["pairs_after_probes"], \
            f"{name} probing taught a pair"
    res["rows_delta_control_minus_mode"] = A["T0"]["rows"] - A["T1"]["rows"]
    print(f"    rows: control {A['T0']['rows']}, mode {A['T1']['rows']} "
          f"(delta {res['rows_delta_control_minus_mode']}); asking in one phrasing and answering "
          "in another taught nothing in any arm", flush=True)

    # ---- 6. the hole, measured and NOT fixed ----------------------------------------
    # `_absence_note` (neural_language.py:5365) files a frame from ANYTHING it is told, and a
    # question's words yield a frame. So a question the house cannot classify as a question goes
    # into `_taught_says` as a tell -- the one store that answers BEFORE the QA store does.
    # Pinned here so that a future "fix" at the write site is a deliberate, measured choice.
    print("\n--- the question-pollution boundary (measured, unfixed) ---", flush=True)
    H = [hole("base", 1, "H_base1"), hole("base", 2, "H_base2"),
         hole("mode", 1, "H_mode1"), hole("mode", 2, "H_mode2")]
    res["hole"] = H
    by = {(h["arm"], h["pairs"]): h for h in H}
    # (a) The write site pollutes in EVERY arm, control included: an unclassified question is
    # filed as a tell no matter which flags are on. That part is not the mode's doing.
    for key in (("base", 1), ("base", 2), ("mode", 1)):
        assert by[key]["question_filed_as_tell"], \
            f"{key} no longer files the question as a tell -- the diagnosis is stale: {by[key]}"
    # (b) But only the MODE's house can be CAUGHT by it, and only in the one-pair state. With
    # elicitation off the follow-up ask is itself unclassifiable, never reaches any answer path,
    # and the house says nothing -- silence by accident, not by design.
    assert by[("mode", 1)]["polluted"], \
        f"the mode no longer pollutes at one pair -- re-measure this: {by[('mode', 1)]}"
    assert by[("base", 1)]["said"] == "" and by[("base", 2)]["said"] == "", \
        f"the control arm now answers something it could not classify: {by[('base', 1)]}"
    assert not by[("base", 2)]["what_is_a_question_word"], \
        f"the control arm learned a question word with elicitation off: {by[('base', 2)]}"
    # (c) The mode's own next pair is what closes it: the word earns its votes, the question
    # stops being heard as a tell, and the store answers from the pair.
    m2 = by[("mode", 2)]
    assert m2["what_is_a_question_word"] and m2["answered_from_store"] \
        and not m2["polluted"] and not m2["question_filed_as_tell"], \
        f"two elicited pairs no longer close the hole for the mode: {m2}"
    print("    pinned: the write site files an unclassified question as a tell in every arm; "
          "only a house that has learned the word can be caught by it, and only in the one-pair "
          "state -- where it repeats the person's own question back at them. The control arm is "
          "silent there for the same reason it cannot answer anything: it never classified the "
          "ask. The mode's second elicited pair earns the word and closes it.", flush=True)

    # ---- 7. the restart, and the held ask that must NOT survive it -------------------
    for name in ("T1", "T2"):
        assert A[name]["saved"] \
            and sorted(A[name]["conv_after"]) == sorted([PAIR_KEY, PAIR2_KEY]), \
            f"{name} lost a pair across a real restart: {A[name]['conv_after']}"
        assert A[name]["store_keys_after"] == A[name]["store_keys"], \
            f"{name} gained or lost a pair on the restart itself"
        assert not A[name]["pending_after_restart"], \
            f"{name} carried a held ask into a new life, where it could pair with anything"
        for text, kind, expect in PROBES:
            before, after = A[name]["probes"][text], A[name]["probes_after"][text]
            if kind in ("exact", "exact_marked", "folded"):
                assert after["from_store"] and after["said"] == before["said"] \
                    and after["said"] == expect, \
                    f"{name} lost {text} across the restart: {after}"
            else:
                assert not after["from_store"], \
                    f"{name} answered {text} from a pair after a restart: {after}"
    assert A["T0"]["conv_after"] == [], "T0 persisted a pair it never made"
    print("    after a real restart: the pair is still answerable in every phrasing the fold "
          "reaches, with the same line, and the held ask is gone", flush=True)

    Path("docs/evidence").mkdir(exist_ok=True)
    Path("docs/evidence/qa_teach_mode_live.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nwrote docs/evidence/qa_teach_mode_live.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
