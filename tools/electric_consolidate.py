"""ELECTRIC C2 -- do taught facts survive CONSOLIDATION?

The generalisation run (docs/electric_generalisation.md) taught 20 novel facts, saved,
restarted and answered 20/20. It did NOT consolidate. E1's real question was never about
retrieval -- it was about the COST of teaching once the consolidator runs, against a
60,000-row binder that evicts by `meta.pop(0)` consulting nothing. This asks that.

COMPARABILITY IS BUILT IN: this harness imports tools/electric_generalise.py's own
seed_state / build / grade and calls E1's generator with the same seed, so `--facts 20
--seed 1` regenerates THE IDENTICAL 20 FACTS as the 20/20 run. The only variable between
that result and this one is whether the consolidator ran.

WHY tools/consolidate_live.py IS NOT USED
It refuses any organ whose state_path is not the live tree (`:129-133`) and requires the
house to be down. Both are correct for a LIVE WRITE and both disqualify it for an
experiment, which must not touch state/language_state.json. So this drives the organ's own
`consolidate()` directly -- the guard lives in the tool, not in the organ -- with the
identical call shape the live tool uses: consolidate(budget=200), then a forced save.

THE HAZARD THIS DESIGN EXISTS TO AVOID
consolidate() is read-only on the binder and writes ONLY through live(..., learn=True): it
replays up to 600 corpus sentences. An earlier draft of this header claimed that leaving
ELECTRIC_TEACH on would therefore record each replayed sentence as a FACT THE USER TOLD.
THE HAZARD ARM MEASURED IT AND THE CLAIM IS FALSE: the only write site of _taught_says is
_absence_note (neural_language :4347), reachable only from hear() (:4311) under a
speaker=="you" guard, and consolidate() calls live() directly with speaker="parent"/"book"
-- it never calls hear(). Teach mode left ON through 600 replays: _taught_says stayed
20/20, _absence_inv 20 -> 20, pollution ZERO subjects.

So teach mode is switched off before the `cons` arm as DEFENCE IN DEPTH, not because a
measured pollution path exists. The inventory size and membership is still the right thing
to check -- it is what would catch such a path if one were ever added, and it is the check
that refuted the claim.

ARMS (one variable: what ran between teaching and saving?)
  nocons   teach -> save(force=True) -> restart -> ask
  cons     teach -> ELECTRIC_TEACH off -> consolidate(budget) -> save -> restart -> ask
  teachon  teach -> ELECTRIC_TEACH LEFT ON -> consolidate(budget) -> save -> restart -> ask
           ^ the HAZARD TEST. Identical outcome to `cons`, which is the result.
All ask E1's HELD-OUT frames graded by role word.

Usage:
  .venv\\Scripts\\python.exe tools\\electric_consolidate.py --arm cons --facts 20 --seed 1
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("nocons", "cons", "teachon"), default="cons")
    ap.add_argument("--facts", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=int, default=200,
                    help="consolidate() rows per call -- the live tool's shape")
    ap.add_argument("--runs", type=int, default=1,
                    help="consolidate() calls; the live tool loops until drained")
    ap.add_argument("--keep", action="store_true", help="print every fact")
    args = ap.parse_args()

    scratch = ROOT / "_tmp" / f"electric_c2_{args.arm}"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    state = seed_state(scratch)

    print(f"ELECTRIC C2 -- CONSOLIDATION SURVIVAL   arm={args.arm.upper()}")
    print(f"{args.facts} facts, seed {args.seed}, budget {args.budget}, "
          f"runs {args.runs}\nscratch {scratch}\n")

    # ------------------------------------------------ life 1: teach ------------
    a = build(state, True)
    gen = te.generate(a, args.facts, args.seed)
    facts = gen["facts"]
    print(f"generator: pool {gen['pool_size']} live words, {gen['attempts']} attempts, "
          f"{gen['binder_collisions']} binder collisions")
    for f in facts:
        a.hear(f["tell"], speaker="you")
    taught = sum(len(v) for v in a._taught_says.values())
    subj_taught = {f["a"] for f in facts}
    abs_before = len(a._absence_inv)
    print(f"taught {len(facts)} facts; _taught_says holds {taught} "
          f"({len(a._taught_says)} subjects); _absence_inv {abs_before}")

    # ------------------------------------------------ consolidate ------------
    cons = {"ran": False}
    if args.arm in ("cons", "teachon"):
        if args.arm == "cons":
            a.ELECTRIC_TEACH = False      # replay must not mint taught facts
        # arm "teachon" is the HAZARD TEST: teach mode left ON through 600 replayed
        # corpus sentences. See docs/electric_c2_hazard.md for what this measured.
        real_before = int((a.san_w >= 1e-6).sum())
        rows = []
        t0 = time.time()
        for _ in range(args.runs):
            r = a.consolidate(budget=args.budget)
            rows.append({k: v for k, v in r.items() if k != "deltas"})
        cons = {"ran": True, "teach_flag_during": bool(a.ELECTRIC_TEACH),
                "runs": rows,
                "taught_says_during": sum(len(v) for v in a._taught_says.values()),
                "subjects_during": len(a._taught_says),
                "absence_inv_after": len(a._absence_inv),
                "san_real_before": real_before,
                "san_real_after": int((a.san_w >= 1e-6).sum()),
                "secs": round(time.time() - t0, 1)}
        print(f"consolidate: {rows}")
        print(f"  taught_says DURING replay = {cons['taught_says_during']} "
              f"(must still be {taught})  subjects {cons['subjects_during']}")
        print(f"  _absence_inv {abs_before} -> {cons['absence_inv_after']}   "
              f"san real {cons['san_real_before']} -> {cons['san_real_after']} "
              f"in {cons['secs']}s")

    saved = a.save_state(force=True)
    size_mb = (scratch / LIVE_STATE).stat().st_size / 1e6
    print(f"saved: {saved.get('saved')}  ({size_mb:.1f} MB)")
    del a

    # ------------------------------------------------ life 2: restart ---------
    b = build(state, True)
    loaded = b.load_state()
    rel = sum(len(v) for v in b._taught_says.values())
    print(f"restart: loaded={loaded.get('loaded')} taught_after_load={rel} "
          f"({len(b._taught_says)} subjects)")

    polluted = sorted(set(b._taught_says) - subj_taught)
    lost = sorted(subj_taught - set(b._taught_says))
    print(f"pollution check: {len(polluted)} non-taught subjects "
          f"{'-- CLEAN' if not polluted else polluted[:8]}")
    if lost:
        print(f"LOST TAUGHT SUBJECTS: {len(lost)} {lost[:8]}")

    # ------------------------------------------------ ask ---------------------
    counts = {"correct": 0, "confabulation": 0, "refusal": 0, "silence": 0, "other": 0}
    by_frame = {}
    direct = 0
    rows_out = []
    for f in facts:
        r = b.answer(f["ask_H"])
        said = str(r.get("utterance") or r.get("response") or "").strip()
        spoken = bool(r.get("spoken"))
        k = grade(f, said, spoken)
        counts[k] += 1
        fr = f["frame_H"].split("-")[0]
        by_frame.setdefault(fr, {"total": 0, "correct": 0, "confabulation": 0,
                                 "refusal": 0, "silence": 0, "other": 0})
        by_frame[fr]["total"] += 1
        by_frame[fr][k] += 1
        is_direct = r.get("source") == "electric_taught"
        direct += 1 if is_direct else 0
        rows_out.append({"frame": fr, "taught": f["tell"], "ask": f["ask_H"],
                         "need": f["answer_H"], "forbid": f["forbid_H"],
                         "spoken": said, "outcome": k,
                         "source": str(r.get("source") or ""),
                         "answered": bool(r.get("answered")),
                         "licensed_refusal": bool(r.get("licensed_refusal"))})

    total = len(rows_out)
    print(f"\n--- RETENTION AFTER {args.arm.upper()} (n={total}) ---")
    for k in ("correct", "confabulation", "refusal", "silence", "other"):
        print(f"  {k:14s} {counts[k]:>3}/{total}"
              + ("   <- worse than silence" if k == "confabulation" else ""))
    print(f"  answered from the taught inventory (source=electric_taught): {direct}")
    print("  by held-out frame:")
    for fr in sorted(by_frame):
        c = by_frame[fr]
        print(f"    {fr}  n={c['total']:2d}  correct {c['correct']:2d}  "
              f"confab {c['confabulation']:2d}  refusal {c['refusal']:2d}  "
              f"silence {c['silence']:2d}  other {c['other']:2d}")
    for r in rows_out:
        if r["outcome"] != "correct" or args.keep:
            print(f"[{r['outcome']:>13s}]{' D' if r['source'] == 'electric_taught' else '  '}"
                  f" {r['ask']}\n"
                  f"{' ' * 16}taught {r['taught']!r}  need {r['need']!r}  "
                  f"said {r['spoken']!r}")

    out = ROOT / "docs" / "evidence" / f"electric_c2_{args.arm}.json"
    out.write_text(json.dumps(
        {"arm": args.arm, "budget": args.budget, "runs": args.runs, "seed": args.seed,
         "consolidation": cons, "taught_before": taught, "taught_after_load": rel,
         "polluted_subjects": polluted, "lost_subjects": lost, "tally": counts,
         "by_frame": by_frame, "direct_answers": direct, "rows": rows_out}, indent=2),
        encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
