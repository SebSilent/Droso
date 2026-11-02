"""What it takes to make a house answer `mira` to a question it refused a minute earlier.

Found by `tools/electric_learn_live.py`, which records that the control and teach arms say nothing
to `who does the lantern belong to` in the life they were taught in and answer `mira` after a
restart. That reads as "the restart makes it worse". It is not what happens, and the way this file
knows is that it tried to prove the restart claim and could not:

  GRID  -- 24 cells, every combination of (the unrelated question row heard?) x (restarted?) x
           (three earlier asks?) for control and teach: **`mira` in none of them.** Every cell
           refuses, coverage 0% / 50% / 53%. Learn answers the verbatim tell in all 24.
  REPLICA -- the learn-live tool's own sequence (`ask_all` in the taught life, save, restart,
           `ask_all` again): control and teach refuse live and answer `mira` restarted. Learn
           answers the verbatim tell in both phases.

So the restart is not the cause, and neither is the one question row this file was written to
blame. What reproduces is the whole life: the house's own earlier asks, six of them, plus the
`who does the mouse chase to` / `who does the mouse chase` pair it was left with at the end of the
round, carried across the save. A remembered question can carry a *different* question over the
coverage gate, and once the gate is open the shape arbiter parses the preposition `to` as the verb
(`{"kind": "object_unknown", "subject": ["lantern"], "verb": "to", "tail": []}`) and lifts `mira`
out of the tell. The word it lifts is the right word -- Mira is who the lantern belongs to -- which
is why this is recorded as a reachability defect and not as an invention.

It is PRE-EXISTING, and the replica arm is the evidence for that word: it reproduces in CONTROL,
where no ELECTRIC flag is on at all, on an organ this task never edited (`git diff --stat HEAD --
organs/` is empty). Learn mode neither causes it nor is bitten by it: in every cell and in the
replica, the full mode answers that ask with the whole tell from the keyed inventory, so the
one-word path is never reached. And in the teach replica `ask_hits_dropped` is 0 -- admissibility
was ON and still did not intercept this, because the row that opened the gate is not the row that
answered: the gate is upstream of admissibility, and the arbiter is downstream of both.

The one row this file was written to blame is `who does the mouse chase to` -- a question the live
house heard at the end of its probe round, saved into the cortex and reloaded off the .npz at the
next boot. It is not the asked question and it is not an answer to anything, and the grid says it
is not sufficient either: it is one of several remembered questions that add up to a house that can
reach this ask at all.

Run:  python tools/electric_restart_qrow.py     ->  docs/evidence/electric_restart_qrow.json
"""
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.electric_learn_live as L    # noqa: E402

REV = "who does the lantern belong to"
TELL = "the lantern belongs to Mira"
EVIDENCE = Path("docs/evidence/electric_restart_qrow.json")


ROUND = ["what ring the bell", "what rings the bell", "what bites the latch"]


def cell(mode, heard, restart, asked_first):
    """One house, one factor set, one ask -- through the same boot the learn-live tool uses.

    `asked_first` is the third factor, and it is here because the first version of this file ran a
    2x2 and cell D did NOT reproduce: the row and the restart together still refused at 50%
    coverage. The learn-live tool asks its whole probe round before the reverse ask, in each life,
    so a house there has three or four questions in it by the time the reverse ask is asked -- and
    that is the configuration that answers `mira`.
    """
    tag = f"qrow_{mode}_{int(heard)}_{int(restart)}_{int(asked_first)}"
    root = L.TMP / "root" / tag
    for p in (root, L.TMP / "sess" / tag):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    (root / "state").mkdir(parents=True, exist_ok=True)
    lang = L.boot(tag, mode, root)
    L.teach(lang)
    if heard:
        lang.hear(L.STRANDED, speaker="you")
        lang._qa_pending = None
    if restart:
        sdir = L.TMP / "sess" / tag
        lang.save_state(force=True)
        for f in sdir.iterdir():
            if f.is_file():
                shutil.copy2(f, root / "state" / f.name)
        lang = L.boot(tag, mode, root)
        loaded = lang.load_state() or {}
        assert loaded.get("loaded"), f"{tag}: restarted house loaded nothing"
    if asked_first:
        # The same asks the learn-live tool puts in front of the reverse ask, in the same order.
        for q in ROUND:
            lang.answer(q)
    r = lang.answer(REV) or {}
    tr = r.get("retrieval") or {}
    parser = tr.get("parser") or r.get("parser") or {}
    return {"mode": mode, "row_heard": heard, "restarted": restart,
            "asked_first": asked_first,
            "ask": REV,
            "answered": bool(r.get("answered")),
            "said": str(r.get("utterance") or "").strip(),
            "source": str(r.get("source") or ""),
            "reason": str(r.get("reason") or "")[:120],
            "shape": parser.get("shape") if isinstance(parser, dict) else None,
            "ask_hits_dropped": tr.get("ask_hits_dropped"),
            "interrog_who": lang.is_interrogative("who"),
            "question_roles": sorted(lang.question_roles.keys())}


def replica(mode):
    """The learn-live tool's OWN sequence -- `ask_all` in the life it was taught in, save, restart,
    `ask_all` again -- because the 24-cell grid above never produced `mira` and this did. Whatever
    the fourth factor is, it is something `ask_all` does that my approximation of it does not, so
    this cell is the one that has to be reported, with the pool it is answering out of.
    """
    tag = f"qrow_replica_{mode}"
    root = L.TMP / "root" / tag
    for p in (root, L.TMP / "sess" / tag):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    (root / "state").mkdir(parents=True, exist_ok=True)
    lang = L.boot(tag, mode, root)
    L.teach(lang)
    live = L.ask_all(lang)
    sdir = L.TMP / "sess" / tag
    lang.save_state(force=True)
    for f in sdir.iterdir():
        if f.is_file():
            shutil.copy2(f, root / "state" / f.name)
    lang2 = L.boot(tag, mode, root)
    assert (lang2.load_state() or {}).get("loaded"), f"{tag}: loaded nothing"
    post = L.ask_all(lang2)
    rows = [str(t) for t in (getattr(lang2, "_taught_says", {}) or {}).keys()]
    return {"mode": mode, "sequence": "ask_all x2 with a save between (the learn-live tool's own)",
            "live_reverse": live["reverse"], "restarted_reverse": post["reverse"],
            "restarted_rows": rows, "restarted_row_count": len(rows)}


def main():
    t0 = time.time()
    bad = []
    cells = [cell(m, h, rs, af)
             for m in ("control", "teach", "learn")
             for h in (False, True)
             for rs in (False, True)
             for af in (False, True)]
    reps = [replica(m) for m in ("control", "teach", "learn")]
    for rp in reps:
        for ph in ("live_reverse", "restarted_reverse"):
            s = rp[ph]["said"]
            if s and s.lower() not in L.SPOKEN_L and s.lower() not in L.WORDS:
                bad.append(f"replica {rp['mode']}/{ph}: invented {s!r}")
        print(f"  {rp['mode']:8s} REPLICA(ask_all x2): live={rp['live_reverse']['said']!r} "
              f"restarted={rp['restarted_reverse']['said']!r} "
              f"src={rp['restarted_reverse']['src'][:14]!r} "
              f"reason={rp['restarted_reverse']['reason'][:34]!r} "
              f"rows={rp['restarted_row_count']}")
    for c in cells:
        key = (c["row_heard"], c["restarted"], c["asked_first"])
        said = c["said"]
        # Nothing may say a sentence nobody told it. `mira` passes: it is a word inside a tell.
        if said and said.lower() not in L.SPOKEN_L and said.lower() not in L.WORDS:
            bad.append(f"{c['mode']}/{key}: invented {said!r}")
        if c["mode"] == "learn":
            if said != TELL:
                bad.append(f"learn/{key}: expected the verbatim tell, said {said!r}")
        else:
            # The narrow arms may refuse and may lift `mira`. Anything else is a new answer, and
            # the point of running eight cells is to be able to say that no cell produced one.
            if said not in ("", "mira"):
                bad.append(f"{c['mode']}/{key}: a third answer {said!r} "
                           f"(reason {c['reason'][:40]!r})")
    mira_cells = sorted({(c["row_heard"], c["restarted"], c["asked_first"])
                         for c in cells if c["said"] == "mira"})
    # The safety claim, stated as something that can fail: a remembered question row is a
    # necessary condition for the one-word answer. If a cell lifts `mira` with no question row in
    # the house, this file has found a wider trigger than the one it was written about.
    if mira_cells and not all(k[0] for k in mira_cells):
        bad.append(f"`mira` reached without a remembered question row: {mira_cells}")
    if any(c["said"] == "mira" for c in cells if c["mode"] == "learn"):
        bad.append("learn mode reached the one-word answer somewhere -- the keyed inventory is not "
                   "answering first in every cell")
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "seconds": round(time.time() - t0, 1),
           "ask": REV,
           "row_heard": L.STRANDED,
           "cells": cells,
           "replica": reps,
           "learn_answers_every_cell": all(c["said"] == TELL for c in cells
                                           if c["mode"] == "learn"),
           "mira_cells_row_restart_askedfirst": mira_cells,
           "mira_arms": sorted({c["mode"] for c in cells if c["said"] == "mira"}),
           "interrogative_who_anywhere": any(c["interrog_who"] for c in cells),
           "failures": bad}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for c in cells:
        print(f"  {c['mode']:8s} row={int(c['row_heard'])} restart={int(c['restarted'])} "
              f"asked={int(c['asked_first'])} "
              f"-> {c['said']!r:30s} src={c['source'][:14]!r:16s} "
              f"reason={c['reason'][:38]!r} shape={json.dumps(c['shape'], ensure_ascii=False)}")
    if bad:
        print(f"[restart-qrow] FAILURES ({len(bad)}):")
        for b in bad:
            print("   -", b)
        return 1
    print(f"[restart-qrow] clean: {len(cells)} grid cells + {len(reps)} replicas, "
          f"`mira` in {len(mira_cells)} of the grid and {len([r for r in reps if r['restarted_reverse']['said'] == 'mira'])} "
          f"replicas -> {EVIDENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
