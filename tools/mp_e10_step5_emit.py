"""STEP 5 emissions -- every figure item 3 asks for, computed from the artifacts by registered code.

Run after tools/mp_e10_step5_scored_run.py has produced its two runs and its diff. It adds keys to the STEP 5
artifact; it never rewrites a value the run itself measured, and it refuses if the artifact is missing.

What each emission is computed from, and what it is NOT:
  * mouth stages  -- heldout_eval.stage_of, the registered classifier, applied to this run's own graded rows.
                     It is NOT the held-out script set: tools/heldout_eval.py has no --state-root and scores the
                     default state/, so pointing it at a bench workdir would be an edit to a published
                     instrument. The population is named in the artifact rather than left implied.
  * H2 scalar     -- word_provenance.content_words, the same function MP-E8's descriptive figure uses, over the
                     live phase, with refusal rate and coverage beside it as the ruling's guardrails.
  * H3 interval   -- both currencies, labelled: rows of graded asks (the floor's currency) and pp of correct
                     counts (the registered quantity). An interval containing zero is reported as not
                     attributable, never as strengthening.
  * ceiling guard -- read from the bench's own replay report, per pass, per depth.
  * A10           -- read from each artifact's resource_ledger_a10.
  * R6            -- precondition status stated from the file that would have to exist, not assumed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "experiments/MP-E10/results/step5_scored_tier120.json"
RUN_R = ROOT / "experiments/MP-E10/results/step5_tier120_replay_armA.json"
RUN_C = ROOT / "experiments/MP-E10/results/step5_tier120_control_armA.json"
DIFF = ROOT / "experiments/MP-E10/results/step5_tier120_replay_vs_control_row_migration.json"
BASE = ROOT / "experiments/MP-E8/results/armA_tier120_curriculum.json"
STAGES = ["gating", "mouth", "recall", "recall_untraced", "shape_arbiter", "other"]

import heldout_eval as he              # noqa: E402  -- the registered stage classifier
import word_provenance as wp           # noqa: E402  -- the registered content-word counter


def rows(art, depth, phase):
    return (((art.get("arms") or {}).get("learn") or {}).get("probes") or {}).get(depth, {}).get(phase, []) or []


def stage_table(art):
    """Apply the registered classifier to every graded row that failed, by depth and phase."""
    per = {}
    other_examples = []
    for depth in ("1", "2", "3"):
        for phase in ("live", "restarted", "reasked"):
            rs = rows(art, depth, phase)
            counts = {s: 0 for s in STAGES}
            graded = failed = 0
            for r in rs:
                graded += 1
                if r.get("cls") == "correct" or r.get("answered"):
                    continue
                failed += 1
                turn = {"spoken": r.get("answered"), "said": r.get("said"), "src": r.get("src"),
                        "reason": r.get("reason", "")}
                st = he.stage_of(turn, r.get("reason") or "")
                counts[st] = counts.get(st, 0) + 1
                if st == "other" and len(other_examples) < 6:
                    other_examples.append({"depth": depth, "phase": phase, "ask": r.get("ask"),
                                           "said": r.get("said"), "src": r.get("src"),
                                           "mech": r.get("mech")})
            per[f"{depth}/{phase}"] = {"graded_rows": graded, "failing_rows": failed, "by_stage": counts}
    return {"per_depth_phase": per, "mass_in_other_named_not_divided_away": other_examples,
            "denominator": "five stages per D-MPE10-01 (gating, mouth, recall, recall_untraced, shape_arbiter); "
                           "`other` is not one of the five and is listed by row when it carries mass",
            "recall_untraced_is_a_default_attribution_not_a_measurement": True}


def fluency(art):
    """H2's scalar: mean content words per emitted answer over the live phase, with its guardrails."""
    spoke, refused, answered_n, graded = [], 0, 0, 0
    for depth in ("1", "2", "3"):
        for r in rows(art, depth, "live"):
            graded += 1
            if r.get("answered") and r.get("said"):
                answered_n += 1
                spoke.append(r["said"])
            elif r.get("cls") == "refused":
                refused += 1
    cw = [len(wp.content_words(s)) for s in spoke]
    return {"mean_content_words_per_emitted_answer": round(sum(cw) / len(cw), 4) if cw else None,
            "emitted_answers": answered_n, "graded_rows_live": graded,
            "refusal_rate_percent": round(100.0 * refused / graded, 4) if graded else None,
            "coverage_percent": round(100.0 * answered_n / graded, 4) if graded else None}


def h3_interval(art_r, art_c, floor_rows, graded_asks):
    """Both currencies, labelled. Never written as strengthening."""
    per = {}
    for depth in ("1", "2", "3"):
        for phase in ("live", "restarted", "reasked"):
            rs, rc = rows(art_r, depth, phase), rows(art_c, depth, phase)
            n = len(rs) or 1
            cr = sum(1 for r in rs if r.get("cls") == "correct")
            cc = sum(1 for r in rc if r.get("cls") == "correct")
            delta_pp = round(100.0 * (cr - cc) / n, 4)
            per[f"{depth}/{phase}"] = {"correct_replay": cr, "correct_control": cc, "rows": n,
                                       "retention_delta_pp_replay_minus_control": delta_pp}
    floor_pp = round(100.0 * floor_rows / graded_asks, 4)
    return {"per_depth_phase": per,
            "floor_in_this_currency_pp_of_graded_asks": floor_pp,
            "interval_rule": ("each delta is reported as [delta - floor, delta + floor] in pp of graded asks. "
                              "A half-width smaller than the floor is not attributable to the treatment."),
            "intervals": {k: [round(v["retention_delta_pp_replay_minus_control"] - floor_pp, 4),
                              round(v["retention_delta_pp_replay_minus_control"] + floor_pp, 4)]
                          for k, v in per.items()},
            "what_an_interval_inside_the_floor_does_not_mean": ("it does not mean replay strengthens anything. "
                                                                "H3 is an interference claim: an interval inside "
                                                                "the floor says the instrument cannot resolve a "
                                                                "difference at this size, in either direction."),
            "margin_pp_registered": 2.0}


def ceiling_guard(art):
    out = {}
    for run in (art.get("arms", {}).get("learn", {}).get("runs") or []):
        rp = run.get("replay")
        if not rp:
            continue
        d = str(run.get("depth"))
        out[d] = {"ceiling_limited": rp.get("ceiling_limited"), "reason_void": rp.get("reason_void"),
                  "passes_registered": rp.get("passes_registered"), "passes_run": rp.get("passes_run"),
                  "gain": rp.get("gain"),
                  "per_pass": [{"pass": p.get("pass"), "ceiling": p.get("ceiling"),
                                "gain_used": p.get("gain_used"),
                                "entries_at_ceiling_before": p.get("entries_at_ceiling_before"),
                                "entries_pushed_to_ceiling_this_pass": p.get("entries_pushed_to_ceiling_this_pass"),
                                "void_for_H3": p.get("void_for_H3")} for p in rp.get("per_pass", [])]}
    return out


def a10(art):
    lr = art.get("resource_ledger_a10") or {}
    return {"available": lr.get("available"), "reason": lr.get("reason"),
            "whole_run_peak_rss_bytes": lr.get("whole_run_peak_rss_bytes"),
            "os_peak": lr.get("os_peak"), "vram": lr.get("vram"),
            "per_phase": lr.get("per_phase"), "n_samples": lr.get("n_samples"),
            "definition_of_cost_per_retained_item": lr.get("definition_of_cost_per_retained_item"),
            "retained_items_by_phase": lr.get("retained_items_by_phase")}


def main() -> int:
    for p in (OUT, RUN_R, RUN_C, DIFF):
        if not p.exists():
            raise SystemExit(f"REFUSED: {p.name} is missing -- the scored run must produce it first")
    art = json.loads(OUT.read_text(encoding="utf-8"))
    a_r, a_c = json.loads(RUN_R.read_text(encoding="utf-8")), json.loads(RUN_C.read_text(encoding="utf-8"))
    diff = json.loads(DIFF.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    fl_ref = art["preflight"]["the_floor_it_scores_against"]
    # The floor arrives as a quoted ledger line, so the number is parsed out of the quote it came from -- the
    # quote is the citation, and parsing it keeps the two from drifting apart.
    import re
    fr = int(re.search(r"(\d+)", fl_ref["n_rows_moved"]["line_reads"]).group(1))
    ga = int(re.search(r"(\d+)", fl_ref["graded_asks"]["line_reads"].replace(",", "")).group(1))

    art["emissions"] = {
        "mouth_stages_replay": stage_table(a_r),
        "mouth_stages_control": stage_table(a_c),
        "H2_fluency_as_ruled": {"replay": fluency(a_r), "control": fluency(a_c),
                                "MP_E8_armA_baseline_same_tier": fluency(base),
                                "baseline_artifact": str(BASE.relative_to(ROOT).as_posix()),
                                "guardrails_beside_it": "refusal rate and coverage, per the ruling"},
        "H3_interference_interval_with_floor": h3_interval(a_r, a_c, fr, ga),
        "row_migration_replay_vs_control": {"n_rows_moved": diff["n_rows_moved"],
                                            "floor_rows_on_these_bytes": fr,
                                            "graded_asks": ga,
                                            "attributable_at_best": diff["n_rows_moved"] - fr,
                                            "reading": ("if the treatment moves no more rows than two identical "
                                                        "runs do, the migration is not attributable to replay")},
        "ceiling_guard_per_pass_replay": ceiling_guard(a_r),
        "ceiling_guard_per_pass_control": ceiling_guard(a_c),
        "A10_resource_ledger": {"replay": a10(a_r), "control": a10(a_c)},
        "R6_four_named_guarded_probes": {
            "probes": ["P-numeral-final", "R-count-moon", "R-disj-reversed", "R-order-ofthe"],
            "status": "NOT MEASURED ON THIS RUN, and the reason is a missing precondition, not an omission",
            "why": ("the four probes are scored by tools/mp_e9_battery.py over a generation journal written by "
                    "tools/run_generation.py. The bench run does not produce that journal, and heldout_eval has "
                    "no --state-root, so no registered instrument reads a bench workdir's house. Running the "
                    "generation pipeline against this house is a separate authorised step, not a flag."),
            "what_would_be_needed": "run_generation.py --state-root <the replayed house> then "
                                    "mp_e9_battery.py --journal <it> --rows <it>",
        },
    }
    OUT.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[step5] emissions written to {OUT.name}; floor {fr} rows of {ga}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
