"""LIVE-HOUSE check for ELECTRIC_QA_PARAPHRASE: the real Droso, booted the way serve.py boots
it, is taught a pair in ONE phrasing and then asked for it in ANOTHER -- with and without the
mark, in the phrasings the fold reaches and the phrasings it must refuse -- before and after a
real restart.

Run:  .venv\\Scripts\\python.exe tools/qa_paraphrase_live.py [beats]

Why this is not the unit test. `tests/test_electric_qa_paraphrase.py` measures a synthetic
organ with one pair in the store. What only a live house can answer is whether the fold survives
the things a unit test stubs out: the real tokenizer, a store holding 200+ pairs a BOOK printed,
the taught path that runs before the store, and the routing in `respond` that has to follow the
fold or the feature only works in the phrasing it was typed in.

Two arms, in two houses:

  P1  elicit ON, paraphrase OFF. This is the configuration that was already measured and
      committed (tools/qa_elicit_live.py), so it is the control: every difference between the
      arms is this flag's doing and nothing else's.
  P2  elicit ON, paraphrase ON.

  A   conversation only. Every pair in the store was typed by a person, which is the only
      kind of record this flag is allowed to fold.
  B   conversation AFTER reading 05_questions. The provenance bound is measured here rather
      than asserted: `who carries droso` is a line the BOOK printed first, so the person's
      identical pair is refused by first-tell-wins and the record that stands is a book
      record. A paraphrase of it must get NOTHING from the store, in either arm.

What has to hold, and is asserted:

  * the two arms start with the same rows and the same store keys -- a lookup folds, it does
    not learn;
  * every phrasing the fold claims to reach IS reached, with the line the person gave, and
    the evidence says so (`person_paraphrase` / `typed_paraphrase`);
  * every phrasing the fold claims NOT to reach is refused, and refused identically in both
    arms: `who droso carries` (order), `who carries droso tomorrow` (a content word added),
    `who carried droso` and `who own the lantern` (under-folds the shared stemmer will not
    bridge). These are the safe half of the policy and they are measured, not assumed;
  * the general no-widening claim, stated once: on every ask this flag did not answer from a
    conversation pair, the house said byte-identically what the control arm says;
  * the guard still refuses, on the lantern's place, from the same source;
  * no ask is answered with its own text, and the leak count does not rise;
  * after a real restart the paraphrases still answer -- the fold is derived from the store
    at lookup time and is not itself a memory -- and a hanging ask is still gone.
"""
import importlib.util as _u
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.qa_elicit_live as q                           # noqa: E402

BEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
q.TMP = Path("_tmp/qa_paraphrase_live")        # the committed tool's scratch dir, not ours

# (ask typed with a `?`, the answer the person gave next, the key the pair is stored under)
PAIRS = [
    ("who carries droso?", "parent carries droso", "who carries droso"),
    ("what rings the bell?", "the copper bell rings", "what rings the bell"),
    ("what holds the door?", "the latch holds the door", "what holds the door"),
    ("what is on the hook?", "the scarf is on the hook", "what is on the hook"),
    ("who owns the lantern?", "mira owns the lantern", "who owns the lantern"),
]
ANSWER_OF = {k: a for _q, a, k in PAIRS}
CONV = [u for pair in PAIRS for u in pair[:2]]

# (probe text, the pair it is a phrasing of, kind)
#   exact    -- the words it was taught in: must answer in BOTH arms, unchanged
#   folded   -- a phrasing the fold claims to reach: must answer in P2 and NOT in P1
#   refused  -- a phrasing the fold claims NOT to reach: must not answer in either arm
#   unpaired -- an ask no person ever taught: both arms must say the same thing
PROBES = [
    # exact
    ("who carries droso", "who carries droso", "exact"),
    ("what rings the bell", "what rings the bell", "exact"),
    ("what holds the door", "what holds the door", "exact"),
    # folded: an article, a copula, do-support, the verb's own inflection
    ("who carries the droso", "who carries droso", "folded"),
    ("who is carrying droso", "who carries droso", "folded"),
    ("who does carry droso", "who carries droso", "folded"),
    ("what ring the bell", "what rings the bell", "folded"),
    ("what is ringing the bell", "what rings the bell", "folded"),
    ("what hold the door", "what holds the door", "folded"),
    ("what on the hook", "what is on the hook", "folded"),
    ("what is on the hook", "what is on the hook", "exact"),
    # folded, marked this time: the person typed a `?` at a phrasing they had not used before
    ("who carries the droso?", "who carries droso", "folded"),
    # the ask normalizer's own case: a passive, words in a different ORDER, so the fold alone
    # cannot reach it -- `normalize_ask_variants` has to, on the warrant of a taught tell.
    ("what was the door held by", "what holds the door", "folded"),
    # refused: order, an added content word, and the under-folds the shared stemmer refuses
    ("who droso carries", "who carries droso", "refused"),
    ("who carries droso tomorrow", "who carries droso", "refused"),
    ("who carried droso", "who carries droso", "refused"),
    ("what rings the bell twice", "what rings the bell", "refused"),
    ("who own the lantern", "who owns the lantern", "refused"),
    ("who is owning the lantern", "who owns the lantern", "refused"),
    ("what was the door held by yesterday", "what holds the door", "refused"),
    # unpaired
    ("where is the moon", None, "unpaired"),
    ("what bites the latch", None, "unpaired"),
    ("where did i say the scarf is?", None, "unpaired"),
]
GUARD_ASK = "where did i say the lantern is?"
FOLDABLE = {k for _a, _a2, k in PAIRS}


def boot(elicit, paraphrase, tag, root):
    """The committed tool's boot, plus this flag -- set before anything is probed."""
    lang = q.boot(elicit, tag, root)
    lang.ELECTRIC_QA_PARAPHRASE = bool(paraphrase)
    return lang


def fresh(elicit, paraphrase, tag, book, beats):
    root = q.TMP / "root" / tag
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    (root / "state").mkdir(parents=True)
    sess = q.TMP / "sess" / tag
    if sess.exists():
        shutil.rmtree(sess, ignore_errors=True)
    lang = boot(elicit, paraphrase, tag, root)
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
    conv = q.conv_keys(lang)
    print(f"      [conversation in {time.time()-t0:.1f}s  pairs={len(lang.qa_store)} "
          f"conv_pairs={len(conv)}]", flush=True)
    lang._house_root = root
    lang._house_tag = tag
    return lang


def restart(elicit, paraphrase, tag):
    sdir, root = q.TMP / "sess" / tag, q.TMP / "root" / tag
    sv = (sdir / "language_state.json").exists()
    for f in sdir.iterdir():
        if f.is_file():
            shutil.copy2(f, root / "state" / f.name)
    lang = boot(elicit, paraphrase, tag, root)
    print(f"      [restart saved={sv}  rows={len(lang.cortex.binder.meta)} "
          f"pairs={len(lang.qa_store)} conv={len(q.conv_keys(lang))}]", flush=True)
    return lang


def probe(lang, leak_keys):
    """Every ask goes through `respond`, the door a chat turn actually uses."""
    out = {}
    for text, pair, kind in PROBES:
        r = lang.respond(text, speaker="you") or {}
        lang._qa_pending = None          # probes are independent questions, not a dialogue
        said = str(r.get("utterance") or r.get("response") or "").strip()[:70]
        src = str(r.get("source") or "")
        out[text] = {"kind": kind, "pair": pair, "spoken": bool(r.get("spoken")),
                     "said": said, "src": src,
                     "evidence": str(r.get("ask_evidence") or ""),
                     "from_store": src == "electric_qa_store",
                     "conv": str((r.get("provenance") or {}).get("source") or ""),
                     "refused": bool(r.get("licensed_refusal")),
                     "leaked": bool(r.get("spoken")) and said in leak_keys}
    return out


def eligible(lang, pair):
    """May THIS house answer THAT pair by folding? Only if the record standing under the key
    is a person's marked ask. In house B the book got there first for one of them, and the
    answer to that pair is refused to the fold -- which is the bound, not a bug."""
    rec = lang.qa_store.get(pair) if pair else None
    prov = (rec or {}).get("prov") or {}
    return bool(rec) and str(prov.get("source") or "") == "conversation" and prov.get("marked")


def run(label, book, tag, beats=None):
    beats = beats or BEATS
    print(f"\n=== {label} ===", flush=True)
    res = {}
    for name, paraphrase in (("P1", False), ("P2", True)):
        lang = fresh(True, paraphrase, f"{tag}_{name}", book, beats)
        rows = len(lang.cortex.binder.meta)
        keys = sorted(lang.qa_store)
        conv = q.conv_keys(lang)
        lk = q.row_keys(lang, ask=True)
        pr = probe(lang, lk)
        conv_after = q.conv_keys(lang)
        grd = lang.answer(GUARD_ASK) or {}
        elig = {p: eligible(lang, pi) for (p, pi, _k) in PROBES if pi}
        leaks = sum(1 for x in pr.values() if x["leaked"])
        print(f"  {name} paraphrase={int(paraphrase)}  rows={rows}  pairs={len(keys)}  "
              f"conv={len(conv)}  answered_from_store="
              f"{sum(1 for x in pr.values() if x['from_store'])}  LEAKS={leaks}", flush=True)
        for text, x in pr.items():
            # What THIS row was allowed to do, arm by arm: an exact phrasing answers from a
            # person's pair in BOTH arms; a folded one answers only with the flag on; and
            # anything whose record is the book's answers from a conversation pair in NEITHER.
            conv_elig = bool(elig.get(x["pair"])) if x["pair"] else False
            if x["kind"] == "exact":
                want = ANSWER_OF[x["pair"]] if conv_elig else None
            elif x["kind"] == "folded":
                want = ANSWER_OF[x["pair"]] if (conv_elig and paraphrase) else None
            else:
                want = None
            hit = x["from_store"] and x["conv"] == "conversation"
            ok = (x["said"] == want) if want else (not hit)
            print(f"      {x['kind']:8s} {text[:36]:38s} src={x['src'][:18]:20}"
                  f" ev={x['evidence'][:16]:18} said={x['said'][:24]:26}"
                  f" {'OK' if ok else 'XX'}{'' if conv_elig else ' (book record)'}", flush=True)
        print(f"      guard via answer(): refused={bool(grd.get('licensed_refusal'))} "
              f"src={str(grd.get('source') or '')!r} "
              f"reason={str(grd.get('reason') or '')[:40]!r}", flush=True)
        lang.save_state(force=True)
        lang2 = restart(True, paraphrase, f"{tag}_{name}")
        pr2 = probe(lang2, q.row_keys(lang2, ask=True))
        folded = [t for t, x in pr2.items() if x["kind"] == "folded"]
        print(f"      after RESTART: conv={len(q.conv_keys(lang2))}  "
              f"pending={bool(getattr(lang2, '_qa_pending', None))}  "
              f"paraphrases_answered="
              f"{sum(1 for t in folded if pr2[t]['from_store'] and pr2[t]['conv'] == 'conversation')}"
              f"/{sum(1 for t in folded if elig.get(pr2[t]['pair']))}  "
              f"LEAKS={sum(1 for x in pr2.values() if x['leaked'])}", flush=True)
        res[name] = {"rows": rows, "keys": keys, "conv": conv, "conv_after": conv_after,
                     "probes": pr, "leaks": leaks, "elig": elig,
                     "guard_refused": bool(grd.get("licensed_refusal")),
                     "guard_src": str(grd.get("source") or ""),
                     "probes_after": pr2, "conv_after_restart": q.conv_keys(lang2),
                     "pending_after_restart": bool(getattr(lang2, "_qa_pending", None))}
    p1, p2 = res["P1"], res["P2"]

    same_rows = p1["rows"] == p2["rows"]
    same_keys = p1["keys"] == p2["keys"]
    same_conv = p1["conv"] == p2["conv"]

    # 1. every folded phrasing of a pair the house MAY fold answers, with the line it was
    #    given, and the control arm does not answer it from the store at all.
    reach, ctrl = [], []
    for text, x in p2["probes"].items():
        if x["kind"] != "folded":
            continue
        if not p2["elig"].get(x["pair"]):
            continue
        want = ANSWER_OF[x["pair"]]
        reach.append(text)
        ok = (x["said"] == want and x["from_store"] and x["conv"] == "conversation"
              and x["evidence"] in ("person_paraphrase", "typed_paraphrase"))
        if not ok:
            print(f"    !! not recovered: {text} -> {x}")
            reach.remove(text)
        c = p1["probes"][text]
        if c["from_store"]:
            print(f"    !! the CONTROL arm answered a paraphrase from the store: {text} -> {c}")
            reach.remove(text)
        ctrl.append(text)

    # 2. nothing the fold claims to refuse is answered from a conversation pair.
    over = [t for t, x in p2["probes"].items()
            if x["kind"] in ("refused", "unpaired") and x["from_store"]
            and x["conv"] == "conversation"]

    # 3. the general claim: anywhere this flag did not answer from a person's pair, the two
    #    arms said the same words and refused the same way.
    silent = [t for t, x in p2["probes"].items()
              if not (x["from_store"] and x["conv"] == "conversation")]
    same = all(p1["probes"][t]["said"] == p2["probes"][t]["said"]
               and p1["probes"][t]["refused"] == p2["probes"][t]["refused"] for t in silent)

    # 4. exact phrasings are untouched by the flag.
    exact_ok = all(p1["probes"][t]["said"] == p2["probes"][t]["said"]
                   for t, x in p2["probes"].items() if x["kind"] == "exact")

    guard = (p1["guard_refused"] and p2["guard_refused"]
             and p1["guard_src"] == p2["guard_src"] != "electric_qa_store")
    echoes = [t for arm in (p1, p2) for t, x in arm["probes"].items()
              if x["said"] and x["said"].rstrip("?").strip() == t.rstrip("?").strip()]
    leaks_same = p1["leaks"] == p2["leaks"]
    probes_wrote_nothing = (p2["conv_after"] == p2["conv"]
                            and p1["conv_after"] == p1["conv"])

    # 5. restart: the fold is derived from the persisted store, not stored itself.
    after = [t for t, x in p2["probes_after"].items()
             if x["kind"] == "folded" and p2["elig"].get(x["pair"])]
    restart_ok = (all(p2["probes_after"][t]["from_store"]
                      and p2["probes_after"][t]["conv"] == "conversation"
                      and p2["probes_after"][t]["said"] == ANSWER_OF[
                          p2["probes_after"][t]["pair"]] for t in after)
                  and p2["conv_after_restart"] == p2["conv"]
                  and not p2["pending_after_restart"])
    after_refused = [t for t, x in p2["probes_after"].items()
                     if x["kind"] in ("refused", "unpaired") and x["from_store"]
                     and x["conv"] == "conversation"]

    print(f"    rows equal: {same_rows} ({p1['rows']}/{p2['rows']})   store keys equal: "
          f"{same_keys}   conv pairs equal: {same_conv} ({p1['conv']})")
    print(f"    folded phrasings eligible {len(reach)}/{len([t for t, x in p2['probes'].items() if x['kind'] == 'folded'])}  "
          f"all recovered with the right line and control silent: {len(reach)}  "
          f"(refused phrasings answered from a person's pair: {over})")
    print(f"    asks the flag did not answer ({len(silent)}/{len(p2['probes'])}): same words "
          f"and same refusal in both arms: {same}   exact phrasings unchanged: {exact_ok}")
    print(f"    guard refuses: {guard} ({p1['guard_src']})   leaks: {p1['leaks']} -> "
          f"{p2['leaks']}   no ask echoed: {not echoes}   probing stored no pair: "
          f"{probes_wrote_nothing}")
    print(f"    after restart: paraphrases still answered {len(after)}: {restart_ok}   "
          f"still nothing refused answered: {not after_refused}   pairs unchanged: "
          f"{p2['conv_after_restart'] == p2['conv']}   pending gone: "
          f"{not p2['pending_after_restart']}", flush=True)
    assert same_rows, "the fold wrote or lost a row"
    assert same_keys and same_conv, "the fold changed what the store holds"
    assert len(reach) == len([t for t, x in p2["probes"].items()
                             if x["kind"] == "folded" and p2["elig"].get(x["pair"])]), \
        "a phrasing the fold claims to reach was not reached"
    assert not over, f"the fold answered something it claims to refuse: {over}"
    assert same, "the fold changed what an ask it does not answer says"
    assert exact_ok, "an exact phrasing stopped answering the way it did"
    assert guard, "the guard stopped refusing"
    assert not echoes, "an ask was answered with its own text"
    assert leaks_same, "the leak count changed"
    assert probes_wrote_nothing, "probing stored a pair"
    assert restart_ok, "the paraphrase did not survive the restart"
    assert not after_refused, "after a restart the fold answered something it refuses"
    return res


def main():
    out = {"beats": BEATS, "conversation": CONV,
           "probes": [{"text": t, "pair": p, "kind": k} for t, p, k in PROBES],
           "answer_of": ANSWER_OF, "houses": {}}
    out["houses"]["A_conversation_only"] = run(
        "A  conversation only (every pair was typed by a person, in one phrasing each)",
        None, "conv", beats=0)
    out["houses"]["B_after_book"] = run(
        "B  conversation after reading 05_questions (a book printed one of these keys first)",
        q.QA, "book")
    Path("docs/evidence").mkdir(parents=True, exist_ok=True)
    Path("docs/evidence/qa_paraphrase_live.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\nwrote docs/evidence/qa_paraphrase_live.json")


if __name__ == "__main__":
    main()
