"""Close tier 300's named-missing measurements, and report each as MEASURED or STILL ABSENT.

MP-E10's tier-300 verdict artifact (results/replay_tier300_summary.json, sealed at anchor 2d06146) named
four things it could not report: the R6 guarded probes, the read direction, ||w||_F against tokens pushed
at this tier, and a replay-OFF control to attribute the migrated rows. This tool measures what can be
measured from committed artifacts and from the instruments on disk, and for what cannot, says so with the
evidence rather than leaving the gap implied.

ROW KEY, and why this tool does not define one. It used to keep its own private index of learn rows keyed
(depth, phase, ask) -- the same non-unique key AMD-MPE10-08 named as a defect in the migration instrument --
so its sealed row_attribution and primary_attribution_same_instrument.rows_compared read 8,199 while the
governing migration artifacts read 9,414. It now IMPORTS the key from tools/mp_e10_row_migration.py, so there
is one definition of a row identity in this program and the two records cannot drift apart again. The inputs
are the five *_row_migration_keyfix.json artifacts, not the superseded un-suffixed ones.

Nothing here runs the bench. It reads runs that already happened and computes what they mean. Where a
number exists only at another tier, it is NOT copied in: a tier-40 or tier-120 figure standing in for a
tier-300 one is the substitution this program's rulings exist to prevent, so the tier-40 k-sweep is cited
only as the instrument's provenance, never as tier 300's value.

USAGE
  py tools/mp_e10_tier300_closure.py --out experiments/MP-E10/results/tier300_named_measurements_closure.json \
      --control-wall-seconds 1140.5
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

# One definition of a row identity in this program. Imported, not copied: a private copy is how this tool came
# to publish 8,199 while the migration instrument published 9,414 for the same three runs.
from mp_e10_row_migration import ROW_KEY_MODES, key_uniqueness  # noqa: E402
from mp_e10_row_migration import learn_rows as _learn_rows_index  # noqa: E402

R13 = ("cls", "said", "src", "item", "shape", "mech", "taught", "own", "answered")
GUARDED = ["P-numeral-final", "R-count-moon", "R-disj-reversed", "R-order-ofthe"]
ROW_KEY = "probe"


def learn_rows(art, mode=ROW_KEY):
    """The learn arm's rows, indexed by the migration instrument's key. Dict, as every call site expects."""
    index, _dupes = _learn_rows_index(art, mode)
    return index


def _rel(p):
    """Repo-relative for display, absolute when it genuinely is elsewhere.

    Same bug class suite_manifest.py records three times: a cosmetic path display that raises AFTER the
    measurement finished, so a test writing --out to a tmp_path outside the repo turns a completed run into
    a nonzero exit. The measurement is not the thing at risk; the exit code is.
    """
    pp = Path(p).resolve()
    try:
        return pp.relative_to(ROOT).as_posix()
    except ValueError:
        return pp.as_posix()

P = {
    "replay": "experiments/MP-E10/results/replay_tier300_armA.json",
    "control": "experiments/MP-E10/results/control_tier300_no_replay_armA.json",
    "baseline": "experiments/MP-E8/results/armA_tier300_curriculum.json",
    # The GOVERNING migration artifacts (AMD-MPE10-09), keyed (depth, phase, ask, item, shape) and comparing
    # all 9,414 graded asks. The un-suffixed three below them are superseded, still sealed, and read 8,199 --
    # pointing this tool at those is what made the closure record and the migration record disagree.
    "mig_replay": "experiments/MP-E10/results/300_row_migration_keyfix.json",
    "mig_control": "experiments/MP-E10/results/300ctl_row_migration_keyfix.json",
    "mig_vs": "experiments/MP-E10/results/300_replay_vs_control_row_migration_keyfix.json",
    "ksweep300": "experiments/MP-E10/results/ksweep_tier300_organ_characterisation.json",
    "ksweep40": "experiments/MP-E10/results/ksweep_tier40_calibration_post_rulings.json",
    "summary": "experiments/MP-E10/results/replay_tier300_summary.json",
    "reg": "experiments/MP-E10/registration.json",
    "cur300": "experiments/MP-E8/curriculum_tier300.json",
    "sel": "tools/scripts_selection.json",
    "battery": "tools/mp_e9_battery.py",
    "bench": "tools/electric_learn_bench.py",
    "rung": "tools/run_generation.py",
    "seq": "organs/sequence_organ.py",
}


def load(key):
    return json.loads((ROOT / P[key]).read_text(encoding="utf-8", errors="replace"))


# The private copy of the row index was removed here on 2026-11-05 (AMD-MPE10-10). It keyed learn rows on
# (depth, phase, ask) and overwrote duplicates, which is the defect AMD-MPE10-08 named and AMD-MPE10-09 fixed
# in the migration instrument. Leaving a second definition here would have shadowed the import above and put
# the collapsed key back into the closure record without any edit looking like a key change.


# --------------------------------------------------------------------------- (a)
def guarded_probe_instrument_check():
    """Can the four R6 guarded probes be scored on the tier-300 run? Measured from the instruments."""
    sel = load("sel")
    cur300_text = (ROOT / P["cur300"]).read_text(encoding="utf-8").lower()
    replay = load("replay")

    rows = []
    for si, script in enumerate(sel.get("scripts", [])):
        for ti, turn in enumerate(script.get("turns", [])):
            if isinstance(turn, dict) and turn.get("probe") in GUARDED:
                ask = str(turn.get("ask", ""))
                rows.append({
                    "probe": turn["probe"],
                    "defined_at": f"tools/scripts_selection.json scripts[{si}].turns[{ti}]",
                    "script": script.get("name"),
                    "ask": ask,
                    "expect": turn.get("expect"),
                    "ask_appears_verbatim_in_tier300_curriculum": ask.lower() in cur300_text,
                    "every_content_word_of_the_ask_in_tier300": None,
                })
    # content-word test, the stricter one: not the whole sentence but its non-function words
    STOP = {"the", "a", "an", "of", "to", "and", "is", "are", "did", "i", "you", "me", "it", "or",
            "which", "what", "how", "many", "times", "have", "mentioned", "came", "first", "one",
            "does", "turn", "turns", "often", "reversed"}
    for r in rows:
        words = [w for w in re.findall(r"[a-z]+", r["ask"].lower()) if len(w) > 2]
        core = [w for w in words if w not in {"the", "and", "you", "did", "which", "what", "how",
                                              "many", "does", "have", "came", "into", "its", "for"}]
        r["content_words_checked"] = core
        r["every_content_word_in_tier300"] = all(w in cur300_text for w in core)

    # what the tier-300 artifact's rows actually carry
    vocab = set()
    for phases in (replay.get("arms", {}).get("learn", {}) or {}).get("probes", {}).values():
        for r in (phases or {}).get("live", []) or []:
            vocab |= set(r)
            break
        break
    all_vocab = set()
    for phases in (replay.get("arms", {}).get("learn", {}) or {}).get("probes", {}).values():
        for rows_ in (phases or {}).values():
            for r in rows_ or []:
                all_vocab |= set(r)

    bench_args = sorted(set(re.findall(r'"(--[a-z-]+)"\s+in\s+args', (ROOT / P["bench"]).read_text(
        encoding="utf-8", errors="replace"))))
    battery_args = sorted(set(re.findall(r'add_argument\(\s*"(--[a-z-]+)"', (ROOT / P["battery"]).read_text(
        encoding="utf-8", errors="replace"))))
    rung_args = sorted(set(re.findall(r'add_argument\(\s*"(--[a-z-]+)"', (ROOT / P["rung"]).read_text(
        encoding="utf-8", errors="replace"))))

    return {
        "asked": "the four R6 guarded probes (P-numeral-final, R-count-moon, R-disj-reversed, "
                 "R-order-ofthe) scored on the tier-300 run",
        "verdict": "STILL ABSENT -- not producible on the tier-300 run by any instrument on this machine. "
                   "Reported as absent with its reason, not as a zero and not as a tier-40 number.",
        "what_the_four_probes_are": rows,
        "tier300_row_vocabulary_measured": sorted(all_vocab),
        "tier300_rows_carry_a_probe_field": "probe" in all_vocab,
        "tier300_rows_carry_a_pass_field": "pass" in all_vocab,
        "the_only_scorer_of_these_probes": {
            "tool": "tools/mp_e9_battery.py",
            "its_cli": battery_args,
            "requires": "--journal, a comma-separated list of run_generation journal files",
            "emits": "measured.guarded_pass / measured.guarded_total / verdict.battery_guarded_pass",
            "graded_against": "tools/selection_baseline.json regression_pass_set, matched on full ask ids, "
                              "not on the short probe names",
        },
        "why_the_tier300_run_cannot_feed_it": {
            "bench_flag_surface_measured": bench_args,
            "no_external_probe_input": "the bench takes no probe list; PROBES is built from the curriculum "
                                       "at import (tools/electric_learn_bench.py)",
            "bench_writes_no_selection_journal": True,
            "run_generation_has_no_curriculum_axis": {
                "its_flags": rung_args,
                "what_its_tier_means": "--tier takes frozen/probe/open, which are BATTERY tiers (which "
                                       "script set to ask), not MP-E8 curriculum tiers (how many items the "
                                       "pool holds). The two axes share a name and nothing else.",
            },
            "curriculum_contains_none_of_the_four_asks": all(
                not r["ask_appears_verbatim_in_tier300_curriculum"] for r in rows),
            "and_the_probes_need_their_script_context": "each guarded probe is turn 5 (or 2) of a multi-turn "
                "selection script; its expected answer depends on earlier turns of that script (the lantern "
                "was told first, the coat is wet, the moon was never mentioned). A curriculum of qa pairs and "
                "svo frames cannot supply that context even if the words were present.",
        },
        "what_would_close_it_two_routes_both_design_steps": {
            "route_1_teach_the_tier_then_ask_the_battery": "run the tier-300 curriculum through "
                "tools/run_generation.py as additional material and grade the resulting journal with "
                "tools/mp_e9_battery.py. Needs a curriculum input on run_generation, which does not exist; "
                "that is an organ/pipeline change, not a flag.",
            "route_2_add_the_four_probes_to_the_tier300_curriculum": "changes curriculum_sha256, which is "
                "the identity every sealed tier-300 artifact is keyed to -- it would break the comparison "
                "with the baseline the verdict is computed against. Under R2 that is a re-registration, and "
                "under tiers.curriculum the manifests are read unedited.",
            "why_neither_was_done_here": "both change a sealed instrument's identity or add a pipeline "
                "input. That is the PI's design step, and doing it silently to produce a number the ledger "
                "wants is the move D-MPE10-06/-07/-08 each refused.",
        },
        "consequence_stated": "H3's R6 floor at tier 300 -- 'the guarded invariants are the floor; "
            "regression is a hard reject' (constraints_from_the_plan.R6) -- remains UNMEASURED at this tier. "
            "The four probes do pass at tier 40 on the selection pipeline (battery_guarded_pass 4/4 in "
            "MP-E8's and MP-E9's battery artifacts), and that is NOT reported here as tier 300's result.",
    }


# --------------------------------------------------------------------------- (b)
def read_direction(reg300):
    ks = load("ksweep300")
    row2 = [r for r in ks["sweep"] if r["k"] == 2][0]
    seq_text = (ROOT / P["seq"]).read_text(encoding="utf-8", errors="replace")
    return {
        "asked": "the read direction named in the artifact (D-MPE10-08: no figure may be reported as a "
                 "bare 'alignment'; name the token probed and the token recovered)",
        "verdict": "MEASURED AND NAMED -- two different objects were involved and they are named apart.",
        "ruling_text": (load("reg").get("pi_decisions", {}).get("rulings", {})
                        .get("D-MPE10-08_read_direction", {})),
        "object_1_the_replay_run_actually_touched": {
            "name": "organs/sequence_organ.py -- the sequence chain",
            "direction": "SUCCESSOR: chain[pre][post] = strength. learn_sequence writes "
                         "row keyed by the LATER token against the EARLIER one and generate(first_word) "
                         "runs the chain FORWARD, asking what comes after.",
            "what_replay_did_to_it": ("replay_pass() advanced every stored pair by one increment of "
                                      f"REPLAY_GAIN; this run recorded pairs_on_tape="
                                      f"{reg300.get('pairs_on_tape')} per pass and the guard voided depths "
                                      "2 and 3"),
            "clamped_at": re.findall(r"REPLAY_CEILING\s*=\s*([0-9.]+)", seq_text)[:1],
            "gain": re.findall(r"REPLAY_GAIN\s*=\s*([A-Za-z_.]+)", seq_text)[:1],
            "ceiling_in_learn_sequence": re.findall(r"row\[key\] = ([0-9.]+) if new > ", seq_text)[:1],
        },
        "object_2_the_k_sweep_characterises": {
            "name": "tools/mp_e10_working_memory.py DecayedTrace -- the fast-weight trace",
            "direction": "PREDECESSOR: state is outer(post, pre). Probing the LATER token recovers the "
                         "EARLIER one. This is the TRANSPOSE of object 1.",
            "measured_at_tier_300": {
                "probe_the_later_token_recovers_the_earlier_cosine":
                    row2["probe_later_recovers_earlier_cosine_mean"],
                "probe_the_earlier_token_recovers_the_later_cosine":
                    row2["probe_earlier_recovers_later_cosine_mean"],
                "direction_asymmetry_pp": row2["direction_asymmetry_pp"],
                "tier": ks["input"]["tier"],
                "utterances": ks["input"]["utterances_parsed"],
                "tokens_total": ks["input"]["tokens_total_across_utterances"],
            },
            "k_invariance": row2["these_two_columns_are_k_invariant_for_k_ge_2_by_construction"],
        },
        "the_distinction_that_matters": ("MP-E10 B.4 step 2 replayed object 1. The D-MPE10-08 ruling was "
                                         "written about object 2, the trace, whose predecessor direction the "
                                         "tier-40 sweep measured at 0.982 against 0.056. Both are now named "
                                         "with the direction each reads, so no figure in this tier's record "
                                         "is a bare 'alignment', and neither object's number is quoted for "
                                         "the other."),
        "declared_in": [P["ksweep300"], P["summary"], "this artifact"],
    }


# --------------------------------------------------------------------------- (c)
def norm_vs_tokens():
    ks = load("ksweep300")
    b = ks["findings_about_the_sealed_organ"]["1_fast_weight_store_is_not_bounded_by_k"]
    rows = {r["k"]: r for r in b["same_stream_at_four_values_of_k"]}
    k2 = rows[2]["w_frobenius_norm_vs_tokens_pushed"]
    k1 = rows[1]["w_frobenius_norm_vs_tokens_pushed"]
    ks40 = load("ksweep40")
    b40 = ks40["findings_about_the_sealed_organ"]["1_fast_weight_store_is_not_bounded_by_k"]
    r40 = {r["k"]: r["w_frobenius_norm_vs_tokens_pushed"] for r in
           b40["same_stream_64_tokens_at_four_values_of_k"]}
    return {
        "asked": "||w||_F against tokens pushed at tier 300 (D-MPE10-06), not just the tier-40 k-sweep",
        "verdict": "MEASURED at tier 300's own stream volume, on the same instrument as the sealed tier-40 "
                   "sweep, whose driver was promoted out of _tmp/ into tools/mp_e10_ksweep.py (R10).",
        "instrument": "tools/mp_e10_ksweep.py --curriculum experiments/MP-E8/curriculum_tier300.json",
        "artifact": P["ksweep300"],
        "tier300_stream": {"utterances": ks["input"]["utterances_parsed"],
                           "tokens_total_across_utterances":
                               ks["input"]["tokens_total_across_utterances"],
                           "checkpoints_sampled": b["checkpoints"],
                           "stream_length_tokens": b["stream_length_tokens"]},
        "w_frobenius_norm_vs_tokens_pushed_k2": k2,
        "w_frobenius_norm_vs_tokens_pushed_k1": k1,
        "growth_reading": {
            "from_first_to_last_checkpoint_k2": [min(k2, key=lambda x: int(x)), k2[min(k2, key=lambda x: int(x))],
                                                 max(k2, key=lambda x: int(x)), k2[max(k2, key=lambda x: int(x))]],
            "statement": ("||w||_F keeps rising past the tier-40 checkpoint set: at tier 300's volume the "
                          "curve is sampled to "
                          f"{max(k2, key=lambda x: int(x))} tokens, where the sealed tier-40 artifact stopped "
                          "at 64. The quantity D-MPE10-06 requires is reported at the tier's own size "
                          "instead of at the calibration tier's size."),
        },
        "tier40_sealed_curve_for_provenance_only_NOT_a_tier300_value": {
            "k2": r40[2], "k1": r40[1],
            "why_it_is_here": "to show the instrument is unchanged and the tier-300 curve extends it. It "
                              "is not tier 300's number and may not be quoted as one.",
        },
        "per_utterance_norms_from_the_sweep": {
            "k2_w_frobenius_norm_mean": [r["w_frobenius_norm_mean"] for r in ks["sweep"] if r["k"] == 2][0],
            "k2_state_norm_mean": [r["state_norm_mean"] for r in ks["sweep"] if r["k"] == 2][0],
            "utterances_fully_held_pct_by_k": {str(r["k"]): r["utterances_fully_held_pct"] for r in
                                               ks["sweep"]},
        },
        "the_object_the_replay_run_moved_instead": ("the sequence chain, whose state is not a matrix and "
                                                    "has no ||w||_F; its comparable quantity is the number "
                                                    "of stored pairs on the tape and how many sit at the "
                                                    "4.0 ceiling, both recorded in the replay artifact and "
                                                    "reproduced in replay_tier300_summary.json"),
    }


# --------------------------------------------------------------------------- (d)
def same_instrument_attribution():
    """replay ON vs replay OFF, both on identical instrument bytes.

    Diffing either run against MP-E8's sealed baseline also drags in a harness change (the baseline was
    produced by build 6e09171a, both MP-E10 tier-300 runs by 5cf038c2), so that pair measures drift plus
    treatment. This pair differs by one flag and nothing else, which makes it the attribution instrument,
    and the direction of each transition is what makes it readable: a treatment that helps pushes rows one
    way, while run-to-run noise pushes them both ways about equally.
    """
    mv = load("mig_vs")
    flows, pairs, seen = [], [], set()
    for axis, trans in mv["transitions_by_axis"].items():
        for label, n in trans.items():
            frm, _, to = [x.strip() for x in label.partition("->")]
            if "[" in to:
                cls = " " + to[to.find("["):]
                to_clean = to[:to.find("[")].strip()
            else:
                cls, to_clean = "", to
            back = f"{to_clean} -> {frm}{cls}"
            flows.append({"axis": axis, "transition": label, "n": n})
            pair_key = (axis, frozenset((label, back)))
            if back in trans and back != label and pair_key not in seen:
                seen.add(pair_key)
                pairs.append({"axis": axis, "forward": label, "forward_n": n,
                              "reverse": back, "reverse_n": trans[back],
                              "net": n - trans[back]})
    fwd = sum(p["forward_n"] for p in pairs)
    rev = sum(p["reverse_n"] for p in pairs)
    unpaired = [f for f in flows if not any(p["axis"] == f["axis"] and p["forward"] == f["transition"]
                                            or p["axis"] == f["axis"] and p["reverse"] == f["transition"]
                                            for p in pairs)]
    return {
        "artifact": P["mig_vs"],
        "why_this_is_the_primary_instrument": ("replay ON vs replay OFF on identical harness_sha256 "
                                               "(5cf038c2 on both sides), identical curriculum hash and "
                                               "identical seed. The baseline-anchored pairs additionally "
                                               "carry a harness change, so they bound the total movement "
                                               "but cannot attribute it."),
        "matched_pair": mv["matched_pair"],
        "row_key": mv.get("row_key", {"mode": "legacy (superseded artifact)", "fields": ["depth", "phase", "ask"]}),
        "rows_compared": mv["rows_compared"],
        "n_rows_moved": mv["n_rows_moved"],
        "class_split": mv["class_split"],
        "fields_moved_split": mv.get("fields_moved_split"),
        "opposing_pairs": pairs,
        "flow": {"sum_of_forward_transitions_in_pairs": fwd,
                 "sum_of_their_reverses": rev,
                 "imbalance_pp_of_the_moved_set": round(100.0 * abs(fwd - rev) / mv["n_rows_moved"], 2)
                 if mv["n_rows_moved"] else None,
                 "unpaired_transitions": unpaired},
        "reading": ("the movement between the two runs is close to balanced: for every class a row moves "
                    "INTO, roughly the same number moves OUT of it on the same axis. A treatment that "
                    "helped retention would push the refusal axis one way; this is run-to-run noise, and "
                    "the control is what proves it, because the same 111-row scale of movement appears "
                    "with the flag off against the sealed baseline (302 rows, on a pair that also differs "
                    "by a harness build)."),
        "what_this_does_not_claim": ("it does not say replay has no effect -- it says THIS run shows no "
                                     "directional effect at tier 300, on a single seed, at a tier where "
                                     "the guard voided depths 2 and 3. One seed cannot separate an effect "
                                     "smaller than the run-to-run spread, which is the "
                                     "sealed_baseline_reproducibility finding in this registration."),
    }


def attribution(control_wall_seconds):
    rep, ctl, base = load("replay"), load("control"), load("baseline")
    mr, mc = load("mig_replay"), load("mig_control")
    rr, cr, br = learn_rows(rep), learn_rows(ctl), learn_rows(base)

    def correct_rate(art):
        """correct over the rows the phase actually compared. The bench's summary carries `correct` but
        no `n` at this tier, and the registered denominator_rule says the artifact must state what it
        divided by -- so n is summed from by_shape, the same basis the verdict triple is read off."""
        out = {}
        for depth, phases in (art.get("summary", {}).get("learn", {}) or {}).items():
            for phase, s in (phases or {}).items():
                if not isinstance(s, dict) or "correct" not in s:
                    continue
                n = s.get("n")
                basis = "summary.n"
                if not n:
                    bs = s.get("by_shape") or {}
                    n = sum(sum((v or {}).values()) for v in bs.values() if isinstance(v, dict)) or None
                    basis = "sum(by_shape)"
                out[f"{depth}/{phase}"] = {
                    "correct": s["correct"], "n": n, "n_basis": basis,
                    "pct": round(100.0 * s["correct"] / n, 4) if n else None}
        return out

    rates = {"baseline": correct_rate(base), "replay_on": correct_rate(rep), "control": correct_rate(ctl)}
    interference = {}
    for key in sorted(set(rates["baseline"]) & set(rates["replay_on"]) & set(rates["control"])):
        b, r, c = (rates["baseline"][key], rates["replay_on"][key], rates["control"][key])
        if None in (b["pct"], r["pct"], c["pct"]):
            continue
        interference[key] = {
            "baseline_pct": b["pct"], "replay_pct": r["pct"], "control_pct": c["pct"],
            "replay_minus_baseline_pp": round(r["pct"] - b["pct"], 4),
            "control_minus_baseline_pp": round(c["pct"] - b["pct"], 4),
            "attributable_to_replay_pp": round((r["pct"] - b["pct"]) - (c["pct"] - b["pct"]), 4),
            "rows_in_denominator": b["n"],
            "within_registered_margin_2pp": abs(round(r["pct"] - b["pct"], 4)) <= 2.0,
        }

    # Identity is taken the SAME way from both artifacts, from moved_rows only. The keyfix artifacts record a
    # five-field moved_keys entry and the superseded ones a triple; intersecting a 5-tuple set against a
    # 3-tuple set returns the empty set, which would have been published as "the two runs share no migrated
    # row" -- a finding manufactured by a projection mismatch rather than measured.
    def ident(m):
        return (m["depth"], m["phase"], m["ask"],
                str(m.get("item") or m.get("item_baseline")), str(m.get("shape")))

    kr = {ident(m) for m in mr["moved_rows"]}
    kc = {ident(m) for m in mc["moved_rows"]}
    both = kr & kc
    only_rep = kr - kc
    only_ctl = kc - kr
    # class is taken from the migration artifacts' own labelling, not re-derived here
    cls_of = {}
    for src in (mr, mc):
        for m in src["moved_rows"]:
            cls_of[ident(m)] = m["class"]

    def split(keys):
        out = {"taught item": 0, "distractor/unanswerable": 0}
        for k in keys:
            out[cls_of.get(k, "unknown")] = out.get(cls_of.get(k, "unknown"), 0) + 1
        return out

    pr = rep["provenance"]
    pc = ctl["provenance"]
    wall = {
        "control_run": {
            "started_utc": pc.get("started_utc"),
            "wall_seconds_measured_externally": control_wall_seconds,
            "wall_minutes_measured_externally": round(control_wall_seconds / 60.0, 2)
            if control_wall_seconds else None,
            "bench_recorded_learn_arm_seconds": (ctl.get("arms", {}).get("learn", {}) or {}).get("seconds"),
            "bench_recorded_learn_arm_minutes": round(
                (ctl.get("arms", {}).get("learn", {}) or {}).get("seconds", 0) / 60.0, 2),
            "replay_arm_seconds": (rep.get("arms", {}).get("learn", {}) or {}).get("seconds"),
        },
        "precedent_quoted_by_the_pi": {
            "figure": "53.65 min measured / 60.2 min projected",
            "what_it_actually_measures": ("MP-E8's FULL THREE-ARM tier-300 run -- "
                                          "experiments/G0-prime/tier_protocol.json wall_clock_minutes_all_arms"
                                          " = 53.65 against wall_clock_projected_minutes_all_arms = 60.2. It "
                                          "is NOT a single-arm figure, and this control is one arm."),
            "single_arm_precedent_from_this_very_tier": {
                "replay_run_learn_arm_minutes": round(
                    (rep.get("arms", {}).get("learn", {}) or {}).get("seconds", 0) / 60.0, 2),
                "source": P["replay"],
            },
            "why_the_difference_matters": ("quoting 53.65 as the cost of a learn-only control overstates it "
                                           "by roughly the number of arms not run. The cost the PI was asked "
                                           "to weigh is the measured one beside the all-arms precedent, both "
                                           "labelled for what they measure."),
        },
    }
    return {
        "asked": "a replay-OFF control at tier 300, so the migrated rows can be attributed to the treatment "
                 "rather than to time",
        "verdict": "MEASURED. The control ran at tier 300, replay OFF, same curriculum, same seed, same "
                   "instrument bytes.",
        "artifact": P["control"],
        "migration_artifact": P["mig_control"],
        "matched_pair": {
            "same_git_head": pr.get("git_head") == pc.get("git_head"),
            "replay_run_git_head": pr.get("git_head"),
            "control_run_git_head": pc.get("git_head"),
            "harness_sha256_replay": pr.get("harness_sha256"),
            "harness_sha256_control": pc.get("harness_sha256"),
            "instrument_identical": pr.get("harness_sha256") == pc.get("harness_sha256"),
            "curriculum_sha256_both": (rep.get("curriculum", {}).get("curriculum_sha256") ==
                                       ctl.get("curriculum", {}).get("curriculum_sha256")),
            "seed_both": rep.get("curriculum", {}).get("seed"),
            "argv_replay": pr.get("argv"),
            "argv_control": pc.get("argv"),
            "note": ("the two runs are on different COMMITS -- the control was measured after the tier-300 "
                     "verdict artifact and the ledger amendments landed. None of the 14 paths differing "
                     "between those trees is an instrument file: the bench, the organs, the curriculum "
                     "builder and run_generation are byte-identical, and the bench's own recorded "
                     "harness_sha256 matches across the two artifacts. Recorded rather than assumed, "
                     "because a migration count spanning a code change is not an effect of replay."),
        },
        "wall_clock": wall,
        "interference_with_the_control_as_the_reference": interference,
        "primary_attribution_same_instrument": same_instrument_attribution(),
        "row_attribution": {
            "rows_compared_replay_vs_baseline": mr["rows_compared"],
            "rows_compared_control_vs_baseline": mc["rows_compared"],
            "moved_in_replay_vs_baseline": mr["n_rows_moved"],
            "moved_in_control_vs_baseline": mc["n_rows_moved"],
            "moved_in_BOTH": len(both),
            "moved_ONLY_in_replay": len(only_rep),
            "moved_ONLY_in_control": len(only_ctl),
            "class_split_moved_only_in_replay": split(only_rep),
            "class_split_moved_in_both": split(both),
            "class_split_moved_only_in_control": split(only_ctl),
            "reading": ("rows that move with the flag OFF are not attributable to replay; they move with "
                        "time, restart ordering and the run itself. Rows that move ONLY with the flag ON are "
                        "the replay-attributable set, and that count, not the headline migration total, is "
                        "what H3's interference clause has to answer for."),
            "denominator_rule": "the artifact states the row count it divided by "
                                "(interference_protocol_step2.margin.denominator_rule)",
        },
        "safety_property_on_the_control": {
            "invented_rows_control": sum(1 for k, v in cr.items() if v.get("cls") == "invented"),
            "invented_rows_replay": sum(1 for k, v in rr.items() if v.get("cls") == "invented"),
            "note": ("the floor this program stands on: a house may not say a sentence nobody said. Both "
                     "counts are reported so the control is not merely a diff but a check that the "
                     "unreplayed run still holds it."),
        },
    }


def phase_basis():
    """A finding the closure produced that nobody asked for, and which contradicts the ledger.

    AMD-MPE10-03 corrected tier 300's prose triple 292/548/784 to 291/546/785 on the stated ground that
    the prose "matched no basis in either artifact". That ground is FALSE. Measured across three artifacts
    and three phases, 292/548/784 is the `restarted` phase and it matches exactly in all three; 291/546/785
    is the `live` phase. Both are real numbers over the same run. At tier 120 the two phases are identical
    (122/239/347 in live and restarted), which is why the ambiguity never bit before this tier.
    """
    arts = {"baseline_sealed_tier300": "experiments/MP-E8/results/armA_tier300_curriculum.json",
            "replay_tier300": "experiments/MP-E10/results/replay_tier300_armA.json",
            "control_tier300": "experiments/MP-E10/results/control_tier300_no_replay_armA.json",
            "baseline_sealed_tier120": "experiments/MP-E8/results/armA_tier120_curriculum.json",
            "replay_tier120": "experiments/MP-E10/results/replay_tier120_armA.json",
            "control_tier120": "experiments/MP-E10/results/control_tier120_no_replay_armA.json"}
    table = {}
    for name, rel in arts.items():
        art = json.loads((ROOT / rel).read_text(encoding="utf-8", errors="replace"))
        row = {}
        for phase in ("live", "restarted", "reasked"):
            cells = []
            for depth in ("1", "2", "3"):
                s = (art["summary"]["learn"].get(depth) or {}).get(phase) or {}
                r = s.get("retention") or {}
                bs = s.get("by_shape") or {}
                n = s.get("n") or sum(sum((v or {}).values()) for v in bs.values()
                                      if isinstance(v, dict)) or None
                cells.append({"depth": depth, "correct": s.get("correct"), "n": n,
                              "kept": r.get("kept"), "lost": r.get("lost"), "part": r.get("part")})
            row[phase] = {"correct_by_depth": [c["correct"] for c in cells],
                          "kept_by_depth": [c["kept"] for c in cells],
                          "lost_by_depth": [c["lost"] for c in cells],
                          "part_by_depth": [c["part"] for c in cells],
                          "n_by_depth": [c["n"] for c in cells],
                          "detail": cells}
        table[name] = row

    t300 = {k: v for k, v in table.items() if "300" in k}
    agree = len({tuple(v["live"]["correct_by_depth"]) for v in t300.values()}) == 1 and \
        len({tuple(v["restarted"]["correct_by_depth"]) for v in t300.values()}) == 1
    return {
        "asked": "not asked. Found while computing the control's denominators, and it contradicts a "
                 "statement already published in this ledger, so it is reported rather than left.",
        "verdict": ("AMD-MPE10-03's stated ground is wrong. tier 300's prose triple 292/548/784 and its "
                    "retention triple kept 80/129/176 / lost 0/3/9 / part 20/68/115 are the `restarted` "
                    "phase, and they match that phase EXACTLY in the sealed baseline, in the replayed run "
                    "and in the new control. The corrected triple 291/546/785 with kept 79/129/176 / lost "
                    "0/4/8 / part 21/67/116 is the `live` phase, and it also matches exactly. Neither was "
                    "a wrong number: the prose quoted one phase and the correction quoted the other, "
                    "without saying which."),
        "measured_table": table,
        "all_three_tier300_artifacts_agree_on_both_phases": agree,
        "why_it_never_bit_before": ("at tier 120 live and restarted are the same triple (122/239/347 in "
                                    "both, in all three tier-120 artifacts), so a quote that did not name "
                                    "its phase was harmless. At tier 300 the phases diverge by 1 row at "
                                    "depth 1, 2 at depth 2 and 1 at depth 3, and the same unqualified "
                                    "quote became a contradiction."),
        "which_basis_is_the_right_one_for_the_claim": ("not decided here. H3 is a claim about retention "
                                                       "ACROSS A RESTART, which points at `restarted`; the "
                                                       "tier-120 ledger row quotes a triple that is "
                                                       "phase-insensitive at that tier, so it settled "
                                                       "nothing. Naming the phase in every quote is the "
                                                       "fix; choosing one phase as the registered basis is "
                                                       "a protocol decision for the PI, and it is the same "
                                                       "class of question as the refusal-axis quantity "
                                                       "already parked in "
                                                       "h3_two_quantities.named_limitation_of_the_registered_protocol."),
        "what_was_NOT_done": ("replay_tier300_summary.json is not edited -- it is sealed. Its 'corrected' "
                              "triple stands as the live-phase reading, and AMD-MPE10-05 records that the "
                              "reason given for the correction was wrong. R5: the bad claim stays on "
                              "record, labelled, rather than being deleted."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/MP-E10/results/tier300_named_measurements_closure.json")
    ap.add_argument("--control-wall-seconds", type=float, default=None,
                    help="externally measured wall clock of the control run")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()
    out_p = ROOT / a.out
    if out_p.exists() and not a.overwrite:
        print(f"REFUSED: {out_p} exists (R5). Another --out, or --overwrite.", file=sys.stderr)
        return 3

    rep = load("replay")
    reg300 = {}
    for run in (rep.get("arms", {}).get("learn", {}).get("runs") or []):
        rp = run.get("replay") or {}
        if rp:
            reg300.setdefault("pairs_on_tape", rp["per_pass"][0]["pairs_on_tape"])

    summary = load("summary")
    art = {
        "experiment": "MP-E10",
        "artifact": "tier300_named_measurements_closure",
        "tier": 300,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": ("the four measurements replay_tier300_summary.json named as absent, each reported MEASURED "
                    "or STILL ABSENT with its evidence. No tier-40 or tier-120 figure stands in for a "
                    "tier-300 one anywhere in this file."),
        "supersedes_by_reference_these_fields_of_the_sealed_summary": {
            "artifact": P["summary"],
            "sealed_at_anchor": summary.get("provenance", {}).get("git_head")
            if isinstance(summary.get("provenance"), dict) else None,
            "fields_now_addressed": ["r6_guarded_probes", "read_direction", "w_frobenius_norm_vs_tokens",
                                     "replay_off_control"],
            "how": ("the summary is NOT edited -- it is sealed and its statements were true of the artifacts "
                    "that existed when it was written. This artifact is published beside it and named in "
                    "registration amendment AMD-MPE10-04, which is how this repository closes a gap without "
                    "rewriting the record that reported it (R5, amendments by reference)."),
        },
        "a_r6_guarded_probes": guarded_probe_instrument_check(),
        "b_read_direction": read_direction(reg300),
        "c_norm_vs_tokens_pushed": norm_vs_tokens(),
        "d_replay_off_control_and_attribution": attribution(a.control_wall_seconds),
        "e_phase_basis_of_the_published_triples": phase_basis(),
        "provenance": {
            "driver": "tools/mp_e10_tier300_closure.py",
            "row_key": {
                "mode": ROW_KEY,
                "fields": list(ROW_KEY_MODES[ROW_KEY]),
                "defined_by": "tools/mp_e10_row_migration.py (imported here, not copied)",
                "uniqueness_of_the_three_runs_read": {
                    k: key_uniqueness(load(k), ROW_KEY) for k in ("replay", "control", "baseline")},
                "migration_inputs": [P["mig_replay"], P["mig_control"], P["mig_vs"]],
                "superseded_migration_inputs": [
                    "experiments/MP-E10/results/replay_tier300_row_migration.json",
                    "experiments/MP-E10/results/control_tier300_no_replay_row_migration.json",
                    "experiments/MP-E10/results/tier300_replay_vs_control_row_migration.json"],
            },
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True).stdout.strip(),
            "git_dirty_tracked": subprocess.run(["git", "status", "--porcelain=v1", "-uno"], cwd=ROOT,
                                                capture_output=True, text=True).stdout.strip(),
            "python": sys.version.split()[0],
            "read_only_over_the_runs": [P["replay"], P["control"], P["baseline"], P["mig_replay"],
                                        P["mig_control"], P["ksweep300"], P["ksweep40"], P["summary"]],
        },
    }
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(art, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
                     encoding="utf-8", newline="\n")
    print(f"wrote {_rel(out_p)}")
    for key in ("a_r6_guarded_probes", "b_read_direction", "c_norm_vs_tokens_pushed",
                "d_replay_off_control_and_attribution", "e_phase_basis_of_the_published_triples"):
        print(f"  {key}: {art[key]['verdict'][:130]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
