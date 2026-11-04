"""The promoted k-sweep driver must reproduce the sealed tier-40 artifact, field for field.

tools/mp_e10_ksweep.py was promoted out of _tmp/mp_e10_ksweep_t40.py on 2026-11-04 under R10: D-MPE10-06's
obligation (||w||_F against tokens pushed) was being produced by a scratch file while the artifact it wrote
was sealed in every ledger. A promotion that changes any number is not a promotion, it is a new instrument
wearing an old name -- so these tests pin the promoted tool to the sealed artifact's own values.

They also pin the two things the rulings require of any artifact this tool writes: D-MPE10-08 (no bare
'alignment'; the read direction is named) and R5 (a target that exists is refused, never overwritten).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "tools" / "mp_e10_ksweep.py"
SEALED = ROOT / "experiments" / "MP-E10" / "results" / "ksweep_tier40_calibration_post_rulings.json"
TIER40 = ROOT / "experiments" / "MP-E8" / "curriculum_tier40.json"

FIELDS = ("utterances_fully_held_pct", "w_diagonal_mass_mean", "state_norm_mean",
          "probe_earlier_recovers_later_cosine_mean", "probe_later_recovers_earlier_cosine_mean",
          "direction_asymmetry_pp", "w_frobenius_norm_mean",
          "order_separation_vs_reversed_utterance_mean", "bag_of_words_order_separation_mean",
          "oldest_weight_measured_mean", "tokens_total", "utterances",
          "tokens_dropped_beyond_window", "decay_per_step")


def _run(tmp_path, *extra):
    out = tmp_path / "ksweep.json"
    r = subprocess.run([sys.executable, str(DRIVER), "--curriculum", str(TIER40),
                        "--out", str(out), *extra],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    return r, out


@pytest.fixture(scope="module")
def sweep(tmp_path_factory):
    r, out = _run(tmp_path_factory.mktemp("ks"))
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def test_promoted_driver_reproduces_the_sealed_sweep(sweep):
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    sq = {r["k"]: r for r in sealed["sweep"]}
    rq = {r["k"]: r for r in sweep["sweep"]}
    assert set(sq) == set(rq), "the registered grid changed"
    bad = [(k, f, sq[k].get(f), rq[k].get(f)) for k in sq for f in FIELDS
           if sq[k].get(f) != rq[k].get(f)]
    assert not bad, f"promotion moved sealed numbers: {bad[:6]}"


def test_boundedness_curve_matches_at_the_sealed_checkpoints(sweep):
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    s = {r["k"]: r["w_frobenius_norm_vs_tokens_pushed"] for r in
         sealed["findings_about_the_sealed_organ"]["1_fast_weight_store_is_not_bounded_by_k"]
         ["same_stream_64_tokens_at_four_values_of_k"]}
    n = {r["k"]: r["w_frobenius_norm_vs_tokens_pushed"] for r in
         sweep["findings_about_the_sealed_organ"]["1_fast_weight_store_is_not_bounded_by_k"]
         ["same_stream_at_four_values_of_k"]}
    for k, curve in s.items():
        # the promoted tool extends the checkpoint list to the tier's stream volume; the sealed
        # checkpoints must still read identically, which is the difference between extending a curve
        # and replacing it.
        assert {c: n[k][c] for c in curve} == curve, f"k={k} curve changed"


def test_read_direction_is_named_not_a_bare_alignment(sweep):
    """D-MPE10-08: every artifact names the token probed and the token recovered."""
    assert "read_direction_declared" in sweep
    assert "PREDECESSOR" in sweep["read_direction_declared"]
    # the successor chain that B.4 step 2 actually replays must be named apart, or the two organs
    # get conflated by a reader who only sees one of them
    assert "sequence_organ" in sweep["read_direction_declared"]
    for row in sweep["sweep"]:
        assert "read_direction_declared" in row
        for f in ("probe_earlier_recovers_later_cosine_mean",
                  "probe_later_recovers_earlier_cosine_mean"):
            assert f in row


def test_norm_against_tokens_pushed_is_its_own_quantity(sweep):
    """D-MPE10-06: ||w||_F against tokens pushed, reported, not folded into a capacity claim."""
    b = sweep["findings_about_the_sealed_organ"]["1_fast_weight_store_is_not_bounded_by_k"]
    for row in b["same_stream_at_four_values_of_k"]:
        assert row["w_frobenius_norm_vs_tokens_pushed"]
        assert row["tokens_pushed"] == b["stream_length_tokens"]
    assert "not bounded by k" in b["answer_as_measured"].lower() or \
        "no capacity limit tied" in b["answer_as_measured"].lower()


def test_existing_target_is_refused_never_overwritten(tmp_path):
    """R5: a sealed artifact is never clobbered by a re-run."""
    r, out = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    before = out.read_text(encoding="utf-8")
    r2, _ = _run(tmp_path)          # same --out a second time
    assert r2.returncode == 3, r2.stdout + r2.stderr
    assert "REFUSED" in r2.stderr
    assert out.read_text(encoding="utf-8") == before, "the refused run still changed the file"


def test_driver_is_tracked_not_in_tmp():
    """R10: the instrument that produces a gate's number must not live in the swept directory."""
    assert DRIVER.exists()
    r = subprocess.run(["git", "ls-files", "--error-unmatch", "tools/mp_e10_ksweep.py"],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0, "promoted driver is not tracked: " + r.stderr


def test_token_vectors_are_deterministic(tmp_path):
    """A stand-in that is not reproducible is not a stand-in, it is noise with a label."""
    sys.path.insert(0, str(ROOT))
    from tools.mp_e10_ksweep import token_vec
    a, b = token_vec("lantern"), token_vec("lantern")
    assert np.allclose(a, b)
    assert not np.allclose(a, token_vec("kettle"))
    assert round(float(np.linalg.norm(a)), 5) == 1.0
