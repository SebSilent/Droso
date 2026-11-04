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


def _run(pair, tmp_path):
    out = tmp_path / f"{pair}.json"
    r = subprocess.run([sys.executable, str(DRIVER), "--pair", pair, "--out", str(out)],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=900)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text(encoding="utf-8", errors="replace"))


@pytest.mark.parametrize("pair", sorted(SEALED_PAIRS))
def test_promotion_reproduces_the_sealed_counts(pair, tmp_path):
    sealed = json.loads(SEALED_PAIRS[pair].read_text(encoding="utf-8", errors="replace"))
    new = _run(pair, tmp_path)
    for f in ("rows_compared", "n_rows_moved", "class_split", "transitions_by_axis"):
        assert new[f] == sealed[f], f"{pair}: {f} changed on promotion: {sealed[f]} -> {new[f]}"
    # the row identity set must match too, not just its size -- 251 rows moving is a different claim if
    # they are not the same 251 rows
    sk = {(m["depth"], m["phase"], m["ask"]) for m in sealed["moved_rows"]}
    nk = {(m["depth"], m["phase"], m["ask"]) for m in new["moved_rows"]}
    assert sk == nk, f"{pair}: the migrated ROW SET differs even though the count agrees"


def test_moved_keys_field_agrees_with_moved_rows(tmp_path):
    new = _run("300", tmp_path)
    assert [list(k) for k in new["moved_keys"]] == \
        sorted([[m["depth"], m["phase"], m["ask"]] for m in new["moved_rows"]])


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
