"""LIVE-HOUSE check for ELECTRIC_QA_ELICIT: the real Droso, booted the way serve.py boots it,
is asked things by a person, is answered back by that person, and then asked again -- with the
question mark and without it -- before and after a restart.

Run:  .venv\\Scripts\\python.exe tools/qa_elicit_live.py [beats]

This is not the unit test and not the audit. `tests/test_electric_qa_elicit.py` measures a
synthetic organ; `tools/book_qa_store_audit.py` measures the book path. What only a live house
can answer is whether the three routes this flag opens are wired at all once the real
tokenizer, a real memory and the real answer ordering are in the way -- and whether opening
them costs anything the earlier work already established.

Two houses, two arms each:

  A  conversation only. No book is read, so the store starts empty and every pair in it was
     typed by a person. This is the feature's home ground, and also the hard case: each
     question word has ONE vote, because nothing else ever taught it, so the `learned` route
     from the audit cannot reach these memories at all.
  B  conversation AFTER reading 05_questions. Book pairs and person pairs in one store. The
     claim here is a negative one: an ask the flag did not answer before it must answer the
     same way after it.

What has to hold, and is asserted:
  * the same number of rows exists in both arms BEFORE probing -- elicitation writes no row,
    it only decides that two utterances were a question and an answer;
  * exactly the pairs that should have formed did, and the three that should not have did
    not: an unmarked ask, an ask whose adjacency was spent, an answer that came too late;
  * where the flag did not answer, the house said byte-identically what it said without it;
  * the guard still refuses, on an ask about a relation this house was never told (the
    lantern's place) -- NOT on the battery's scarf ask, because the tells this house hears
    do say where the scarf is, and refusing that would itself be the bug;
  * no ask is ever answered with its own text;
  * the leak count does not rise: a question must not become sayable because a person typed
    one at him;
  * after a real restart the elicited pairs are still answerable WITHOUT the mark, and the
    pending ask is gone.
"""
import importlib.util as _u
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.converse as converse                       # noqa: E402
from organs.higher_cortex import row_is_ask             # noqa: E402

_s = _u.spec_from_file_location("rev_qa", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)

BEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
TMP = Path("_tmp/qa_elicit_live")
FILES = sorted(Path("books").glob("*.txt"))
QA = next(k for k, p in enumerate(FILES) if "05_questions" in p.name)

# A scripted conversation. `expect` is what the store should hold afterwards, and the three
# NEGATIVE cases are the point: this flag's whole risk is pairing something that was never an
# answer, so two of the eight turns exist only to be refused.
CONV = [
    "who carries droso?",          # ask
    "parent carries droso",        # the next thing said: PAIR
    "what rings the bell?",        # ask
    "the copper bell rings",       # PAIR
    "where is the moon?",          # ask, never answered
    "the kettle whistles twice",   # not an answer: adjacency SPENT
    "the moon is behind the barn",  # the right words, one turn too late
    "who feeds the dog",           # an ask with no `?`: never becomes pending
    "parent feeds the dog",        # so this pairs with nothing
]
STORED = ["who carries droso", "what rings the bell"]
MARKED = [k + "?" for k in STORED]
REFUSED = ["who feeds the dog", "where is the moon", "the moon is behind the barn"]
ANSWER_OF = {"who carries droso": "parent carries droso",
             "what rings the bell": "the copper bell rings"}

# Asks the flag has NO pair for. Both arms must say the same thing for every one of them --
# that is the whole of the safety claim about the routing widening.
UNPAIRED = ["where did i say the scarf is?", "who does the lantern belong to?",
            "what bites the latch?", "where is the scarf", "who carries the droso",
            "who carries droso tomorrow", "is the kettle warm?"]
SCARF_ASK = "where did i say the scarf is?"
# The guard has to be asked about a relation this house was NEVER told. `where did i say
# the scarf is?` is the battery's guarded ask, but the TELLS this house hears include
# "the scarf is on the hook", so here the honest answer is that fact and a refusal would be
# a bug. The lantern was only ever said to BELONG to Mira, so its place is the absence.
GUARD_ASK = "where did i say the lantern is?"


def boot(elicit, tag, root):
    """One real house, flags wired the way tools/serve.py wires them, in the same order."""
    agent = converse.build(TMP / "sess" / tag, project_root=str(root))
    lang = agent.language
    lang.ELECTRIC_TEACH = True
    lang.ELECTRIC_ANSWER = True
    lang.ABSENCE_INVENTORY = True
    lang.ELECTRIC_ASK_MARKS = True
    lang.ELECTRIC_ASK_ADMISSIBILITY = True
    lang.ELECTRIC_QA_STORE = True
    lang.ELECTRIC_QA_ELICIT = bool(elicit)
    # Timing knobs BEFORE the tells. The first version of this set them after, so the six
    # tells were heard with the real inter-hear gate still live and which of them produced
    # a row depended on wall-clock -- the arms "differed by a row" for a reason that had
    # nothing to do with the flag. That is a harness artifact, and it ate the one invariant
    # that matters most: elicitation must write no row.
    lang.exposure_enabled = False        # house A reads nothing; house B turns it on
    lang.social_drive = 1.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang.exposure_speed_s = 0.0
    lang.cortex.MIN_HEAR_INTERVAL_S = 0.0
    for t in _m.TELLS:
        lang.hear(t, speaker="you")
    return lang


def fresh(elicit, tag, book, beats):
    root = TMP / "root" / tag
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    (root / "state").mkdir(parents=True)
    # The SESSION dir has to be wiped too: saves land there, and a leftover from an earlier
    # run gets copied into the shadow's state dir by restart().
    sess = TMP / "sess" / tag
    if sess.exists():
        shutil.rmtree(sess, ignore_errors=True)
    lang = boot(elicit, tag, root)
    if book is not None:
        lang.set_books_dir(Path("books"))
        lang._book_idx = book
        lang.exposure_enabled = True
        t0 = time.time()
        for _ in range(beats):
            lang.expose_tick(world_dt=5.0)
        print(f"      [read {beats} lines in {time.time()-t0:.1f}s]", flush=True)
    t0 = time.time()
    for u in CONV:
        lang.respond(u, speaker="you")
    print(f"      [conversation in {time.time()-t0:.1f}s  "
          f"conv_pairs={sum(1 for r in lang.qa_store.values() if (r.get('prov') or {}).get('source') == 'conversation')}]",
          flush=True)
    lang._house_root = root
    lang._house_tag = tag
    return lang


def restart(elicit, tag):
    """Save, move the session files into the shadow's state dir, boot again."""
    sdir, root = TMP / "sess" / tag, TMP / "root" / tag
    t0 = time.time()
    sv = (sdir / "language_state.json").exists()
    for f in sdir.iterdir():
        if f.is_file():
            shutil.copy2(f, root / "state" / f.name)
    lang = boot(elicit, tag, root)
    print(f"      [restart saved={sv} in {time.time()-t0:.1f}s  "
          f"rows={len(lang.cortex.binder.meta)} pairs={len(lang.qa_store)}]", flush=True)
    return lang


def row_keys(lang, ask=None):
    out = set()
    for m in lang.cortex.binder.meta:
        if ask is None or bool(row_is_ask(m)) == ask:
            out.add(" ".join(str(t) for t in (m.get("tokens") or [])))
    return out


def conv_keys(lang):
    return sorted(k for k, r in lang.qa_store.items()
                  if (r.get("prov") or {}).get("source") == "conversation")


def probe(lang, asks, leak_keys):
    """Every ask goes through `respond`, the door a chat turn actually uses -- not
    `answer`, which is one of the paths behind it."""
    out = {}
    for a in asks:
        r = lang.respond(a, speaker="you") or {}
        # Probes are independent questions, not a conversation: a marked ask followed by an
        # unmarked one would otherwise PAIR the probes with each other and measure a memory
        # this loop invented. The pending ask is cleared after every probe.
        lang._qa_pending = None
        said = str(r.get("utterance") or r.get("response") or "").strip()[:70]
        src = str(r.get("source") or "")
        out[a] = {"spoken": bool(r.get("spoken")), "said": said, "src": src,
                  "evidence": str(r.get("ask_evidence") or ""),
                  "from_store": src == "electric_qa_store",
                  "conv": str((r.get("provenance") or {}).get("source") or ""),
                  "refused": bool(r.get("licensed_refusal")),
                  "leaked": bool(r.get("spoken")) and said in leak_keys}
    return out


def run(label, book, tag, expect, beats=None):
    """One house, both arms. `expect` is the set of conversation pairs that SHOULD form
    here, and it is not always every pair in CONV: a key the book already holds cannot be
    paired again by a person, because first tell wins."""
    beats = beats or BEATS
    print(f"\n=== {label} ===", flush=True)
    res = {}
    for name, elicit in (("E1", False), ("E2", True)):
        lang = fresh(elicit, f"{tag}_{name}", book, beats)
        # Counted BEFORE probing: answering writes memory, so a count taken afterwards
        # measures the answer path and not the flag.
        rows = len(lang.cortex.binder.meta)
        lk = row_keys(lang, ask=True)
        asks = MARKED + STORED + REFUSED + UNPAIRED
        if book is not None:
            asks += [k for k in sorted(lang.qa_store)
                     if (lang.qa_store[k].get("prov") or {}).get("source")
                     != "conversation"][:4]
        pr = probe(lang, asks, lk)
        # The guard is reached through `answer`, the door it lives behind. Through
        # `respond` this ask never gets there at all in a house that was never taught
        # `where` -- which is its own fact, and is printed below as `routed=`.
        grd = lang.answer(GUARD_ASK) or {}
        stored = conv_keys(lang)
        prov_src = {k: str((lang.qa_store[k].get("prov") or {}).get("source") or "")
                    for k in STORED if k in lang.qa_store}
        leaks = sum(1 for x in pr.values() if x["leaked"])
        by_store = sum(1 for x in pr.values() if x["from_store"])
        print(f"  {name} elicit={int(elicit)}  rows={rows}  conv_pairs={len(stored)}  "
              f"answered_from_store={by_store}  LEAKS={leaks}", flush=True)
        for a in MARKED + STORED + REFUSED + UNPAIRED:
            x = pr[a]
            print(f"      {a[:38]:42s} src={x['src'][:18]:20} ev={x['evidence'][:13]:15}"
                  f"said={x['said'][:26]:28} ref={x['refused']!s:5} leak={x['leaked']!s:5}",
                  flush=True)
        print(f"      guard via answer(): refused={bool(grd.get('licensed_refusal'))} "
              f"src={str(grd.get('source') or '')!r} "
              f"reason={str(grd.get('reason') or '')[:44]!r}", flush=True)
        lang.save_state(force=True)
        lang2 = restart(elicit, f"{tag}_{name}")
        pr2 = probe(lang2, STORED + UNPAIRED, row_keys(lang2, ask=True))
        print(f"      after RESTART: conv_pairs={len(conv_keys(lang2))}  "
              f"pending={bool(getattr(lang2, '_qa_pending', None))}  "
              f"unmarked_answered="
              f"{sum(1 for k in STORED if pr2[k]['from_store'])}/{len(STORED)}  "
              f"LEAKS={sum(1 for x in pr2.values() if x['leaked'])}", flush=True)
        res[name] = {"rows": rows, "stored": stored, "probes": pr, "leaks": leaks,
                     "by_store": by_store, "probes_after": pr2,
                     "stored_after": conv_keys(lang2),
                     "guard_refused": bool(grd.get("licensed_refusal")),
                     "guard_src": str(grd.get("source") or ""),
                     "prov_src": prov_src,
                     "pending_after_restart": bool(getattr(lang2, "_qa_pending", None))}
    e1, e2 = res["E1"], res["E2"]
    exp = sorted(expect)
    exp_marked = [k + "?" for k in exp]

    same_rows = e1["rows"] == e2["rows"]
    # `conv_keys` sorts, so the expected set is compared sorted: the order a pair lands in
    # the store is not a claim of this flag and must not become one through a test.
    exact_pairs = e2["stored"] == exp and e1["stored"] == []
    marked = all(e2["probes"][k]["from_store"]
                 and e2["probes"][k]["evidence"] == "typed" for k in exp_marked)
    unmarked = all(e2["probes"][k]["from_store"]
                   and e2["probes"][k]["evidence"] == "person_marked"
                   and e2["probes"][k]["said"] == ANSWER_OF[k] for k in exp)
    # ONE safety claim, stated at its widest: everywhere the flag did not answer from a
    # pair a person typed, the house said the same words and refused the same way it says
    # and refuses without the flag. That covers the book pairs, the guarded asks, the
    # near-misses and the unpaired asks in a single sentence, and it is the sentence the
    # routing widening is measured by.
    untouched = [a for a, x in e2["probes"].items() if x["conv"] != "conversation"]
    same = all(e1["probes"][a]["said"] == e2["probes"][a]["said"]
               and e1["probes"][a]["refused"] == e2["probes"][a]["refused"]
               for a in untouched)
    same_after = all(e1["probes_after"][a]["said"] == e2["probes_after"][a]["said"]
                     for a in e2["probes_after"]
                     if e2["probes_after"][a]["conv"] != "conversation")
    guard = (e1["guard_refused"] and e2["guard_refused"]
             and e1["guard_src"] == e2["guard_src"] != "electric_qa_store")
    # He must never answer a question by repeating it. This is the defect the live house
    # found: a marked ask landed in the taught inventory, and the taught path -- which runs
    # before the store -- spoke the ask back as its own answer.
    echoes = [a for arm in (e1, e2) for a, x in arm["probes"].items()
              if x["said"] and x["said"].rstrip("?").strip() == a.rstrip("?").strip()]
    restart_ok = (e2["stored_after"] == exp and not e2["pending_after_restart"]
                  and all(e2["probes_after"][k]["from_store"] for k in exp))
    leaks_same = e1["leaks"] == e2["leaks"]
    # First tell wins, and a person is not allowed to overwrite a line a book printed with
    # the same words. House B measures it: `who carries droso` is in 05_questions already,
    # so the person's identical pair is refused and the BOOK's answer is what stands.
    held = [k for k in STORED if k not in exp]
    first_tell = all(k in e2["prov_src"] and e2["prov_src"][k] != "conversation"
                     for k in held)
    print(f"    rows equal: {same_rows} ({e1['rows']}/{e2['rows']})   "
          f"conv pairs: off={len(e1['stored'])} on={len(e2['stored'])} "
          f"expected={exp} exact={exact_pairs}   marked={marked} unmarked={unmarked}")
    print(f"    asks the flag did not answer ({len(untouched)}/{len(e2['probes'])}): "
          f"same words and same refusal in both arms: {same} (after restart {same_after})"
          f"   guard refuses: {guard}   leaks: {e1['leaks']} -> {e2['leaks']}"
          f"   no ask echoed: {not echoes}   first-tell holds {held}: {first_tell}   "
          f"restart keeps pairs, drops pending: {restart_ok}", flush=True)
    assert same_rows, "elicitation wrote or lost a row"
    assert not echoes, f"an ask was answered with its own text: {echoes}"
    assert exact_pairs, f"elicited the wrong pairs: off={e1['stored']} on={e2['stored']}"
    assert marked and unmarked, "an elicited pair is not answerable both ways"
    assert same and same_after, "the routing widened what an unpaired ask says"
    assert guard, "the guard stopped refusing"
    assert leaks_same, "the leak count changed"
    assert first_tell, "a person overwrote a pair the book printed first"
    assert restart_ok, "the pair or the pending ask did not survive the restart correctly"
    return res


def main():
    out = {"beats": BEATS, "conversation": CONV, "houses": {}}
    out["houses"]["A_conversation_only"] = run(
        "A  conversation only (no book read: every pair was typed by a person)",
        None, "conv", STORED, beats=0)
    # House B expects ONE conversation pair, not two: `who carries droso` is already in the
    # book the house just read, and first-tell-wins refuses the person's identical pair.
    out["houses"]["B_after_book"] = run(
        "B  conversation after reading 05_questions (book pairs and person pairs together)",
        QA, "book", ["what rings the bell"])
    Path("docs/evidence").mkdir(parents=True, exist_ok=True)
    Path("docs/evidence/qa_elicit_live.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\nwrote docs/evidence/qa_elicit_live.json")


if __name__ == "__main__":
    main()
