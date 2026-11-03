"""G0-prime instrument tests -- the tools that measure must themselves be checked.

Nothing here builds a house. They read the two sealed evidence files and exercise pure functions, so
they run in well under a second, which matters because the bench they guard takes eight minutes.

The central test is the one that distinguishes the two artifacts. G0-prime promotes a PRE-flag
snapshot into the tracked tree beside the POST-flag evidence, and the two are nearly identical JSON
blobs of the same size. A suite that cannot tell them apart cannot tell whether the gate closed.
"""
import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.bench_noise_floor as nf            # noqa: E402
import tools.word_provenance as wp              # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence" / "electric_learn_bench.json"
BASELINE = ROOT / "experiments" / "MP-E9" / "baselines" / "bench_pre_arbiter_tell_HEAD.json"
MANIFEST = ROOT / "experiments" / "MP-E9" / "baselines" / "bench_pre_arbiter_tell_HEAD.manifest.json"
# BOTH registrations, not one. This test originally named only MP-E9's, so G0-prime -- the gate whose
# artifacts this file pins -- was never actually verified by it, and a stale seal on the neighbour's file
# read as a failure of the organism's instruments. A gate verifies its own seal and the gate it unblocks.
G0_REG = ROOT / "experiments" / "G0-prime" / "registration.json"
REG = ROOT / "experiments" / "MP-E9" / "registration.json"
REGS = [G0_REG, REG]


@pytest.fixture(scope="module")
def evidence():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE.exists():
        pytest.skip("pre-flag baseline not derived: tools/derive_pre_flag_snapshot.py")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the two artifacts are distinct

def test_the_committed_evidence_is_the_post_flag_run(evidence):
    rows = [r for _k, r in wp.probe_rows(evidence)]
    assert sum(1 for r in rows if r.get("src") == "arbiter tell") == 36
    assert sum(1 for r in rows if r.get("said") == "says") == 16


def test_the_promoted_baseline_is_the_pre_flag_run(baseline):
    """The guard against promoting the wrong file.

    Both artifacts are ~1.47 MB JSON blobs with the same keys and the same 40 items and 136 probes.
    Only the row mix says which side of the flag a run came from, and docs/HANDOVER.md publishes that
    mix: arbiter head 1034 -> 1014 and silence 1535 -> 1519 across ELECTRIC_ARBITER_TELL, with 36
    arbiter-tell rows appearing only after it.
    """
    rows = [r for _k, r in wp.probe_rows(baseline)]
    src = {}
    for r in rows:
        src[str(r.get("src"))] = src.get(str(r.get("src")), 0) + 1
    assert src.get("arbiter tell", 0) == 0, "this file has arbiter-tell rows: it is not pre-flag"
    assert src.get("arbiter head") == 1034, src.get("arbiter head")
    assert src.get("") == 1535, src.get("")
    assert sum(1 for r in rows if r.get("said") == "says") == 0
    assert src.get("electric_absence") == 24, "the guarded-absence contract must survive the move"


def test_the_manifest_records_the_pre_flag_signature_matching_the_handover():
    if not MANIFEST.exists():
        pytest.skip("manifest not written: tools/derive_pre_flag_snapshot.py")
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert man["pre_flag_signature"]["MATCHES"] is True
    assert man["derived_from_commit_subject"].startswith("ELECTRIC_QA_ANSWER_MEMORY")
    assert man["rederived_from_scratch"] is True


def test_the_baseline_is_re_derivable_not_merely_copied():
    """R10's requirement is re-derivability, and the tool that provides it must not rot silently."""
    p = ROOT / "tools" / "derive_pre_flag_snapshot.py"
    assert p.exists()
    r = subprocess.run([sys.executable, str(p), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--finish" in r.stdout


# ---------------------------------------------------------------- the clone comparator

def _doc(rows_by_phase):
    return {"arms": {"learn": {"probes": {"1": rows_by_phase}}}}


def test_diff_detects_nothing_between_identical_runs():
    a = _doc({"live": [{"ask": "x", "said": "y", "cls": "correct", "src": "s", "item": "i",
                        "shape": "subject", "mech": "m", "taught": "t", "own": "o",
                        "reason": "r", "answered": True}]})
    assert nf.diff(nf.flat(a), nf.flat(a)) == []


def test_diff_detects_a_class_change():
    base = [{"ask": "x", "said": "y", "cls": "correct", "src": "s", "item": "i",
             "shape": "subject", "mech": "m", "taught": "t", "own": "o", "reason": "r",
             "answered": True}]
    moved = [dict(base[0], cls="refused")]
    d = nf.diff(nf.flat(_doc({"live": base})), nf.flat(_doc({"live": moved})))
    assert len(d) == 1 and ".cls:" in d[0]


def test_diff_detects_a_said_change_and_ignores_timing():
    """`seconds` and `started_utc` are excluded by design: a run that took longer is not a run that
    measured something else."""
    row = {"ask": "x", "said": "y", "cls": "correct", "src": "s", "item": "i", "shape": "subject",
           "mech": "m", "taught": "t", "own": "o", "reason": "r", "answered": True}
    a = _doc({"live": [row]})
    b = _doc({"live": [dict(row, said="z")]})
    assert len(nf.diff(nf.flat(a), nf.flat(b))) == 1
    a["arms"]["learn"]["probes"]["1"]["live"][0].pop("cls")
    assert nf.VOLATILE == ("seconds", "started_utc")


def test_diff_reports_a_row_count_change_as_one_difference_not_a_crash():
    a = _doc({"live": [{"ask": "x", "said": "", "cls": "refused", "src": "", "item": "i",
                        "shape": "s", "mech": "m", "taught": "t", "own": "o", "reason": "r",
                        "answered": False}]})
    b = _doc({"live": []})
    d = nf.diff(nf.flat(a), nf.flat(b))
    assert len(d) == 1 and "coordinate sets differ" in d[0]


def test_headline_recomputes_from_rows_rather_than_trusting_the_table(evidence):
    """The gate reads correct/partial/refused tallies. If it copied them from the summary block it
    would be trusting the thing under test to grade itself, so this recomputes the same cell by
    walking the rows and requires nf.headline() to agree."""
    h = nf.headline(evidence)
    mine = {}
    for key, r in wp.probe_rows(evidence):
        # probe_rows coordinates look like "learn/d3/live[12]" -- the index is part of the last token
        coord, _idx = key.rsplit("[", 1)
        arm, depth, phase = coord.split("/")
        cell = mine.setdefault((arm, depth, phase), {})
        cls = str(r.get("cls"))
        cell[cls] = cell.get(cls, 0) + 1
    assert h["learn"]["3"]["live"] == mine[("learn", "d3", "live")]
    assert h["learn"]["3"]["live"]["correct"] == 115, "the published learn depth-3 figure"


# ---------------------------------------------------------------- the seal

def test_registration_seal_verifies_against_the_registration():
    """A registration that names its harness by a hash somebody typed is a claim. This checks the
    claim, and it is the reason tools/registration_seal.py exists.

    THE CIRCULARITY, in plain sight. This test seals experiments/G0-prime/decision.md, and that file
    cites the suite run this test belongs to. A document cannot both quote a number and be sealed
    against the moment the number was taken, so the procedure is: run the suite once, write the result
    into the decision record, re-stamp, then re-run THIS test alone to prove the seal is fresh. The
    suite is never run twice to chase a total -- see decision.md §7.
    """
    missing = [p for p in REGS if not p.exists()]
    if missing:
        pytest.skip(f"registration not written: {[str(m.relative_to(ROOT)) for m in missing]}")
    for reg in REGS:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "registration_seal.py"),
                            str(reg), "--check"], capture_output=True, text=True)
        assert r.returncode == 0, f"{reg.relative_to(ROOT)}\n{r.stdout}{r.stderr}"


def test_no_registration_seals_its_own_bytes():
    """A registration listing itself is stale the instant the seal is written -- writing the seal changes
    the file -- so --check can never come back clean. That is a permanent self-inflicted DRIFT line, and
    DRIFT lines that never clear train the reader to ignore the checker. Both registrations are asserted
    free of it, because the bug was live in MP-E9's manifest for most of this gate."""
    for reg in REGS:
        if not reg.exists():
            pytest.skip("registration not written")
        d = json.loads(reg.read_text(encoding="utf-8"))
        files = d.get("harness_hashes", {}).get("files", {})
        rel = reg.relative_to(ROOT).as_posix()
        assert rel not in files, f"{rel} seals its own bytes; --check can never be clean"
        assert d.get("harness_hashes", {}).get("self_excluded", {}).get("path") == rel, \
            f"{rel} does not record the exclusion, so the omission looks accidental"


def test_no_registration_seals_another_registration():
    """G0-prime's manifest listed MP-E9/registration.json and MP-E9's listed G0-prime's. Two ledgers
    sealing each other is a cycle that no stamp sequence can satisfy -- re-stamping one invalidates the
    other's record of it -- and it is worse than merely unfixable: a registration pinned only by another
    registration proves the two agree with each other, not that anything matches the world. Both are
    asserted free of cross-registration entries, with the exclusion recorded rather than silent."""
    for reg in REGS:
        if not reg.exists():
            pytest.skip("registration not written")
        d = json.loads(reg.read_text(encoding="utf-8"))
        files = d.get("harness_hashes", {}).get("files", {})
        cross = [f for f in files if f.endswith("registration.json")]
        assert not cross, f"{reg.relative_to(ROOT)} seals another registration: {cross}"
        rec = d.get("harness_hashes", {}).get("registrations_excluded")
        assert rec, f"{reg.relative_to(ROOT)} drops registrations silently; the exclusion must be recorded"


def test_index_cross_check_is_not_vacuous():
    """The seal's strongest claim is that it matches what GIT HOLDS, not what the worktree would hash to.
    The first implementation of that cross-check keyed its dict on the FILE MODE from `git ls-files -s`,
    so all 100644 files collapsed into a single entry: it printed "1 of 29 are in the git index", the
    membership test was never true, and the drift loop compared nothing. It passed by construction.

    This asserts the numbers the check prints are the real ones. It is the only kind of assertion that
    catches a check that cannot fail -- not that it reports clean, but that it accounts for every file."""
    for reg in REGS:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "registration_seal.py"),
                            str(reg), "--check"], capture_output=True, text=True)
        m = re.search(r"\[seal\] (\d+) of (\d+) are in the git index", r.stdout)
        assert m, f"check printed no index accounting:\n{r.stdout}{r.stderr}"
        in_index, total = int(m.group(1)), int(m.group(2))
        assert total > 1, f"{reg.relative_to(ROOT)} seals {total} file(s)"
        assert in_index == total, (f"{reg.relative_to(ROOT)}: only {in_index}/{total} sealed files are "
                                   f"in the index -- an untracked artifact is sealed as a prediction")
        assert "INDEX-DRIFT" not in r.stdout, f"{reg.relative_to(ROOT)}:\n{r.stdout}"


def test_registration_head_contains_its_sealed_files():
    """A seal must name a commit that ALREADY CONTAINS the bytes it hashes.

    Both registrations recorded git_head 698a6d3 while hashing bench_noise_floor.py's R13a fields,
    tools/mp_e9_gate.py, tests/test_mp_e9_gate.py, gate_validation.json and 22 new tests -- none of
    which 698a6d3 has ever seen. Every other check passed, because the worktree agrees with itself and
    the index agrees with the worktree. Only asking the COMMIT exposes it, and that is the same defect
    class as the plan's stale 0b5f191: a hash pointed at bytes that do not exist where the record says
    they do. Unfalsifiable, however internally consistent.

    This is the check the ordering rule exists to satisfy: commit, THEN stamp.
    """
    for reg in REGS:
        d = json.loads(reg.read_text(encoding="utf-8"))
        hh = d.get("harness_hashes", {})
        head = hh.get("git_head") or ""
        files = hh.get("files") or {}
        assert head, f"{reg.relative_to(ROOT)} has no git_head to anchor to"
        assert len(files) > 1, f"{reg.relative_to(ROOT)} seals {len(files)} file(s)"

        r = subprocess.run(["git", "ls-tree", "-r", head, "--", *files],
                           cwd=str(ROOT), capture_output=True, text=True)
        assert r.returncode == 0, f"git ls-tree {head[:9]} failed: {r.stderr}"
        in_commit = {}
        for line in r.stdout.splitlines():
            meta, sep, path = line.partition("\t")
            if not sep:
                continue
            parts = meta.split()
            if len(parts) >= 3 and parts[1] == "blob":
                in_commit[path.replace("\\", "/")] = parts[2]

        absent = [f for f in files if f not in in_commit]
        wrong = [(f, files[f].get("git_blob_sha1"), in_commit[f])
                 for f in files if f in in_commit
                 and files[f].get("git_blob_sha1") != in_commit[f]]
        assert not absent, (
            f"{reg.relative_to(ROOT)} seals {len(absent)} file(s) that are ABSENT from its own "
            f"git_head {head[:9]} -- the stamp was taken before they were committed:\n  "
            + "\n  ".join(sorted(absent)[:15]))
        assert not wrong, (
            f"{reg.relative_to(ROOT)} disagrees with git_head {head[:9]} on {len(wrong)} file(s):\n"
            + "\n".join(f"  {f}: sealed {a[:10]} vs commit {b[:10]}" for f, a, b in wrong[:15]))
        # NOT `git_dirty`: stamping one registration dirties the tree for the next, and the dirty file is
        # a registration, which no seal hashes. The field that matters is the path-scoped one -- uncommitted
        # bytes among the files this seal actually lists.
        dirty_sealed = hh.get("git_dirty_sealed")
        assert dirty_sealed is not None, (
            f"{reg.relative_to(ROOT)} records only the blunt git_dirty; a stamp taken before that field "
            f"existed must be re-taken, or the anchor is unverified")
        assert dirty_sealed == [], (
            f"{reg.relative_to(ROOT)} was stamped with these sealed files uncommitted: {dirty_sealed}")
        assert hh["stamp_ordering"]["rule"].startswith("COMMIT FIRST, THEN STAMP"), \
            f"{reg.relative_to(ROOT)} does not state the ordering rule the anchor depends on"


def test_report_coordinate_count_is_not_a_display_artefact():
    """The first version of tools/noise_floor_report.py built its coordinate set from the capped
    8-row preview, so it published "8 distinct rows touched" when 11 rows actually moved -- a display
    limit reported as a measurement. Recompute from the clone files and require agreement."""
    rep = ROOT / "experiments" / "G0-prime" / "results" / "noise_floor" / "per_arm_breakdown.json"
    clones = sorted((ROOT / "experiments" / "G0-prime" / "results" / "noise_floor"
                     ).glob("clone_*.json"))
    if not rep.exists() or len(clones) < 3:
        pytest.skip("clone run not published yet")
    pa = json.loads(rep.read_text(encoding="utf-8"))
    flats = [nf.flat(json.loads(f.read_text(encoding="utf-8"))) for f in clones]

    coords = set()
    for i in range(len(flats)):
        for j in range(i + 1, len(flats)):
            for d in nf.diff(flats[i], flats[j]):
                if "]." in d:
                    coords.add(d.split("].", 1)[0] + "]")
    assert pa["concentration"]["distinct_rows_touched"] == len(coords)
    assert len(pa["concentration"]["coordinates"]) == len(coords)
    assert len(pa["samples"]["clone1vs2"]) <= 8, "samples is a preview; counts must not come from it"


def test_report_separates_graded_from_reason_differences():
    rep = ROOT / "experiments" / "G0-prime" / "results" / "noise_floor" / "per_arm_breakdown.json"
    if not rep.exists():
        pytest.skip("report not published yet")
    pa = json.loads(rep.read_text(encoding="utf-8"))
    c = pa["concentration"]
    assert set(c["graded_coordinates"]) <= set(c["coordinates"])
    # graded rows are exactly the coordinates whose differing field is a graded one
    assert c["distinct_rows_with_graded_field_difference"] == len(c["graded_coordinates"])
    # The gate-critical claim: no row changed CLASS between clones.
    assert "cls" not in c["by_field"], c["by_field"]
    assert pa["verdict"]["strict_identity_all_arms"] is False


def test_seals_block_carries_the_components_the_plan_requires():
    from tools.electric_learn_bench import seals
    s = seals(["--test"])
    for key in ("git_head", "git_dirty", "interpreter", "prefix", "base_prefix", "in_venv",
                "harness_sha256", "argv", "packages"):
        assert key in s, key
    assert s["requirements_pinned"] is False
    assert s["packages"]["numpy"]


def test_seals_cannot_kill_a_run_over_a_missing_sysconfig_key():
    """The first version read sysconfig.get_paths()["environment"], which does not exist in this
    venv, and it raised at the END of an eight-minute measurement. A seal is metadata; it is never
    allowed to be the thing that destroys the number it describes."""
    import subprocess
    import sys as _sys

    src = ("import sys; sys.path.insert(0, '.');"
           "import sysconfig;"
           "real = sysconfig.get_paths;"
           "sysconfig.get_paths = lambda *a, **k: {};"
           "from tools.electric_learn_bench import seals;"
           "s = seals(['--x']);"
           "print('prefix_ok', bool(s['prefix']), 'venv', s['in_venv'])")
    r = subprocess.run([_sys.executable, "-c", src], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-800:]
    assert "prefix_ok True" in r.stdout


# ------------------------------------------------------------------ R13(a), as ruled by the PI
#
# These pin a DECISION, not an invention of the agent's. The PI chose R13 option (a) -- a registered
# tolerance, field-level and narrow -- after B.1 step 3 was falsified by measurement. The tests below
# encode the ruling's shape: nine identity fields, one tolerated field, one excluded cell, and a
# fail-closed default for anything the ruling did not enumerate.

RULED_IDENTITY = {"cls", "said", "src", "item", "shape", "mech", "taught", "own", "answered"}


def _row(**kw):
    base = dict(ask="when does the bell toll", said="the bell tolls", cls="correct",
                src="electric_taught", item="bell", shape="pair_exact", mech="m",
                taught="the bell tolls", own="the bell tolls", reason="coverage 40%", answered=1)
    base.update(kw)
    return base


def _flat(phase, *rows):
    doc = {"arms": {"learn": {"probes": {"1": {phase: list(rows)}}}},
           "told": ["the bell tolls"], "failures": [], "items": 40, "probes": 136, "summary": {}}
    return nf.flat(doc)


def test_r13a_identity_fields_are_exactly_the_ruled_nine():
    assert set(nf.IDENTITY_FIELDS) == RULED_IDENTITY
    assert nf.TOLERATED_FIELDS == ("reason",)
    assert "reason" not in nf.IDENTITY_FIELDS
    # The PI named `said` explicitly: the one graded difference the clones produced IS the says-gap
    # row, and `said` is what MP-E9 grades. Tolerating it would buy reproducibility with the currency
    # the next gate spends.
    assert "said" in nf.IDENTITY_FIELDS
    assert set(nf.GRADED) == RULED_IDENTITY | {"reason", "ask"}


def test_r13a_tolerates_a_reason_difference_and_still_reports_it():
    v = nf.r13a_assess({"p": nf.diff_records(_flat("live", _row()),
                                             _flat("live", _row(reason="coverage 41%")))})
    assert v["tolerated_reason_only"] == 1
    assert v["identity_outside_excluded_cell"] == 0
    assert v["verdict"] == "MET WITH REGISTERED EXCLUSION"
    # Tolerated is not invisible: a noise floor that hides the noise it forgave is not a measurement.
    assert v["differences_total"] == 1
    assert v["rows_touched_list"] == ["learn/d1/live[0]"]


def test_r13a_does_not_tolerate_a_said_difference():
    v = nf.r13a_assess({"p": nf.diff_records(_flat("live", _row(said="the bell tolls")),
                                             _flat("live", _row(said="the bell rings")))})
    assert v["identity_outside_excluded_cell"] == 1
    assert v["tolerated_reason_only"] == 0
    assert v["verdict"] == "NOT REPRODUCIBLE UNDER R13(a)"


def test_said_inside_the_excluded_cell_is_counted_as_a_difference_not_as_noise():
    """The excluded cell is EXCLUDED from the claim, not reclassified as tolerance. The row still shows
    up as an identity difference, so the artifact cannot read as if the instrument agreed with itself."""
    v = nf.r13a_assess({"p": nf.diff_records(
        _flat("reasked", _row(said="droso says when does the bell toll")),
        _flat("reasked", _row(said="when the bell toll")))})
    assert v["identity_in_excluded_cell"] == 1
    assert v["tolerated_reason_only"] == 0
    assert v["rows_touched_list"] == ["learn/d1/reasked[0]"]


def test_unenumerated_ask_is_held_to_identity_fail_closed():
    """The ruling enumerated nine identity fields and one tolerated field, and did not mention `ask`.
    Silence from a ruling is not permission: an unenumerated field is not noise by default."""
    assert "ask" in nf.UNENUMERATED_FIELDS and "ask" in nf.REQUIRED_FIELDS
    v = nf.r13a_assess({"p": nf.diff_records(_flat("live", _row(ask="when does the bell toll")),
                                             _flat("live", _row(ask="when does the bell ring")))})
    assert v["identity_outside_excluded_cell"] == 1


def test_sealed_clones_meet_r13a_only_with_the_registered_exclusion():
    d = json.loads((ROOT / "experiments" / "G0-prime" / "results" / "noise_floor" /
                    "noise_floor.json").read_text(encoding="utf-8"))
    r = d["criterion_r13a"]
    assert r["verdict"] == "MET WITH REGISTERED EXCLUSION"
    assert r["identity_outside_excluded_cell"] == 0
    assert r["identity_in_excluded_cell"] == 2      # the same row, seen from both diverging pairs
    assert r["tolerated_reason_only"] == 20
    assert r["rows_touched"] == 11
    # The literal B.1 wording is NOT rewritten by the tolerance. A reader must see that the original
    # rule failed, or the registered criterion silently becomes "whatever the tool now reports".
    assert d["noise_floor_verdict"] == "NOT REPRODUCIBLE"
    assert "row for row" in d["criterion_literal"]


def test_the_excluded_cell_is_the_says_gap_row_itself():
    p = json.loads((ROOT / "experiments" / "G0-prime" / "results" / "noise_floor" /
                    "per_arm_breakdown.json").read_text(encoding="utf-8"))
    ex = p["r13a"]["excluded_rows"]
    assert ex, "the excluded cell must be named in the artifact, not merely counted"
    assert all(e.startswith("learn/d1/reasked[120].said:") for e in ex)
    for e in ex:
        vals = e.split(": ", 1)[1]
        assert "droso says when does the bell toll" in vals and "when the bell toll" in vals
    assert p["r13a"]["graded_differences_outside_excluded_cell"] == 0


def test_comparator_and_report_agree_because_they_share_one_field_definition():
    n = json.loads((ROOT / "experiments" / "G0-prime" / "results" / "noise_floor" /
                    "noise_floor.json").read_text(encoding="utf-8"))
    p = json.loads((ROOT / "experiments" / "G0-prime" / "results" / "noise_floor" /
                    "per_arm_breakdown.json").read_text(encoding="utf-8"))
    assert n["criterion_r13a"]["verdict"] == p["r13a"]["verdict"]
    assert n["configuration"]["identity_fields_r13a"] == p["r13a"]["identity_fields"]
    assert (p["r13a"]["graded_differences_total"]
            == n["criterion_r13a"]["identity_in_excluded_cell"]
            + n["criterion_r13a"]["identity_outside_excluded_cell"])
