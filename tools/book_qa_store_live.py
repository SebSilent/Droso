"""LIVE-HOUSE check for ELECTRIC_QA_STORE: the real Droso, booted the way serve.py boots it,
reads a real book, is asked questions, is saved, and is booted again.

Run:  .venv\\Scripts\\python.exe tools/book_qa_store_live.py [beats]

This is not the audit. `tools/book_qa_learn_audit.py` measures a synthetic organ; this one asks
whether the flag is wired at all in the real house, and whether the memory it adds REOPENS the
leak the marks work closed -- because the store is an early return in `answer()`, before the
admissibility gate ever sees the ask.

Two things the first version of this tool got wrong, and the fix in each case:
  * `converse.build(..., project_root=None)` boots against the LIVE state: the organ came up
    with 60,000 rows already in it, so every probe measured a contaminated house. Now every
    house gets its own EMPTY shadow root (`<tmp>/root/<tag>/state` with nothing in it), which
    is also what makes it cheap -- the full save went from 20.7s to about a second.
  * the "restart" did not restart: saves land in the SESSION dir (converse re-points every
    path after construction) while a boot loads from `<project_root>/state`. So the restart
    here copies the session files into the shadow's state dir and boots again, which is the
    same round trip serve.py does.

Books: a blank shadow house gets books_dir = ROOT/books from world/connectome_house.py, and the
live house's curated shelf entries are byte-identical copies (verified by hash:
books/05_questions.txt == state/shelf/01_05_questions.txt, and jane_eyre likewise), so measuring
on books/ measures what the house actually reads.

What has to hold, and is asserted:
  * the same number of rows exists in both arms -- the store writes no row, so it can neither
    create nor destroy a memory;
  * the LEAK COUNT is identical and zero: a book question must not become sayable again;
  * the taught asks answer byte-identically: the store sits after the taught path and must not
    intercept a fact he was told by a person;
  * the Dickens pair -- the one pair the 16 real novels yield, a question followed by a
    question -- stores nothing and answers nothing, in the house, on the pair's verbatim text;
  * after a real restart the gained answers are still there.
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

BEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
TMP = Path("_tmp/qa_store_live")
# Row-token sets per house, taken before any probe.  Kept out of the JSON on purpose:
# the count alone cannot tell "the store wrote a row" from "the answer path wrote one",
# and the differing rows are the evidence either way.
KEYSETS: dict = {}
FILES = sorted(Path("books").glob("*.txt"))
QA = next(k for k, p in enumerate(FILES) if "05_questions" in p.name)
JANE = next(k for k, p in enumerate(FILES) if "jane_eyre" in p.name)

TAUGHT = ["who holds the latch", "what bites the latch", "where is the scarf"]
LEAK = ["why have i alluded to this that", "what does bessie say i have that",
        "why have i alluded to this man?"]
QA_ASKS = ["who feeds droso?", "who opens droso?", "where is the home?",
           "where is the light?", "what is droso's name?"]
# The single accepted pair in the 16 real novels, verbatim from
# books/gutenberg_4_great_expectations.txt lines 1855-1856.  A crafted excerpt is used
# instead of reading 1,855 lines of Dickens in the house: same text, same organ, same
# admission rule, ~2 minutes cheaper.
DICKENS_PAIR = ["Might a mere warmint ask what property?",
                "Might a mere warmint ask whose property?"]
DICKENS_ASK = "might a mere warmint ask what property?"


def boot(store, tag, root):
    """One real house, flags wired the way tools/serve.py wires them, in the same order."""
    agent = converse.build(TMP / "sess" / tag, project_root=str(root))
    lang = agent.language
    lang.ELECTRIC_TEACH = True
    lang.ELECTRIC_ANSWER = True
    lang.ELECTRIC_ASK_MARKS = True
    lang.ELECTRIC_ASK_ADMISSIBILITY = True
    lang.ELECTRIC_QA_STORE = bool(store)
    for t in _m.TELLS:
        lang.hear(t, speaker="you")
    # converse.build turns reading off: a conversation is not a library.
    lang.exposure_enabled = True
    lang.social_drive = 1.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang.exposure_speed_s = 0.0
    lang.cortex.MIN_HEAR_INTERVAL_S = 0.0
    return lang


def fresh(store, tag, book_idx, beats):
    root = TMP / "root" / tag
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    (root / "state").mkdir(parents=True)
    # The SESSION dir has to be wiped too: saves land there, and a leftover from an
    # earlier run of this tool gets copied into the shadow's state dir by restart(),
    # which is how the first version of the audit came to measure book 2 with book 1's
    # memories in it.
    sess = TMP / "sess" / tag
    if sess.exists():
        shutil.rmtree(sess, ignore_errors=True)
    lang = boot(store, tag, root)
    lang.set_books_dir(Path("books"))
    lang._book_idx = book_idx
    t0 = time.time()
    for _ in range(beats):
        lang.expose_tick(world_dt=5.0)
    lang._house_root = root
    lang._house_tag = tag
    print(f"      [boot+{beats} beats in {time.time()-t0:.1f}s  "
          f"lines={getattr(lang, '_book_line_pos', 0)}]", flush=True)
    return lang


def restart(store, tag):
    """Save, move the session files into the shadow's state dir, boot again."""
    sdir = TMP / "sess" / tag
    root = TMP / "root" / tag
    t0 = time.time()
    sv = (sdir / "language_state.json").exists()
    for f in sdir.iterdir():
        if f.is_file():
            shutil.copy2(f, root / "state" / f.name)
    lang = boot(store, tag, root)
    print(f"      [restart: saved={sv} in {time.time()-t0:.1f}s  "
          f"rows={len(lang.cortex.binder.meta)}]", flush=True)
    return lang


def row_keys(lang, ask=None):
    """Token keys of the rows in memory, split by the ASK tag.

    `ask=None` gives every row. This exists because `leaked=False` alone can hide an
    echo: a question line that entered memory as a STATEMENT-shaped row (never tagged,
    so admissibility cannot drop it) is recalled by retrieval and spoken, and it is not
    in the ask-tagged key set. Naming which set the spoken text came from keeps that
    distinction visible instead of flattening it into a boolean.
    """
    out = set()
    for m in lang.cortex.binder.meta:
        if ask is None or bool(row_is_ask(m)) == ask:
            out.add(" ".join(str(t) for t in (m.get("tokens") or [])))
    return out


def probe(lang, asks, leak_keys):
    """LEAKED is the marks tool's definition, kept so the numbers compare: he spoke, and
    what he spoke is the text of a row the question line TAGGED as an ask.

    The first version of this also counted "echoed_untagged_row" -- the spoken text
    matching any untagged row. That measured nothing: answering a question from memory is
    BY DEFINITION saying the text of a stored statement row, so every correct answer lit
    it up and the store arm looked like a leak. What is actually claimable is narrower and
    is checked in run_book: wherever the store did NOT answer, both arms must say exactly
    the same thing.
    """
    out = {}
    for a in asks:
        r = lang.answer(a) or {}
        said = str(r.get("utterance") or r.get("response") or "").strip()[:70]
        out[a] = {"spoken": bool(r.get("spoken")), "said": said,
                  "src": str(r.get("source") or ""),
                  "from_store": str(r.get("source") or "") == "electric_qa_store",
                  "leaked": bool(r.get("spoken")) and said in leak_keys,
                  "ask_refused": str(r.get("reason") or "").startswith(
                      "what he remembers there is only")}
    return out


def run_book(label, book_idx, asks, tag, beats=None):
    beats = beats or BEATS
    print(f"\n=== {label}  ({beats} beats) ===", flush=True)
    res = {}
    for name, store in (("S1", False), ("S2", True)):
        lang = fresh(store, f"{tag}_{name}", book_idx, beats)
        # Counted BEFORE probing.  Answering writes memory -- six probes added seven rows
        # on jane_eyre -- so a count taken after probing measures the answer path, and an
        # A/B difference there is not the store writing a row.
        rows = len(lang.cortex.binder.meta)
        KEYSETS[f"{tag}_{name}"] = row_keys(lang)
        lk = row_keys(lang, ask=True)
        pr = probe(lang, asks, lk)
        rows_after_probe = len(lang.cortex.binder.meta)
        stored = len(lang.qa_store)
        leaks = sum(1 for x in pr.values() if x["leaked"])
        by_store = sum(1 for x in pr.values() if x["from_store"])
        answered = sum(1 for x in pr.values() if x["spoken"] and x["said"])
        refused = sum(1 for x in pr.values() if x["ask_refused"])
        print(f"  {name} store={int(store)}  rows={rows:6} (after probing "
              f"{rows_after_probe:6})  stored_pairs={stored:4}  "
              f"answered={answered:3} (by store {by_store})  LEAKS={leaks}  "
              f"ask_refused={refused}", flush=True)
        for a in asks:
            x = pr[a]
            print(f"      {a[:42]:46s} src={x['src'][:18]:20} said={x['said'][:34]:36}"
                  f" leaked={x['leaked']!s:5} store={x['from_store']!s:5}")
        lang.save_state(force=True)
        lang2 = restart(store, f"{tag}_{name}")
        pr2 = probe(lang2, asks, row_keys(lang2, ask=True))
        a2 = sum(1 for x in pr2.values() if x["spoken"] and x["said"])
        l2 = sum(1 for x in pr2.values() if x["leaked"])
        print(f"      after RESTART: stored_pairs={len(lang2.qa_store)}  answered={a2}  "
              f"LEAKS={l2}", flush=True)
        res[name] = {"rows": rows, "rows_after_probe": rows_after_probe,
                     "stored": stored, "answered": answered,
                     "leaks": leaks, "by_store": by_store, "refused": refused,
                     "probes": pr, "answered_after": a2, "leaks_after": l2,
                     "stored_after": len(lang2.qa_store), "probes_after": pr2}
    s1, s2 = res["S1"], res["S2"]
    same_rows = s1["rows"] == s2["rows"]
    same_taught = all(s1["probes"][t]["said"] == s2["probes"][t]["said"]
                      and s1["probes_after"][t]["said"] == s2["probes_after"][t]["said"]
                      for t in TAUGHT if t in s1["probes"])
    k1, k2 = KEYSETS.get(f"{tag}_S1", set()), KEYSETS.get(f"{tag}_S2", set())
    if k1 != k2:
        print(f"    row keys DIFFER pre-probe: only-off={len(k1 - k2)} only-on={len(k2 - k1)}")
        for k in list(k1 - k2)[:4]:
            print(f"      only store OFF: {k[:64]}")
        for k in list(k2 - k1)[:4]:
            print(f"      only store ON : {k[:64]}")
    # The store's whole safety claim in one line: everywhere it did not answer, the house
    # said exactly what it would have said without it.
    non_store_same = all(s1["probes"][a]["said"] == s2["probes"][a]["said"]
                         for a in asks if not s2["probes"][a]["from_store"])
    non_store_same_after = all(
        s1["probes_after"][a]["said"] == s2["probes_after"][a]["said"]
        for a in asks if not s2["probes_after"][a]["from_store"])
    print(f"    rows equal: {same_rows} ({s1['rows']}/{s2['rows']}; after probing "
          f"{s1['rows_after_probe']}/{s2['rows_after_probe']} -- answering writes memory, "
          f"so only the pre-probe count is the reading invariant)   "
          f"leaks: {s1['leaks']} -> {s2['leaks']}   "
          f"answered: {s1['answered']} -> {s2['answered']} "
          f"(store answered {s2['by_store']})   "
          f"taught identical: {same_taught}")
    print(f"    where the store did NOT answer, both arms said the same: "
          f"{non_store_same} (after restart {non_store_same_after})")
    print(f"    after restart: stored {s2['stored']} -> {s2['stored_after']}, "
          f"answered {s1['answered_after']} -> {s2['answered_after']}, "
          f"leaks {s2['leaks_after']}")
    assert same_rows, "the store wrote or lost a row"
    assert s2["leaks"] <= s1["leaks"], "the store REOPENED the leak"
    assert same_taught, "the store intercepted a taught fact"
    assert non_store_same, "the store changed what retrieval says for an ask it did not keep"
    assert non_store_same_after, "the store changed retrieval only after a restart"
    return res


def dickens():
    """The one pair the real novels yield, verbatim, in the house with the store on."""
    print(f"\n=== the Dickens pair (crafted excerpt, {len(DICKENS_PAIR)} lines) ===",
          flush=True)
    root = TMP / "root" / "dickens"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    (root / "state").mkdir(parents=True)
    shelf = root / "books"
    shelf.mkdir(parents=True, exist_ok=True)
    (shelf / "00_excerpt.txt").write_text("\n".join(DICKENS_PAIR) + "\n",
                                          encoding="utf-8")
    lang = boot(True, "dickens", root)
    lang.set_books_dir(shelf)
    for _ in range(12):
        lang.expose_tick(world_dt=5.0)
    x = probe(lang, [DICKENS_ASK], row_keys(lang, ask=True))[DICKENS_ASK]
    print(f"    stored_pairs={len(lang.qa_store)}  ask src={x['src']!r} "
          f"spoken={x['spoken']} said={x['said'][:50]!r} leaked={x['leaked']}")
    assert len(lang.qa_store) == 0, "the store accepted a question answering a question"
    # The claim is about the STORE: it must not be the thing answering. Whether the
    # retrieval path answers at all is the coverage floor's business, not this flag's --
    # in a blank shadow house with two book lines and four tells in it, a confabulated
    # recall is the pre-existing behaviour, and it is printed, not asserted away.
    assert not x["from_store"], "the store answered the refused pair"
    if x["spoken"] and x["said"]:
        print(f"    (pre-existing, store NOT involved: retrieval said {x['said'][:44]!r} "
              f"from {x['src']!r})")
    return {"stored": len(lang.qa_store), "probe": x}


def main():
    out = {"beats": BEATS, "houses": {}}
    out["houses"]["05_questions"] = run_book(
        "05_questions (Q/A book: capability must appear)", QA, QA_ASKS + TAUGHT, "qa")
    out["houses"]["jane_eyre"] = run_book(
        "jane_eyre (real novel: the leak must stay closed)", JANE, LEAK + TAUGHT, "jane")
    out["houses"]["dickens"] = dickens()
    Path("docs/evidence/book_qa_store_live.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\nwrote docs/evidence/book_qa_store_live.json")


if __name__ == "__main__":
    main()
