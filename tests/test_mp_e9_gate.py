"""Tests for the MP-E9 gate harness: does it execute the REGISTERED standard, and only that?

The failure these tests exist to prevent is a harness that looks like the registration while
measuring something else -- thresholds restated as literals, a missing invariant scored as a pass, or
an abort condition widened to include a class the PI explicitly ruled non-aborting. So the tests change
the registration and check that the verdict moves with it: if the harness ignored the file, these fail.
"""
import copy
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.mp_e9_gate as mg        # noqa: E402

COMMITTED = mg.COMMITTED
REG = mg.load(mg.REG)
DOC = mg.load(COMMITTED)
REF = DOC
NOISE = mg.load(mg.NOISE)
TIERS = mg.load(mg.TIERS)


@pytest.fixture(scope="module")
def res():
    return mg.evaluate(DOC, REF, REG, NOISE, TIERS)


def test_harness_reproduces_every_registered_baseline_number():
    """--validate-registration is the wiring check: on the pre-treatment evidence the harness must
    produce exactly the numbers the registration says it will produce."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "mp_e9_gate.py"),
                        "--validate-registration"], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout, r.stdout
    for k in ("UNTRACEABLE_ASSERTED_rows", "toll_rows", "arbiter_tell_rows",
              "learn_correct_live_depths_1_2_3"):
        assert f"OK   {k}" in r.stdout, f"{k} was not checked:\n{r.stdout}"


def test_verdicts_move_when_the_registration_moves():
    """Each verdict must be computed from the registration's numbers, not from literals in the harness.

    The decisive form: loosen exactly the number that is currently binding and the verdict flips. A
    hardcoded threshold would ignore the edited file and the test would fail -- which is the only way to
    tell "reads the registration" apart from "happens to agree with it today"."""
    reg = copy.deepcopy(REG)
    reg["hypotheses"]["H1"]["numeric_thresholds"]["asserted_untraceable_rows_max"] = 16
    assert mg.evaluate(DOC, REF, reg, NOISE, TIERS)["H1"]["pass"] is True

    # H2's only binding term on today's evidence is says_rows_flagged_max: arbiter-tell is already 36,
    # no row loses correct, and the census is exactly 65.
    reg = copy.deepcopy(REG)
    reg["hypotheses"]["H2"]["numeric_thresholds"]["says_rows_flagged_max"] = 16
    assert mg.evaluate(DOC, REF, reg, NOISE, TIERS)["H2"]["pass"] is True

    reg = copy.deepcopy(REG)
    reg["hypotheses"]["H2"]["numeric_thresholds"]["arbiter_tell_rows_equal"] = 35
    r = mg.evaluate(DOC, REF, reg, NOISE, TIERS)
    assert r["H2"]["observed"]["arbiter_tell_rows"] == 36 and r["H2"]["pass"] is False

    reg = copy.deepcopy(REG)
    reg["hypotheses"]["H3"]["numeric_thresholds"]["toll_correct_min"] = 0
    reg["hypotheses"]["H3"]["numeric_thresholds"]["asserted_untraceable_rows_max"] = 16
    assert mg.evaluate(DOC, REF, reg, NOISE, TIERS)["H3"]["pass"] is True

    # The learn floor is read from the registration's baseline, so raising it must break H4 and C3.
    reg = copy.deepcopy(REG)
    reg["measured_baseline_at_registration"]["sentence_level"]["learn_correct_live_depths_1_2_3"] = \
        [999, 999, 999]
    bat = {"frozen_correct": 19, "frozen_total": 24, "guarded_pass": 4, "guarded_total": 4}
    r = mg.evaluate(DOC, REF, reg, NOISE, TIERS, battery=bat)
    assert r["H4"]["invariants_pass"] is False, "a floor of 999 must not pass at 38/75/115"
    assert r["abort_conditions"]["C3"]["fired"] is True


def test_a_missing_anchor_raises_instead_of_defaulting():
    reg = copy.deepcopy(REG)
    del reg["hypotheses"]["H2"]["numeric_thresholds"]
    with pytest.raises(KeyError):
        mg.evaluate(DOC, REF, reg, NOISE, TIERS)


def test_numeric_thresholds_are_transcriptions_and_carry_their_source(res):
    for h in ("H1", "H2", "H3", "H4"):
        nt = REG["hypotheses"][h]["numeric_thresholds"]
        assert "transcribed_from" in nt, f"{h} has a number with no stated origin"
        assert isinstance(nt["transcribed_from"], str) and nt["transcribed_from"]
    # H2/H3/H4 prose is unchanged, so the transcription source must still equal it.
    for h in ("H2", "H3", "H4"):
        assert REG["hypotheses"][h]["numeric_thresholds"]["transcribed_from"] == \
               REG["hypotheses"][h]["threshold"]
    # H1's prose WAS amended by the ruling, so its source string is deliberately the older text.
    assert REG["hypotheses"]["H1"]["numeric_thresholds"]["transcribed_from"] != \
           REG["hypotheses"]["H1"]["threshold"]
    assert "0 asserted-untraceable rows" in REG["hypotheses"]["H1"]["numeric_thresholds"]["transcribed_from"]


def test_c1_counts_the_asserted_class_and_fires_at_sixteen(res):
    """D-G0P-03 as a number: C1 fires at 16 today. Had the ruling gone the other way it would fire at
    22, and MP-E9 would have opened under a different abort condition than the one it is registered with."""
    c1 = res["abort_conditions"]["C1"]
    assert c1["fired"] is True
    assert res["H1"]["observed"]["asserted_rows"] == 16
    assert res["H1"]["observed"]["heard_rows_reported_not_counted"] == 6
    assert 16 + 6 == 22 and res["H1"]["observed"]["asserted_rows"] != 22


def test_heard_rows_are_reported_not_erased(res):
    wl = res["word_level"]
    assert wl["UNTRACEABLE_HEARD_rows"] == 6
    assert wl["heard_words"] == {"which": 3, "why": 3}
    assert wl["asserted_words"] == ["says"]


def test_h4_cannot_pass_by_omitting_the_battery(res):
    """A missing invariant is not a satisfied invariant."""
    assert res["H4"]["pass"] is None
    assert res["H4"]["invariants_pass"] is True
    assert "battery" in str(res["H4"]["battery"]).lower()
    good = {"frozen_correct": 19, "frozen_total": 24, "guarded_pass": 4, "guarded_total": 4,
            "provenance": {"electric": {"verified": True, "state": "off"}}}
    with_good = mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=good)
    assert with_good["H4"]["pass"] is True
    bad = dict(good, frozen_correct=18)
    with_bad = mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=bad)
    assert with_bad["H4"]["pass"] is False


def test_h4_battery_clause_carries_the_electric_condition_not_just_four_numbers():
    """H4's registered text says "battery frozen 19/24 WITH ELECTRIC OFF".

    The first version of the gate compared four numbers and nothing else, so a battery run with
    the treatment wired in would have satisfied the clause while measuring a different system.
    An unrecorded ELECTRIC state is not the same as a verified off one -- run_generation.py
    stamps the keys on every path precisely so the two cannot be confused.
    """
    numbers = {"frozen_correct": 19, "frozen_total": 24, "guarded_pass": 4, "guarded_total": 4}
    on = dict(numbers, provenance={"electric": {"verified": True, "state": "ON"}})
    assert mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=on)["H4"]["pass"] is False
    unrecorded = dict(numbers, provenance={"electric": {"verified": False, "state": "unrecorded"}})
    assert mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=unrecorded)["H4"]["pass"] is False
    no_provenance = dict(numbers)
    assert mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=no_provenance)["H4"]["pass"] is False, \
        "an artifact with no ELECTRIC provenance must not satisfy a clause that names ELECTRIC"


def test_the_gate_reads_the_instruments_nested_measured_block():
    """tools/mp_e9_battery.py writes provenance + measured; the gate must read the real shape."""
    art = {"measured": {"frozen_correct": 19, "frozen_total": 24,
                        "guarded_pass": 4, "guarded_total": 4},
           "provenance": {"electric": {"verified": True, "state": "off", "chunks": 6}}}
    r = mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=art)
    assert r["H4"]["battery"] is True
    assert r["H4"]["battery_clause"] is True


def test_morphology_matching_is_whole_word():
    """`spring` and `bring` are not members of the `ring` class. Substring matching would inflate the
    count H3 is judged on, and the inflation would be invisible because it moves in the wrong direction
    only when the class is supposed to be small."""
    doc = {"arms": {"learn": {"probes": {"1": {"live": [
        {"ask": "what rings the bell", "said": "the bell rings", "cls": "correct", "src": "x",
         "item": "bell", "shape": "s", "mech": "m", "taught": "t", "own": "o", "reason": "r",
         "answered": 1},
        {"ask": "what springs the latch", "said": "the latch springs", "cls": "correct", "src": "x",
         "item": "latch", "shape": "s", "mech": "m", "taught": "t", "own": "o", "reason": "r",
         "answered": 1},
        {"ask": "what brings the dog", "said": "the dog brings", "cls": "correct", "src": "x",
         "item": "dog", "shape": "s", "mech": "m", "taught": "t", "own": "o", "reason": "r",
         "answered": 1}]}}}},
        "told": [], "failures": [], "items": 40, "probes": 136, "summary": {}}
    m = mg.morphology_class(doc, {"ring": ("rings", "ring")})
    assert m["ring"]["rows"] == 1, m


# --------------------------------------------------------------------------- flag-OFF pin, not a criterion
#
# Everything in this function describes the house BEFORE any MP-E9 treatment. ELECTRIC_QA_MORPH_NORMALIZE
# is expected to move `toll correct` off 0, and when it does this test must still pass, because it is
# measured on the pre-treatment evidence with both flags off. The failure it prevents is the quiet one:
# a treatment run flips a census pin, someone edits the pin to match, and R2's line that a criterion may
# not move after the result has been turned into a mechanism. The flag-ON expectations live in a SEPARATE
# function that reads its numbers from registered_predictions, never from literals.


def test_registered_toll_census_survives_whole_word_matching(res):
    """The registration says 54 rows touch `toll`, 0 correct. That number was produced before this
    matcher existed, so agreement is evidence the matcher is the same class, not a new one."""
    assert res["morphology_class"]["toll"]["rows"] == 54
    assert res["morphology_class"]["toll"]["correct"] == 0
    assert res["says_gap_census"]["rows"] == 81
    assert res["says_gap_census"]["refused_plus_echo"] == 65


def test_the_flag_off_pin_is_measured_with_both_flags_off():
    """A pin about the pre-treatment state is only a pin if the state it reads has no treatment in it.

    This reads the flags back off the artifact's own provenance rather than trusting that whoever
    ran the bench left them alone: an artifact produced with ELECTRIC_QA_MORPH_NORMALIZE on would
    satisfy every assertion above by accident while describing a different house.
    """
    prov = (DOC.get("provenance") or {}).get("electric_flags") or {}
    for f in ("ELECTRIC_ARBITER_HEAD_BOUND", "ELECTRIC_QA_MORPH_NORMALIZE"):
        assert prov.get(f, False) is False, f"{f} is ON in the artifact the flag-OFF pin reads"


# Cells the registered noise floor ALREADY accounts for: G0-prime measured 11 rows of 3,672 moving
# between three identical clones, all of them in these two cells, because `_note_spoken` is gated on
# a 2.0 s wall clock (organs/neural_language.py:946-948). R13 excluded exactly these cells from the
# noise-floor claim. Tolerating them here is not a criterion loosened after the result -- it is the
# registered tolerance applied in advance, and everything outside it is a hard failure.
R13_TIME_DEPENDENT_CELLS = ("learn/1/reasked", "learn/1/restarted")


def test_flag_off_reproduction_is_row_for_row_not_by_count():
    """The registered A/B requirement: an OFF arm must reproduce the pre-treatment artifact.

    Counts agree when a row has moved out of one class and into another, so counts cannot prove
    inertness. This compares row identity -- ask, said, src, cls -- keyed by the cell and item that
    produced it, so a difference names itself instead of becoming a delta.
    """
    off = ROOT / "experiments/MP-E9/results/ab_flag_off.json"
    if not off.exists():
        pytest.skip("flag-OFF A/B artifact not produced yet")
    cand = mg.load(off)

    def keyed(doc):
        out = {}
        for arm, res in (doc.get("arms") or {}).items():
            for depth, ph in (res.get("probes") or {}).items():
                for phase, rows in ph.items():
                    for r in rows:
                        out[(arm, depth, phase, str(r.get("item")), str(r.get("shape")))] = (
                            str(r.get("ask")), str(r.get("said")), str(r.get("src")),
                            str(r.get("cls")))
        return out

    base, new = keyed(DOC), keyed(cand)
    gained = {k: v for k, v in new.items() if k not in base}
    lost = {k: v for k, v in base.items() if k not in new}
    moved = {k: (base[k], new[k]) for k in base if k in new and base[k] != new[k]}

    def outside_r13(d):
        return {k: v for k, v in d.items()
                if f"{k[0]}/{k[1]}/{k[2]}" not in R13_TIME_DEPENDENT_CELLS}

    g, l, m = outside_r13(gained), outside_r13(lost), outside_r13(moved)
    assert not g and not l and not m, (
        f"flag-OFF run is not the pre-treatment house, outside the cells R13 already accounts for: "
        f"gained={list(g.items())[:2]} lost={list(l.items())[:2]} moved={list(m.items())[:2]}")
    # Inside the tolerated cells the difference is still counted and reported, never assumed away:
    # a flag-OFF run that moves MORE than the registered 11 rows is telling us something.
    n_r13 = len(gained) + len(lost) + len(moved)
    assert n_r13 <= 11, (
        f"{n_r13} rows moved, including inside the R13 cells; G0-prime measured 11 of 3,672 across "
        "three clones. More movement than the registered floor is a finding about the instrument, "
        "not a tolerance to widen.")


def test_noise_floor_precondition_blocks_scoring():
    """Scoring an arm on an instrument that cannot reproduce itself attributes noise to treatment."""
    blocked = mg.evaluate(DOC, REF, REG, None, TIERS)
    assert blocked["preconditions"]["noise_floor_blocks_scoring"] is True
    assert blocked["preconditions"]["noise_floor_r13a"] == "NOISE FLOOR ARTIFACT ABSENT"
    assert mg.evaluate(DOC, REF, REG, NOISE, TIERS)["preconditions"]["noise_floor_blocks_scoring"] is False


def test_tier_40_protocol_is_checked_not_assumed(res):
    assert res["preconditions"]["tier_40_protocol"]["matches_registered_tier_40"] is True
    other = json.loads(json.dumps(DOC))
    other["items"] = 120
    assert mg.evaluate(other, REF, REG, NOISE, TIERS)["preconditions"]["tier_40_protocol"] \
        ["matches_registered_tier_40"] is False


def test_amendments_are_partitioned_by_whether_a_result_existed():
    """R2 permits pre-run amendments and forbids post-result edits. MP-E9 now HAS results, so the
    guard cannot be "no amendment says results_existed" -- that would be false forever. It becomes
    two guards, and the second one is the stronger: after a result exists, an amendment may record
    an outcome but must declare that it moved no number, and the numbers themselves are checked
    against the artifact in test_a_recorded_outcome_is_the_artifact_it_names."""
    pre = [a for a in REG["registration_amendments"] if not a["results_existed"]]
    post = [a for a in REG["registration_amendments"] if a["results_existed"]]
    assert pre, "every amendment claims a result existed; nothing was registered before the run"

    for a in pre:
        assert a["what"] and a["why"], a
        # The flag's meaning is registered, not assumed. `results_existed` means a TREATMENT ARM
        # produced a result; baseline measurements are a separate fact and must be stated as one.
        assert a.get("treatment_results_existed") is False, \
            f"{a['what'][:40]}: treatment_results_existed missing or true"
        if a.get("baseline_measurements_existed"):
            # An instrument change made after a measurement exists is admissible in ONE direction:
            # it may remove a pass, never manufacture one. The direction has to be in the record,
            # or the amendment is unverifiable and R2's guard is decorative.
            assert a.get("direction"), \
                f"{a['what'][:40]}: baseline measurements existed and no direction was stated"

    for a in post:
        assert a.get("result_it_follows"), (
            f"{a['what'][:40]}: an amendment made after a treatment result must name that result")
        d = (a.get("direction") or "").lower()
        assert "no threshold" in d or "record only" in d or "prediction added" in d, (
            f"{a['what'][:40]}: post-result amendment does not declare that it moved no number "
            f"(direction={a.get('direction')!r})")


# --------------------------------------------------------------------------- flag-ON predictions
#
# These read their expected numbers from registered_predictions, which were transcribed from H1/H2/H3
# BEFORE any treatment artifact existed. Nothing below is a literal threshold: a number that appears
# in a test and not in the registration is a number the registration does not license.


PRED = REG.get("registered_predictions") or {}


def test_the_predictions_were_registered_before_any_treatment_ran():
    """R2, in the direction that matters: the prediction must predate the result it judges."""
    assert PRED, "registered_predictions is missing from the registration"
    assert PRED["written_before_any_treatment_ran"] is True
    stamp = PRED["predicted_at"]
    for key in ("P1_arbiter_head_bound", "P2_qa_morph_normalize"):
        p = PRED[key]["artifact"]
        assert p.startswith("experiments/MP-E9/results/"), f"{key} artifact is not in results/"
        f = ROOT / p
        if f.exists():
            art = mg.load(f)
            started = (art.get("provenance") or {}).get("started_utc")
            assert started, f"{p} carries no started_utc, so the ordering cannot be checked"
            assert stamp <= started, (
                f"{key}: prediction written at {stamp} but the treatment ran at {started}. A "
                "prediction written after the run is a description of the run.")


def test_prediction_numbers_are_transcriptions_not_literals():
    """Every P1/P2 number that came from a hypothesis must still equal that hypothesis's threshold.

    If someone edits the prediction to match a result, this fails even if the prediction test itself
    would now pass -- the transcription and the threshold are two places that must keep agreeing.
    """
    nt = {k: v["numeric_thresholds"] for k, v in REG["hypotheses"].items()}
    p1 = PRED["P1_arbiter_head_bound"]["numeric"]
    assert p1["UNTRACEABLE_ASSERTED_rows_max"] == nt["H1"]["asserted_untraceable_rows_max"]
    assert p1["says_rows_flagged_max"] == nt["H2"]["says_rows_flagged_max"]
    assert p1["arbiter_tell_rows_equal"] == nt["H2"]["arbiter_tell_rows_equal"]
    assert p1["rows_losing_correct_max"] == nt["H2"]["rows_losing_correct_max"]
    assert p1["says_gap_refused_plus_echo_min"] == nt["H2"]["says_gap_refused_plus_echo_min"]
    p2 = PRED["P2_qa_morph_normalize"]["numeric"]
    assert p2["toll_correct_min"] == nt["H3"]["toll_correct_min"]
    assert p2["invented_rows_max"] == nt["H3"]["invented_rows_max"]
    assert p2["guarded_absence_rows_equal"] == nt["H3"]["guarded_absence_rows_equal"]


def _treatment(key):
    if not PRED:
        pytest.skip("no registered predictions to judge a treatment against")
    f = ROOT / PRED[key]["artifact"]
    if not f.exists():
        pytest.skip(f"{key}: treatment artifact {PRED[key]['artifact']} not produced yet -- "
                    "the prediction is registered and unjudged, which is not the same as passing")
    return mg.evaluate(mg.load(f), REF, REG, NOISE, TIERS)


def test_flag_on_p1_arbiter_head_bound_meets_its_registered_prediction():
    r = _treatment("P1_arbiter_head_bound")
    n = PRED["P1_arbiter_head_bound"]["numeric"]
    wl = r["word_level"]
    assert wl["UNTRACEABLE_ASSERTED_rows"] <= n["UNTRACEABLE_ASSERTED_rows_max"], (
        f"H1 predicted {wl['UNTRACEABLE_ASSERTED_rows']} -> 0 and got "
        f"{wl['UNTRACEABLE_ASSERTED_rows']}")
    assert r["H2"]["observed"]["says_rows_flagged"] <= n["says_rows_flagged_max"]
    assert r["H2"]["observed"]["arbiter_tell_rows"] == n["arbiter_tell_rows_equal"], (
        "the bound ate the tell path: 36 rows are the conversions the flag must leave intact")
    assert r["row_movement_vs_reference"]["rows_losing_correct"] <= n["rows_losing_correct_max"]
    gap = r["says_gap_census"]
    assert gap["rows"] == n["says_gap_census_rows_equal"], "the census itself shrank"
    assert gap["refused_plus_echo"] >= n["says_gap_refused_plus_echo_min"]
    assert gap["refused_plus_echo"] == n["says_gap_refused_plus_echo_expected"], (
        f"predicted the 16 speaking rows become refused, taking refused+echo to "
        f"{n['says_gap_refused_plus_echo_expected']}; measured {gap['refused_plus_echo']}. "
        "This is a FINDING about partial recovery, not a number to edit here.")


@pytest.mark.xfail(
    strict=True,
    reason=("REGISTERED NEGATIVE, not a broken test. P2's prediction (toll correct 0 -> at least 6 "
            "of 54) was falsified by measurement: 0 of 3,672 rows differ from the pre-treatment "
            "artifact, so the morphology flag is inert on this bench and the store-key premise is "
            "false for the toll pair -- the stored question and the probe ask already produce the "
            "identical qa_key. See registered_predictions.P2_qa_morph_normalize.outcome. strict=True "
            "means if anyone makes this pass without updating that record, the suite fails."))
def test_flag_on_p2_qa_morph_normalize_meets_its_registered_prediction():
    r = _treatment("P2_qa_morph_normalize")
    n = PRED["P2_qa_morph_normalize"]["numeric"]
    toll = r["morphology_class"]["toll"]
    assert toll["rows"] == n["toll_rows_equal"], (
        "the class census moved, so `correct` is being measured over a different population")
    assert toll["correct"] >= n["toll_correct_min"], (
        f"H3 predicted toll correct 0 -> at least {n['toll_correct_min']} of 54; measured "
        f"{toll['correct']}")
    assert r["invented"]["summary_invented_rows"] <= n["invented_rows_max"], (
        "widened keys admitted a sentence nobody said: the store is answering with invention")
    assert toll["correct"] + toll["refused"] <= n["toll_correct_plus_refused_equal"]
    assert r["word_level"]["guarded_absence_rows"] == n["guarded_absence_rows_equal"]


# Every number an outcome block is allowed to claim, and where it comes from in the artifact.
OUTCOME_FIELDS = {
    "UNTRACEABLE_ASSERTED_rows": lambda r: r["word_level"]["UNTRACEABLE_ASSERTED_rows"],
    "UNTRACEABLE_HEARD_rows": lambda r: r["word_level"].get("UNTRACEABLE_HEARD_rows"),
    "says_rows_flagged": lambda r: r["H2"]["observed"]["says_rows_flagged"],
    "arbiter_tell_rows": lambda r: r["H2"]["observed"]["arbiter_tell_rows"],
    "guarded_absence_rows": lambda r: r["word_level"]["guarded_absence_rows"],
    "says_gap_refused_plus_echo": lambda r: r["says_gap_census"]["refused_plus_echo"],
    "says_gap_rows": lambda r: r["says_gap_census"]["rows"],
    "toll_rows": lambda r: r["morphology_class"]["toll"]["rows"],
    "toll_correct": lambda r: r["morphology_class"]["toll"]["correct"],
    "toll_refused": lambda r: r["morphology_class"]["toll"]["refused"],
    "toll_echo": lambda r: r["morphology_class"]["toll"]["echo"],
    "invented_rows": lambda r: r["invented"]["summary_invented_rows"],
    "rows_gaining_correct": lambda r: r["row_movement_vs_reference"]["rows_gaining_correct"],
    "rows_losing_correct": lambda r: r["row_movement_vs_reference"]["rows_losing_correct"],
}


def test_a_recorded_outcome_is_the_artifact_it_names():
    """An outcome block that flatters its own measurement is the same corruption as an edited
    prediction, so every number in it is recomputed from the artifact it points at."""
    for key in ("P1_arbiter_head_bound", "P2_qa_morph_normalize"):
        o = PRED[key].get("outcome")
        assert o, f"{key} has been run and records no outcome"
        r = _treatment(key)
        for name, claimed in o["measured"].items():
            assert name in OUTCOME_FIELDS, f"{key}: {name} is recorded but not recomputable"
            got = OUTCOME_FIELDS[name](r)
            assert got == claimed, f"{key}.{name}: outcome says {claimed}, artifact says {got}"
        # prediction_met is arithmetic over the recorded numbers, never a sentiment about them.
        n = PRED[key]["numeric"]
        if key.startswith("P1"):
            want = o["measured"]["UNTRACEABLE_ASSERTED_rows"] <= n["UNTRACEABLE_ASSERTED_rows_max"]
        else:
            want = o["measured"]["toll_correct"] >= n["toll_correct_min"]
        assert o["prediction_met"] is want, f"{key}: prediction_met disagrees with its own numbers"


def test_pi_rulings_are_recorded_as_decisions_with_reasoning():
    d = REG["pi_decisions_resolved"]
    assert set(d) == {"D-G0P-02_clone_criterion", "D-G0P-03_heard_not_told_scope",
                      "D-G0P-04_suite_measurement"}
    for k, v in d.items():
        assert v.get("decided_by"), k
        assert v.get("reasoning") or v.get("note"), f"{k} records a verdict with no reasoning"
    clone = d["D-G0P-02_clone_criterion"]
    assert set(clone["identity_required_on"]) == {"cls", "said", "src", "item", "shape",
                                                  "mech", "taught", "own", "answered"}
    assert clone["tolerated_as_noise"] == ["reason"]
    assert "said" not in clone["tolerated_as_noise"]
    assert clone["excluded_from_the_noise_floor_claim"] == ["learn/1/reasked", "learn/1/restarted"]
    assert "injectable clock" in clone["long_term_fix_scheduled_not_improvised"]
    heard = d["D-G0P-03_heard_not_told_scope"]
    assert "third class" in heard["ruling"].lower() or "THIRD CLASS" in heard["ruling"]
    assert "C1 fires at 16" in heard["consequence_registered"]


def test_the_ruling_and_the_code_agree_on_the_field_lists():
    """The PI's words and the comparator's constants must be the same nine fields. If someone edits one
    side, this fails -- which is the only thing standing between a decision record and a tool."""
    import tools.bench_noise_floor as nf
    ruled = set(REG["pi_decisions_resolved"]["D-G0P-02_clone_criterion"]["identity_required_on"])
    assert ruled == set(nf.IDENTITY_FIELDS)
    assert tuple(REG["pi_decisions_resolved"]["D-G0P-02_clone_criterion"]["tolerated_as_noise"]) == \
        nf.TOLERATED_FIELDS
