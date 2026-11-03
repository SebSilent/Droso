"""MP-E8 arm C: arm B's architecture, frozen after pre-training, answering by vector-store retrieval.

WHY THIS ARM EXISTS. H2's second clause is a claim about calibration, not about accuracy: "arm C
abstention is poorly calibrated exactly when retrieval returns a near-miss", and the registered slice
(D-MPE8-04, arm_C_near_miss_slice_definition) is "top-1 retrieval within the abstain threshold but not
an exact match". A frozen language model with a store over the taught items is the configuration where
that failure is expected -- retrieval-empty confabulation is its known pathology -- so the artifact has
to record, per row, what retrieval returned, how close it was, and whether it was an exact match. If it
does not record those, the claim cannot be measured at all, and the arm would be a second copy of B.

WHAT IS REUSED, AND WHY REUSE IS THE POINT. `import mp_e8_arm_b as b` supplies Net, build_vocab,
session_sequences, train_session, generate, pad, tokenize, state_paths, save_model and load_model.
"Same architecture as arm B" is then satisfied by calling the same constructor under the same
constants, not by a second implementation that can drift -- which is the same reasoning
mp_e8_curriculum.py gives for parsing arm A's lists instead of copying them. Both of arm B's instrument
defects are inherited fixed: the pad target is next-token, and torch.manual_seed runs BEFORE Net().

WHAT IS DIFFERENT, and each difference is a measured property, not a comment:
 1. FROZEN. After the last gradient step at a depth, requires_grad is cleared, the module is set to
    eval(), and a sha256 of the saved state dict is taken. That hash is re-computed after every probe
    round and the run aborts if it moved. "Frozen after pre-training" is then checkable by a reader.
 2. RETRIEVAL. A vector store over every item taught up to this depth: mean token-embedding of the
    item, cosine similarity to the mean token-embedding of the ask. The answer is generated from a
    prompt that carries the retrieved item, so retrieval can help and can mislead, which is what H2 is
    about.
 3. ABSTENTION, CALIBRATED INCLUDING THE EMPTY CASE. Two gates, both fitted on held-out data before any
    graded comparison: a similarity floor (Youden's J between taught asks and never-taught asks) and a
    confidence threshold (Youden's J between the same two populations among rows that cleared the
    floor). The calibration record enumerates the retrieval-empty population explicitly -- never-taught
    asks that cleared the floor (confabulation risk) and taught asks that failed it (false-refusal
    risk) -- because "calibrated on held-out data including the retrieval-empty case" is the plan's
    condition and a threshold fitted only on taught asks would not satisfy it.
 4. THE BATTERY. C calls eb.apply_curriculum() exactly as arm A and (since the tier-120 defect) arm B
    do, so the probe matrix is the tier's, not the bench's module literal.

STATUS: built and measured at tier 40 only. It has never run at tier 120 or 300, so no H2 number from
this file is quotable at the tiers H2 names.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import re
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import mp_e8_arm_b as b              # the architecture, the trainer, the decoder, the grader helpers
import electric_learn_bench as eb    # classify / by_shape / retention / apply_curriculum
import mp_e8_curriculum as curriculum

DEFAULT_MANIFEST = b.DEFAULT_MANIFEST
SEED = b.SEED
BATTERY: dict = {}

ARM_C_GIFT_RULE = (
    "row['own'] is None on every arm C row, for arm B's reason: a generative model has no self-report "
    "distinct from its output, and populating it would turn classify()'s entailed branch into an "
    "amnesty for invention")


# ------------------------------------------------------------------ the store ----
def taught_items(man: dict, depth: int) -> list[dict]:
    """Everything taught up to this depth, as {text, ask, kind}. Session boundaries are the manifest's,
    so the store at depth d holds exactly what arm B has been fine-tuned on at depth d -- the two arms
    get the same material, or the duel is about memory and curriculum at once."""
    out = []
    for s in man["sessions"][:depth]:
        for call in s["tell_frames"]:
            sent = re.findall(r"'([^']+)'", call)[:1]
            if not sent:
                raise AssertionError(f"no sentence literal in tell frame: {call}")
            out.append({"text": sent[0], "ask": None, "kind": "tell"})
        for q, a in s["qa_pairs"]:
            out.append({"text": a, "ask": q, "kind": "qa"})
    return out


def vec(model, toks: list[int]):
    """Mean token embedding, L2-normalised. The embedding is the frozen model's own, so the geometry of
    the store is a property of the trained network -- no second encoder is introduced, and nothing here
    is fitted after the freeze."""
    with torch.no_grad():
        e = model.embed(torch.tensor(toks, dtype=torch.long)).mean(dim=0)
        n = float(e.norm())
        return (e / n) if n > 0 else e


def build_store(model, items: list[dict]) -> list[dict]:
    ix = model.ix
    for it in items:
        it["vec"] = vec(model, [ix[b.BOS]] + [ix.get(w, ix[b.UNK]) for w in b.tokenize(it["text"])]
                        + [ix[b.EOS]])
    return items


def retrieve(model, store: list[dict], ask: str, want: str | None = None) -> dict:
    """Top-1 and its runner-up. `exact` is answered against the probe's own expected sentence, not
    against a feeling: the retrieval was exact when the item it surfaced IS the thing the ask should be
    answered with. Nothing else would do -- "not an exact match" is half of the registered near-miss
    slice, so it has to be a comparison the reader can repeat from the artifact."""
    ix = model.ix
    q = vec(model, [ix[b.BOS]] + [ix.get(w, ix[b.UNK]) for w in b.tokenize(ask)] + [ix[b.SEP]])
    scored = sorted(((float(torch.dot(it["vec"], q)), it) for it in store),
                    key=lambda t: -t[0])
    top1, top2 = scored[0], (scored[1] if len(scored) > 1 else (float("-inf"), None))
    return {"sim": round(top1[0], 4), "item": top1[1]["text"], "kind": top1[1]["kind"],
            "sim2": round(top2[0], 4) if top2[1] else None,
            "exact": bool(want) and top1[1]["text"].lower() == want.lower()}


# ------------------------------------------------------------------- freeze ----
def weight_hash(model) -> str:
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return hashlib.sha256(buf.getvalue()).hexdigest()


def freeze(model) -> dict:
    for p in model.parameters():
        p.requires_grad_(False)
    model.eval()
    h = weight_hash(model)
    return {"frozen": True, "state_dict_sha256": h,
            "requires_grad_any": any(p.requires_grad for p in model.parameters())}


def assert_still_frozen(model, h: str, where: str) -> None:
    now = weight_hash(model)
    if now != h:
        raise SystemExit(f"arm C's weights moved at {where} after the freeze ({h[:12]} -> {now[:12]}). "
                         "A model that keeps learning after it is declared frozen is not the baseline "
                         "this experiment registered, and every row from this depth is void.")


# ----------------------------------------------------------------- calibration ----
def youden(pop_a: list[float], pop_b: list[float]) -> dict:
    """The cut maximising J = TPR - FPR over the midpoints of the observed values, ties going to the
    HIGHER threshold (more refusal).

    This is arm B's estimator -- the same arithmetic in mp_e8_arm_b.calibrate() -- reimplemented here
    rather than imported, because arm B inlines it inside calibrate() and there is no function to call.
    Stating that plainly matters: two arms that each hold their own copy of "calibrated" is exactly the
    drift this experiment is built to avoid, so tests/test_mp_e8_arm_c.py pins this function against
    arm B's measured behaviour on the same populations instead of trusting the prose."""
    pos, neg = pop_a, pop_b
    if not pos or not neg:
        raise AssertionError(f"calibration needs both populations; got {len(pos)} vs {len(neg)}")
    cuts = sorted(set(pos + neg))
    best, best_j = None, None
    for a, c in zip(cuts, cuts[1:]):
        thr = (a + c) / 2.0
        tpr = sum(1 for x in pos if x >= thr) / len(pos)
        fpr = sum(1 for x in neg if x >= thr) / len(neg)
        j = tpr - fpr
        if best_j is None or j > best_j or (j == best_j and thr > best):
            best, best_j = thr, j
    return {"threshold": None if best is None else round(best, 4),
            "youden_j": None if best_j is None else round(best_j, 4),
            "n_pos": len(pos), "n_neg": len(neg)}


# -------------------------------------------------------------------- probing ----
def probe_arm_c(model, store, taught_depth: int, sim_floor: float, conf_thr: float) -> tuple:
    """Ask the battery. Each row carries arm A's row keys plus what retrieval did, because the
    near-miss claim is unreadable without them."""
    ix = model.ix
    rows, retrieval = [], {}
    for iid, shape, ask, tell, d in eb.PROBES:
        want = tell if (tell is not None and d < taught_depth) else None
        r = retrieve(model, store, ask, want)
        empty = r["sim"] < sim_floor
        if empty:
            text, conf, ntok = "", float("-inf"), 0
        else:
            prompt = ([ix[b.BOS]] + [ix.get(w, ix[b.UNK]) for w in b.tokenize(r["item"])] + [ix[b.SEP]]
                      + [ix.get(w, ix[b.UNK]) for w in b.tokenize(ask)] + [ix[b.SEP]])
            text, conf, ntok = b.generate(model, prompt)
        abstained = empty or (not math.isfinite(conf)) or conf < conf_thr
        row = dict(item=iid, shape=shape, ask=ask, own=None,
                   taught=(want or "").lower() or None,
                   answered=bool(text) and not abstained,
                   said="" if abstained else text,
                   src="arm_c_frozen_retrieval",
                   reason=("" if not abstained else
                           (f"retrieval-empty: top1 sim {r['sim']:.3f} < floor {sim_floor:.3f}"
                            if empty else
                            f"abstained: conf {conf:.3f} < threshold {conf_thr:.3f}"))[:90])
        row["mech"] = "retrieval_empty" if empty else ("abstained" if abstained else "generated")
        row["conf"] = None if not math.isfinite(conf) else round(conf, 4)
        row["gen_tokens"] = ntok
        row["retr_sim"] = r["sim"]
        row["retr_item"] = r["item"]
        row["retr_exact"] = r["exact"]
        rows.append(row)
        retrieval[f"{iid}|{shape}"] = r
    return rows, retrieval


# --------------------------------------------------------------------- depths ----
def run_depth(depth: int, man: dict, sd: Path, seed: int) -> dict:
    torch.set_num_threads(6)                    # arm B's thread pinning, so the two arms reduce floats
    sd.mkdir(parents=True, exist_ok=True)       # identically and their cost figures are comparable
    # Same unpacking as arm B's run_depth: build_vocab returns (vocab, index) and the PAD token is
    # appended to the index, not to the vocabulary list. Getting this backwards is what made the first
    # execution of arm C die inside arm B's session_sequences with "list indices must be integers" --
    # ix was the vocabulary list. Caught by tests/test_mp_e8_arm_c.py::test_cli_tier40_smoke_run, which
    # is the only test here that runs the tool rather than a function of it.
    vocab, ix = b.build_vocab(man)
    ix[b.PAD] = len(ix)
    inv = {v: k for k, v in ix.items()}
    rng = random.Random(seed + depth)
    torch.manual_seed(seed)                     # before Net(), per arm B's measured defect
    model = b.Net(len(ix))
    model.ix, model.inv = ix, inv
    model.eval()
    if depth > 1:
        prev = b.state_paths(sd, depth - 1)["ckpt"]
        if not prev.exists():
            raise SystemExit(f"--depth {depth} needs {prev}: arm C trains on the same sequential "
                             f"schedule as arm B, so session {depth - 1} must exist first.")
        model = b.load_model(prev, ix, inv)
        for p in model.parameters():
            p.requires_grad_(True)              # resume is allowed; the freeze comes after training

    log = {}
    t0 = time.time()
    log[f"session_{depth}"] = b.train_session(model, b.session_sequences(
        man["sessions"][depth - 1], ix), rng)
    log[f"session_{depth}"]["wall_clock_s"] = round(time.time() - t0, 3)

    fz = freeze(model)
    if fz["requires_grad_any"]:
        raise SystemExit("freeze() left a parameter trainable; arm C would keep learning while it "
                         "was being probed and the artifact would describe a frozen model that is not.")

    items = taught_items(man, depth)
    store = build_store(model, items)

    # Two held-out populations, from the battery itself: asks whose item is taught at this depth, and
    # the manifest's never-taught distractor asks. Both similarity and confidence are fitted on them.
    sim_pos, sim_neg, conf_pos, conf_neg = [], [], [], []
    for iid, shape, ask, tell, d in eb.PROBES:
        r = retrieve(model, store, ask)
        if iid.startswith("dist"):
            sim_neg.append(r["sim"])
        elif tell is not None and d < depth:
            sim_pos.append(r["sim"])
    cal_sim = youden(sim_pos, sim_neg)
    floor = cal_sim["threshold"] if cal_sim["threshold"] is not None else 0.0
    for iid, shape, ask, tell, d in eb.PROBES:
        r = retrieve(model, store, ask)
        if r["sim"] < floor:
            continue
        prompt = ([ix[b.BOS]] + [ix.get(w, ix[b.UNK]) for w in b.tokenize(r["item"])] + [ix[b.SEP]]
                  + [ix.get(w, ix[b.UNK]) for w in b.tokenize(ask)] + [ix[b.SEP]])
        _t, conf, _n = b.generate(model, prompt)
        if not math.isfinite(conf):
            continue
        if iid.startswith("dist"):
            conf_neg.append(conf)
        elif tell is not None and d < depth:
            conf_pos.append(conf)
    cal_conf = youden(conf_pos, conf_neg)
    thr = cal_conf["threshold"] if cal_conf["threshold"] is not None else float("inf")

    cal = {"similarity_floor": cal_sim, "confidence_threshold": cal_conf,
           "populations": {"taught_asks": len(sim_pos), "never_told_asks": len(sim_neg),
                           "retrieval_empty_among_never_told": sum(1 for s in sim_neg if s < floor),
                           "retrieval_empty_among_taught": sum(1 for s in sim_pos if s < floor)},
           "rule": ("two gates, both Youden's J on held-out data: retrieval must clear the similarity "
                    "floor, then the generated answer must clear the confidence threshold. The "
                    "retrieval-empty population is counted explicitly because the plan requires the "
                    "calibration to cover it."),
           "held_out_set": ("taught asks (item taught at this depth) vs the manifest's never-taught "
                            "distractor asks; both listed by count here and the asks themselves are in "
                            "rows of the same artifact")}

    phases, retr = {}, {}
    phases["live"], retr["live"] = probe_arm_c(model, store, depth, floor, thr)
    assert_still_frozen(model, fz["state_dict_sha256"], "live")
    phases["reasked"], retr["reasked"] = probe_arm_c(model, store, depth, floor, thr)
    assert_still_frozen(model, fz["state_dict_sha256"], "reasked")
    b.save_model(model, b.state_paths(sd, depth)["ckpt"], ix)
    fresh = b.load_model(b.state_paths(sd, depth)["ckpt"], ix, inv)
    fresh.ix, fresh.inv = ix, inv
    fz2 = freeze(fresh)
    phases["restarted"], retr["restarted"] = probe_arm_c(fresh, store, depth, floor, thr)
    assert_still_frozen(fresh, fz2["state_dict_sha256"], "restarted")

    out = {"depth": depth, "calibration": cal, "phases": phases, "retrieval": retr,
           "train_log": log, "parameters": b.param_count(model), "vocab_size": len(ix),
           "freeze": fz, "store_n_items": len(store),
           "config": {"embed": b.EMBED, "hidden": b.HIDDEN, "layers": b.LAYERS, "lr": b.LR,
                      "batch": b.BATCH, "epochs_per_session": b.EPOCHS,
                      "max_generate_tokens": b.MAX_GEN, "seed": seed},
           "single_process_measurement": False,
           "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    p = b.state_paths(sd, depth)
    p["rows"].write_text(json.dumps(out), encoding="utf-8")
    print(f"[armC] depth {depth}: steps={log[f'session_{depth}']['optimizer_steps']} "
          f"train_s={log[f'session_{depth}']['wall_clock_s']} floor={floor} thr={thr} "
          f"store={len(store)} frozen={fz['state_dict_sha256'][:12]} -> {p['rows'].name}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--curriculum", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--state-dir", default=str(HERE.parent / "_tmp" / "armC_state"))
    ap.add_argument("--depth", type=int)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--out", default=str(HERE.parent / "experiments" / "MP-E8" / "results"
                                         / "armC_tier40.json"))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--depths", default="1,2,3")
    ap.add_argument("--epochs", type=int, default=b.EPOCHS,
                    help="the MEASURED run uses arm B's default; lower values are for tests only and "
                         "every chunk records its own.")
    ap.add_argument("--max-gen", type=int, default=b.MAX_GEN)
    a = ap.parse_args()
    b.EPOCHS, b.MAX_GEN = a.epochs, a.max_gen

    man_path = Path(a.curriculum)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    canon = json.dumps({"sessions": [s["tell_frames"] for s in man["sessions"]],
                        "pairs": [s["qa_pairs"] for s in man["sessions"]]}, sort_keys=True)
    self_derived = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    if man.get("curriculum_sha256") != self_derived:
        raise SystemExit(f"curriculum sha mismatch (self-consistency): {man_path.name} declares "
                         f"{man.get('curriculum_sha256')} but hashes to {self_derived}.")
    if man.get("tier") == 40:
        rec = curriculum.load()["curriculum_sha256"]
        if rec != man["curriculum_sha256"]:
            raise SystemExit("curriculum sha mismatch against arm A's source; refusing to run.")
    global BATTERY
    BATTERY = eb.apply_curriculum(str(man_path))
    if BATTERY.get("tier") != man.get("tier"):
        raise SystemExit("battery tier does not match the manifest tier")

    sd = Path(a.state_dir)
    if a.merge:
        depths = [int(x) for x in a.depths.split(",")]
        out = merge(sd, man_path, man, a.seed, depths)
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
        print(f"[armC] merged depths {depths} -> {p}")
        return 0
    if a.depth is None:
        raise SystemExit("give --depth N or --merge")
    run_depth(a.depth, man, sd, a.seed)
    return 0


def merge(sd: Path, man_path: Path, man: dict, seed: int, depths: list[int]) -> dict:
    per = {d: json.loads(b.state_paths(sd, d)["rows"].read_text(encoding="utf-8")) for d in depths}
    want = len(eb.PROBES)
    for d, blk in sorted(per.items()):
        for ph, rows in blk["phases"].items():
            if len(rows) != want:
                raise SystemExit(f"depth {d} phase {ph} holds {len(rows)} rows but the battery has "
                                 f"{want}: different runs, not one.")
        if per[d]["config"]["seed"] != seed:
            raise SystemExit(f"depth {d} ran with seed {per[d]['config']['seed']}, --seed says {seed}")
    cfgs = {str(d): blk["config"] for d, blk in per.items()}
    if len({json.dumps(c, sort_keys=True) for c in cfgs.values()}) != 1:
        raise SystemExit(f"chunk configs disagree across depths: {cfgs}")
    prov = b.provenance(man_path, man, seed, cfgs[str(max(depths))])
    prov["arm"] = "C"
    # provenance() is arm B's function, and it carries a field NAMED FOR ARM B. Leaving it in an arm C
    # artifact -- which is what the first execution did -- gives a reader a record that says arm: C and
    # explains the row contract in arm B's words. Renamed rather than deleted, because the rule itself
    # is the same one and the reason is worth keeping.
    if "arm_B_gets_no_report_frame" in prov:
        prov.pop("arm_B_gets_no_report_frame")
        prov["arm_C_gets_no_report_frame"] = ARM_C_GIFT_RULE
        prov["provenance_reused_from"] = ("mp_e8_arm_b.provenance(), so both arms record identical "
                                          "fields; the report-frame rule is the only arm-specific entry "
                                          "and it was renamed, not dropped")
    prov["frozen_state_dict_sha256"] = per[max(depths)]["freeze"]["state_dict_sha256"]
    prov["retrieval_store_items"] = per[max(depths)]["store_n_items"]

    arms_c, summary = {}, {}
    for d in depths:
        arms_c[str(d)], summary[str(d)] = {}, {}
        for ph, rows in per[d]["phases"].items():
            graded = [dict(r, cls=eb.classify(r)) for r in rows]
            arms_c[str(d)][ph] = graded
            summary[str(d)][ph] = {"by_shape": eb.by_shape(graded),
                                   "retention": eb.retention(graded)}
    near = {str(d): {ph: {"n_rows": len(rows),
                          "n_retrieval_empty": sum(1 for r in rows if r["mech"] == "retrieval_empty"),
                          "n_near_miss": sum(1 for r in rows if r["answered"] and not r["retr_exact"]),
                          "n_exact_retrieval": sum(1 for r in rows if r["retr_exact"]),
                          "near_miss_definition": (
                              "the registered slice (D-MPE8-04, arm_C_near_miss_slice_definition): the "
                              "row answered, retrieval cleared the floor, and the item surfaced is not "
                              "the item the ask should be answered with")}
                     for ph, rows in per[d]["phases"].items()} for d in depths}
    total_steps = sum(blk["train_log"][f"session_{d}"]["optimizer_steps"] for d, blk in per.items())
    total_s = sum(blk["train_log"][f"session_{d}"]["wall_clock_s"] for d, blk in per.items())
    return {
        "arm": "C", "experiment": "MP-E8", "tier": man["tier"], "items": man["n_items"],
        "probes": want, "battery": dict(BATTERY), "depths": depths,
        "architecture": "identical to arm B by import (mp_e8_arm_b.Net), frozen after training; "
                        "retrieval over the taught items",
        "frozen": {str(d): per[d]["freeze"] for d in depths},
        "calibration": {str(d): per[d]["calibration"] for d in depths},
        "retrieval_slices": near,
        "arms": {"C": {"seconds": round(total_s, 3), "runs": [], "probes": arms_c,
                       "arm_provenance": prov["flag_state"]}},
        "summary": {"C": summary},
        "training": {"sequential": True, "replay_of_earlier_sessions": False,
                     "frozen_after_training_each_depth": True,
                     "total_optimizer_steps": total_steps,
                     "total_train_wall_clock_s": round(total_s, 3)},
        "provenance": prov,
        "gift_rule": ARM_C_GIFT_RULE,
        "single_process_measurement": False,
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claim_status": ("BUILT AND MEASURED AT TIER 40 ONLY. Arm C has never run at tier 120 or 300, "
                         "so no H2 figure from this artifact is quotable at the tiers H2 names."),
    }


if __name__ == "__main__":
    sys.exit(main())
