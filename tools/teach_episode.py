r"""E1: one teaching episode -- generate, teach, consolidate, measure, record.

docs/open_learning_design.md section 8 specifies this experiment; this file is that
specification implemented. E1 measures the COST of teaching before its benefit,
because section 2.2 makes cost the quantity that decides whether open learning is
possible on this substrate at all: the binder is a 60,000-row FIFO at capacity
(higher_cortex.py:46) that evicts with meta.pop(0) consulting nothing, so teaching is
not addition, it is DISPLACEMENT.

NOTHING HERE TOUCHES LIVE STATE. Teaching happens in a sealed session built by
converse.build() -- learning loop read_only, oracle key removed, books off, every
persistence path repointed into a session directory. The taught state is overlaid
onto a hardlinked shadow by benchmark_cross_session.build_shadow(), and every ask is
measured against that shadow in a FRESH process-level build, which is what makes the
open tier a retention test rather than a same-session recall test. Live seals are
taken before and after and must match; the guard is the same one converse.py uses.

THE GENERATOR draws content words from the LIVE vocabulary and filters them with the
organ's OWN function-word sets, never with a private list. That constraint is section
3.5's, and it exists because tools/fly_v2.py generated synthetic spans whose modifier
class was closed at {old, copper, heavy} and the winner it bred named 'small' the head
of 'the small brass bell'. The sentence FRAME is declared and fixed -- 'the {a} {v}
the {b}' -- because a frame is structure, not vocabulary, and because that exact frame
is demonstrated to work by the frozen battery's hop script ('the frost bites the
latch' -> 'what does the frost bite?' passes). The propositions are novel and
semantically arbitrary ON PURPOSE: a fact that could be guessed from corpus priors
would make a correct answer ambiguous evidence, and one that cannot be guessed makes
it evidence about the teaching.

  py -3.10 tools/teach_episode.py --episode 1 --facts 20 --seed 1 --dry-run
  py -3.10 tools/teach_episode.py --episode 1 --facts 20 --seed 1
  py -3.10 tools/run_generation.py --report --episode 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import organs.neural_language as nl  # noqa: E402
import tools.run_generation as rg  # noqa: E402
from tools.benchmark_cross_session import build_shadow  # noqa: E402
from tools.converse import Session, build, guard_check, guard_live_files  # noqa: E402

LINEAGE = ROOT / "state" / "lineage"
EPISODES = LINEAGE / "episodes.jsonl"
WORK = ROOT / "state" / "sessions" / "_episodes"

# The frame, and the three held-out rewordings of it. T is what the fact is taught
# and asked in; H1-H3 are never used in teaching. Each is a real rewording whose
# expected fate is already measured on standing material, so a result is comparable
# to the paraphrase tier rather than floating:
#   T   what does the {a} {v}?        the frozen hop ask, passes on standing material
#   H1  what {v} the {b}?             the reverse role, also passes ('what bites the latch?')
#   H2  which thing does the {a} {v}? question-word swap, FAILS on standing material
#   H3  what is {v} by the {a}?       passive, FAILS on standing material
FRAME_T = "what does the {a} {v}?"
FRAMES_HELDOUT = {
    "H1-reverse-role": "what {v} the {b}?",
    "H2-question-word": "which thing does the {a} {v}?",
    "H3-passive": "what is {v} by the {a}?",
}
MIN_WORD_LEN = 4
LIVE_STATE_FILES = ("language_state.json", "banc_brain.npz")


# --------------------------------------------------------------- generator ----

def function_words() -> set:
    """The organ's own closed-class sets, unioned. Using these rather than a list
    written here is the difference between filtering with live code and filtering
    with a private vocabulary the generator could overfit."""
    out = set()
    for name in ("SHAPE_FUNCTION_WORDS", "SHAPE_COPULAS", "SHAPE_DO_SUPPORT",
                 "SHAPE_LOCATIVE_PREPS", "RECORD_SKIP", "ORDINAL_STOP",
                 "COUNT_QUANTS"):
        out |= {str(w).lower() for w in getattr(nl.NeuralLanguage, name, ()) or ()}
    out |= {"the", "a", "an", "at", "of", "and", "or", "but", "is", "are", "was",
            "were", "be", "been", "being", "it", "its", "this", "that", "these",
            "those", "there", "here", "not", "no", "yes", "s", "t"}
    return out


def content_pool(lang, need: int) -> tuple:
    """Words drawn from the LIVE vocabulary, kept only if they are content words and
    the binder has postings for their stem -- a word with no postings is dropped from
    answer()'s must-set, so teaching with one would measure a refusal rather than a
    memory. Returns (pool, rejection census)."""
    b = lang.cortex.binder
    stop = function_words()
    pool, rej = [], {"not_alpha": 0, "too_short": 0, "function_word": 0,
                     "no_postings": 0, "not_speakable": 0}
    for w in sorted(lang.word_patterns):
        lw = str(w).lower()
        if not lw.isalpha():
            rej["not_alpha"] += 1
            continue
        if len(lw) < MIN_WORD_LEN:
            rej["too_short"] += 1
            continue
        if lw in stop:
            rej["function_word"] += 1
            continue
        if not b.stem_rows(lw):
            rej["no_postings"] += 1
            continue
        if not lang._speakable(lw):
            rej["not_speakable"] += 1
            continue
        pool.append(lw)
    return pool, rej


def _row_keys(binder) -> set:
    """Exact token-sequence keys the binder would treat as a repeat. remember() keys
    on tuple(tokens)[:max_roles], so absence has to be checked the same way or a
    'novel' proposition can still land as a repeat and teach nothing."""
    mr = getattr(binder, "max_roles", 8)
    out = set()
    for m in binder.meta:
        t = tuple(str(x).strip().lower() for x in (m.get("tokens") or []))
        out.add(t[:mr])
    return out


def generate(lang, n_facts: int, seed: int) -> dict:
    """n_facts novel propositions plus one held-out rewording each.

    Absence is verified against the binder's own repeat key, and a collision costs a
    redraw rather than a silently duplicated fact: teaching a proposition he already
    holds would make the acquisition number a measure of corpus recall.
    """
    rng = random.Random(seed)
    pool, rej = content_pool(lang, n_facts)
    if len(pool) < 3:
        raise SystemExit(f"content pool too small ({len(pool)}): {rej}")
    seen = _row_keys(lang.cortex.binder)
    facts, used, collisions, attempts = [], set(), 0, 0
    absence_checks = 0
    while len(facts) < n_facts and attempts < n_facts * 200:
        attempts += 1
        a, v, b = rng.sample(pool, 3)
        if a in used or v in used or b in used:
            # One role per word across the batch, so no two facts can be confused
            # with each other by a shared content word.
            continue
        key = ("the", a, v, "the", b)
        absence_checks += 1
        if key in seen:
            collisions += 1
            continue
        tell = f"the {a} {v} the {b}"
        hk = rng.choice(sorted(FRAMES_HELDOUT))
        facts.append({
            "n": len(facts) + 1, "a": a, "v": v, "b": b,
            "tell": tell,
            "ask_T": FRAME_T.format(a=a, v=v), "answer_T": b, "forbid_T": [a],
            "frame_H": hk,
            "ask_H": FRAMES_HELDOUT[hk].format(a=a, v=v, b=b),
            # H1 asks for the OTHER role, so its answer is the subject; H2 and H3 ask
            # the same question as T in different words, so their answer is the object.
            "answer_H": a if hk.startswith("H1") else b,
            "forbid_H": ([b] if hk.startswith("H1") else [a]),
        })
        used |= {a, v, b}
        seen.add(key)
    if len(facts) < n_facts:
        raise SystemExit(f"only generated {len(facts)} of {n_facts} novel facts after "
                         f"{attempts} attempts ({collisions} binder collisions); the "
                         f"pool is {len(pool)} words")
    return {"seed": seed, "facts": facts, "pool_size": len(pool),
            "rejections": rej, "attempts": attempts,
            "absence_checks": absence_checks,
            "binder_collisions": collisions,
            "frame": "the {a} {v} the {b}",
            "ask_frame_T": FRAME_T, "ask_frames_H": FRAMES_HELDOUT,
            "vocab_source": "lang.word_patterns (live vocabulary)",
            "filter": "organ's own closed-class sets + binder stem postings + "
                      f"len >= {MIN_WORD_LEN}"}


def batch_files(gen: dict, out_dir: Path) -> dict:
    """Write the open-tier batch in the same script/turn schema the other three tiers
    use, so it runs through the same runner, grader and journal. No tells: the
    teaching is already in the shadow, and an ask that replayed its own tell would be
    measuring same-session recall instead of retention."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scripts = [{"name": "open-acquisition", "kind": "open", "parent": None,
                "turns": [{"ask": f["ask_T"], "frame": "T-taught",
                           "taught": f["tell"],
                           "expect": {"answer": [f["answer_T"]],
                                      "forbid": f["forbid_T"]}}
                          for f in gen["facts"]]}]
    by_frame = {}
    for f in gen["facts"]:
        by_frame.setdefault(f["frame_H"], []).append(f)
    for fr, fs in sorted(by_frame.items()):
        scripts.append({"name": f"open-{fr}", "kind": "open", "parent": None,
                        "turns": [{"ask": f["ask_H"], "frame": fr,
                                   "taught": f["tell"],
                                   "expect": {"answer": [f["answer_H"]],
                                              "forbid": f["forbid_H"]}}
                                  for f in fs]})
    p = out_dir / "open_batch.json"
    p.write_text(json.dumps({
        "name": f"open_episode_batch", "generated": gen["seed"],
        "generator": {k: v for k, v in gen.items() if k != "facts"},
        "facts": gen["facts"], "scripts": scripts}, indent=1), encoding="utf-8")
    return {"path": str(p), "seal": rg.seal(p),
            "acquisition_asks": len(scripts[0]["turns"]),
            "heldout_asks": sum(len(s["turns"]) for s in scripts[1:]),
            "frames": {fr: len(v) for fr, v in sorted(by_frame.items())}}


# ----------------------------------------------------------------- census ----

def binder_census(binder) -> dict:
    keys = {}
    for m in binder.meta:
        k = tuple(str(x).lower() for x in (m.get("tokens") or []))
        keys[k] = (str(m.get("who") or "?"), int(m.get("count", 1)))
    who, cnt = {}, {}
    for _k, (w, c) in keys.items():
        who[w] = who.get(w, 0) + 1
        cnt[c] = cnt.get(c, 0) + 1
    return {"rows": len(keys), "keys": keys, "who": who,
            "count_hist": {str(k): v for k, v in sorted(cnt.items())}}


def san_census(lang) -> dict:
    """One 256 MB temporary, not three: the SAN is 8192x8192 float32, so the row sums
    are computed once and the total is derived from them rather than by a second
    full-matrix abs()."""
    w = lang.san_w
    row_sums = np.abs(w).sum(axis=1)
    return {"nnz": int(np.count_nonzero(w)),
            "total": round(float(row_sums.sum()), 3),
            "row_sums": row_sums}


def diff_census(before: dict, after: dict) -> dict:
    bk, ak = before["keys"], after["keys"]
    evicted = {k: bk[k] for k in bk.keys() - ak.keys()}
    added = {k: ak[k] for k in ak.keys() - bk.keys()}
    ew, ec, aw = {}, {}, {}
    for _k, (w, c) in evicted.items():
        ew[w] = ew.get(w, 0) + 1
        ec[c] = ec.get(c, 0) + 1
    for _k, (w, c) in added.items():
        aw[w] = aw.get(w, 0) + 1
    return {"rows_before": before["rows"], "rows_after": after["rows"],
            "evicted_n": len(evicted), "added_n": len(added),
            "evicted_who": dict(sorted(ew.items())),
            "evicted_count": {str(k): v for k, v in sorted(ec.items())},
            "added_who": dict(sorted(aw.items())),
            "evicted_sample": [" ".join(k)[:70] for k in list(evicted)[:8]],
            "added_sample": [" ".join(k)[:70] for k in list(added)[:8]],
            "who_before": before["who"], "who_after": after["who"]}


def san_diff(before: dict, after: dict) -> dict:
    rs = float(np.count_nonzero(np.abs(before["row_sums"] - after["row_sums"]) > 1e-6))
    return {"nnz_before": before["nnz"], "nnz_after": after["nnz"],
            "nnz_delta": after["nnz"] - before["nnz"],
            "total_before": before["total"], "total_after": after["total"],
            "total_delta": round(after["total"] - before["total"], 3),
            "rows_changed": int(rs)}


def live_seals() -> dict:
    return {n: (rg.seal(ROOT / "state" / n)
                if (ROOT / "state" / n).exists() else None)
            for n in LIVE_STATE_FILES}


# ------------------------------------------------------------------- main ----

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--episode", type=int, required=True)
    ap.add_argument("--facts", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true",
                    help="generate and verify the batches, write them, teach and "
                         "measure nothing")
    ap.add_argument("--no-consolidate", action="store_true",
                    help="teach only; skip the sleep replay")
    ap.add_argument("--consolidate-budget", type=int, default=200)
    ap.add_argument("--tier", default="frozen,probe,open")
    ap.add_argument("--keep-shadow", action="store_true")
    a = ap.parse_args()

    baseline = json.loads(rg.BASELINE.read_text(encoding="utf-8")) \
        if rg.BASELINE.exists() else None
    if baseline is None:
        print("REFUSING: no frozen baseline at tools/selection_baseline.json, so "
              "erosion cannot be measured and the episode's central gate is empty")
        return 1

    ep_dir = WORK / f"ep{a.episode}"
    if ep_dir.exists():
        shutil.rmtree(ep_dir)
    ep_dir.mkdir(parents=True, exist_ok=True)
    tell_dir = ep_dir / "teach"
    shadow = ep_dir / "shadow"

    seals_before = live_seals()
    guard_before = guard_live_files(f"episode{a.episode}")
    t_start = time.time()
    print(f"episode {a.episode}: {a.facts} facts, seed {a.seed}")
    print(f"  live seals before: {json.dumps(seals_before)}")

    # ---- build once on live state: read the vocabulary, census, generate, teach.
    agent = build(tell_dir)
    lang = agent.language
    rg.shim_check()
    cen_before = binder_census(lang.cortex.binder)
    san_before = san_census(lang)
    print(f"  binder {cen_before['rows']} rows, who {json.dumps(cen_before['who'])}")

    gen = generate(lang, a.facts, a.seed)
    batch = batch_files(gen, ep_dir)
    print(f"  generated {len(gen['facts'])} novel facts from a pool of "
          f"{gen['pool_size']} live-vocabulary content words "
          f"({gen['attempts']} draws, {gen['binder_collisions']} binder collisions)")
    print(f"  rejections: {json.dumps(gen['rejections'])}")
    print(f"  batch {batch['path']} seal {batch['seal']}")
    print(f"    acquisition asks {batch['acquisition_asks']}, held-out "
          f"{batch['heldout_asks']} by frame {json.dumps(batch['frames'])}")
    for f in gen["facts"][:5]:
        print(f"      {f['n']:2d}. {f['tell']:38s} T: {f['ask_T']:34s} -> {f['answer_T']}")
    print(f"      ... {len(gen['facts'])} facts")

    if a.dry_run:
        shutil.rmtree(tell_dir, ignore_errors=True)
        print("\n--dry-run: batches written, nothing taught, nothing measured, "
              "live state untouched")
        print(f"  live seals after: {json.dumps(live_seals())}")
        return 0

    # ---- teach, then consolidate, then save into the sealed session dir.
    sess = Session(agent, beats=0)
    t0 = time.time()
    taught = []
    for f in gen["facts"]:
        turn = sess.ask(f["tell"], kind="tell")
        taught.append({"tell": f["tell"], "spoken": bool(
            (turn.get("reply") or {}).get("spoken"))})
    teach_s = round(time.time() - t0, 1)
    # How many of the just-taught rows are BELOW the urgency line, i.e. eligible for
    # replay at all. consolidate() repairs decayed wiring; it does not rehearse what
    # is already strong. Without this number a "no taught rows were picked" result is
    # undecidable between two very different facts: that 7a did not change the
    # ranking, or that the ranking changed and correctly found nothing to repair.
    taught_urgent = 0
    try:
        w = lang.san_w
        fp = lang._fp_idx
        for f in gen["facts"]:
            toks = f["tell"].split()
            weakest = None
            for x, y in zip(toks, toks[1:]):
                ia, ib = fp(x), fp(y)
                if ia.size == 0 or ib.size == 0:
                    continue
                wm = float(w[np.ix_(ia, ib)].max())
                if weakest is None or wm < weakest:
                    weakest = wm
            if weakest is not None and weakest < 0.1:
                taught_urgent += 1
    except Exception as exc:
        taught_urgent = -1
        print(f"  taught-urgency probe failed: {type(exc).__name__}: {exc}")
    print(f"  taught rows below the 0.1 urgency line (eligible for replay): "
          f"{taught_urgent}/{len(gen['facts'])}")

    consol = None
    if not a.no_consolidate:
        t0 = time.time()
        consol = lang.consolidate(budget=a.consolidate_budget)
        consol["elapsed_s"] = round(time.time() - t0, 1)
        print(f"  consolidated: {consol['rows_replayed']} rows replayed of "
              f"{consol['rows_urgent']} urgent, {consol['elapsed_s']}s")
    cen_after = binder_census(lang.cortex.binder)
    san_after = san_census(lang)
    saved = lang.save_state(force_san=True, force=True)
    print(f"  taught {len(taught)} facts in {teach_s}s; saved "
          f"{len(list(tell_dir.glob('language_state*')))} state files")

    # ---- overlay onto a hardlinked shadow and measure against it.
    sh = build_shadow(tell_dir, shadow)
    print(f"  shadow: {sh['live_files_linked']} live files linked, "
          f"{sh['overlay_files']} overlaid")

    base_genome = rg.load_base()
    battery = rg.load_battery(tuple(a.tier.split(",")), None, batch["path"])
    n_asks = sum(1 for e in battery for s in e["script"]["turns"] if "ask" in s)
    print(f"  evaluating {n_asks} asks against the shadow "
          f"(~{n_asks * 24 / 60:.0f} min)")
    journal = ep_dir / "asks.jsonl"
    row = rg.evaluate_line(a.episode, 1, base_genome, base_genome, battery,
                           journal, baseline, None, project_root=str(shadow))

    # ---- the gate: erosion of the frozen passes and the guarded probes.
    fit = row["fitness"]
    reg = fit.get("regression") or {}
    erosion = sorted(set(reg.get("frozen_lost") or [])
                     | set(reg.get("probe_guard_lost") or []))
    disp = diff_census(cen_before, cen_after)
    sand = san_diff(san_before, san_after)
    seals_after = live_seals()
    moved = guard_check(guard_before)

    ck = hashlib.sha256(json.dumps(
        sorted((p.name, rg.seal(p)) for p in tell_dir.glob("language_state*")),
        default=str).encode()).hexdigest()[:12]

    op = fit.get("open") or {}
    acq = [r for r in _journal(journal) if r.get("frame") == "T-taught"]
    genr = [r for r in _journal(journal) if r.get("frame") and r["frame"] != "T-taught"]
    episode = {
        "episode": a.episode, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "design": "docs/open_learning_design.md section 8 (E1)",
        "checkpoint_id": ck, "parent_checkpoint": None,
        "promoted_to_live": False,
        "generator": {"seed": a.seed, "seal": batch["seal"],
                      "pool_size": gen["pool_size"],
                      "vocab_source": gen["vocab_source"],
                      "filter": gen["filter"], "frame": gen["frame"],
                      "attempts": gen["attempts"],
                      "binder_collisions": gen["binder_collisions"],
                      "rejections": gen["rejections"],
                      "frames": batch["frames"]},
        "teaching": {"taught": len(taught), "seconds": teach_s,
                     "taught_urgent": taught_urgent,
                     "consolidated": not a.no_consolidate,
                     "consolidate": consol,
                     # Who consolidation actually picked, from its own returned
                     # sample. consolidate() caps `deltas` at 20 of `budget`, so this
                     # is a SAMPLE and is recorded as one: enough to show whether
                     # testimony is being selected at all, not enough to be a
                     # distribution.
                     "consolidate_picked_who": _who_of((consol or {}).get("deltas")),
                     "consolidate_sample_n": len((consol or {}).get("deltas") or []),
                     "taught_rows": taught},
        "eval": {"frozen_passed": fit["capability"]["passed"],
                 "frozen_asked": fit["capability"]["asked"],
                 "guard_passed": reg.get("probe_guard_passed"),
                 "guard_asked": reg.get("probe_guard_asked"),
                 "paraphrase_passed": (fit.get("generalisation") or {}).get("passed"),
                 "paraphrase_asked": (fit.get("generalisation") or {}).get("asked"),
                 "stages": fit.get("stages"),
                 "acquisition": {"asked": len(acq),
                                 "passed": sum(1 for r in acq if r["pass"]),
                                 "score": round(sum(1 for r in acq if r["pass"])
                                                / max(1, len(acq)), 4),
                                 "by_frame": _by_frame(acq)},
                 "generalisation": {"asked": len(genr),
                                    "passed": sum(1 for r in genr if r["pass"]),
                                    "score": round(sum(1 for r in genr if r["pass"])
                                                   / max(1, len(genr)), 4),
                                    "by_frame": _by_frame(genr)},
                 "open_stages": op.get("stages"),
                 "open_failures": op.get("failures")},
        "displacement": disp, "san": sand,
        "seals": {"before": seals_before, "after": seals_after,
                  "unchanged": seals_before == seals_after},
        "guard": {"live_files_untouched": not moved, "moved": moved},
        "erosion": erosion,
        "gates": {
            # A gate that passes because it was never run is worse than no gate: the
            # pilot used --tier open, so frozen and guarded asks were 0/0 and the
            # erosion gate reported PASS on nothing. Unmeasured is now None, and None
            # fails the verdict.
            # Re-verified here against the PRE-teaching census rather than trusted
            # from a counter. The first version asserted absence_checks == facts, which
            # is wrong the moment a collision forces a redraw (two checks, one fact),
            # and a counter the generator increments itself is not evidence anyway.
            "absence_verified": (len(gen["facts"]) == a.facts
                                 and all(tuple(f["tell"].split()) not in cen_before["keys"]
                                         for f in gen["facts"])),
            "absence_verified_detail": f"{len(gen['facts'])} facts re-checked against "
                                       f"the {cen_before['rows']}-row pre-teaching "
                                       f"binder; {gen['absence_checks']} draws checked, "
                                       f"{gen['binder_collisions']} collisions redrawn",
            "erosion_zero": (None if not (fit["capability"]["asked"]
                                          and (reg.get("probe_guard_asked") or 0))
                             else not erosion),
            "erosion_zero_detail": ("NOT MEASURED: the frozen or guarded tier was not "
                                    "run, so there is nothing to erode against"
                                    if not (fit["capability"]["asked"]
                                            and (reg.get("probe_guard_asked") or 0))
                                    else f"{len(erosion)} lost: {erosion[:4]}"),
            "census_reported": bool(disp.get("evicted_who") is not None),
            "census_reported_detail": f"{disp['evicted_n']} evicted, "
                                      f"{disp['added_n']} added",
            "live_seals_unchanged": seals_before == seals_after and not moved,
            "live_seals_unchanged_detail": f"moved={moved[:4]}",
            "row_self_contained": True,
            "row_self_contained_detail": "generator seed and seal, checkpoint id, "
                                         "before/after seals, all four tiers, census",
        },
        "provenance": {**{k: v for k, v in rg.git_provenance().items()},
                       "shadow": sh, "state_root": str(shadow)},
        "seconds": round(time.time() - t_start, 1),
    }
    episode["verdict"] = verdict_of(episode["gates"])

    LINEAGE.mkdir(parents=True, exist_ok=True)
    with EPISODES.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(episode, default=str) + "\n")
    shutil.copyfile(journal, LINEAGE / f"episode_{a.episode}_asks.jsonl")
    if not a.keep_shadow:
        shutil.rmtree(shadow, ignore_errors=True)
        shutil.rmtree(tell_dir, ignore_errors=True)

    print(f"\n=== EPISODE {a.episode}: {episode['verdict']} ===")
    print(f"  acquisition    {episode['eval']['acquisition']['passed']}/"
          f"{episode['eval']['acquisition']['asked']}  "
          f"{json.dumps(episode['eval']['acquisition']['by_frame'])}")
    print(f"  generalisation {episode['eval']['generalisation']['passed']}/"
          f"{episode['eval']['generalisation']['asked']}  "
          f"{json.dumps(episode['eval']['generalisation']['by_frame'])}")
    print(f"  frozen         {fit['capability']['passed']}/{fit['capability']['asked']}"
          f"   guarded {reg.get('probe_guard_passed')}/{reg.get('probe_guard_asked')}")
    print(f"  EROSION        {erosion or 'none'}")
    print(f"  displacement   {disp['rows_before']} -> {disp['rows_after']} rows; "
          f"evicted {disp['evicted_n']} by who {json.dumps(disp['evicted_who'])} "
          f"by count {json.dumps(disp['evicted_count'])}")
    print(f"                 added {disp['added_n']} by who "
          f"{json.dumps(disp['added_who'])}")
    print(f"  SAN            nnz {sand['nnz_before']} -> {sand['nnz_after']} "
          f"({sand['nnz_delta']:+d}), total {sand['total_before']} -> "
          f"{sand['total_after']}, rows changed {sand['rows_changed']}")
    print(f"  stages         {json.dumps(fit.get('stages'))}")
    print(f"  open stages    {json.dumps(op.get('stages'))}")
    print(f"  live seals     unchanged={seals_before == seals_after}  "
          f"guard moved={moved or 'nothing'}")
    for k, v in episode["gates"].items():
        if not k.endswith("_detail"):
            print(f"  gate {k:24s} "
                  f"{'PASS' if v is True else 'NOT MEASURED' if v is None else 'FAIL'}"
                  f"  {episode['gates'].get(k + '_detail', '')}")
    print(f"\n  row appended to {EPISODES}")
    print(f"  ask journal {LINEAGE / f'episode_{a.episode}_asks.jsonl'}")
    print(f"  report: py -3.10 tools/run_generation.py --report --episode {a.episode}")
    print(f"  {episode['seconds']}s")
    return 0 if episode["verdict"] == "PASS" else 1


REQUIRED_GATES = ("absence_verified", "erosion_zero", "census_reported",
                  "live_seals_unchanged", "row_self_contained")


def verdict_of(gates: dict) -> str:
    """True passes, False fails, and None -- a gate that was never run -- ALSO fails.

    The pilot ran with --tier open, so the frozen and guarded tiers were 0/0 and the
    erosion gate reported PASS on nothing it had measured. A gate that can pass by
    not being run is worse than no gate, because it is the one that gets trusted.

    A gate that is ABSENT fails too, for the same reason: an episode row written by an
    older or partial code path would otherwise pass by omission.
    """
    return "PASS" if all(gates.get(k) is True for k in REQUIRED_GATES) else "FAIL"


def _journal(p: Path) -> list:
    if not Path(p).exists():
        return []
    return [json.loads(l) for l in
            Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def _who_of(deltas) -> dict:
    out = {}
    for d in deltas or []:
        k = str(d.get("who") or "?")
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _by_frame(rows: list) -> dict:
    out = {}
    for r in rows:
        d = out.setdefault(str(r.get("frame")), [0, 0])
        d[1] += 1
        d[0] += 1 if r["pass"] else 0
    return {k: {"passed": v[0], "asked": v[1]} for k, v in sorted(out.items())}


if __name__ == "__main__":
    sys.exit(main())
