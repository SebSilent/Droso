"""Arm C's contract: same architecture as B by identity, frozen in a way a reader can check, and a
battery that belongs to the tier it trained on.

Nothing here measures H2. These tests hold the instrument to what the registration says it is, and the
one slow test runs the real CLI at tier 40 with a deliberately tiny epoch count -- the artifact it
writes says so, and no number from it is quotable as a measurement.
"""
import json
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import mp_e8_arm_b as b          # noqa: E402
import mp_e8_arm_c as c          # noqa: E402

PY = sys.executable


def test_architecture_is_arm_b_by_identity_not_by_copy():
    """The plan requires arm C to share arm B's architecture. Identity of the class object is the only
    version of that claim which cannot drift; a second Net() in this file would be a second contract."""
    assert c.b is b and c.b.Net is b.Net
    for k in ("EMBED", "HIDDEN", "LAYERS", "LR", "BATCH"):
        assert getattr(c.b, k) == getattr(b, k), k


def test_youden_takes_the_more_refusing_side_of_a_tie():
    """The estimator both arms' abstention rests on, pinned against a hand-checkable case: positives
    near 0.9, negatives near 0.1 -- the perfect cut is the midpoint of the gap, and J is 1.0."""
    r = c.youden([0.9, 0.95, 0.88], [0.1, 0.05, 0.2])
    # The cut is the midpoint of the GAP, which is between the largest negative (0.2) and the smallest
    # positive (0.88) -- 0.54, not 0.5. The first version of this test asserted 0.5, which was my
    # arithmetic error about the estimator, not a bug in it: the cut search runs over midpoints of
    # OBSERVED values, and 0.5 is not one of them.
    assert r["threshold"] == 0.54, r
    assert r["youden_j"] == 1.0
    assert (r["n_pos"], r["n_neg"]) == (3, 3)
    # a genuine tie, to exercise the refusal-biased tie-break: both cuts give J = 0.5
    t = c.youden([0.9, 0.3], [0.1, 0.5])
    assert t["youden_j"] == 0.5 and t["threshold"] == 0.7, t
    # an empty population is a refusal, not a threshold of infinity
    try:
        c.youden([], [0.1])
    except AssertionError:
        pass
    else:
        raise AssertionError("calibration ran with one population empty")


def test_freeze_empties_the_grad_stream_and_the_hash_is_the_frozen_state():
    """`frozen after pre-training` is the arm's whole identity, so it has to be a measured property:
    no trainable parameter left, and a state-dict hash that survives an inference pass. assert_still_
    frozen() is what runs between every probe round in the real tool, and a hash that moved there
    aborts the depth rather than writing an artifact about a model that kept learning."""
    m = b.Net(50)
    assert any(p.requires_grad for p in m.parameters())
    fz = c.freeze(m)
    assert fz["frozen"] and not fz["requires_grad_any"]
    assert c.weight_hash(m) == fz["state_dict_sha256"]
    with torch.no_grad():
        m(torch.tensor([[0, 1, 2]]))
    c.assert_still_frozen(m, fz["state_dict_sha256"], "inference only")
    # and the check actually checks: perturb the weights and it must refuse
    with torch.no_grad():
        m.fc.bias.add_(1.0)
    try:
        c.assert_still_frozen(m, fz["state_dict_sha256"], "deliberate perturbation")
    except SystemExit:
        pass
    else:
        raise AssertionError("assert_still_frozen() let a model that changed past the freeze")


def test_retrieval_exactness_is_a_comparison_with_the_expected_answer():
    """`exact` is half of the registered near-miss slice, so it must be reproducible from the row, not
    a feeling about the store."""
    m = b.Net(40)
    # The store vector is b.EMBED-dimensional, because vec() pools the model's own embedding table. A
    # hand-built store entry has to match that or torch.dot is comparing vectors from different spaces
    # -- which is the kind of thing that reads as a test bug and is really a dimension contract.
    m.ix = {w: i for i, w in enumerate([b.BOS, b.EOS, b.SEP, b.UNK] + [f"w{i}" for i in range(36)])}
    m.inv = list(m.ix.keys())
    store = [{"text": "the dog bites the latch", "ask": None, "kind": "tell",
              "vec": torch.ones(b.EMBED) / (b.EMBED ** 0.5)}]
    r = c.retrieve(m, store, "what bites the latch", want="the dog bites the latch")
    # exactness is the contract; the SIGN of the similarity is not. An untrained embedding table puts
    # the query anywhere on the sphere, and measured here it came out at -0.0041 against a hand-built
    # unit vector. Asserting sim > 0 would have been a claim about a random init, not about retrieval.
    assert r["exact"] is True, r
    assert -1.0 <= r["sim"] <= 1.0 and r["sim2"] is None, r
    r2 = c.retrieve(m, store, "what bites the latch", want="the cat sits")
    assert r2["exact"] is False, "a wrong item surfaced as top-1 must not be called exact"
    r3 = c.retrieve(m, store, "where is the harbor", want=None)
    assert r3["exact"] is False, "a never-taught ask has no exact match by definition"


def test_cli_tier40_smoke_run_is_labelled_as_nothing_more():
    """The whole pipeline, on the real battery, at a test epoch count. What this proves is that the
    artifact is shaped like a measurement and says it is not one."""
    sd = ROOT / "_tmp" / "armC_smoke_state"
    out = ROOT / "_tmp" / "armC_smoke.json"
    for depth in (1, 2, 3):
        r = subprocess.run([PY, str(ROOT / "tools" / "mp_e8_arm_c.py"), "--curriculum",
                            str(ROOT / "experiments" / "MP-E8" / "curriculum_tier40.json"),
                            "--state-dir", str(sd), "--depth", str(depth), "--epochs", "3"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    r = subprocess.run([PY, str(ROOT / "tools" / "mp_e8_arm_c.py"), "--curriculum",
                        str(ROOT / "experiments" / "MP-E8" / "curriculum_tier40.json"),
                        "--state-dir", str(sd), "--merge", "--depths", "1,2,3",
                        "--epochs", "3", "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    a = json.loads(out.read_text(encoding="utf-8"))
    assert a["arm"] == "C" and a["tier"] == 40
    assert a["probes"] == 136 and a["battery"]["tier"] == 40
    assert a["battery"]["n_probes_built_by_this_bench"] == 136
    for d in ("1", "2", "3"):
        assert a["frozen"][d]["requires_grad_any"] is False
        assert set(a["arms"]["C"]["probes"][d]) == {"live", "reasked", "restarted"}
        for ph, rows in a["arms"]["C"]["probes"][d].items():
            assert len(rows) == 136
            assert all(row["own"] is None and row["src"] == "arm_c_frozen_retrieval" for row in rows)
            assert all("cls" in row and "retr_sim" in row for row in rows)
        assert a["calibration"][d]["populations"]["never_told_asks"] > 0
        assert "retrieval_empty_among_never_told" in a["calibration"][d]["populations"]
    assert "TIER 40 ONLY" in a["claim_status"]
    assert a["training"]["frozen_after_training_each_depth"] is True


def test_merge_refuses_a_battery_that_does_not_match_the_chunks():
    """The tier-120 arm B defect, made structurally impossible for arm C: rows from one battery cannot
    be merged under another."""
    sd = ROOT / "_tmp" / "armC_mismatch_state"
    sd.mkdir(parents=True, exist_ok=True)
    d = b.state_paths(sd, 1)
    d["rows"].write_text(json.dumps({
        "depth": 1, "phases": {"live": [{"item": "x", "shape": "y"}]},
        "train_log": {"session_1": {"optimizer_steps": 1, "wall_clock_s": 0.0}},
        "config": {"embed": b.EMBED, "hidden": b.HIDDEN, "layers": b.LAYERS, "lr": b.LR,
                   "batch": b.BATCH, "epochs_per_session": 3, "max_generate_tokens": b.MAX_GEN,
                   "seed": b.SEED},
        "calibration": {}, "retrieval": {}, "parameters": 1, "vocab_size": 1,
        "freeze": {"state_dict_sha256": "x"}, "store_n_items": 0, "restarted_from": None}),
        encoding="utf-8")
    r = subprocess.run([PY, str(ROOT / "tools" / "mp_e8_arm_c.py"), "--curriculum",
                        str(ROOT / "experiments" / "MP-E8" / "curriculum_tier40.json"),
                        "--state-dir", str(sd), "--merge", "--depths", "1", "--out",
                        str(ROOT / "_tmp" / "armC_mismatch_should_not_exist.json")],
                       capture_output=True, text=True)
    assert r.returncode != 0, "a 1-row chunk merged under a 136-ask battery"
    assert "battery" in (r.stdout + r.stderr).lower()
    assert not (ROOT / "_tmp" / "armC_mismatch_should_not_exist.json").exists()
