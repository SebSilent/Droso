"""MP-E8 arm B -- a sequential neural language model, fine-tuned session by session on the same
curriculum arm A reads.

Built under PI ruling D-MPE8-02 (add the pinned ML dependency; do not hand-roll the trainer) and
D-MPE8-01's provenance rule (flag state and environment travel with every arm's numbers).

WHAT THIS ARM IS
  A 1-layer LSTM language model, ~3.3M parameters, over a word vocabulary built from the curriculum
  manifest and nothing else. Training is SEQUENTIAL: session 1 is fine-tuned, then session 2 from
  those weights, then session 3. No replay of earlier sessions, no joint training -- that is the
  point, because catastrophic forgetting (E9) is one of the axes the duel measures.

WHAT IT IS GIVEN, AND WHAT IT IS NOT
  It sees exactly the manifest's tell frames and QA pairs. The probe asks for the TELL items are NOT
  in its training material: arm A is told sentences and must answer asks it was never asked, and a
  model trained on the asks would be trained on the test. The 16 QA pairs are curriculum material and
  arm A has them too, so they are fair game. `train_test_disjoint` in the artifact measures this
  rather than asserting it.

ABSTENTION (plan: Refusal fairness)
  Arm B gets its OWN confidence threshold, calibrated on held-out data at every depth, so refusal is
  a contest rather than a structural gift to arm A. Confidence is the mean log-probability per token
  of the continuation the model actually chose. The threshold is the cut that best separates
  confidence on items it WAS taught from confidence on asks it was NEVER taught -- Youden's J on those
  two distributions, ties broken toward refusing more. The rule is fixed here, before any graded row
  is compared to another arm, and the held-out sets are recorded in full.

CHUNKING
  The 600 s command cap is handled the way MP-E9 handled it: one invocation trains and evaluates ONE
  depth, checkpointing to --state-dir; `--merge` assembles the artifact. The merged file says
  single_process_measurement: false, because one process genuinely did not do this run. Wall-clock is
  summed from the per-depth measurements, never back-filled.

Run (three chunks then a merge):
  .venv/Scripts/python.exe tools/mp_e8_arm_b.py --depth 1 --state-dir _tmp/armB
  .venv/Scripts/python.exe tools/mp_e8_arm_b.py --depth 2 --state-dir _tmp/armB
  .venv/Scripts/python.exe tools/mp_e8_arm_b.py --depth 3 --state-dir _tmp/armB
  .venv/Scripts/python.exe tools/mp_e8_arm_b.py --merge --state-dir _tmp/armB \
      --out experiments/MP-E8/results/armB_tier40.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tools"))

import torch
import torch.nn as nn

import electric_learn_bench as eb          # the grader: classify, by_shape, retention, PROBES
import mp_e8_curriculum as curriculum      # the manifest contract, incl. sha recomputation

DEFAULT_MANIFEST = HERE / "experiments" / "MP-E8" / "curriculum_tier40.json"

# ---------------------------------------------------------------- the model ----
EMBED = 256
HIDDEN = 768
LAYERS = 1
LR = 3e-4
BATCH = 8
EPOCHS = 60
MAX_GEN = 14
SEED = 20261103

BOS, EOS, SEP, UNK = "<bos>", "<eos>", "<sep>", "<unk>"
SPECIALS = [BOS, EOS, SEP, UNK]
WORD_RE = re.compile(r"[a-z']+|\?")

# Arm B is a generative model: it has no separate self-report field. classify() reads row["own"] to
# decide whether an unexpected sentence was ENTAILED by something the house itself said, and leaving
# own set to the generated text would silently regrade every invention as an entailment -- a gift to
# arm B. So own is None for every arm B row, and the inventions classify as inventions.
ARM_B_GIFT_RULE = (
    "row['own'] is None on every arm B row: a generative model has no self-report distinct from its "
    "output, and populating it would turn classify()'s entailed branch into an amnesty for invention")


def tokenize(s: str) -> list[str]:
    return WORD_RE.findall((s or "").lower())


def _rel(p: Path) -> str:
    """Display a path repo-relative when it is inside the repo; --curriculum may be anywhere."""
    try:
        return str(Path(p).resolve().relative_to(HERE)).replace("\\", "/")
    except ValueError:
        return str(p)


def manifest_text(man: dict) -> list[str]:
    """Every string the manifest actually contains, in manifest order. Vocabulary comes from here and
    nowhere else, so the vocab is a property of the curriculum, not of the probe set."""
    out: list[str] = []
    for s in man["sessions"]:
        out.extend(s["tell_frames"])
        for q, a in s["qa_pairs"]:
            out.extend([q, a])
    return out


def build_vocab(man: dict) -> tuple[list[str], dict]:
    words: list[str] = []
    seen = set()
    for line in manifest_text(man):
        # tell_frames are source CALLS (svo('the dog bites the latch', ...)); the words inside them
        # are what matters, and the code identifiers never reach the model's input either.
        for t in tokenize(re.sub(r"\b(svo|intr|obl|who|what|where|when|why|how)\b", " ", line)):
            if t not in seen:
                seen.add(t)
                words.append(t)
    vocab = SPECIALS + sorted(words)
    return vocab, {w: i for i, w in enumerate(vocab)}


class Net(nn.Module):
    def __init__(self, vocab_size: int):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, EMBED)
        self.lstm = nn.LSTM(EMBED, HIDDEN, LAYERS, batch_first=True)
        self.fc = nn.Linear(HIDDEN, vocab_size)

    def forward(self, x, state=None):
        h, state = self.lstm(self.embed(x), state)
        return self.fc(h), state


def param_count(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters())


# ---------------------------------------------------------------- the data ----
def session_sequences(sess: dict, ix: dict) -> list[list[int]]:
    """One session's material as token streams. Tell frames become [bos] sentence [eos]; QA pairs
    become [bos] question [sep] answer [eos] -- the only place the model ever sees a question asked."""
    seqs: list[list[int]] = []
    for call in sess["tell_frames"]:
        sent = re.findall(r"'([^']+)'", call)[:1]
        if not sent:
            raise AssertionError(f"no sentence literal in tell frame: {call}")
        seqs.append([ix[BOS]] + [ix.get(w, ix[UNK]) for w in tokenize(sent[0])] + [ix[EOS]])
    for q, a in sess["qa_pairs"]:
        seqs.append([ix[BOS]] + [ix.get(w, ix[UNK]) for w in tokenize(q)] + [ix[SEP]]
                    + [ix.get(w, ix[UNK]) for w in tokenize(a)] + [ix[EOS]])
    return seqs


def pad(batch: list[list[int]], ix: dict):
    n = max(len(s) for s in batch)
    x = torch.full((len(batch), n), ix[PAD] if PAD in ix else ix[EOS], dtype=torch.long)
    for i, s in enumerate(batch):
        x[i, :len(s)] = torch.tensor(s, dtype=torch.long)
    y = torch.full((len(batch), n), -100, dtype=torch.long)
    for i, s in enumerate(batch):
        y[i, 1:len(s)] = torch.tensor(s[1:], dtype=torch.long)
    return x, y


PAD = "<pad>"


# ------------------------------------------------------------------ training ----
def train_session(model, seqs, rng) -> dict:
    t0 = time.time()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossf = nn.CrossEntropyLoss()
    steps = 0
    last = None
    for _ in range(EPOCHS):
        order = list(range(len(seqs)))
        rng.shuffle(order)
        for i in range(0, len(order), BATCH):
            batch = [seqs[j] for j in order[i:i + BATCH]]
            if len(batch) < 2:
                continue
            x, y = pad(batch, model.ix)
            logits, _ = model(x)
            loss = lossf(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
            steps += 1
            last = float(loss.detach())   # .detach(): converting a requires_grad tensor to a scalar
                                          # warns and keeps graph memory alive across the epoch loop
    return {"optimizer_steps": steps, "epochs": EPOCHS, "batch": BATCH,
            "final_loss": last, "wall_clock_s": round(time.time() - t0, 3)}


# ----------------------------------------------------------------- inference ----
def generate(model, prompt: list[int], max_len: int = MAX_GEN) -> tuple[str, float, int]:
    """Greedy decode. Returns (text, mean log-prob per generated token, tokens emitted).

    Confidence is per-token, not per-sequence: a summed log-prob would make long answers look
    unconfident for being long, and length is exactly what the fluency description measures.
    """
    ix = model.ix
    inv = model.inv
    toks = list(prompt)
    out: list[str] = []
    logps: list[float] = []
    with torch.no_grad():
        for _ in range(max_len):
            logits, _ = model(torch.tensor([toks], dtype=torch.long))
            lp = torch.log_softmax(logits[0, -1], dim=-1)
            nxt = int(torch.argmax(lp))
            logps.append(float(lp[nxt]))
            if nxt == ix[EOS]:
                break
            toks.append(nxt)
            w = inv[nxt]
            if w in SPECIALS:
                continue
            out.append(w)
    text = " ".join(out).replace(" ?", "?").strip()
    conf = sum(logps) / len(logps) if logps else float("-inf")
    return text, conf, len(out)


def ask_prompt(ask: str, ix: dict) -> list[int]:
    return [ix[BOS]] + [ix.get(w, ix[UNK]) for w in tokenize(ask)] + [ix[SEP]]


def probe_arm_b(model, taught_depth: int, threshold: float) -> list[dict]:
    """Ask everything, exactly as eb.probe() does for arm A, and emit the same row keys so a keyed
    row-for-row comparison between arms is possible."""
    ix = model.ix
    rows = []
    for iid, shape, ask, tell, d in eb.PROBES:
        want = tell if (tell is not None and d < taught_depth) else None
        text, conf, ntok = generate(model, ask_prompt(ask, ix))
        abstained = not math.isfinite(conf) or conf < threshold
        row = dict(item=iid, shape=shape, ask=ask,
                   own=None,
                   taught=(want or "").lower() or None,
                   answered=bool(text) and not abstained,
                   said="" if abstained else text,
                   src="arm_b_lstm",
                   reason=("" if not abstained else
                           f"abstained: conf {conf:.3f} < threshold {threshold:.3f}")[:90])
        row["mech"] = "abstained" if abstained else "generated"
        row["conf"] = None if not math.isfinite(conf) else round(conf, 4)
        row["gen_tokens"] = ntok
        rows.append(row)
    return rows


# ---------------------------------------------------------------- calibration ----
def calibrate(model, taught_depth: int) -> dict:
    """Fix the abstention threshold on held-out data, at this depth, before any graded comparison.

    Two populations, both things the model is actually asked about:
      taught      -- asks whose item IS taught at this depth (refusing these costs correctness)
      never_told  -- the bench's DISTRACTORS, asks with no answer anywhere in the curriculum
                     (answering these is confabulation)
    The threshold is the cut maximising Youden's J = TPR - FPR between them. Ties go to the HIGHER
    threshold, i.e. to refusing more, because an uncalibrated tendency to speak is the failure this
    arm is being watched for.
    """
    ix = model.ix
    taught_c, distr_c = [], []
    for iid, shape, ask, tell, d in eb.PROBES:
        _t, conf, _n = generate(model, ask_prompt(ask, ix))
        if iid.startswith("dist"):
            distr_c.append(conf)
        elif tell is not None and d < taught_depth:
            taught_c.append(conf)
    if not taught_c or not distr_c:
        raise AssertionError("calibration needs both populations; got "
                             f"taught={len(taught_c)} never_told={len(distr_c)}")
    cuts = sorted(set(taught_c + distr_c))
    best, best_j = None, None
    for a, b in zip(cuts, cuts[1:]):
        thr = (a + b) / 2.0
        tpr = sum(1 for c in taught_c if c >= thr) / len(taught_c)      # speaks when it knows
        fpr = sum(1 for c in distr_c if c >= thr) / len(distr_c)        # speaks when it cannot know
        j = tpr - fpr
        # ties -> higher threshold: iterate ascending and keep on >=, so the last equal best wins
        if best_j is None or j >= best_j:
            best_j, best = j, thr
    return {"threshold": round(best, 4), "youden_j": round(best_j, 4),
            "n_taught_asks": len(taught_c), "n_never_told_asks": len(distr_c),
            "taught_conf": {"min": round(min(taught_c), 4), "median": round(sorted(taught_c)[len(taught_c) // 2], 4),
                            "max": round(max(taught_c), 4)},
            "never_told_conf": {"min": round(min(distr_c), 4),
                                "median": round(sorted(distr_c)[len(distr_c) // 2], 4),
                                "max": round(max(distr_c), 4)},
            "rule": "Youden's J on taught-vs-never-told per-token log-prob; ties to the higher "
                    "threshold (refuse more)",
            "held_out_set": "the bench's DISTRACTORS (asks with no answer in the curriculum) plus the "
                            "confidence distribution over taught asks; both listed by count here and "
                            "the asks themselves are in rows[] of the same artifact"}


# ----------------------------------------------------------------- provenance ----
def git(*a) -> str:
    try:
        return subprocess.run(["git", *a], cwd=str(HERE), capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def torch_build() -> dict:
    return {"version": torch.__version__, "cuda_version": torch.version.cuda,
            "cuda_available": bool(torch.cuda.is_available()),
            "threads": torch.get_num_threads(),
            "note": "D-MPE8-02 condition (c): the +cpu wheel and a cu12x wheel of the same version "
                    "are different machines, and H4's cost claim has to be able to tell them apart"}


def provenance(man_path: Path, man: dict, seed: int, arch: dict) -> dict:
    return {
        "arm": "B",
        "git_head": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "interpreter": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch_build(),
        "harness": "tools/mp_e8_arm_b.py",
        "harness_sha256": hashlib.sha256((HERE / "tools" / "mp_e8_arm_b.py").read_bytes()).hexdigest(),
        "grader": "tools/electric_learn_bench.py (eb.classify, eb.by_shape, eb.retention)",
        "grader_sha256": hashlib.sha256((HERE / "tools" / "electric_learn_bench.py").read_bytes()).hexdigest(),
        "curriculum_file": _rel(man_path),
        "curriculum_sha256": man["curriculum_sha256"],
        # Recomputed from arm A's SOURCE, not read from the manifest: the contract is that the file
        # arm B trained on is still the curriculum the live bench teaches.
        "curriculum_sha256_recomputed_from_arm_A_source": curriculum.load()["curriculum_sha256"],
        "seed": seed,
        "architecture": dict(arch, type="LSTM",
                             source="read back from each chunk's own state file, not from the merge "
                                    "process's globals"),
        "parameters": None,   # filled by the caller once the model exists
        "flag_state": {
            # D-MPE8-01 condition 1, applied to an arm that has no ELECTRIC flags at all. Arm B is a
            # separate process with no Droso organ in it: saying so is the difference between a clean
            # number and a number a reader can attribute to a flag that was never present.
            "electric_flags": {a: False for a in eb.tm.CANDIDATE_ATTRS},
            "flags_reach_this_arm": False,
            "meaning": "arm B contains no Droso organ and runs no ELECTRIC attribute; its zero is a "
                       "property of the LSTM, not of a flag, and it is NOT evidence about the shipped "
                       "organism",
        },
        "arm_B_gets_no_report_frame": ARM_B_GIFT_RULE,
    }


# --------------------------------------------------------------------- state ----
def state_paths(d: Path, depth: int) -> dict:
    return {"ckpt": d / f"model_d{depth}.pt", "rows": d / f"rows_d{depth}.json",
            "calib": d / f"calib_d{depth}.json", "train": d / f"train_d{depth}.json"}


def save_model(m: nn.Module, path: Path, ix: dict) -> None:
    torch.save({"state": m.state_dict(), "vocab": list(ix.keys())}, path)


def load_model(path: Path, ix: dict, inv: dict) -> Net:
    m = Net(len(ix))
    m.ix, m.inv = ix, inv
    blob = torch.load(path, map_location="cpu", weights_only=False)
    m.load_state_dict(blob["state"])
    m.eval()
    return m


# ---------------------------------------------------------------------- run ----
def run_depth(depth: int, man: dict, sd: Path, seed: int) -> dict:
    torch.set_num_threads(6)
    rng = random.Random(seed + depth)
    vocab, ix = build_vocab(man)
    ix[PAD] = len(ix)
    inv = {v: k for k, v in ix.items()}

    sd.mkdir(parents=True, exist_ok=True)
    model = Net(len(ix))
    model.ix, model.inv = ix, inv
    torch.manual_seed(seed)
    model.eval()

    # sequential fine-tuning: resume from the previous depth's checkpoint, never from scratch
    if depth > 1:
        prev = state_paths(sd, depth - 1)["ckpt"]
        if not prev.exists():
            raise SystemExit(f"--depth {depth} needs {prev}: arm B is SEQUENTIAL, session {depth-1} "
                             f"must have been fine-tuned before session {depth}. Run the depths in "
                             f"order; there is no shortcut that keeps the forgetting measurement.")
        model = load_model(prev, ix, inv)

    log = {}
    t0 = time.time()
    log[f"session_{depth}"] = train_session(model, session_sequences(man["sessions"][depth - 1], ix), rng)
    log[f"session_{depth}"]["wall_clock_s"] = round(time.time() - t0, 3)

    cal = calibrate(model, depth)
    phases = {}
    phases["live"] = probe_arm_b(model, depth, cal["threshold"])
    phases["reasked"] = probe_arm_b(model, depth, cal["threshold"])
    save_model(model, state_paths(sd, depth)["ckpt"], ix)
    fresh = load_model(state_paths(sd, depth)["ckpt"], ix, inv)
    phases["restarted"] = probe_arm_b(fresh, depth, cal["threshold"])

    out = {"depth": depth, "calibration": cal, "phases": phases, "train_log": log,
           "parameters": param_count(model), "vocab_size": len(ix),
           # Written INTO the chunk's state, not read back off the merge process's globals: if a chunk
           # ran with --epochs 5 and the merge ran with the default 60, an artifact that printed 60
           # would be describing a run that did not happen.
           "config": {"embed": EMBED, "hidden": HIDDEN, "layers": LAYERS, "lr": LR, "batch": BATCH,
                      "epochs_per_session": EPOCHS, "max_generate_tokens": MAX_GEN, "seed": seed},
           "single_process_measurement": False,
           "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    p = state_paths(sd, depth)
    p["rows"].write_text(json.dumps(out), encoding="utf-8")
    print(f"[armB] depth {depth}: steps={log[f'session_{depth}']['optimizer_steps']} "
          f"train_s={log[f'session_{depth}']['wall_clock_s']} "
          f"thr={cal['threshold']} params={param_count(model)} -> {p['rows'].name}", flush=True)
    return out


def merge(sd: Path, man_path: Path, man: dict, seed: int, depths: list[int]) -> dict:
    per = {d: json.loads(state_paths(sd, d)["rows"].read_text(encoding="utf-8")) for d in depths}
    missing = [d for d in depths if d not in per]
    if missing:
        raise SystemExit(f"no state for depths {missing} in {sd}")
    params = per[max(depths)]["parameters"]
    # every chunk must have run with the same architecture, or the "one sequential model" story is
    # false: depth 2 continues depth 1's weights, and weights trained at a different hidden size
    # would not even load. Checked rather than assumed.
    cfgs = {str(d): blk["config"] for d, blk in per.items()}
    if len({json.dumps(c, sort_keys=True) for c in cfgs.values()}) != 1:
        raise SystemExit(f"chunk configs disagree across depths: {cfgs} -- the depths were not run "
                         f"as one model. Re-run every chunk with identical hyperparameters.")
    arch = per[max(depths)]["config"]
    if arch["seed"] != seed:
        raise SystemExit(f"--seed {seed} does not match the seed the chunks ran with "
                         f"({arch['seed']}); the artifact would record a run that did not happen.")
    prov = provenance(man_path, man, seed, arch)
    prov["parameters"] = params
    prov["chunk_configs"] = cfgs

    # train/test disjointness, measured not asserted
    train_words = set()
    for s in man["sessions"]:
        for call in s["tell_frames"]:
            train_words |= set(tokenize(re.findall(r"'([^']+)'", call)[0]))
        for q, a in s["qa_pairs"]:
            train_words |= set(tokenize(q)) | set(tokenize(a))
    probe_asks = {ask for _i, _s, ask, _t, _d in eb.PROBES}
    asks_in_train = sorted(a for a in probe_asks
                           if all(w in train_words for w in tokenize(a)) and a not in
                           {q for s in man["sessions"] for q, _a in s["qa_pairs"]})

    arms_b = {}
    for d, blk in per.items():
        arms_b[str(d)] = {}
        for ph, rows in blk["phases"].items():
            graded = [dict(r, cls=eb.classify(r)) for r in rows]
            # a LIST, matching arm A's probes[depth][phase] shape exactly, so tools/ab_reproduction.py
            # can key rows by (arm, depth, phase, item, shape) across arms without a special case.
            arms_b[str(d)][ph] = graded
    summary = {str(d): {ph: {"by_shape": eb.by_shape(blk["phases"][ph]),
                             "retention": eb.retention(blk["phases"][ph])}
                        for ph in blk["phases"]} for d, blk in per.items()}

    total_steps = sum(blk["train_log"][f"session_{d}"]["optimizer_steps"] for d, blk in per.items())
    total_train_s = sum(blk["train_log"][f"session_{d}"]["wall_clock_s"] for d, blk in per.items())

    return {
        "arm": "B",
        "experiment": "MP-E8",
        "tier": man["tier"],
        "items": man["n_items"],
        "probes": len(eb.PROBES),
        "depths": depths,
        "arms": {"B": {"seconds": round(total_train_s, 3), "runs": [], "probes": arms_b,
                       "arm_provenance": prov["flag_state"]}},
        "summary": {"B": summary},
        "training": {"sequential": True, "replay_of_earlier_sessions": False,
                     "total_optimizer_steps": total_steps,
                     "total_train_wall_clock_s": round(total_train_s, 3),
                     "per_session": {str(d): blk["train_log"][f"session_{d}"] for d, blk in per.items()},
                     "vocabulary_built_from": "the curriculum manifest only"},
        "calibration": {str(d): per[d]["calibration"] for d in per},
        "train_test_disjoint": {
            "claim": "no probe ask for a TELL item was used as a training target",
            "probe_asks_whose_words_all_appear_in_training": asks_in_train,
            "n_probe_asks": len(probe_asks),
            "reading": "word overlap is not the violation; a trained (question -> answer) PAIR is. "
                       "This list exists so a reader can see which asks share vocabulary with the "
                       "corpus and judge the comparison anyway.",
        },
        "single_process_measurement": False,
        "single_process_measurement_reason": (
            f"arm B was produced by {len(depths)} sequential chunk invocations plus a merge, each "
            f"under the 600 s command cap, communicating through {sd}/model_d*.pt. Recording false "
            "here is the point: a wall-clock claim that pretends one process did the whole run is "
            "the kind of cost number H4 cannot be compared on."),
        "chunk_invocations": [f"--depth {d}" for d in depths] + ["--merge"],
        "provenance": prov,
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    global EPOCHS, MAX_GEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--curriculum", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--state-dir", default=str(HERE / "_tmp" / "armB_state"))
    ap.add_argument("--depth", type=int)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--out", default=str(HERE / "experiments" / "MP-E8" / "results" / "armB_tier40.json"))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--depths", default="1,2,3")
    ap.add_argument("--epochs", type=int, default=EPOCHS,
                    help="optimizer epochs per session; the MEASURED run uses the default 60. Lower "
                         "values exist for tests only, and every chunk's own value is recorded in the "
                         "artifact, so a shrunken run cannot be mistaken for the real one.")
    ap.add_argument("--max-gen", type=int, default=MAX_GEN)
    a = ap.parse_args()
    EPOCHS, MAX_GEN = a.epochs, a.max_gen

    man_path = Path(a.curriculum)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    # (1) SELF-CONSISTENCY. The manifest's own content must hash to the sha it declares. The check
    # under this one compares the DECLARED sha to arm A's source, which catches "wrong curriculum"
    # but NOT "edited curriculum with a stale header" -- measured, not suspected: arm B ran a
    # tampered tier-40 manifest to completion with rc=0 (the first execution of
    # tests/test_mp_e8_arm_b.py). Same canonical form as tools/mp_e8_curriculum.py and the bench:
    # {sessions, pairs}, distractors excluded.
    canon = json.dumps({"sessions": [s["tell_frames"] for s in man["sessions"]],
                        "pairs": [s["qa_pairs"] for s in man["sessions"]]}, sort_keys=True)
    self_derived = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    if man.get("curriculum_sha256") != self_derived:
        raise SystemExit(
            f"curriculum sha mismatch (self-consistency): {man_path.name} declares "
            f"{str(man.get('curriculum_sha256'))[:16]} but its content hashes to {self_derived[:16]}. "
            f"The manifest was edited after it was sealed, and the curriculum IS the experiment.")
    # (2) IT IS THE REGISTERED CURRICULUM, not merely a self-consistent one. Only meaningful for the
    # tier arm A carries as literals; a 120-item manifest cannot equal a 40-item source hash, so the
    # check is scoped by tier instead of being silently applied to every manifest.
    if man.get("tier") == 40:
        recomputed = curriculum.load()["curriculum_sha256"]
        if recomputed != man["curriculum_sha256"]:
            raise SystemExit(f"curriculum sha mismatch: file says {man['curriculum_sha256'][:16]}, "
                             f"recomputed {recomputed[:16]}. Arm B refuses to run on a manifest that "
                             f"is not the one registered.")

    sd = Path(a.state_dir)
    if a.merge:
        depths = [int(x) for x in a.depths.split(",")]
        out = merge(sd, man_path, man, a.seed, depths)
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
        print(f"[armB] merged depths {depths} -> {p}")
        print(f"[armB] total optimizer steps {out['training']['total_optimizer_steps']}, "
              f"train wall-clock {out['training']['total_train_wall_clock_s']} s, "
              f"parameters {out['provenance']['parameters']:,}")
        return 0
    if a.depth is None:
        raise SystemExit("give --depth N (one depth per process) or --merge")
    run_depth(a.depth, man, sd, a.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
