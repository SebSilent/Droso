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
    good = {"frozen_correct": 19, "frozen_total": 24, "guarded_pass": 4, "guarded_total": 4}
    with_good = mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=good)
    assert with_good["H4"]["pass"] is True
    bad = dict(good, frozen_correct=18)
    with_bad = mg.evaluate(DOC, REF, REG, NOISE, TIERS, battery=bad)
    assert with_bad["H4"]["pass"] is False


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


def test_registered_toll_census_survives_whole_word_matching(res):
    """The registration says 54 rows touch `toll`, 0 correct. That number was produced before this
    matcher existed, so agreement is evidence the matcher is the same class, not a new one."""
    assert res["morphology_class"]["toll"]["rows"] == 54
    assert res["morphology_class"]["toll"]["correct"] == 0
    assert res["says_gap_census"]["rows"] == 81
    assert res["says_gap_census"]["refused_plus_echo"] == 65


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


def test_no_mp_e9_result_exists_yet_and_the_amendments_say_so():
    """R2 permits pre-run amendments and forbids post-result edits. The file must keep that auditable."""
    for a in REG["registration_amendments"]:
        assert a["results_existed"] is False, a
        assert a["what"] and a["why"]
    assert REG["status"].startswith("OPEN (B.2)")
    assert "NO treatment arm has been run" in REG["status"]


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
