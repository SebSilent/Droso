"""ELECTRIC C3 -- LONGEVITY: repeated teach / consolidate / restart cycles.

C1 and C2 each ran ONE life. This runs three, teaching 5 NEW facts in each, and asks
every fact taught so far back in paraphrase after every cycle. The question is not
"does a fact survive a restart" (C2 answered that for the keyed inventory) but whether
the inventory and the old path DEGRADE with use:

  * retention by cohort age -- does a fact taught in cycle 1 still answer in cycle 3?
  * interference -- does a later cohort's teaching damage an earlier cohort's answers?
  * displacement -- the binder is a 60,000-row FIFO and consolidation replays 600
    corpus sentences per cycle. The keyed _taught_says inventory CANNOT be evicted, but
    the old path's binder rows CAN, so the path distribution per cohort is where
    longevity failure should first show up.
  * refusals and confabulations, counted separately, per cohort.

FACTS ARE DISJOINT BY CONSTRUCTION. All 15 are drawn in ONE call to E1's generator,
whose `used` set is per-call: "one role per word across the batch, so no two facts can
be confused with each other by a shared content word". So shared-word interference is
designed OUT, not overlooked -- any damage measured here is damage from the cycles
themselves, and a word-collision arm is a separate experiment.

RESTART IS SIMULATED, NOT REAL: each cycle builds a fresh organ object over the same
state file, exactly as C2 did. A real serve.py shutdown/startup is not tested.

Teach mode is switched off before consolidate() as defence in depth. C2's hazard arm
(docs/electric_c2_hazard.md) showed leaving it on pollutes NOTHING -- consolidation
never reaches hear(), the only writer of _taught_says -- so this is a choice, not a
measured necessity.

Usage:
  .venv\\Scripts\\python.exe tools\\electric_longevity.py --cycles 3 --per-cycle 5 --seed 1
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.electric_generalise import (                   # noqa: E402
    build, grade, seed_state, te)

LIVE_STATE = "language_state.json"


def probe(organ, facts, content_words):
    """Ask every fact back twice: same-words control (T) and held-out paraphrase (H).

    Through answer(), the real entry point -- NOT live(). answer() calls
    live(text, learn=True, speaker="you") internally, so each question WIRES the
    connectome: probing perturbs the system it is measuring, which is one of the
    things this experiment is about (see the ORDER column, first-half vs second-half
    of the same probe pass).
    """
    out = []
    for f in facts:
        for which in ("T", "H"):
            ask = f["ask_T"] if which == "T" else f["ask_H"]
            t0 = time.perf_counter()
            rep = organ.answer(ask)
            said = str(rep.get("utterance") or rep.get("response") or "").strip()
            spoken = bool(rep.get("spoken"))
            out.append({
                "n": f["n"], "which": which, "frame": f["frame_H"],
                "ask": ask, "need": f["answer_H"], "said": said,
                "source": str(rep.get("source") or ""),
                "answered": bool(rep.get("answered")),
                "licensed_refusal": bool(rep.get("licensed_refusal")),
                "verdict": grade(f, said, spoken),
                "ms": round((time.perf_counter() - t0) * 1000, 1),
                "contam": sorted(w for w in _toks(said)
                                 if w in content_words
                                 and w not in (f["a"], f["v"], f["b"]))
            })
    return out


def _toks(text):
    import re
    return set(re.findall(r"[a-z]{2,}", str(text or "").lower()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=3)
    ap.add_argument("--per-cycle", type=int, default=5)
    ap.add_argument("--budget", type=int, default=200,
                    help="consolidate() rows per call, per cycle")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--keep", action="store_true", help="print every ask")
    ap.add_argument("--probe-electric", choices=("on", "off"), default="on", help=(
        "off = probe with all three ELECTRIC flags down, so answer() CANNOT consult the "
        "keyed _taught_says inventory and only the binder rows carry the memory. That is "
        "the displacement test: the inventory is a dict and cannot be FIFO-evicted, so an "
        "on-probe can report perfect retention while the old path has already lost the "
        "fact. Teaching still happens with ELECTRIC on in both arms."))
    args = ap.parse_args()

    total = args.cycles * args.per_cycle
    scratch = ROOT / "_tmp" / "electric_longevity"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    state = seed_state(scratch)

    print(f"ELECTRIC C3 -- LONGEVITY   {args.cycles} cycles x {args.per_cycle} new "
          f"facts = {total} facts, budget {args.budget}, seed {args.seed}\n"
          f"scratch {scratch}\n")

    # Draw ALL facts in one generator call so the disjointness guarantee holds across
    # the whole experiment, then hand out slices per cycle.
    g0 = build(state, True)
    gen = te.generate(g0, total, args.seed)
    facts = gen["facts"]
    for i, f in enumerate(facts):
        f["cycle"] = i // args.per_cycle + 1        # which cohort this fact belongs to
    del g0
    content_words = {w for f in facts for w in (f["a"], f["v"], f["b"])}
    print(f"generator: pool {gen['pool_size']} live words, {gen['attempts']} attempts, "
          f"{gen['binder_collisions']} binder collisions; {len(content_words)} distinct "
          f"content words over {len(facts)} facts (disjoint by construction)")

    cycles_out = []
    taught_so_far = []
    for c in range(1, args.cycles + 1):
        cohort = facts[(c - 1) * args.per_cycle: c * args.per_cycle]
        taught_so_far = taught_so_far + cohort
        print(f"\n=== CYCLE {c} ==========================================================")

        # ---- a fresh organ over the same file: the restart ----
        o = build(state, True)
        o.ELECTRIC_TEACH = True
        inv_before = {k: sorted(v) for k, v in o._taught_says.items()}
        n_before = sum(len(v) for v in o._taught_says.values())
        subj_before = len(o._taught_says)
        for f in cohort:
            o.hear(f["tell"], speaker="you")
        n_after = sum(len(v) for v in o._taught_says.values())
        # A cohort fact whose tell was already held under the same subject would be
        # silently dropped by first-tell-wins; disjointness should prevent it, so any
        # hit here means the disjointness guarantee failed and the count is a lie.
        clobbered = [f["tell"] for f in cohort
                     if f["a"] in inv_before and f["v"] in inv_before[f["a"]]]
        print(f"restart #{c}: loaded {n_before} taught facts ({subj_before} subjects); "
              f"taught {len(cohort)} new -> {n_after} ({len(o._taught_says)} subjects)"
              + (f"  CLOBBERED BY FIRST-TELL-WINS: {clobbered}" if clobbered else ""))

        # ---- consolidate ----
        o.ELECTRIC_TEACH = False
        t0 = time.perf_counter()
        stats = o.consolidate(budget=args.budget)
        csec = round(time.perf_counter() - t0, 1)
        print(f"consolidate: {stats.get('rows_scanned')} scanned, "
              f"{stats.get('rows_urgent')} urgent, {stats.get('rows_replayed')} replayed "
              f"x {stats.get('passes')} passes, {csec}s")
        n_post = sum(len(v) for v in o._taught_says.values())
        print(f"inventory after consolidation: {n_post} facts, "
              f"{len(o._taught_says)} subjects, _absence_inv {len(o._absence_inv)}")

        # ---- save, then restart and probe ----
        o.save_state(force=True)
        size_kb = (scratch / LIVE_STATE).stat().st_size // 1024
        subjects_post = len(o._taught_says)
        absence_post = len(o._absence_inv)
        del o
        print(f"save: {size_kb} KB, {subjects_post} subjects in the inventory")

        p = build(state, args.probe_electric == "on")
        rows = probe(p, taught_so_far, content_words)
        cycle_of = {f["n"]: f["cycle"] for f in taught_so_far}
        by_cohort = {}
        for f in taught_so_far:
            by_cohort.setdefault(f["cycle"], {"H": {}, "T": {}})
        for r in rows:
            cyc = cycle_of[r["n"]]
            by_cohort[cyc][r["which"]][r["verdict"]] = \
                by_cohort[cyc][r["which"]].get(r["verdict"], 0) + 1
        paths_h = {}
        for r in rows:
            if r["which"] == "H":
                paths_h[r["source"]] = paths_h.get(r["source"], 0) + 1
        contam = [r for r in rows if r["which"] == "H" and r["contam"]
                  and r["verdict"] != "correct"]
        print(f"probe after cycle {c}: {len(taught_so_far)} facts x 2 frames")
        for cyc in sorted(by_cohort):
            h = by_cohort[cyc]["H"]
            print(f"  cohort {cyc} (age {c - cyc}) at cycle {c}: "
                  f"H correct {h.get('correct',0)}/{args.per_cycle} "
                  f"confab {h.get('confabulation',0)} refuse {h.get('refusal',0)} "
                  f"other {h.get('other',0)} silence {h.get('silence',0)}")
        print(f"  H paths: {paths_h}")
        print(f"  contaminated non-correct H replies: {len(contam)}")
        cycles_out.append({
            "cycle": c, "facts_taught": len(taught_so_far),
            "inventory": {"before": n_before, "after_teach": n_after,
                          "after_cons": n_post, "subjects": subjects_post,
                          "absence_inv": absence_post,
                          "clobbered": clobbered},
            "consolidate": stats, "state_kb": size_kb,
            "by_cohort_H": {str(k): v["H"] for k, v in by_cohort.items()},
            "by_cohort_T": {str(k): v["T"] for k, v in by_cohort.items()},
            "paths_H": paths_h,
            "contaminated": [r["n"] for r in contam],
            "rows": rows,
        })
        del p

    # ------------------------------------------------------ final report --------
    last = cycles_out[-1]
    rows = last["rows"]
    print("\n=== FINAL (after all cycles) =============================================")
    for which in ("T", "H"):
        sel = [r for r in rows if r["which"] == which]
        vd = {}
        for r in sel:
            vd[r["verdict"]] = vd.get(r["verdict"], 0) + 1
        print(f"{which} frame ({'same words' if which=='T' else 'held-out paraphrase'}): "
              f"{vd}")
    print("\nRetention by cohort age, held-out paraphrase:")
    for cyc in sorted(last["by_cohort_H"], key=int):
        h = last["by_cohort_H"][cyc]
        ci = int(cyc)
        print(f"  cohort {ci} (taught cycle {ci}, probed after cycle {args.cycles}, "
              f"age {args.cycles - ci}): correct {h.get('correct',0)}/{args.per_cycle} "
              f"confab {h.get('confabulation',0)} refuse {h.get('refusal',0)} "
              f"other {h.get('other',0)} silence {h.get('silence',0)}")
    if args.keep:
        for r in rows:
            if r["which"] == "H":
                print(f"  n{r['n']:>2} {r['frame']:<18} {r['verdict']:<14} "
                      f"{r['source']:<18} | {r['ask']} -> {r['said'][:60]}")

    out = {"arm": f"longevity_probe-{args.probe_electric}",
           "probe_electric": args.probe_electric,
           "cycles": args.cycles, "per_cycle": args.per_cycle,
           "budget": args.budget, "seed": args.seed, "generator": gen,
           "facts": [{k: f[k] for k in ("n", "a", "v", "b", "tell", "frame_H",
                                        "answer_H")} for f in facts],
           "cycles_out": cycles_out, "final": {
               "T": {k: v for k, v in _vd([r for r in rows if r["which"] == "T"]).items()},
               "H": {k: v for k, v in _vd([r for r in rows if r["which"] == "H"]).items()},
           }}
    dest = ROOT / "docs" / "evidence" / (
        "electric_c3_longevity.json" if args.probe_electric == "on"
        else "electric_c3_longevity_oldpath.json")
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


def _vd(rows):
    d = {}
    for r in rows:
        d[r["verdict"]] = d.get(r["verdict"], 0) + 1
    return d


if __name__ == "__main__":
    raise SystemExit(main())
