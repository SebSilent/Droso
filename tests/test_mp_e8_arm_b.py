"""MP-E8 arm B: the contract tests.

Arm B is a real trainer now (D-MPE8-02), so the tests are about the things that would make its numbers
a lie rather than about whether torch works:

  * it refuses a manifest that is not the registered curriculum;
  * it cannot be shortcut into a non-sequential run (that would destroy the forgetting measurement);
  * its rows are keyable against arm A's rows by tools/ab_reproduction.py;
  * it gets no amnesty in the grader (row["own"] is None on every row);
  * the environment it ran in is recorded, because H4 is a cost comparison.

Everything here runs with --epochs 1 into a throwaway state dir. The measured artifact is produced by
the default 60-epoch chunks under experiments/MP-E8/results/, and every chunk writes its own config
into its own state file, so a shrunken test run cannot be mistaken for the real one even by accident.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

TOOL = str(ROOT / "tools" / "mp_e8_arm_b.py")
MANIFEST = str(ROOT / "experiments" / "MP-E8" / "curriculum_tier40.json")
PY = sys.executable


def run(*args, expect_rc=0):
    r = subprocess.run([PY, TOOL, *args], capture_output=True, text=True, timeout=900)
    if expect_rc == 0 and r.returncode != 0:
        raise AssertionError(f"arm B failed: {r.stdout[-800:]}{r.stderr[-800:]}")
    return r


@pytest.fixture(scope="module")
def depth1(tmp_path_factory):
    sd = tmp_path_factory.mktemp("armB_d1")
    run("--curriculum", MANIFEST, "--state-dir", str(sd), "--depth", "1",
        "--epochs", "1", "--max-gen", "4")
    return sd, json.loads((sd / "rows_d1.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the gate ----

def test_a_manifest_that_is_not_the_registered_curriculum_is_refused(tmp_path):
    """Two arms that disagree on curriculum_sha256 did not run the same experiment."""
    man = json.loads(Path(MANIFEST).read_text(encoding="utf-8"))
    man["sessions"][0]["tell_frames"][0] = man["sessions"][0]["tell_frames"][0].replace(
        "the dog bites the latch", "the dog bites the gate")
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(man), encoding="utf-8")
    r = run("--curriculum", str(bad), "--state-dir", str(tmp_path / "sd"), "--depth", "1",
            "--epochs", "1", expect_rc=1)
    assert "curriculum sha mismatch" in (r.stdout + r.stderr), r.stdout[-500:]


def test_depth_2_cannot_run_without_depth_1(tmp_path):
    """Sequential is the arm. A shortcut that re-initialises per depth would erase catastrophic
    forgetting, which is one of the nine axes the duel measures."""
    r = run("--curriculum", MANIFEST, "--state-dir", str(tmp_path / "sd"), "--depth", "2",
            "--epochs", "1", expect_rc=1)
    assert "arm B is SEQUENTIAL" in (r.stdout + r.stderr), r.stdout[-500:]


# ------------------------------------------------- the target-alignment defect ----
# These two tests exist because the first MEASURED arm B run was worthless and every structural
# assertion below passed it. Rows were keyable, own was None on all 1,224 of them, each phase held its
# 136 probes, the loss fell to 0.0055 -- and every row's answer was the empty string, because pad()
# built y[k] = s[k] (train the model to copy its input) instead of y[k] = s[k+1]. Greedy decode then
# predicted <sep> after the <sep> of a taught question at 88% of the probability mass and emitted zero
# tokens, so arm B "scored" 0 correct / 136 refused at every depth. D-MPE8-02 registered exactly this
# risk: a subtly wrong baseline loses for the wrong reason. See tools/mp_e8_arm_b.py::pad.

def test_pad_targets_are_the_next_token():
    import mp_e8_arm_b as ab
    ix = {"<pad>": 7, "<eos>": 1}
    seqs = [[0, 4, 5, 6], [2, 3]]
    x, y = ab.pad(seqs, ix)
    for row, s in zip(y.tolist(), seqs):
        assert row[:len(s) - 1] == s[1:], f"y={row} for s={s}: the target is not the NEXT token"
        assert set(row[len(s) - 1:]) == {-100}, f"tail not masked in {row}"
    assert x.tolist()[1][2:] == [ix["<pad>"], ix["<pad>"]], "padding did not reach the row end"


def test_two_processes_reproduce_depth1_exactly(tmp_path):
    """Arm B's headline number is an invention rate, and two measured runs of the SAME configuration
    moved 672 of 1,224 rows -- invented [35,52,38] vs [75,95,80] -- because run_depth() built the Net
    before calling torch.manual_seed(), so the initial weights were drawn from PyTorch's
    entropy-seeded generator instead of the registered seed. Reproducibility is not a nicety here: a
    single run cannot support a comparison against arm A. This test is the regression guard."""
    outs = []
    for i in (1, 2):
        sd = tmp_path / f"sd{i}"
        run("--curriculum", MANIFEST, "--state-dir", str(sd), "--depth", "1",
            "--epochs", "30", "--max-gen", "4")
        blk = json.loads((sd / "rows_d1.json").read_text(encoding="utf-8"))
        # cls is added at merge time, not in the chunk, so the comparison is on what a chunk holds:
        # the generated text, its confidence and whether the gate let it through.
        outs.append({"final_loss": blk["train_log"]["session_1"]["final_loss"],
                     "threshold": blk["calibration"]["threshold"],
                     "rows": [[r["ask"], r["said"], r["conf"], r["mech"]]
                              for ph in ("live", "reasked", "restarted") for r in blk["phases"][ph]]})
    a, b = outs
    assert a["final_loss"] == b["final_loss"], f"{a['final_loss']} vs {b['final_loss']}"
    assert a["threshold"] == b["threshold"], f"threshold {a['threshold']} vs {b['threshold']}"
    assert a["rows"] == b["rows"], "two processes produced different rows from the same seed"


def test_a_trained_model_answers_a_taught_question():
    """The behavioural floor, and the one that does not depend on the algebra being written this way:
    a model that has seen a QA pair thirty times must be ABLE to say something when asked it. Nothing
    here writes an artifact, so no shrunken epoch count can be mistaken for the measured run."""
    import random
    import mp_e8_arm_b as ab
    man = json.loads(Path(MANIFEST).read_text(encoding="utf-8"))
    vocab, ix = ab.build_vocab(man)
    ix[ab.PAD] = len(ix)
    inv = {v: k for k, v in ix.items()}
    model = ab.Net(len(ix))
    model.ix, model.inv = ix, inv
    ab.EPOCHS = 30                      # test-only shrink; the measured chunks use the default 60
    ab.train_session(model, ab.session_sequences(man["sessions"][0], ix), random.Random(ab.SEED))
    q, a = man["sessions"][0]["qa_pairs"][0]
    text, conf, ntok = ab.generate(model, ab.ask_prompt(q, ix))
    assert ntok > 0, (f"zero tokens emitted after a taught question (conf {conf}). The model is not "
                      f"predicting the next token; check pad().")
    assert set(text.lower().split()) & set(ab.tokenize(a)), \
        f"answer {text!r} shares no word with the taught answer {a!r}"


# ---------------------------------------------------------------- the rows ----

def test_rows_are_keyable_against_arm_A(depth1):
    _sd, blk = depth1
    want = {"item", "shape", "ask", "own", "taught", "answered", "said", "src", "reason", "mech"}
    for phase, rows in blk["phases"].items():
        assert rows, f"{phase} produced no rows"
        assert len(rows) == 136, f"{phase} has {len(rows)} rows, arm A has 136 probes"
        for r in rows:
            assert want <= set(r), f"{phase} row missing {want - set(r)}"


def test_own_is_none_on_every_row_so_invention_gets_no_amnesty(depth1):
    """classify() calls an unexpected sentence ENTAILED when it equals row['own']. Setting own to the
    model's own output would regrade every invention as a entailment -- a gift to arm B."""
    _sd, blk = depth1
    for phase, rows in blk["phases"].items():
        for r in rows:
            assert r["own"] is None, f"{phase}/{r['item']}: own={r['own']!r}"


def test_the_bench_grader_scores_arm_B_rows_without_special_handling(depth1):
    import electric_learn_bench as eb
    _sd, blk = depth1
    allowed = {"correct", "partial", "refused", "absence", "entailed", "echo", "cross_echo",
               "misattrib", "invented"}
    for phase, rows in blk["phases"].items():
        for r in rows:
            assert eb.classify(r) in allowed


# ------------------------------------------------------------- abstention ----

def test_the_threshold_is_fixed_on_heldout_data_before_scoring(depth1):
    _sd, blk = depth1
    cal = blk["calibration"]
    assert cal["n_taught_asks"] > 0 and cal["n_never_told_asks"] > 0
    assert cal["rule"].startswith("Youden")
    assert cal["threshold"] is not None
    # the two populations must be separable enough for the threshold to mean something
    assert cal["youden_j"] > 0.0, cal


def test_never_told_asks_are_abstained_on(depth1):
    """Refusal fairness: an arm that speaks on every distractor has not been calibrated."""
    _sd, blk = depth1
    dist = [r for r in blk["phases"]["live"] if r["item"].startswith("dist")]
    assert dist, "no distractor probes reached the arm"
    refused = sum(1 for r in dist if r["said"] == "")
    assert refused >= len(dist) * 0.5, f"only {refused}/{len(dist)} never-told asks refused"


# ----------------------------------------------------------- provenance ----

def test_environment_and_chunking_are_recorded(depth1, tmp_path):
    _sd, blk = depth1
    assert blk["single_process_measurement"] is False
    assert blk["config"]["epochs_per_session"] == 1, "the test run must record what it actually ran"
    assert blk["train_log"]["session_1"]["optimizer_steps"] > 0
    assert blk["train_log"]["session_1"]["wall_clock_s"] > 0


def test_merged_artifact_carries_torch_build_and_refuses_mismatched_chunks(depth1, tmp_path):
    sd = Path(depth1[0])
    # depth 2 needs depth 1's checkpoint; reuse the module fixture's dir copy
    run("--curriculum", MANIFEST, "--state-dir", str(sd), "--depth", "2",
        "--epochs", "1", "--max-gen", "4")
    out = tmp_path / "armB.json"
    run("--merge", "--state-dir", str(sd), "--curriculum", MANIFEST, "--out", str(out),
        "--depths", "1,2", "--epochs", "1", "--max-gen", "4")
    art = json.loads(out.read_text(encoding="utf-8"))
    t = art["provenance"]["torch"]
    assert t["version"] and "cuda_available" in t and "threads" in t
    assert art["provenance"]["curriculum_sha256"] == art["provenance"][
        "curriculum_sha256_recomputed_from_arm_A_source"]
    assert art["single_process_measurement"] is False
    assert art["chunk_invocations"] == ["--depth 1", "--depth 2", "--merge"]
    assert art["arms"]["B"]["probes"]["1"]["live"], "merged rows missing"
    assert 2_000_000 < art["provenance"]["parameters"] < 10_000_000, \
        f"plan requires a 2-10M parameter arm B: {art['provenance']['parameters']:,}"

    # a chunk that ran with different hyperparameters must not merge into one model's artifact
    p = sd / "rows_d2.json"
    bad = json.loads(p.read_text(encoding="utf-8"))
    bad["config"]["epochs_per_session"] = 99
    p.write_text(json.dumps(bad), encoding="utf-8")
    r = run("--merge", "--state-dir", str(sd), "--curriculum", MANIFEST,
            "--out", str(tmp_path / "nope.json"), "--depths", "1,2", expect_rc=1)
    assert "chunk configs disagree" in (r.stdout + r.stderr)


def test_vocab_is_built_from_the_curriculum_and_nothing_else(depth1):
    """A word that exists only in a distractor ask must not be in the vocabulary: that would mean the
    arm was handed part of the test set."""
    import mp_e8_arm_b as ab
    man = json.loads(Path(MANIFEST).read_text(encoding="utf-8"))
    _vocab, ix = ab.build_vocab(man)
    sys.path.insert(0, str(ROOT / "tools"))
    import electric_learn_bench as eb
    dist_only = set()
    taught_words = {w for line in ab.manifest_text(man) for w in ab.tokenize(line)}
    for shape, ask, _why in eb.DISTRACTORS:
        dist_only |= {w for w in ab.tokenize(ask) if w not in taught_words}
    assert dist_only, "distractors share all vocabulary with the curriculum; test is vacuous"
    for w in dist_only:
        assert w not in ix, f"{w!r} is a distractor-only word that entered the vocabulary"
