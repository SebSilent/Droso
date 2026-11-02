"""AUDIT: does the book learn_qa path turn MARKED book questions into answerable QA
memories, and do those memories survive a restart?

Three parts, in the order the questions have to be answered.

  1 CORPUS  Is the pairing rule fed by real books at all? No organ, no learning, just the
            arithmetic `learn_qa` runs, replayed over every line of every book. This is the
            question an organ-level count cannot answer: a store of zero after 400 beats is
            either "the path is inert" or "I read too little", and only the corpus can say
            which. It also tests the tempting fix -- widening the adjacency window, and
            letting any statement line in the book be the answer -- so a decision to change
            the pairing rule would be made against a number instead of a hope.

  2 ARMS    The store, live, with and without the question-mark channel. Same book, same
            line order, same beats, one organ per arm. Counts what a pair has to pass
            through: calls, arithmetic refusals, admissions, refusals by provenance.

  3 RESTART save_state(force=True) -> a fresh organ -> load_state() -> ask every stored
            question again. The claim being measured is persistence, not lookup: a pair
            that answers from RAM and not from disk is a memory he has only until lunch.

Nothing here changes behaviour. It reads. `ELECTRIC_QA_STORE` and `ELECTRIC_ASK_MARKS` are
the flags under test and both default off; the guarded grader contract is not touched.
"""
import importlib.util as _u
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, ".")

import organs.neural_language as nl                       # noqa: E402
from connectome.engine import HybridEngine                # noqa: E402
from connectome.substrate import build_core_graph         # noqa: E402
from organs.tokenizer import TokenizerOrgan               # noqa: E402

BEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
FILES = sorted(Path("books").glob("*.txt"))
SYNTH = {"05_questions.txt", "grounded_primer.txt", "07_prose.txt"}
# A book with marks AND pairs (synthetic supervision), a real novel (marks, no pairs),
# and a mark-free book (the null). All three are needed: the first measures the path,
# the second measures whether a novel can feed it, the third is the control.
BOOKS = [("05_questions (synthetic, marks+pairs)",
          [i for i, p in enumerate(FILES) if p.name == "05_questions.txt"][0]),
         ("jane_eyre (real novel, 382 marks)",
          [i for i, p in enumerate(FILES) if "jane_eyre" in p.name][0]),
         ("01_caregiver (no marks at all)",
          [i for i, p in enumerate(FILES) if p.name.startswith("01_")][0])]


def words(ln):
    return [w for w in "".join(c if c.isalnum() else " "
                               for c in ln.lower()).split() if w]


def arithmetic(q, a):
    """`learn_qa`'s admission rule, copied rather than called so the corpus scan needs no
    organ. One role missing, one novel word, or no pair."""
    if not q or not a:
        return None
    qset, aset = set(q), set(a)
    missing = [i for i, w in enumerate(a) if w not in qset]
    novel = [w for w in q if w not in aset]
    if len(missing) != 1 or len(novel) != 1:
        return None
    return int(missing[0]), novel[0]


def part1_corpus():
    """Every book, every question line, three candidate sources for the A side."""
    out = {"books": {}, "totals": {}}
    tot = {"q_lines": 0, "next_pass": 0, "win6_pass": 0, "stmt_pass": 0,
           "stmt_false_order": 0}
    for p in FILES:
        raw = p.read_text(encoding="utf-8", errors="ignore").lower()
        lines = raw.splitlines()
        ws = [words(ln) for ln in lines]
        marks = [nl.question_mark_positions(ln) for ln in lines]
        trailing = [bool(ln.rstrip().endswith("?")) for ln in lines]
        stmt = defaultdict(list)
        for i, t in enumerate(ws):
            if t and not marks[i]:
                stmt[len(t)].append(i)
        b = {"q_lines": sum(trailing), "next_pass": 0, "win6_pass": 0,
             "stmt_pass": 0, "stmt_answer_is_question": 0, "false_order": 0}
        for i, q in enumerate(ws):
            if not q or not trailing[i]:
                continue
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            if nxt and arithmetic(q, nxt):
                b["next_pass"] += 1
            for k in range(1, 7):
                j = i + k
                if j >= len(ws) or not ws[j]:
                    break
                if arithmetic(q, ws[j]):
                    b["win6_pass"] += 1
                    break
            hit = None
            for j in (jj for k in range(len(q), len(q) + 4)
                      for jj in stmt.get(k, ())):
                if arithmetic(q, ws[j]):
                    hit = j
                    break
            if hit is not None:
                b["stmt_pass"] += 1
                if hit < i:                       # the "answer" precedes the question
                    b["false_order"] += 1
        out["books"][p.name] = b
        for k in ("q_lines", "next_pass", "win6_pass", "stmt_pass"):
            tot[k] += b[k]
        tot["stmt_false_order"] += b["false_order"]
    out["totals"] = tot
    real = {k: v for k, v in out["books"].items() if k not in SYNTH}
    tot["real_book_pairs_next_line"] = sum(v["next_pass"] for v in real.values())
    tot["real_book_pairs_win6"] = sum(v["win6_pass"] for v in real.values())
    tot["real_book_pairs_any_statement"] = sum(v["stmt_pass"] for v in real.values())
    return out


def build(store, marks, book_idx, state_path=None, prov=0):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=state_path)
    o.persist = state_path is not None
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0        # a measurement, not an afternoon
    o.EXPOSURE_MIN_REAL_S = 0.0
    o.exposure_speed_s = 0.0
    o.exposure_enabled = True
    o.social_drive = 1.0                      # attends every line: nothing is skipped
    o.books_dir = Path("books")
    o._book_idx = book_idx
    o.ELECTRIC_QA_STORE = bool(store)
    o.ELECTRIC_ASK_MARKS = bool(marks)
    o.ELECTRIC_QA_PROVENANCE = bool(prov)
    return o


def instrument(o):
    """Count what learn_qa was asked and what it said, without touching the organ."""
    tally = {"calls": 0, "learned": 0, "refused": 0, "reasons": defaultdict(int)}
    real = o.learn_qa

    def spy(q, a, provenance=None):
        r = real(q, a, provenance=provenance)
        tally["calls"] += 1
        if r.get("learned"):
            tally["learned"] += 1
        else:
            tally["refused"] += 1
            tally["reasons"][r.get("reason", "no tokens") or "no tokens"] += 1
        return r

    o.learn_qa = spy
    return tally


def read(o, beats):
    for _ in range(beats):
        o.expose_tick(world_dt=5.0)
    return o


def ask(o, key, punctuate=True):
    """Put a stored question back to him the way a person would type it."""
    text = key + ("?" if punctuate else "")
    r = o.answer(text)
    return {"answered": bool(r.get("answered")),
            "source": str(r.get("source") or ""),
            "said": str(r.get("response") or r.get("utterance") or "").strip()}


def part2_arms(beats):
    res = {}
    for label, idx in BOOKS:
        arms = {}
        for name, store, marks, prov in (
                ("S0 store=off marks=off prov=off", 0, 0, 0),
                ("S1 store=on  marks=off prov=off", 1, 0, 0),
                ("S2 store=on  marks=on  prov=off", 1, 1, 0),
                ("S3 store=on  marks=on  prov=on ", 1, 1, 1)):
            o = build(store, marks, idx, prov=prov)
            tally = instrument(o)
            read(o, beats)
            pos = int(getattr(o, "_book_line_pos", 0))
            marks_arr = list(getattr(o, "_book_marks", []) or [])[:pos]
            isq = list(getattr(o, "_book_is_q", []) or [])[:pos]
            interior = sum(1 for i, m in enumerate(marks_arr)
                           if m and not (i < len(isq) and isq[i]))
            stored = len(o.qa_store)
            arms[name] = {
                "lines_read": pos,
                "marked_lines": sum(1 for m in marks_arr if m),
                "trailing_lines": sum(1 for x in isq if x),
                "interior_only_lines": interior,
                "learn_qa_calls": tally["calls"],
                "pairs_learned": tally["learned"],
                "arithmetic_refused": tally["refused"],
                "stored_pairs": stored,
                "questions_with_a_memory": len({(v["prov"]["line"])
                                                for v in o.qa_store.values()}),
                # The learning side, which is what the ordering defect corrupts.
                "qa_pairs_seen": o.qa_pairs_seen,
                "interrogatives": len(o.interrogatives),
                "role_votes": sum(sum(v.values())
                                  for v in o.question_roles.values()),
                "reasons": {k: v for k, v in tally["reasons"].items()},
            }
        a1 = arms["S1 store=on  marks=off prov=off"]
        a2 = arms["S2 store=on  marks=on  prov=off"]
        a3 = arms["S3 store=on  marks=on  prov=on "]
        arms["DELTA marks on - off"] = {
            "stored_pairs": a2["stored_pairs"] - a1["stored_pairs"],
            "questions_with_a_memory": (a2["questions_with_a_memory"]
                                        - a1["questions_with_a_memory"]),
        }
        arms["DELTA provenance on - off"] = {
            "stored_pairs": a3["stored_pairs"] - a2["stored_pairs"],
            "qa_pairs_seen": a3["qa_pairs_seen"] - a2["qa_pairs_seen"],
            "role_votes": a3["role_votes"] - a2["role_votes"],
            "interrogatives": a3["interrogatives"] - a2["interrogatives"],
        }
        res[label] = arms
    return res


def part3_restart(beats):
    """Store -> disk -> fresh organ -> ask. On the book that actually yields pairs."""
    idx = BOOKS[0][1]
    o = build(1, 1, idx)
    read(o, beats)
    keys = sorted(o.qa_store)
    before = {k: ask(o, k) for k in keys}
    sp = Path("_tmp") / "qa_audit_state.json"
    sp.parent.mkdir(exist_ok=True)
    if sp.exists():
        sp.unlink()
    o.state_path = sp
    o.persist = True
    saved = o.save_state(force=True)
    o2 = build(1, 1, idx, state_path=sp)
    loaded = o2.load_state()
    after = {k: ask(o2, k) for k in keys}
    nopunct = {k: ask(o2, k, punctuate=False) for k in keys}
    return {
        "stored": len(keys),
        "saved": bool(saved.get("saved")),
        "state_bytes": sp.stat().st_size if sp.exists() else 0,
        "loaded": bool(loaded.get("loaded", True)) if isinstance(loaded, dict) else True,
        "store_after_load": len(o2.qa_store),
        "answerable_before_restart": sum(1 for v in before.values() if v["answered"]),
        "answerable_after_restart": sum(1 for v in after.values() if v["answered"]),
        "answered_by_qa_store_after_restart": sum(
            1 for v in after.values() if v["source"] == "electric_qa_store"),
        "exact_answer_line_after_restart": sum(
            1 for k, v in after.items()
            if v["said"] == " ".join(o.qa_store[k]["a"])),
        "answerable_without_the_mark": sum(1 for v in nopunct.values() if v["answered"]),
        "sources_after": _tally(v["source"] for v in after.values()),
        "sources_no_mark": _tally(v["source"] for v in nopunct.values()),
        "sample": [{"q": k, "a": " ".join(o.qa_store[k]["a"]),
                    "after": after[k]["said"], "src": after[k]["source"],
                    "noinfo": nopunct[k]["answered"]}
                   for k in keys[:6]],
    }


def part4_gate_and_vote(beats):
    """Two things part 3 could not see.

    (a) REACHABILITY THROUGH THE HOUSE'S OWN DOOR. `respond()` routes an utterance to
        `answer()` only when it contains a word he has LEARNED as an interrogative, and
        `_qa_store_answer` then demands a typed `?`. Asking through `answer()` directly,
        as part 3 did, skips the first gate. This is the number the house can actually
        realize.

    (b) THE VOTE. `learn_qa` teaches question_roles / interrogatives / answer_types and
        increments qa_pairs_seen BEFORE `_qa_keep` decides the pair is not an answer. So a
        pair the store refuses still teaches him which words ask, and which role they ask
        about. Measured here on the one real pair the corpus contains.
    """
    idx = BOOKS[0][1]
    o = build(1, 1, idx)
    read(o, beats)
    keys = sorted(o.qa_store)
    via_respond = {}
    for k in keys:
        r = o.respond(k + "?", speaker="you")
        via_respond[k] = {"answered": bool(r.get("answered")),
                          "source": str(r.get("source") or "")}
    # What he says to the same ask with the mark missing, and where it comes from.
    unmarked = {}
    for k in keys:
        r = o.respond(k, speaker="you")
        unmarked[k] = {"answered": bool(r.get("answered")),
                       "source": str(r.get("source") or ""),
                       "exact": str(r.get("response") or "").strip()
                                  == " ".join(o.qa_store[k]["a"])}
    # The same house with the provenance flag on: does it keep every pair it kept
    # before, and does the unmarked ask now reach the store instead of recall?
    o3 = build(1, 1, idx, prov=1)
    read(o3, beats)
    keys3 = sorted(o3.qa_store)
    unmarked3 = {}
    for k in keys3:
        r = o3.respond(k, speaker="you")
        unmarked3[k] = {"answered": bool(r.get("answered")),
                        "source": str(r.get("source") or ""),
                        "exact": str(r.get("response") or "").strip()
                                   == " ".join(o3.qa_store[k]["a"])}
    marked3 = {}
    for k in keys3:
        r = o3.respond(k + "?", speaker="you")
        marked3[k] = str(r.get("source") or "")
    # The vote leak, on the pair the corpus really contains.
    o2 = build(1, 1, [i for i, p in enumerate(FILES)
                      if "great_expectations" in p.name][0])
    before_int = set(o2.interrogatives)
    before_roles = dict(o2.question_roles.get("what", {}))
    lr = o2.learn_qa(["might", "a", "mere", "warmint", "ask", "what", "property"],
                     ["might", "a", "mere", "warmint", "ask", "whose", "property"],
                     provenance={"book": "gutenberg_4_great_expectations.txt",
                                 "line": 0, "mark": 6, "tokens": 7,
                                 "answer_is_question": True, "answer_line": 1})
    o4 = build(1, 1, [i for i, p in enumerate(FILES)
                      if "great_expectations" in p.name][0], prov=1)
    lr4 = o4.learn_qa(
        ["might", "a", "mere", "warmint", "ask", "what", "property"],
        ["might", "a", "mere", "warmint", "ask", "whose", "property"],
        provenance={"book": "gutenberg_4_great_expectations.txt", "line": 0,
                    "mark": 6, "tokens": 7, "answer_is_question": True,
                    "answer_line": 1})
    return {
        "stored": len(keys),
        "prov_on_stored": len(keys3),
        "same_pairs_kept": keys == keys3,
        "unmarked_ask_answered_prov_on": sum(1 for v in unmarked3.values()
                                            if v["answered"]),
        "unmarked_ask_from_store_prov_on": sum(
            1 for v in unmarked3.values()
            if v["source"] == "electric_qa_store"),
        "unmarked_ask_exact_line_prov_on": sum(1 for v in unmarked3.values()
                                               if v["exact"]),
        "marked_ask_from_store_prov_on": sum(
            1 for v in marked3.values() if v == "electric_qa_store"),
        "prov_on_vote_leak": {"learn_qa_said": lr4,
                              "qa_pairs_seen": o4.qa_pairs_seen,
                              "roles_for_what": dict(o4.question_roles.get("what", {})),
                              "answer_types_for_what": dict(
                                  o4.answer_types.get("what", {})),
                              "interrogatives": sorted(o4.interrogatives)},
        "answerable_through_respond": sum(1 for v in via_respond.values()
                                         if v["answered"]),
        "by_qa_store_through_respond": sum(
            1 for v in via_respond.values()
            if v["source"] == "electric_qa_store"),
        "unmarked_ask_answered": sum(1 for v in unmarked.values() if v["answered"]),
        "unmarked_ask_answered_from_store": sum(
            1 for v in unmarked.values()
            if v["source"] == "electric_qa_store"),
        "unmarked_ask_says_the_exact_line_anyway": sum(
            1 for v in unmarked.values() if v["exact"]),
        "unmarked_sources": _tally(v["source"] for v in unmarked.values()),
        "vote_leak": {
            "pair": "might a mere warmint ask what property / ...whose property",
            "learn_qa_said": lr,
            "store_kept": len(o2.qa_store),
            "qa_pairs_seen": o2.qa_pairs_seen,
            "roles_for_what_before": before_roles,
            "roles_for_what_after": dict(o2.question_roles.get("what", {})),
            "answer_types_for_what": dict(o2.answer_types.get("what", {})),
            "interrogatives_gained": sorted(set(o2.interrogatives) - before_int),
        },
    }


def _tally(it):
    d = defaultdict(int)
    for x in it:
        d[x or "(silent)"] += 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    report = {"beats": BEATS, "corpus": part1_corpus(),
              "arms": part2_arms(BEATS), "restart": part3_restart(BEATS),
              "gate_and_vote": part4_gate_and_vote(BEATS)}
    t = report["corpus"]["totals"]
    print("=== 1 CORPUS: can a real book feed the pairing rule? ===")
    print(f"  question lines in corpus        : {t['q_lines']}")
    print(f"  pairs passing arithmetic (next) : {t['next_pass']}")
    print(f"  pairs passing arithmetic (win 6): {t['win6_pass']}")
    print(f"  pairs vs ANY statement line     : {t['stmt_pass']} "
          f"(of which the 'answer' PRECEDES the question: {t['stmt_false_order']})")
    print(f"  REAL BOOKS ONLY  next={t['real_book_pairs_next_line']} "
          f"win6={t['real_book_pairs_win6']} any_statement={t['real_book_pairs_any_statement']}")

    print(f"\n=== 2 ARMS (store on, {BEATS} beats per arm) ===")
    for label, arms in report["arms"].items():
        print(f"  --- {label}")
        for name, a in arms.items():
            if name.startswith("DELTA"):
                print(f"      {name}: {a}")
                continue
            print(f"      {name}  lines={a['lines_read']:4d} "
                  f"marked={a['marked_lines']:3d} trailing={a['trailing_lines']:3d} "
                  f"interior_only={a['interior_only_lines']:3d} "
                  f"calls={a['learn_qa_calls']:4d} learned={a['pairs_learned']:3d} "
                  f"stored={a['stored_pairs']:3d} "
                  f"q_with_memory={a['questions_with_a_memory']:3d} "
                  f"seen={a['qa_pairs_seen']:3d} votes={a['role_votes']:3d} "
                  f"interrog={a['interrogatives']:2d}")
    for label, arms in report["arms"].items():
        for name, a in arms.items():
            if not name.startswith("DELTA") and a["reasons"]:
                top = dict(sorted(a["reasons"].items(),
                                  key=lambda kv: -kv[1])[:3])
                print(f"      refusal reasons [{label.split(' ')[0]} {name[:2]}]: {top}")
                break

    r = report["restart"]
    print("\n=== 3 RESTART (05_questions, store on, marks on) ===")
    for k in ("stored", "saved", "state_bytes", "store_after_load",
              "answerable_before_restart", "answerable_after_restart",
              "answered_by_qa_store_after_restart",
              "exact_answer_line_after_restart", "answerable_without_the_mark"):
        print(f"  {k:36s}: {r[k]}")
    print(f"  sources_after                       : {r['sources_after']}")
    print(f"  sources_no_mark                     : {r['sources_no_mark']}")
    for s in r["sample"]:
        print(f"    Q '{s['q']}'  book A '{s['a']}'  said '{s['after']}' "
              f"[{s['src']}]  without-? answered={s['noinfo']}")

    g = report["gate_and_vote"]
    print("\n=== 4 THE HOUSE'S OWN DOOR, AND THE VOTE ===")
    print(f"  stored pairs                          : {g['stored']}")
    print(f"  answerable through respond()          : "
          f"{g['answerable_through_respond']}/{g['stored']}")
    print(f"  ...answered BY THE STORE via respond(): "
          f"{g['by_qa_store_through_respond']}/{g['stored']}")
    print(f"  ask WITHOUT the typed ?  answered     : "
          f"{g['unmarked_ask_answered']}/{g['stored']}")
    print(f"  ...of those from the STORE            : "
          f"{g['unmarked_ask_answered_from_store']}/{g['stored']}")
    print(f"  ...saying the exact line anyway       : "
          f"{g['unmarked_ask_says_the_exact_line_anyway']}/{g['stored']}")
    print(f"  sources for the unmarked ask          : {g['unmarked_sources']}")
    print("  --- the same house with ELECTRIC_QA_PROVENANCE on:")
    print(f"      pairs kept (identical set?)         : "
          f"{g['prov_on_stored']}  identical={g['same_pairs_kept']}")
    print(f"      unmarked ask answered               : "
          f"{g['unmarked_ask_answered_prov_on']}/{g['stored']}")
    print(f"      ...answered FROM THE STORE          : "
          f"{g['unmarked_ask_from_store_prov_on']}/{g['stored']}")
    print(f"      ...saying the exact printed line    : "
          f"{g['unmarked_ask_exact_line_prov_on']}/{g['stored']}")
    print(f"      marked ask still from the store     : "
          f"{g['marked_ask_from_store_prov_on']}/{g['stored']}")
    p = g["prov_on_vote_leak"]
    print(f"      the refused pair now says           : {p['learn_qa_said']}")
    print(f"      qa_pairs_seen / roles for 'what'    : "
          f"{p['qa_pairs_seen']} / {p['roles_for_what']}")
    print(f"      answer_types / interrogatives       : "
          f"{p['answer_types_for_what']} / {p['interrogatives']}")
    v = g["vote_leak"]
    print(f"  --- the pair the store REFUSES and the vote ACCEPTS: {v['pair']}")
    print(f"      learn_qa returned                 : {v['learn_qa_said']}")
    print(f"      pairs kept in the store           : {v['store_kept']}")
    print(f"      qa_pairs_seen (the metric)        : {v['qa_pairs_seen']}")
    print(f"      roles for 'what' before / after   : "
          f"{v['roles_for_what_before']} -> {v['roles_for_what_after']}")
    print(f"      answer_types for 'what'           : {v['answer_types_for_what']}")
    print(f"      interrogatives gained             : {v['interrogatives_gained']}")

    # THE VERDICT. Everything above is a measurement; these are the claims the
    # improvement has to keep true, checked here rather than in prose.
    leak = g["vote_leak"]
    claims = [
        ("real novels feed the pairing rule nothing",
         t["real_book_pairs_next_line"] <= 1),
        ("the marks channel adds no pair (acquisition is not the channel's gap)",
         all(a["DELTA marks on - off"]["stored_pairs"] == 0
             for a in report["arms"].values())),
        ("provenance costs no memory: the same pairs are kept",
         g["same_pairs_kept"]),
        ("a refused pair teaches nothing under the flag",
         g["prov_on_vote_leak"]["qa_pairs_seen"] == 0
         and not g["prov_on_vote_leak"]["roles_for_what"]),
        ("a refused pair DOES teach today (the defect is real, not rhetorical)",
         leak["qa_pairs_seen"] == 1 and leak["roles_for_what_after"] == {"5": 1}),
        ("the store answers an unmarked ask only under the flag",
         g["unmarked_ask_answered_from_store"] == 0
         and g["unmarked_ask_from_store_prov_on"] == g["stored"]),
        ("the exact printed line is what comes back",
         g["unmarked_ask_exact_line_prov_on"] == g["stored"]),
        ("a marked ask is unaffected -- no regression on the path that worked",
         g["marked_ask_from_store_prov_on"] == g["stored"]),
        ("pairs survive a restart and stay answerable",
         r["answerable_after_restart"] == r["stored"]
         and r["store_after_load"] == r["stored"]),
    ]
    print("\n=== VERDICT ===")
    bad = 0
    for name, ok in claims:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        bad += 0 if ok else 1
    report["verdict"] = {"checks": [{"claim": n, "pass": bool(x)} for n, x in claims],
                         "failed": bad}
    print(f"\n{len(claims) - bad}/{len(claims)} claims hold")

    Path("docs/evidence").mkdir(exist_ok=True)
    Path("docs/evidence/book_qa_store_audit.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")
    print("\nwrote docs/evidence/book_qa_store_audit.json")
