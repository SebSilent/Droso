"""AUDIT: does the book `learn_qa` path give him ANSWERABLE memories, and do they survive a
restart?  Run:  .venv\\Scripts\\python.exe tools/book_qa_learn_audit.py [beats]

What the path claims to be (organs/neural_language.py): "A question immediately followed by its
answer is the only supervision anywhere in this system, and it is enough."

What this measures, per book, per arm:

  1. PAIRING     how many question lines were paired with their next line, how many passed
                 learn_qa's structural gate, and why the rest were refused.
  2. STORAGE     whether the accepted PAIR -- the question linked to its answer -- is kept
                 anywhere, or thrown away after it casts its role vote.
  3. ANSWERABLE  ask each accepted pair's question the way the book printed it, and count what
                 he answers, from which path, and how often that is the pair's own filler.
  4. RESTART     save_state(force) -> fresh organ -> load_state(), which also applies the
                 cortex delta: this is the house's real restart path.
  5. A/B         the store arm is diffed against the no-store arm question by question, so a
                 gained answer and a LOST one are both visible.

Arms:
  marks=off store=off   the house before the channel
  marks=on  store=off   the channel, votes only -- what the audit measured as of the channel work
  marks=on  store=on    ELECTRIC_QA_STORE: accepted pairs kept, with provenance

Books are chosen deliberately: `05_questions.txt` and `grounded_primer.txt` are written as Q/A
pairs, so they are the BEST case this path can have; `gutenberg_4_jane_eyre.txt` is a real novel,
382 question lines, and is what he actually reads.
"""
import importlib.util as _u
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import organs.neural_language as nl                       # noqa: E402
from organs.higher_cortex import row_is_ask               # noqa: E402
from connectome.engine import HybridEngine                # noqa: E402
from connectome.substrate import build_core_graph         # noqa: E402
from organs.tokenizer import TokenizerOrgan               # noqa: E402

_s = _u.spec_from_file_location("rev_nm", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)

BEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
MR = 8
FILES = sorted(Path("books").glob("*.txt"))


def _i(needle):
    return next(k for k, p in enumerate(FILES) if needle in p.name)


BOOKS = {"05_questions (written as Q/A)": _i("05_questions"),
         "grounded_primer (written as Q/A)": _i("grounded_primer"),
         "jane_eyre (a real novel)": _i("jane_eyre")}

TMP = Path("_tmp/qa_audit")
TMP.mkdir(parents=True, exist_ok=True)
ARMS = ((False, False), (True, False), (True, True))


def rows_of(toks, mr=MR):
    """The rows one utterance creates, reproducing hear()'s windowing exactly."""
    if len(toks) <= mr:
        return [tuple(toks[:mr])]
    step_w = max(2, mr // 2)
    return [tuple(toks[i:i + mr])
            for i in range(0, max(1, len(toks) - mr + 1), step_w)]


def build(book_idx, marks, store, state_path=None):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=state_path)
    o.persist = state_path is not None
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    o.EXPOSURE_MIN_REAL_S = 0.0
    o.exposure_speed_s = 0.0
    o.exposure_enabled = True
    o.books_dir = Path("books")
    o.social_drive = 1.0
    o._book_idx = book_idx
    o.ELECTRIC_ASK_MARKS = bool(marks)
    o.ELECTRIC_ASK_ADMISSIBILITY = True
    o.ELECTRIC_QA_STORE = bool(store)
    o.ELECTRIC_ANSWER = True
    for t in _m.TELLS:
        o.hear(t, speaker="you")
    return o


def read(o, beats):
    for _ in range(beats):
        o.expose_tick(world_dt=5.0)
    return o


def answer_line_kept(o, q, a):
    """Is the accepted pair's LINK anywhere in the organ's own state?  Keyed search: the
    question text must appear as a key AND the answer's words must appear in what it maps to.
    Rows are not a pair: the binder holds the answer line as a window of tokens with no record
    that it answered anything."""
    qtext = " ".join(q)
    for attr, val in list(vars(o).items()):
        if not isinstance(val, dict):
            continue
        for k, v in val.items():
            if str(k).strip().lower() == qtext:
                if a and any(str(t) in json.dumps(v, default=str) for t in a[:1]):
                    return attr
    return None


def ask_of(p):
    return " ".join(p["q"]) + "?"


def srcs_of(responses):
    out = {}
    for v in responses.values():
        out[v["source"]] = out.get(v["source"], 0) + 1
    return out


def run_arm(name, idx, marks, store):
    tag = f"{'marks' if marks else 'nomarks'}_{'store' if store else 'nostore'}"
    sp = TMP / f"st_{tag}.json"
    for extra in (sp, Path(str(sp) + ".cortex.delta.json")):
        if extra.exists():
            extra.unlink()                 # an arm must not inherit another's memory
    o = build(idx, marks, store, sp)
    pairs = []
    orig = o.learn_qa

    def spy(q, a, provenance=None, _o=orig, _p=pairs):
        r = _o(q, a, provenance=provenance)
        _p.append({"q": list(q), "a": list(a), "res": dict(r),
                   "prov": dict(provenance or {})})
        return r
    o.learn_qa = spy
    read(o, BEATS)

    passed = [p for p in pairs if p["res"].get("learned")]
    refused = [p for p in pairs if not p["res"].get("learned")]
    reasons = {}
    for p in refused:
        r = str(p["res"].get("reason", "?"))
        key = r.split(" roles")[0] + " missing" if "roles" in r else r
        reasons[key] = reasons.get(key, 0) + 1

    # only the lines he actually READ, not the whole loaded book
    pos = int(getattr(o, "_book_line_pos", 0))
    mk = (getattr(o, "_book_marks", None) or [])[:pos]
    bl = (getattr(o, "_book_lines", None) or [])[:pos]
    bq = (getattr(o, "_book_is_q", None) or [])[:pos + 1]
    marks_lines = sum(1 for m in mk if m)
    interior = sum(1 for m, t in zip(mk, bl)
                   if m and len(t) > 1 and m[-1] < len(t) - 1)
    links = sum(1 for p in passed if answer_line_kept(o, p["q"], p["a"]))
    rows = o.cortex.binder._seen
    ans_rows = sum(1 for p in passed if any(k in rows for k in rows_of(p["a"])))

    # What the store's admission rule refuses: an accepted pair whose answer line was itself
    # printed as a question. In the real corpus this is the ONLY pair novels yield.
    q_by_a = 0
    for p in passed:
        for i, t in enumerate(bl):
            if t == p["q"] and i + 1 < len(bq) and bq[i + 1]:
                q_by_a += 1
                break

    def ask_all(org):
        out = {}
        for p in passed:
            r = org.answer(ask_of(p))
            resp = str(r.get("response") or "")
            out[ask_of(p)] = {
                "answered": bool(r.get("answered")) and bool(resp.strip()),
                "response": resp,
                "source": str(r.get("source") or r.get("reason") or "?"),
                "right": bool(resp.strip())
                         and str(p["res"].get("filler", "")) in resp}
        return out

    now = ask_all(o)
    sv = o.save_state(force=True)
    o2 = build(idx, marks, store, sp)
    ld = o2.load_state()
    after = ask_all(o2)

    stored = len(o.qa_store)
    stored_after = len(o2.qa_store)

    print(f"  [{tag:18s}] paired={len(pairs):4d} passed={len(passed):4d} "
          f"refused={len(refused):4d}  stored={stored:4d}")
    print(f"      marked lines={marks_lines:4d} (interior {interior})   "
          f"pair LINKED in state={links}/{len(passed)}   answer line as rows="
          f"{ans_rows}/{len(passed)}")
    print(f"      accepted pairs whose ANSWER LINE IS ITSELF A QUESTION={q_by_a}"
          f"/{len(passed)}   refused reasons={reasons}")
    print(f"      ANSWERABLE now={sum(1 for v in now.values() if v['answered'])}"
          f"/{len(passed)}  right-filler="
          f"{sum(1 for v in now.values() if v['right'])}  "
          f"sources={srcs_of(now)}")
    print(f"      saved={sv.get('saved')} mode={sv.get('mode')} loaded={bool(ld)}   "
          f"stored after restart={stored_after}")
    print(f"      ANSWERABLE after restart="
          f"{sum(1 for v in after.values() if v['answered'])}/{len(passed)}  right-filler="
          f"{sum(1 for v in after.values() if v['right'])}   role votes "
          f"{sum(sum(v.values()) for v in o.question_roles.values())}->"
          f"{sum(sum(v.values()) for v in o2.question_roles.values())}, pairs_seen "
          f"{o.qa_pairs_seen}->{o2.qa_pairs_seen}")

    del o, o2
    return {"paired": len(pairs), "passed": len(passed), "refused": len(refused),
            "reasons": reasons, "marked_lines": marks_lines, "interior_marked": interior,
            "pairs_linked_in_state": links, "answer_rows_present": ans_rows,
            "accepted_answer_is_question_too": q_by_a, "stored": stored,
            "stored_after": stored_after,
            "answerable_before": sum(1 for v in now.values() if v["answered"]),
            "right_before": sum(1 for v in now.values() if v["right"]),
            "answerable_after": sum(1 for v in after.values() if v["answered"]),
            "right_after": sum(1 for v in after.values() if v["right"]),
            "now": now, "after": after}


def main():
    report = {}
    for name, idx in BOOKS.items():
        print(f"\n=== {name}  ({BEATS} beats) ===")
        arms = {}
        for marks, store in ARMS:
            arms[(marks, store)] = run_arm(name, idx, marks, store)
        base = arms[(True, False)]
        new = arms[(True, True)]
        gained = [q for q in new["now"]
                  if new["now"][q]["answered"] and not base["now"].get(q, {})["answered"]]
        lost = [q for q in base["now"]
                if base["now"][q]["answered"] and not new["now"].get(q, {})["answered"]]
        changed = [q for q in base["now"]
                   if base["now"][q]["answered"] and new["now"].get(q, {})["answered"]
                   and base["now"][q]["response"] != new["now"][q]["response"]]
        print(f"    STORE A/B (marks on, store off -> on): answered "
              f"{base['answerable_before']} -> {new['answerable_before']}   "
              f"gained={len(gained)} lost={len(lost)} reworded={len(changed)}")
        print(f"    after restart: answered {base['answerable_after']} -> "
              f"{new['answerable_after']}   right-filler {base['right_after']} -> "
              f"{new['right_after']}   stored pairs kept {new['stored']} -> "
              f"{new['stored_after']}")
        for q in gained[:4]:
            print(f"      GAINED {q[:52]:54s} -> {new['now'][q]['response'][:56]}")
        for q in lost[:4]:
            print(f"      LOST   {q[:52]:54s} was {base['now'][q]['response'][:56]}")
        for q in changed[:4]:
            print(f"      REWORD {q[:52]:54s} {base['now'][q]['response'][:34]} -> "
                  f"{new['now'][q]['response'][:34]}")
        report[name] = {"paired": base["paired"], "passed": base["passed"],
                        "refused_reasons": base["reasons"],
                        "marked_lines": base["marked_lines"],
                        "interior_marked": base["interior_marked"],
                        "pairs_linked_in_state": base["pairs_linked_in_state"],
                        "answer_rows_present": base["answer_rows_present"],
                        "accepted_answer_is_question_too":
                            base["accepted_answer_is_question_too"],
                        "arms": {f"{'marks' if k[0] else 'nomarks'}_"
                                 f"{'store' if k[1] else 'nostore'}":
                                 {kk: vv for kk, vv in v.items()
                                  if kk not in ("now", "after")}
                                 for k, v in arms.items()},
                        "store_ab": {"answered_before": [base["answerable_before"],
                                                         new["answerable_before"]],
                                     "gained": gained, "lost": lost, "reworded": changed,
                                     "answered_after": [base["answerable_after"],
                                                        new["answerable_after"]],
                                     "right_after": [base["right_after"],
                                                     new["right_after"]],
                                     "stored": [new["stored"], new["stored_after"]]}}
    out = Path("docs/evidence/book_qa_learn_audit.json")
    out.write_text(json.dumps({"beats": BEATS, "books": report}, indent=2),
                   encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
