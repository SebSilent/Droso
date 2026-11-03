"""MP-E9 GATE HARNESS -- implements H1-H4 and abort conditions C1-C3 against the REGISTERED numbers.

WHY THIS FILE READS ITS OWN REGISTRATION INSTEAD OF STATING THRESHOLDS. Every number this harness
judges lives in `experiments/MP-E9/registration.json`: the prose threshold in `hypotheses`, and the
pre-treatment baseline in `measured_baseline_at_registration`. Restating "36 arbiter-tell rows" or
"38/75/115" here would create a second copy that can drift, and a drifted copy is worse than none,
because it looks like the registered standard while measuring something else. The numeric form of each
prose threshold is carried in `hypotheses.H*.numeric_thresholds`, added to the registration BEFORE any
run, and a missing anchor raises rather than defaulting.

WHAT IT DOES AND DOES NOT CLAIM. MP-E9 has not been run. This harness exists so that when a treatment
arm produces an evidence file, the verdict is computed by frozen code rather than improvised while the
result is visible -- which is the whole of R2. In `--validate-registration` mode it runs on the CURRENT
committed evidence, where every hypothesis is EXPECTED to sit exactly where the registration recorded
the pre-treatment baseline. Reproducing that baseline proves the wiring; it is not a result, and the
`status` field says so.

THE PRECONDITION IS NOT COSMETIC. `tier_protocol.json` requires the noise floor to be established
before any treatment arm is scored, and the clone criterion is now R13(a) as ruled by the PI. If that
verdict is not MET the harness refuses to score: attributing instrument noise to a treatment is the
failure mode the gate exists to prevent.

WORD BOUNDARIES, NOT SUBSTRINGS. The morphology class is matched on whole-word forms from the
registration's `registered_kin` (surface/stem pairs). Substring matching would score `spring` and
`bring` as members of the `ring` class, which would inflate exactly the number H3 is judged on.

THE PARTS THAT CANNOT BE COMPUTED FROM THE BENCH. H4's battery invariants (frozen 19/24 with ELECTRIC
off, guarded 4/4) come from the held-out battery, a different instrument with its own artifact. They
are reported as not_evaluated with the flag that would settle them, never as a pass by omission.

Run:  .venv/Scripts/python.exe tools/mp_e9_gate.py --validate-registration
      .venv/Scripts/python.exe tools/mp_e9_gate.py --evidence path/to/post_treatment.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import tools.bench_noise_floor as nf          # noqa: E402
import tools.word_provenance as wp            # noqa: E402

REG = HERE / "experiments" / "MP-E9" / "registration.json"
NOISE = HERE / "experiments" / "G0-prime" / "results" / "noise_floor" / "noise_floor.json"
TIERS = HERE / "experiments" / "G0-prime" / "tier_protocol.json"
COMMITTED = HERE / "docs" / "evidence" / "electric_learn_bench.json"


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def anchor(node, path):
    """Fetch a registered number by its path. A missing anchor is an error, never a default."""
    for k in path:
        if not isinstance(node, dict) or k not in node:
            raise KeyError(f"registered anchor missing: {'.'.join(path)}")
        node = node[k]
    return node


def row_text(r):
    return " ".join(str(r.get(f) or "") for f in ("ask", "said", "own", "taught", "item")).lower()


# ------------------------------------------------------------------ the metrics, one function each

def word_level(doc):
    """The grader's verdicts, plus the counts the thresholds name. Sets are built once."""
    res = wp.audit(doc)
    sets = wp.build_sets(doc)
    says, frame, absence = wp.sets_from(doc)
    says_audits = [wp.audit_row(r, sets) for _k, r in says]
    abs_audits = [wp.audit_row(r, sets) for _k, r in absence]
    return {
        "rows_audited": res["rows_audited"],
        "UNTRACEABLE_ASSERTED_rows": res["verdict_counts"]["UNTRACEABLE_ASSERTED"],
        "UNTRACEABLE_HEARD_rows": res["verdict_counts"]["UNTRACEABLE_HEARD"],
        "asserted_words": sorted(w for w, e in res["untraceable_words"].items()
                                 if "asserted" in e["severity"]),
        "heard_words": {w: e["rows"] for w, e in res["untraceable_words"].items()
                        if "heard" in e["severity"]},
        "says_rows": len(says),
        "says_rows_flagged_asserted": sum(1 for a in says_audits
                                          if a["verdict"] == "UNTRACEABLE_ASSERTED"),
        "narration_frame_rows": len(frame),
        "guarded_absence_rows": len(absence),
        "absence_rows_admitted_by_form": sum(1 for a in abs_audits
                                             if a["verdict"] == "admitted_refusal"),
        "silence_rows": res["verdict_counts"]["silent"],
    }


def src_count(doc, value):
    return sum(1 for _k, r in wp.probe_rows(doc) if r.get("src") == value)


def morphology_class(doc, forms):
    """Rows whose text contains any registered FORM of the class, as a whole word.

    `forms` maps a class label to its surface/stem pair, e.g. toll -> ('toll','tolls'). The class
    label `toll` is the one H3 is judged on; the kin are reported beside it because the defect is the
    stemmer, so a fix that converts toll but not carries has not fixed the class.
    """
    pats = {label: [re.compile(r"\b%s\b" % re.escape(f)) for f in pair]
            for label, pair in forms.items()}
    rows = list(wp.probe_rows(doc))
    out = {}
    for label, ps in pats.items():
        hit = [(k, r) for k, r in rows if any(p.search(row_text(r)) for p in ps)]
        out[label] = {"rows": len(hit),
                      "correct": sum(1 for _k, r in hit if r.get("cls") == "correct"),
                      "refused": sum(1 for _k, r in hit if r.get("cls") == "refused"),
                      "echo": sum(1 for _k, r in hit if r.get("cls") == "echo"),
                      "partial": sum(1 for _k, r in hit if r.get("cls") == "partial")}
    return out


def says_gap_census(doc, asks):
    want = set(asks)
    rows = [r for _k, r in wp.probe_rows(doc) if str(r.get("ask")) in want]
    by = {}
    for r in rows:
        by[str(r.get("cls"))] = by.get(str(r.get("cls")), 0) + 1
    return {"asks": sorted(want), "rows": len(rows), "by_cls": dict(sorted(by.items())),
            "refused_plus_echo": by.get("refused", 0) + by.get("echo", 0),
            "speaking": by.get("partial", 0) + by.get("correct", 0)}


def learn_correct_live(doc):
    h = nf.headline(doc)
    return {d: (h.get("learn", {}).get(d, {}).get("live", {}) or {}).get("correct", 0)
            for d in ("1", "2", "3")}


def invented_rows(doc):
    """The bench's own sentence-level INVENTED verdicts, summed from the summary matrix."""
    tot = 0
    for _arm, depths in (doc.get("summary") or {}).items():
        if not isinstance(depths, dict):
            continue
        for _depth, phases in depths.items():
            if not isinstance(phases, dict):
                continue
            for _phase, blk in phases.items():
                by_shape = (blk or {}).get("by_shape")
                if not isinstance(by_shape, dict):
                    continue
                for counts in by_shape.values():
                    tot += int((counts or {}).get("invented", 0) or 0)
    return {"summary_invented_rows": tot, "failure_list_rows": len(doc.get("failures") or [])}


def correct_row_movement(candidate, reference):
    """Positional: rows correct in the reference and not now, and the reverse."""
    a = dict(nf.flat(reference))
    b = dict(nf.flat(candidate))
    shared = [k for k in a if k in b]
    losing = [k for k in shared if a[k]["cls"] == "correct" and b[k]["cls"] != "correct"]
    gaining = [k for k in shared if a[k]["cls"] != "correct" and b[k]["cls"] == "correct"]
    return {"rows_compared": len(shared),
            "reference_only_rows": len([k for k in a if k not in b]),
            "candidate_only_rows": len([k for k in b if k not in a]),
            "rows_losing_correct": len(losing), "rows_gaining_correct": len(gaining),
            "losing_list": losing[:20], "gaining_list": gaining[:20]}


# ------------------------------------------------------------------ verdicts

def kin_forms(reg):
    """toll plus every registered kin, as (surface, stem) pairs."""
    forms = {"toll": ("toll", "tolls")}
    for pair in anchor(reg, ("hypotheses", "H3", "registered_kin")):
        parts = str(pair).split("/")
        forms[pairs_label(parts)] = tuple(parts)
    return forms


def pairs_label(parts):
    return parts[-1]


def evaluate(candidate, reference, reg, noise, tiers, battery=None):
    base = reg["measured_baseline_at_registration"]
    hyp = reg["hypotheses"]
    nt = {h: anchor(reg, ("hypotheses", h, "numeric_thresholds")) for h in ("H1", "H2", "H3", "H4")}

    wl = word_level(candidate)
    forms = kin_forms(reg)
    morph = morphology_class(candidate, forms)
    asks = base["word_level_from_the_new_grader"]["UNTRACEABLE_ASSERTED_asks"]
    census = says_gap_census(candidate, asks)
    learn = learn_correct_live(candidate)
    floor = base["sentence_level"]["learn_correct_live_depths_1_2_3"]
    move = correct_row_movement(candidate, reference)
    arb_tell = src_count(candidate, "arbiter tell")
    inv = invented_rows(candidate)
    tier_ok = candidate.get("items") == 40 and candidate.get("probes") == 136

    r13a = str((noise or {}).get("criterion_r13a", {}).get("verdict", "NOISE FLOOR ARTIFACT ABSENT"))
    precondition_met = r13a.startswith("MET")

    toll_correct = morph["toll"]["correct"]
    h1_pass = wl["UNTRACEABLE_ASSERTED_rows"] == nt["H1"]["asserted_untraceable_rows_max"]
    h2_pass = (wl["says_rows_flagged_asserted"] == nt["H2"]["says_rows_flagged_max"]
               and arb_tell == nt["H2"]["arbiter_tell_rows_equal"]
               and move["rows_losing_correct"] == nt["H2"]["rows_losing_correct_max"]
               and census["refused_plus_echo"] >= nt["H2"]["says_gap_refused_plus_echo_min"])
    h3_pass = (toll_correct >= nt["H3"]["toll_correct_min"]
               and inv["summary_invented_rows"] == nt["H3"]["invented_rows_max"]
               and wl["UNTRACEABLE_ASSERTED_rows"] == nt["H3"]["asserted_untraceable_rows_max"]
               and wl["guarded_absence_rows"] == nt["H3"]["guarded_absence_rows_equal"])
    h4_invariants = (wl["guarded_absence_rows"] == nt["H4"]["guarded_absence_rows_equal"]
                     and wl["absence_rows_admitted_by_form"] == nt["H4"]["absence_admitted_by_form_equal"]
                     and all(learn[d] >= floor[i] for i, d in enumerate(("1", "2", "3"))))
    bat = battery or {}
    # The instrument (tools/mp_e9_battery.py) nests the four numbers under "measured" beside its
    # provenance block; a hand-written fixture carries them flat. Accept both, prefer the nested
    # form. A missing key must not silently read as a pass.
    bat_m = bat.get("measured") or bat
    h4_battery = (bat_m.get("frozen_correct") == nt["H4"]["battery_frozen_correct"]
                  and bat_m.get("frozen_total") == nt["H4"]["battery_frozen_total"]
                  and bat_m.get("guarded_pass") == nt["H4"]["battery_guarded_pass"]
                  and bat_m.get("guarded_total") == nt["H4"]["battery_guarded_total"]) if bat else None
    # H4's clause says "WITH ELECTRIC OFF". Four numbers alone do not carry that condition: a
    # battery run with the treatment wired in would satisfy all four and measure a different
    # thing. The state is read from provenance.electric, which the instrument derives from
    # provenance.code_flags -- stamped on EVERY path by run_generation.py:1410-1416, "per the E25
    # invariant that a missing key must never be indistinguishable from a deliberate off". So an
    # old journal with no keys reports `unrecorded`, and unrecorded is NOT off.
    elec = (bat.get("provenance") or {}).get("electric") or {}
    electric_off = bool(elec.get("verified")) and elec.get("state") == "off"
    h4_battery_clause = (bool(h4_battery) and electric_off) if bat else None

    return {
        "preconditions": {
            "noise_floor_r13a": r13a,
            "noise_floor_blocks_scoring": not precondition_met,
            "tier_40_protocol": {
                "items": candidate.get("items"), "probes": candidate.get("probes"),
                "matches_registered_tier_40": tier_ok,
                "registered": anchor(tiers, ("compute_budget_and_deferral", "measured_tier_40"))
                if tiers else None},
        },
        "H1": {"threshold_as_registered": hyp["H1"]["threshold"],
               "numeric": nt["H1"], "observed": {"asserted_rows": wl["UNTRACEABLE_ASSERTED_rows"],
                                                 "heard_rows_reported_not_counted":
                                                     wl["UNTRACEABLE_HEARD_rows"]},
               "pass": h1_pass},
        "H2": {"threshold_as_registered": hyp["H2"]["threshold"],
               "numeric": nt["H2"],
               "observed": {"says_rows_flagged": wl["says_rows_flagged_asserted"],
                            "arbiter_tell_rows": arb_tell,
                            "rows_losing_correct": move["rows_losing_correct"],
                            "says_gap_refused_plus_echo": census["refused_plus_echo"]},
               "pass": h2_pass},
        "H3": {"threshold_as_registered": hyp["H3"]["threshold"],
               "numeric": nt["H3"],
               "observed": {"toll_correct": toll_correct, "toll_rows": morph["toll"]["rows"],
                            "kin_correct": {k: v["correct"] for k, v in morph.items() if k != "toll"},
                            "invented_rows": inv["summary_invented_rows"],
                            "asserted_rows": wl["UNTRACEABLE_ASSERTED_rows"],
                            "guarded_absence_rows": wl["guarded_absence_rows"]},
               "pass": h3_pass},
        "H4": {"threshold_as_registered": hyp["H4"]["threshold"], "numeric": nt["H4"],
               "observed": {"guarded_absence_rows": wl["guarded_absence_rows"],
                            "absence_admitted_by_form": wl["absence_rows_admitted_by_form"],
                            "learn_correct_live": learn},
               "invariants_pass": h4_invariants,
               "battery": ("not supplied -- pass --battery PATH" if not bat else h4_battery),
               "battery_measured": (None if not bat else bat_m),
               "battery_electric": ("not supplied" if not bat else
                                    {"state": elec.get("state"),
                                     "verified": elec.get("verified"),
                                     "off_counts_as_verified": electric_off}),
               "battery_clause": ("not supplied -- pass --battery PATH" if not bat
                                  else h4_battery_clause),
               "pass": (h4_invariants and h4_battery_clause) if bat else None},
        "abort_conditions": {
            "C1": {"fired": not h1_pass,
                   "measured_by": reg["abort_conditions"]["C1"]["measured_by"],
                   "note": ("D-G0P-03 as ruled: C1 counts the ASSERTED class only. heard-not-told rows "
                            "are reported and are NOT aborts -- the harness put that word in front of "
                            "the organism, so it is a leakage channel in the instrument rather than "
                            "confabulation by the organism.")},
            "C2": {"fired": (wl["guarded_absence_rows"] != nt["H3"]["guarded_absence_rows_equal"]
                             or wl["absence_rows_admitted_by_form"] != wl["guarded_absence_rows"]),
                   "measured_by": reg["abort_conditions"]["C2"]["measured_by"]},
            "C3": {"fired": any(learn[d] < floor[i] for i, d in enumerate(("1", "2", "3"))),
                   "measured_by": reg["abort_conditions"]["C3"]["measured_by"],
                   "registered_floor": floor, "observed": learn},
            # C4 and C5 were ABSENT from the first version of this output. Absence and a deliberate
            # false are different claims, and the house rule (run_generation.py:1410-1416, "a
            # missing key must never be indistinguishable from a deliberate off") says a condition
            # that cannot be measured yet must be reported as unable, not as unmeasured.
            "C4": {"fired": None, "state": "NOT YET MEASURABLE",
                   "measured_by": reg["abort_conditions"]["C4"]["measured_by"],
                   "why": "C4 counts qa_store rows whose provenance is neither person_marked nor "
                          "person_paraphrase. That population only exists once "
                          "ELECTRIC_QA_MORPH_NORMALIZE widens the store keys, which is PRE-1 / B.2 "
                          "step 2 and has not been implemented. A pre-treatment count over today's "
                          "288 electric_qa_store rows would measure a key form the condition does "
                          "not describe, so no number is reported rather than a misleading one."},
            "C5": {"fired": None, "state": "VACUOUS PRE-TREATMENT",
                   "measured_by": reg["abort_conditions"]["C5"]["measured_by"],
                   "why": "C5 groups GAINED rows by probe shape. In the pre-treatment self-check "
                          "rows_gaining_correct == 0, so there is nothing to group and the "
                          "condition cannot fire. It becomes measurable only against a treatment "
                          "candidate, where row_movement_vs_reference supplies the gains."},
        },
        "word_level": wl,
        "morphology_class": morph,
        "says_gap_census": census,
        "row_movement_vs_reference": move,
        "src_counts": {"arbiter tell": arb_tell, "arbiter head": src_count(candidate, "arbiter head"),
                       "electric_absence": src_count(candidate, "electric_absence")},
        "invented": inv,
        "registered_baseline": {
            "UNTRACEABLE_ASSERTED_rows": base["word_level_from_the_new_grader"]["UNTRACEABLE_ASSERTED_rows"],
            "UNTRACEABLE_HEARD_rows": base["word_level_from_the_new_grader"]["UNTRACEABLE_HEARD_rows"],
            "arbiter_tell_rows": base["word_level_from_the_new_grader"]["arbiter_tell_rows"],
            "guarded_absence_rows": base["word_level_from_the_new_grader"]["guarded_absence_rows"],
            "narration_frame_rows": base["word_level_from_the_new_grader"]["narration_frame_rows"],
            "silence_rows": base["word_level_from_the_new_grader"]["silence_rows"],
            "toll_correct": base["morphology_class_toll"]["correct"],
            "toll_rows": base["morphology_class_toll"]["rows_touching_toll"],
            "says_gap_rows": sum(base["says_gap_ask_census"][k]
                                 for k in ("refused", "echo_what", "says_partial")),
            "learn_correct_live_depths_1_2_3": floor,
            "rows_audited": base["word_level_from_the_new_grader"]["rows_audited"],
        },
    }


def validate_registration(res):
    """Does the harness reproduce the numbers the registration says it will see, pre-treatment?"""
    want = res["registered_baseline"]
    got = {
        "UNTRACEABLE_ASSERTED_rows": res["word_level"]["UNTRACEABLE_ASSERTED_rows"],
        "UNTRACEABLE_HEARD_rows": res["word_level"]["UNTRACEABLE_HEARD_rows"],
        "arbiter_tell_rows": res["src_counts"]["arbiter tell"],
        "guarded_absence_rows": res["word_level"]["guarded_absence_rows"],
        "narration_frame_rows": res["word_level"]["narration_frame_rows"],
        "silence_rows": res["word_level"]["silence_rows"],
        "toll_correct": res["morphology_class"]["toll"]["correct"],
        "toll_rows": res["morphology_class"]["toll"]["rows"],
        "says_gap_rows": res["says_gap_census"]["rows"],
        "learn_correct_live_depths_1_2_3": list(res["H4"]["observed"]["learn_correct_live"].values()),
        "rows_audited": res["word_level"]["rows_audited"],
    }
    bad = []
    for k, exp in sorted(want.items()):
        act = got[k]
        ok = act == exp
        print(f"[mp-e9] {'OK  ' if ok else 'FAIL'} {k}: harness={act} registered={exp}")
        if not ok:
            bad.append(k)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default=str(COMMITTED))
    ap.add_argument("--reference", default=str(COMMITTED),
                    help="the row matrix to judge 'no correct row is lost' against")
    ap.add_argument("--battery", default=None, help="held-out battery artifact for H4's invariants")
    ap.add_argument("--validate-registration", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    reg, cand, ref = load(REG), load(a.evidence), load(a.reference)
    tiers = load(TIERS) if TIERS.exists() else {}
    noise = load(NOISE) if NOISE.exists() else None
    battery = load(a.battery) if a.battery else None

    res = evaluate(cand, ref, reg, noise, tiers, battery)
    same = pathlib.Path(a.evidence).resolve() == pathlib.Path(a.reference).resolve()
    is_committed = pathlib.Path(a.evidence).resolve() == COMMITTED.resolve()
    res["status"] = ("BASELINE SELF-CHECK -- candidate is the registered pre-treatment evidence. "
                     "No treatment has been run; every hypothesis below is in its pre-treatment state "
                     "and is expected to fail. This is a wiring check, not a result."
                     if is_committed else "POST-TREATMENT EVALUATION" + ("" if not same else " (reference=candidate, so no row movement is claimable)"))

    bad = validate_registration(res) if a.validate_registration else []

    if a.out:
        p = pathlib.Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"[mp-e9] -> {p}")

    for h in ("H1", "H2", "H3", "H4"):
        v = res[h]
        print(f"[mp-e9] {h}: pass={v['pass']} observed={v['observed']}")
    print(f"[mp-e9] aborts: " + ", ".join(
        f"{k}={v['fired']}" for k, v in sorted(res["abort_conditions"].items())))
    print(f"[mp-e9] {res['status']}")

    if a.validate_registration:
        if bad:
            print(f"[mp-e9] REGISTRATION VALIDATION FAILED on: {', '.join(bad)}")
            return 1
        print("[mp-e9] registration validation: the harness reproduces every registered baseline number")
        return 0
    if res["preconditions"]["noise_floor_blocks_scoring"]:
        print("[mp-e9] REFUSING TO SCORE: the clone criterion (R13a) is not met on this instrument")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
