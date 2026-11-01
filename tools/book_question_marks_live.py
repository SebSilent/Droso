"""A short LIVE-HOUSE check of the question-mark channel: real books, real exposure, four arms.

Not an A/B of answers. This asks the narrower question the channel makes a claim about: when
he READS a book, do the lines that were questions in the source end up as rows the house is
willing to quote as facts -- and does turning the channel on cost him a row?

Arms (one organ each, same book, same line order, same beats):

  A1 marks=off  admissibility=off   today's house
  A2 marks=off  admissibility=on    the tag read, but only what `is_q` already knew
  A3 marks=on   admissibility=off   the channel RECORDES, nothing consults it
  A4 marks=on   admissibility=on    the pair

What has to hold, and is asserted:
  * the same number of rows exists in every arm -- the channel touches no token and no
    chunking, so it can only rename rows, never create or destroy one;
  * A3 speaks EXACTLY what A1 speaks: marks alone are inaudible;
  * A4 tags no row A2 did not, on a line that carries no mark: the position math is right.

WHICH BOOK, and why it matters: `books/` opens on `01_caregiver.txt`, which contains NO
question mark anywhere -- as do 02, 03, 04 and 06_stories (36,000 lines). That is the whole
reason an earlier audit found "0 marked rows in 60,000". Reading book 0 measures nothing
here, so this check runs BOTH a dialogue-rich novel (Jane Eyre, 382 question lines in 2,579)
and a mark-free one, and the mark-free one must show four identical arms.
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

BEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 400
MR = 8
FILES = sorted(Path("books").glob("*.txt"))
BOOKS = {"jane_eyre (382 question lines)": [i for i, p in enumerate(FILES)
                                            if "jane_eyre" in p.name][0],
         "caregiver (no marks at all)": [i for i, p in enumerate(FILES)
                                         if p.name.startswith("01_")][0]}
GENERIC = ["who does the mouse chase", "where is the scarf", "what bites the latch"]


def rows_of(toks, mr=MR):
    """The rows one utterance creates, reproducing hear()'s windowing exactly."""
    if len(toks) <= mr:
        return [tuple(toks[:mr])]
    step_w = max(2, mr // 2)
    return [tuple(toks[i:i + mr])
            for i in range(0, max(1, len(toks) - mr + 1), step_w)]


def build(marks, admissible, book_idx):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=None)
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0        # a measurement, not an afternoon
    o.EXPOSURE_MIN_REAL_S = 0.0
    o.exposure_speed_s = 0.0
    o.exposure_enabled = True
    o.books_dir = Path("books")
    o.social_drive = 1.0                      # attends every line: nothing is skipped
    o._book_idx = book_idx                    # which book he opens, decided below
    o.ELECTRIC_ASK_MARKS = bool(marks)
    o.ELECTRIC_ASK_ADMISSIBILITY = bool(admissible)
    for t in _m.TELLS:
        o.hear(t, speaker="you")
    return o


def read(o, beats):
    for _ in range(beats):
        o.expose_tick(world_dt=5.0)
    return o


def attribute(o):
    """Which rows the READ lines created, and how each is tagged. expose_tick advances
    _book_line_pos one line per attended beat, so the lines it read are the prefix."""
    binder = o.cortex.binder
    pos = int(getattr(o, "_book_line_pos", 0))
    lines = list(getattr(o, "_book_lines", []) or [])[:pos]
    marks = list(getattr(o, "_book_marks", []) or [])[:pos]
    assert len(lines) == len(marks) == pos, f"parallel arrays broke at {pos}"
    q_rows = q_tag = s_rows = s_tag = 0
    q_only, s_only = set(), set()
    for i, toks in enumerate(lines):
        marked = bool(marks[i])
        for key in rows_of(toks):
            at = binder._seen.get(key)
            tagged = bool(at is not None and at < len(binder.meta)
                          and row_is_ask(binder.meta[int(at)]))
            if marked:
                q_rows += 1
                q_tag += tagged
                q_only.add(key)
            else:
                s_rows += 1
                s_tag += tagged
                s_only.add(key)
    return {"lines": pos, "q_lines": sum(1 for m in marks if m),
            "q_rows": q_rows, "q_tagged": q_tag, "q_quotable": q_rows - q_tag,
            "s_rows": s_rows, "s_tagged": s_tag,
            "rows_shared_by_question_and_statement": len(q_only & s_only),
            "rows_total": len(binder.meta)}


def pick_probes(book_idx, beats):
    """Questions the house has actually READ, asked back to it. A leak is an answer whose
    words come out of a remembered question, and the only way to find one is to ask
    something that is in the book."""
    o = read(build(True, True, book_idx), beats)
    pos = int(o._book_line_pos)
    lines, marks = o._book_lines[:pos], o._book_marks[:pos]
    q = [" ".join(t) for t, m in zip(lines, marks) if m]
    short = [x for x in q if len(x.split()) <= MR][:4]
    long = [x for x in q if len(x.split()) > MR][:2]
    # The leak SHAPE, measured in tests/test_electric_ask_marks.py: an asking one word
    # away from a line the book printed as a question. Asking the line back verbatim is
    # not where a question escapes -- his own ask is filtered from his own recall by the
    # qset guard -- so the near-miss is the case that has to be probed.
    near = [" ".join(list(x.split())[:-1] + ["that"]) for x in short[:2]]
    return short + long + near + GENERIC


def question_row_keys(o):
    """Every row the question lines created, arm-independently: the same lines and the
    same windowing, so a spoken string that appears here came out of a question."""
    pos = int(o._book_line_pos)
    keys = set()
    for t, m in zip(o._book_lines[:pos], o._book_marks[:pos]):
        if m:
            keys |= {" ".join(w) for w in rows_of(list(t))}
    return keys


def probe(o, questions, q_keys):
    """A LEAK is measured, not inferred: he spoke, and what he spoke is a row a question
    line made. The first version of this tool reported `dropped` from a trace key that
    does not exist -- every arm read None, which looked like 'no leak' and was really
    'not measured'. `ask_refused` is the refusal the admissibility gate names itself."""
    out = {}
    for q in questions:
        r = o.answer(q) or {}
        said = str(r.get("utterance") or r.get("response") or "").strip()[:70]
        reason = str(r.get("reason") or "")
        out[q] = {"spoken": bool(r.get("spoken")), "said": said,
                  "src": str(r.get("source") or ""),
                  "leaked": bool(r.get("spoken")) and said in q_keys,
                  "ask_refused": reason.startswith("what he remembers there is only"),
                  "reason": reason[:60]}
    return out


def main():
    res = {}
    for book_name, book_idx in BOOKS.items():
        beats = BEATS if "jane" in book_name else max(120, BEATS // 2)
        questions = pick_probes(book_idx, beats)
        print(f"\n=== {book_name}  ({beats} beats, {len(questions)} probes) ===")
        for name, marks, adm in (("A1", False, False), ("A2", False, True),
                                 ("A3", True, False), ("A4", True, True)):
            o = read(build(marks, adm, book_idx), beats)
            a = attribute(o)
            pr = probe(o, questions, question_row_keys(o))
            res[(book_name, name)] = {"marks": marks, "admissibility": adm,
                                      "attribution": a, "probes": pr,
                                      "leaks": sum(1 for x in pr.values()
                                                   if x["leaked"])}
            print(f"  {name} marks={int(marks)} admissibility={int(adm)}  "
                  f"lines={a['lines']:4} (q {a['q_lines']:3})  rows={a['rows_total']:5}  "
                  f"q_rows={a['q_rows']:4} tagged={a['q_tagged']:4} "
                  f"QUOTABLE={a['q_quotable']:4}  stmt_tagged={a['s_tagged']}  "
                  f"shared={a['rows_shared_by_question_and_statement']}")
        a1, a2, a3, a4 = (res[(book_name, k)]["attribution"]
                          for k in ("A1", "A2", "A3", "A4"))
        print(f"  quotable question rows: A2={a2['q_quotable']} -> A4={a4['q_quotable']}"
              f"   tagged by marks: +{a4['q_tagged'] - a2['q_tagged']}")
        print(f"  rows that exist: {a1['rows_total']} / {a2['rows_total']} / "
              f"{a3['rows_total']} / {a4['rows_total']} (must be equal)")
        assert a1["rows_total"] == a2["rows_total"] == a3["rows_total"] == a4["rows_total"], \
            "the channel must not create or destroy a row -- it renames rows, nothing else"
        assert a4["s_tagged"] == a2["s_tagged"], \
            "the channel tagged a row from an UNMARKED line: the position math is wrong"
        assert a3["s_tagged"] == a1["s_tagged"], \
            "marks alone moved a statement row's tag"
        lk = {k: res[(book_name, k)]["leaks"] for k in ("A1", "A2", "A3", "A4")}
        print(f"  LEAKS (spoke a row a question line made): "
              f"A1={lk['A1']} A2={lk['A2']} A3={lk['A3']} A4={lk['A4']}")
        assert lk["A4"] == 0, "the pair still recites a remembered question"
        assert lk["A3"] == lk["A1"], \
            "the tag alone changed what is spoken -- the gate is what acts, not the tag"
        same = [q for q in questions
                if res[(book_name, "A1")]["probes"][q]["said"]
                != res[(book_name, "A3")]["probes"][q]["said"]]
        assert not same, f"marks alone changed what the house says: {same}"
        print(f"  A1 vs A3 speak identically: {not same}")
        print("  probes:")
        for q in questions:
            v = {k: res[(book_name, k)]["probes"][q] for k in ("A1", "A2", "A3", "A4")}
            moved = len({x["said"] for x in v.values()}) > 1
            print(f"    {q!r:58} {'CHANGED' if moved else 'same'}")
            if moved:
                for k, x in v.items():
                    print(f"      {k} {'said=' + repr(x['said']) if x['spoken'] else 'silent':52}"
                          f" src={x['src']:20} leaked={x['leaked']!s:5}"
                          f" refused={x['ask_refused']}")

    json.dump({f"{b}|{k}": v for (b, k), v in res.items()},
              open("docs/evidence/book_question_marks_live.json", "w",
                   encoding="utf-8"), indent=1)
    print("\nwrote docs/evidence/book_question_marks_live.json")


if __name__ == "__main__":
    main()
