"""The promoted row-migration driver must reproduce the sealed migration numbers exactly.

tools/mp_e10_row_migration.py was promoted out of _tmp/row_migration.py on 2026-11-04 under R10. Three
published artifacts were produced by that scratch file -- replay_tier120_row_migration.json,
control_tier120_no_replay_row_migration.json, replay_tier300_row_migration.json -- and each is sealed in
every ledger while the code that computed them was not on disk in tracked form at all.

These tests re-run the promoted tool against the same pairs into a temp path and require the counts that
were published to come back unchanged. If the promotion changed the keying or the field set, this is where
it shows.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "tools" / "mp_e10_row_migration.py"
R13 = ("cls", "said", "src", "item", "shape", "mech", "taught", "own", "answered")

# (pair id, the sealed artifact that pair produced)
SEALED_PAIRS = {
    "120": ROOT / "experiments/MP-E10/results/replay_tier120_row_migration.json",
    "300": ROOT / "experiments/MP-E10/results/replay_tier300_row_migration.json",
    "120ctl": ROOT / "experiments/MP-E10/results/control_tier120_no_replay_row_migration.json",
}


def _run(pair, tmp_path, mode="probe"):
    out = tmp_path / f"{pair}_{mode}.json"
    r = subprocess.run([sys.executable, str(DRIVER), "--pair", pair, "--row-key", mode,
                        "--out", str(out)],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=900)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text(encoding="utf-8", errors="replace"))


@pytest.mark.parametrize("pair", sorted(SEALED_PAIRS))
def test_legacy_key_reproduces_the_superseded_counts(pair, tmp_path):
    """`--row-key legacy` is defined as the mode that reproduces the published figures, so THIS is the
    contract the promotion test always had -- the mode, not the assertion, is what changed. AMD-MPE10-08
    proved the sealed key collapses rows, so the corrected default cannot reproduce those numbers and must
    not be asked to: what is preserved here is the ability to reproduce them exactly.
    """
    sealed = json.loads(SEALED_PAIRS[pair].read_text(encoding="utf-8", errors="replace"))
    new = _run(pair, tmp_path, mode="legacy")
    for f in ("rows_compared", "n_rows_moved", "class_split", "transitions_by_axis"):
        assert new[f] == sealed[f], f"{pair}: {f} changed under the legacy key: {sealed[f]} -> {new[f]}"
    # the row identity set must match too, not just its size -- 251 rows moving is a different claim if
    # they are not the same 251 rows
    sk = {(m["depth"], m["phase"], m["ask"]) for m in sealed["moved_rows"]}
    nk = {(m["depth"], m["phase"], m["ask"]) for m in new["moved_rows"]}
    assert sk == nk, f"{pair}: the migrated ROW SET differs even though the count agrees"
    assert new["row_key"]["collapses_any_row"] is True, (
        f"{pair}: the legacy key was supposed to collapse rows and now does not -- the artifact it "
        f"reproduces would no longer mean what it said")


def test_corrected_key_compares_every_graded_ask(tmp_path):
    """The point of the fix: rows_compared must equal the graded asks the run contains, not the number of
    keys a non-unique identity could address."""
    new = _run("300", tmp_path, mode="probe")
    den, ku = new["denominator"], new["row_key"]["uniqueness"]
    assert new["rows_compared"] == den["graded_asks_baseline"] == den["graded_asks_replayed"] == 9414
    assert new["row_key"]["collapses_any_row"] is False
    for side in ("baseline", "replayed"):
        assert ku[side]["rows_total"] == ku[side]["distinct_keys"], ku[side]
        assert ku[side]["rows_collapsed_by_this_key"] == 0


def test_moved_keys_field_agrees_with_moved_rows(tmp_path):
    new = _run("300", tmp_path)
    assert [list(k) for k in new["moved_keys"]] == \
        sorted([[m["depth"], m["phase"], m["ask"], m["item"], m["shape"]] for m in new["moved_rows"]])


def test_matched_pair_is_checked_not_assumed(tmp_path):
    new = _run("300", tmp_path)
    mp = new["matched_pair"]
    for side in ("replayed", "baseline"):
        assert mp[side]["harness_sha256"], f"{side} records no instrument hash"
        assert mp[side]["curriculum_sha256"], f"{side} records no curriculum identity"
    # a comparison that spans a code change or a different curriculum is not an effect of the treatment
    assert isinstance(mp["differences_that_break_the_comparison"], list)
    assert isinstance(mp["same_git_head"], bool)


def test_diff_is_restricted_to_the_nine_identity_fields(tmp_path):
    """R13: identity required on nine fields, only `reason` tolerated as noise. A migration count that
    included `reason` would report the licensed-absence flip as if it were a graded change."""
    new = _run("300", tmp_path)
    for m in new["moved_rows"]:
        assert set(m["fields_moved"]) <= set(R13), m["fields_moved"]
        assert "reason" not in m["detail"], "reason leaked into an identity diff"


def test_existing_target_is_refused_never_overwritten(tmp_path):
    out = tmp_path / "sealed_like.json"
    out.write_text("ORIGINAL", encoding="utf-8")
    r = subprocess.run([sys.executable, str(DRIVER), "--pair", "300", "--out", str(out)],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=900)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "REFUSED" in r.stderr
    assert out.read_text(encoding="utf-8") == "ORIGINAL"


def test_driver_is_tracked_not_in_tmp():
    assert DRIVER.exists()
    r = subprocess.run(["git", "ls-files", "--error-unmatch", "tools/mp_e10_row_migration.py"],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0, "promoted driver is not tracked: " + r.stderr


# --------------------------------------------------------------------------- AMD-MPE10-08
# The row key must be UNIQUE in every curriculum the instrument is pointed at. This is the test whose
# absence let (depth, phase, ask) silently drop 1,215 graded asks at tier 300 and 522 at tier 120 while
# three published artifacts quoted the collapsed number as if it were the run.
sys.path.insert(0, str(ROOT / "tools"))
import mp_e10_row_migration as mig  # noqa: E402

CURRICULUMS = {
    "tier 40 arm A": ROOT / "experiments/MP-E8/results/armA_tier40_inertness.json",
    "tier 120 baseline": ROOT / "experiments/MP-E8/results/armA_tier120_curriculum.json",
    "tier 120 replay": ROOT / "experiments/MP-E10/results/replay_tier120_armA.json",
    "tier 120 control": ROOT / "experiments/MP-E10/results/control_tier120_no_replay_armA.json",
    "tier 300 baseline": ROOT / "experiments/MP-E8/results/armA_tier300_curriculum.json",
    "tier 300 replay": ROOT / "experiments/MP-E10/results/replay_tier300_armA.json",
    "tier 300 control": ROOT / "experiments/MP-E10/results/control_tier300_no_replay_armA.json",
}
# what the collapsed key measured, recorded here so a future change to the curriculum cannot quietly
# redefine the defect away
COLLAPSE_UNDER_LEGACY = {"tier 120 baseline": 522, "tier 120 replay": 522, "tier 120 control": 522,
                         "tier 300 baseline": 1215, "tier 300 replay": 1215, "tier 300 control": 1215}


@pytest.mark.parametrize("label", sorted(CURRICULUMS))
def test_probe_key_is_unique_in_every_curriculum(label):
    p = CURRICULUMS[label]
    if not p.exists():
        pytest.skip(f"{p.name} not on disk")
    art = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    ku = mig.key_uniqueness(art, "probe")
    assert ku["is_unique"], f"{label}: the corrected key still collapses {ku['rows_collapsed_by_this_key']} rows"
    assert ku["rows_total"] == ku["distinct_keys"], ku
    assert ku["key_fields"] == ["depth", "phase", "ask", "item", "shape"]


@pytest.mark.parametrize("label", sorted(COLLAPSE_UNDER_LEGACY))
def test_legacy_key_still_collapses_the_measured_number_of_rows(label):
    """Pins the defect itself. If this ever passes with zero collapse, the artifact set has changed under
    AMD-MPE10-08 and the supersession record needs re-reading -- it is NOT a sign that the bug got better."""
    art = json.loads(CURRICULUMS[label].read_text(encoding="utf-8", errors="replace"))
    ku = mig.key_uniqueness(art, "legacy")
    assert ku["rows_collapsed_by_this_key"] == COLLAPSE_UNDER_LEGACY[label], ku


def test_shape_is_an_authored_property_not_a_model_output():
    """`shape` is one of the nine compared fields, so keying on it is only legitimate if it cannot move
    between runs. Measured across baseline, replay and control -- three runs with different answers -- the
    shape sequence per (depth, phase, ask, item) group is identical in all three."""
    seqs = {}
    for tag, p in (("baseline", CURRICULUMS["tier 300 baseline"]),
                   ("replay", CURRICULUMS["tier 300 replay"]),
                   ("control", CURRICULUMS["tier 300 control"])):
        art = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        g = {}
        for depth, phases in (art["arms"]["learn"]["probes"]).items():
            for phase, rlist in (phases or {}).items():
                for i, r in enumerate(rlist or []):
                    g.setdefault((str(depth), phase, str(r.get("ask")), str(r.get("item"))), []).append(
                        (i, str(r.get("shape"))))
        seqs[tag] = {k: tuple(s for _, s in sorted(v)) for k, v in g.items()}
    assert set(seqs["baseline"]) == set(seqs["replay"]) == set(seqs["control"])
    differing = sum(1 for k in seqs["baseline"]
                    if seqs["baseline"][k] != seqs["replay"][k] or seqs["baseline"][k] != seqs["control"][k])
    assert differing == 0, (f"{differing} (ask,item) groups carry a run-dependent shape: shape is an output, "
                            "and keying on it would hide the movement this instrument exists to catch")


def test_item_alone_does_not_close_the_gap():
    """The obvious fix -- add `item` -- is not enough. Measured: 1,044 rows still collapse at tier 300."""
    art = json.loads(CURRICULUMS["tier 300 replay"].read_text(encoding="utf-8", errors="replace"))
    vals = {}
    for depth, phases in (art["arms"]["learn"]["probes"]).items():
        for phase, rlist in (phases or {}).items():
            for r in rlist or []:
                vals.setdefault((str(depth), phase, str(r.get("ask")), str(r.get("item"))), 0)
                vals[(str(depth), phase, str(r.get("ask")), str(r.get("item")))] += 1
    assert sum(vals.values()) - len(vals) == 1044, "the four-field key no longer measures 1,044 collapsed"
