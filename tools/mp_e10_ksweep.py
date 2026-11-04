"""MP-E10 k-sweep -- ORGAN CHARACTERISATION, not a scored run, not a hypothesis verdict.

Promoted out of `_tmp/mp_e10_ksweep_t40.py` on 2026-11-04 for one reason that is a house rule: R10 says a
number a gate depends on cannot live in `_tmp/`, because `_tmp/` is swept. D-MPE10-06's obligation is
"||w||_F against tokens pushed is reported as its own quantity in every MP-E10 artifact", and the only
thing that produced that quantity was a scratch file. The tier-40 artifact it wrote is sealed; the driver
that reproduces it was one `git clean` away from not existing.

WHAT IT DOES. Reads a committed MP-E8 curriculum manifest (unedited -- tiers.curriculum requires it),
extracts every taught surface string, and pushes those utterances through
tools/mp_e10_working_memory.DecayedTrace at every registered k, reporting what the trace holds and what it
can do with it.

WHAT IT IS NOT. Not evidence for H1 or H2. The registration's `result_quoting_guard_while_blocked` is
copied into this artifact's header, so a file read on its own cannot escape it. And the trace here is NOT
the object MP-E10 B.4 step 2 replays: `--replay` in tools/electric_learn_bench.py calls
organs/sequence_organ.replay_tier, which advances the sequence organ's SUCCESSOR chain (pre -> post,
clamped at 4.0). DecayedTrace is a fast-weight PREDECESSOR map, outer(post, pre) -- the transpose. This
sweep characterises the trace; the tier-300 run moved the chain. Conflating them would be the exact
substitution D-MPE10-08 was written to prevent, so both are named in the output.

THE TOKEN VECTORS ARE A STAND-IN, AND SAY SO. The house projects words into SAN cells; this uses a
deterministic hash projection into dim=64 so the measurement is reproducible without touching the organ's
weights. Every figure is therefore a property of the TRACE, not of Droso.

USAGE
  py tools/mp_e10_ksweep.py --curriculum experiments/MP-E8/curriculum_tier300.json
  py tools/mp_e10_ksweep.py --out experiments/MP-E10/results/ksweep_tier40_reproduction.json
A target that already exists is refused unless --overwrite is given, so this tool can never clobber a
sealed artifact.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.mp_e10_working_memory import DEFAULT_DECAY, DecayedTrace, unigram_context  # noqa: E402

REG = ROOT / "experiments/MP-E10/registration.json"
DEFAULT_CURRICULUM = ROOT / "experiments/MP-E8/curriculum_tier40.json"
DIM = 64
# Token counts at which ||w||_F is sampled, per D-MPE10-06. The tier-40 run used (8,16,32,64) and its
# sealed artifact carries exactly those, so they stay the base; a tier whose stream is longer extends the
# list up to its own token volume rather than reporting a curve that stops short of the tier.
BASE_CHECKPOINTS = (8, 16, 32, 64)


def _rel(p):
    """Repo-relative for display, absolute when it genuinely is elsewhere.

    A test that runs the driver against a tmp_path outside the repo used to crash HERE, after the whole
    sweep had completed -- the same class of bug suite_manifest.py records three times in its own history.
    A cosmetic path must not be able to decide the exit code of a finished measurement.
    """
    pp = Path(p).resolve()
    try:
        return pp.relative_to(ROOT).as_posix()
    except ValueError:
        return pp.as_posix()


def token_vec(tok: str, dim: int = DIM) -> np.ndarray:
    """Deterministic unit vector per token. A stand-in for the house's SAN projection."""
    h = hashlib.sha256(tok.lower().encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
    v = rng.normal(size=dim).astype("float32")
    return v / np.linalg.norm(v)


def utterances(curriculum_path: Path):
    """Every taught surface string in the manifest: qa answers, qa questions, svo frames."""
    cur = json.loads(Path(curriculum_path).read_text(encoding="utf-8"))
    out = []
    for s in cur["sessions"]:
        for q, a in s.get("qa_pairs", []) or []:
            out.append({"text": a, "kind": "qa_answer", "session": s["session"]})
            out.append({"text": q, "kind": "qa_question", "session": s["session"]})
        for f in s.get("tell_frames", []) or []:
            m = re.match(r"svo\('([^']+)'", f)
            if m:
                out.append({"text": m.group(1), "kind": "tell_frame", "session": s["session"]})
    return out, cur


def cosine(a, b):
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return 0.0 if na == 0 or nb == 0 else float(np.dot(a, b) / (na * nb))


def checkpoints_for(total_tokens: int):
    """The base checkpoints, extended to the tier's own stream length.

    A ||w||_F curve that stops at 64 tokens says nothing about a tier that pushes thousands, and silently
    truncating the curve is how a growing quantity gets reported as a stable one.
    """
    cps = [c for c in BASE_CHECKPOINTS if c <= max(total_tokens, BASE_CHECKPOINTS[-1])]
    step = 256
    while cps and cps[-1] + step <= total_tokens:
        cps.append(cps[-1] + step)
    if total_tokens and (not cps or cps[-1] != total_tokens):
        cps.append(total_tokens)          # the tier's full volume is the point of the exercise
    return tuple(cps) or BASE_CHECKPOINTS


def boundedness_probe(cps):
    """Does k bound the fast-weight store? Push a long stream and watch w while the ring stays full."""
    toks = [token_vec(f"tok{i}") for i in range(max(cps))]
    rows = []
    for k in (1, 2, 8, 22):
        t = DecayedTrace(k, DIM)
        curve = {}
        for i, v in enumerate(toks, start=1):
            t.push(v)
            if i in cps:
                curve[str(i)] = round(float(np.linalg.norm(t.w)), 4)
        rows.append({
            "k": k,
            "tokens_pushed": len(toks),
            "ring_slots_in_use": int(t.age_ok.sum()),
            "n_pushed": t.n_pushed,
            "w_frobenius_norm_vs_tokens_pushed": curve,
            "w_nonzero_rows": int((np.abs(t.w).sum(axis=1) > 0).sum()),
            "adjacent_pairs_in_stream": len(toks) - 1,
        })
    return {
        "question": "Is the associative store bounded by k, or does it accumulate every adjacency "
                    "ever pushed until clear()?",
        "stream_length_tokens": len(toks),
        "checkpoints": list(cps),
        "same_stream_at_four_values_of_k": rows,
        "answer_as_measured": ("The ring is bounded -- slots in use never exceeds k -- but ||w||_F is the "
                               "same at k=2, k=8 and k=22 at every checkpoint and grows with the NUMBER OF "
                               "TOKENS PUSHED, not with k. The fast-weight state has no capacity limit tied "
                               "to k: it holds every adjacent pair the organ has ever seen until a restart."),
        "status_after_ruling": ("RULED, D-MPE10-06: this is the design, not a defect -- the plan describes "
                               "two objects and the module implements two. k bounds the activation trace "
                               "only. The obligation the ruling creates is the one this probe satisfies: "
                               "||w||_F against tokens pushed is reported as its own quantity in every "
                               "MP-E10 artifact, so 'capacity k' can never be read as a capacity claim "
                               "about the whole organ."),
    }


def k1_degeneracy_probe():
    """The registered grid starts at k=1. What does the pair state become there?"""
    seq = [token_vec(f"w{i}") for i in range(6)]
    out = {}
    for k in (1, 2, 3):
        t = DecayedTrace(k, DIM)
        for v in seq:
            t.push(v)
        self_links = sum(np.outer(v, v) for v in seq[1:])
        pair_links = sum(np.outer(post, pre) for pre, post in zip(seq, seq[1:]))
        out[k] = {
            "w_equals_sum_of_self_links": bool(np.allclose(t.w, self_links)),
            "w_equals_sum_of_adjacent_pair_links": bool(np.allclose(t.w, pair_links)),
            "diagonal_mass": round(float(np.trace(t.w)), 4),
            "offdiag_frobenius": round(float(np.linalg.norm(t.w - np.diag(np.diag(t.w)))), 4),
        }
    return {
        "question": "The module's docstring says self-links are excluded by construction, because the "
                    "state is outer(post, pre). Is that true at k=1?",
        "mechanism": ("push() takes `prev = self.ring[(head-1) % k]` -- a numpy VIEW -- and then writes "
                      "`self.ring[head] = v`. At k=1, (head-1) % 1 == head, so prev aliases the slot being "
                      "overwritten and is the NEW vector by the time outer(v, prev) is evaluated. The "
                      "'pair' recorded at k=1 is outer(v_i, v_i), a self-link."),
        "measured": out,
        "answer_as_measured": ("No. At k=1 the state is exactly the sum of self-links and its diagonal "
                               "mass is nonzero, while at k=2 and k=3 the diagonal mass is 0.0 and the "
                               "state is the sum of adjacent pair-links. k=1 is the FIRST POINT OF THE "
                               "REGISTERED GRID, so the grid's baseline is not a smaller version of the "
                               "other points -- it is a different object."),
        "status_after_ruling": ("RULED, D-MPE10-07: k=1 is excluded from the SCORED grid by AMD-MPE10-01 "
                               "-- excluded, not deleted, which is why this row is still printed and its "
                               "diagonal mass is still the detector."),
    }


DIRECTION_DECLARATION = (
    "READ DIRECTION, named per PI ruling D-MPE10-08 (no figure may be reported as a bare 'alignment'). "
    "This instrument is tools/mp_e10_working_memory.DecayedTrace, whose state is outer(post, pre): it is a "
    "PREDECESSOR map. Probing the token that came LATER recovers the token that came EARLIER (measured "
    "cosine ~0.982); probing the earlier token does not recover the later one (~0.056). The columns below "
    "are named for which token was probed and which was recovered, never as 'alignment'. NOT THE SAME "
    "OBJECT AS MP-E10 B.4 STEP 2: the --replay runs call organs/sequence_organ.replay_tier, which advances "
    "the sequence organ's SUCCESSOR chain (pre -> post, clamped at REPLAY_CEILING 4.0) and is read forward "
    "by generate(first_word). The trace is the transpose of that chain. A tier-300 replay number and a "
    "tier-300 trace number describe different organs and may not be substituted for one another.")


def direction_probe():
    """Does the store answer 'what came before' or 'what comes next'?"""
    seq = [token_vec(f"w{i}") for i in range(6)]
    t = DecayedTrace(8, DIM)
    for v in seq:
        t.push(v)
    earlier_gets_later = [cosine(t.read(pre), post) for pre, post in zip(seq, seq[1:])]
    later_gets_earlier = [cosine(t.read(post), pre) for pre, post in zip(seq, seq[1:])]
    return {
        "question": "outer(post, pre) maps which way? A next-token predictor needs the forward link.",
        "declared_direction": DIRECTION_DECLARATION,
        "measured": {"probe_the_earlier_token_recovers_the_later_cosine":
                     round(float(np.mean(earlier_gets_later)), 6),
                     "probe_the_later_token_recovers_the_earlier_cosine":
                     round(float(np.mean(later_gets_earlier)), 6)},
        "answer_as_measured": ("The store is a PREDECESSOR map: probing the later token returns the "
                               "earlier one strongly, probing the earlier token does not return the later "
                               "one."),
        "status_after_ruling": ("RULED, D-MPE10-08: the organ is NOT transposed. If a scored run needs the "
                                "successor map, that is a registered organ change with its own design step."),
    }


def sweep_one(k, utts, scored_grid):
    held, dropped, norms, oldest = 0, 0, [], []
    succ, pred, order_sep, bag_sep, diag, wnorms = [], [], [], [], [], []
    tok_total = 0
    for u in utts:
        toks = u["text"].lower().replace("?", "").split()
        vecs = [token_vec(x) for x in toks]
        tok_total += len(vecs)
        tr = DecayedTrace(k, DIM)
        for v in vecs:
            tr.push(v)
        n = len(vecs)
        held += 1 if n <= k else 0
        dropped += max(0, n - k)
        norms.append(float(np.linalg.norm(tr.state())))
        w = tr.w
        diag.append(float(np.trace(w)))
        wnorms.append(float(np.linalg.norm(w)))
        live = tr.weights() > 0
        oldest.append(float(tr.weights()[live].min()) if live.any() else 0.0)
        for pre, post in zip(vecs, vecs[1:]):
            succ.append(cosine(tr.read(pre), post))
            pred.append(cosine(tr.read(post), pre))
        rev = DecayedTrace(k, DIM)
        for v in vecs[::-1]:
            rev.push(v)
        order_sep.append(1.0 - cosine(tr.state(), rev.state()))
        bag_sep.append(1.0 - cosine(unigram_context(vecs), unigram_context(vecs[::-1])))
    mean = lambda xs: round(float(np.mean(xs)), 6) if xs else None
    return {
        "k": k,
        "in_scored_grid": k in scored_grid,
        "exclusion_reason_if_not": (None if k in scored_grid else
                                    "k=1 is degenerate (self-links, diagonal mass nonzero) -- excluded "
                                    "from the scored grid by AMD-MPE10-01 on PI ruling D-MPE10-07, printed "
                                    "here because the diagonal mass is the evidence"),
        "read_direction_declared": ("probe_earlier_recovers_later = probe an EARLIER token, see what comes "
                                    "back on the LATER side; probe_later_recovers_earlier = probe a LATER "
                                    "token, recover the EARLIER one. Named per PI ruling D-MPE10-08: no "
                                    "read() figure may be reported as a bare 'alignment', because the "
                                    "store is a predecessor map and the two columns are not equal."),
        "decay_per_step": DEFAULT_DECAY,
        "oldest_weight_at_this_k": round(DEFAULT_DECAY ** (k - 1), 8),
        "oldest_weight_measured_mean": mean(oldest),
        "utterances": len(utts),
        "tokens_total": tok_total,
        "utterances_fully_held": held,
        "utterances_fully_held_pct": round(100.0 * held / len(utts), 2),
        "tokens_dropped_beyond_window": dropped,
        "state_norm_mean": mean(norms),
        "probe_earlier_recovers_later_cosine_mean": mean(succ),
        "probe_later_recovers_earlier_cosine_mean": mean(pred),
        "direction_asymmetry_pp": round(100.0 * (mean(pred) - mean(succ)), 4) if succ else None,
        "these_two_columns_are_k_invariant_for_k_ge_2_by_construction": (
            "read() uses only the fast-weight state, and the state accumulates every adjacent pair "
            "regardless of k -- see the boundedness probe. They are NOT a k-sweep result; they are one "
            "number printed once per k, and saying so is the difference between a measurement and a table."),
        "w_diagonal_mass_mean": mean(diag),
        "w_frobenius_norm_mean": mean(wnorms),
        "order_separation_vs_reversed_utterance_mean": mean(order_sep),
        "bag_of_words_order_separation_mean": mean(bag_sep),
    }


def main() -> int:
    t0 = time.time()      # the whole measurement, not the write
    argv = sys.argv[1:]
    cur_path = ROOT / argv[argv.index("--curriculum") + 1] if "--curriculum" in argv \
        else DEFAULT_CURRICULUM
    tier = json.loads(cur_path.read_text(encoding="utf-8")).get("tier")
    if "--out" in argv:
        out = ROOT / argv[argv.index("--out") + 1]
    else:
        out = ROOT / f"experiments/MP-E10/results/ksweep_tier{tier}_organ_characterisation.json"
    if out.exists() and "--overwrite" not in argv:
        print(f"REFUSED: {out} already exists. A sealed artifact is never overwritten (R5). "
              f"Choose another --out, or pass --overwrite deliberately.", file=sys.stderr)
        return 3

    reg = json.loads(REG.read_text(encoding="utf-8"))
    grid = reg["k_sweep"]["grid_tokens"]
    scored = reg["k_sweep"].get("grid_scored_tokens", grid)
    utts, cur = utterances(cur_path)
    if not utts:
        print(f"REFUSED: no utterances parsed from {cur_path}", file=sys.stderr)
        return 2
    lengths = [len(u["text"].lower().replace("?", "").split()) for u in utts]
    total_tokens = sum(lengths)
    cps = checkpoints_for(total_tokens)
    rows = [sweep_one(k, utts, scored) for k in grid]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain=v1", "-uno"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()

    art = {
        "experiment": "MP-E10",
        "artifact": f"ksweep_tier{tier}_organ_characterisation",
        "schema": 2,
        "kind": ("ORGAN CHARACTERISATION. Not a scored run, not a hypothesis verdict. No curriculum "
                 "session was taught to any arm, no bench was run."),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "read_direction_declared": DIRECTION_DECLARATION,
        "quoting_guard_attached": {
            "rule_source": "experiments/MP-E10/registration.json -> result_quoting_guard_while_blocked",
            "open_decisions_at_generation": sorted(
                (reg.get("open_decisions_for_PI") or reg.get("open_decisions_for_pi") or {})),
            "meaning": ("No figure in this file may be quoted as evidence for or against H1 or H2. This "
                        "sweep says what the organ is, not how well Droso does."),
        },
        "rulings_this_run_is_made_under": {
            "D-MPE10-06": ("||w||_F against tokens pushed is reported as its own quantity -- see "
                           "findings_about_the_sealed_organ.1, which carries the curve at "
                           f"{list(cps)} tokens for THIS tier's stream volume."),
            "D-MPE10-07": ("k=1 is excluded from the scored grid and still printed with its diagonal "
                           "mass, because the mass is the evidence for the exclusion."),
            "D-MPE10-08": ("The trace is a predecessor map and is not transposed; each row carries "
                           "read_direction_declared, and the header names the object the --replay runs "
                           "actually touch (the sequence organ's successor chain), so the two cannot be "
                           "substituted for each other."),
        },
        "input": {
            "curriculum": _rel(cur_path),
            "curriculum_sha256": cur["curriculum_sha256"],
            "tier": tier,
            "n_items": cur["n_items"],
            "utterances_parsed": len(utts),
            "by_kind": {k: sum(1 for u in utts if u["kind"] == k)
                        for k in sorted({u["kind"] for u in utts})},
            "tokens_per_utterance": {"min": min(lengths), "max": max(lengths),
                                     "mean": round(sum(lengths) / len(lengths), 3)},
            "tokens_total_across_utterances": total_tokens,
        },
        "token_vectors_are_a_stand_in": ("Deterministic sha256-seeded unit vectors, dim 64. Every figure "
                                         "is a property of the trace, not of Droso's SAN. To make it a "
                                         "property of Droso the same sweep must run over the organ's real "
                                         "projections."),
        "registered_grid": grid,
        "sweep": rows,
        "findings_about_the_sealed_organ": {
            "summary": ("Three properties of the sealed trace, each measured rather than argued, each "
                        "ruled on (D-MPE10-06, -07, -08). None is fixed here: the organ's behaviour is "
                        "untouched."),
            "1_fast_weight_store_is_not_bounded_by_k": boundedness_probe(cps),
            "2_registered_grid_point_k1_degenerates_to_self_links": k1_degeneracy_probe(),
            "3_the_store_is_a_predecessor_map_not_a_successor_map": direction_probe(),
        },
        "provenance": {
            "module": "tools/mp_e10_working_memory.py",
            "driver": "tools/mp_e10_ksweep.py",
            "driver_promoted_from": "_tmp/mp_e10_ksweep_t40.py",
            "promotion_reason": ("R10: a number a gate depends on cannot live in _tmp/, which is swept. "
                                 "D-MPE10-06's obligation was being produced by a scratch file while the "
                                 "artifact it wrote was sealed."),
            "argv": list(argv),
            "git_head": head,
            "git_dirty_tracked": dirty,
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "decay_per_step": DEFAULT_DECAY,
            "dim": DIM,
            "wall_seconds": None,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    art["provenance"]["wall_seconds"] = round(time.time() - t0, 3)
    out.write_text(json.dumps(art, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"wrote {_rel(out)}  (tier {tier}, {len(rows)} k values, {len(utts)} utterances, "
          f"{total_tokens} tokens, checkpoints {list(cps)}, {art['provenance']['wall_seconds']}s)")
    for r in rows:
        print(f"  k={r['k']:>2}  held={r['utterances_fully_held_pct']:>6}%  "
              f"diag_mass={r['w_diagonal_mass_mean']:<9}  "
              f"succ={r['probe_earlier_recovers_later_cosine_mean']}  "
              f"pred={r['probe_later_recovers_earlier_cosine_mean']}  "
              f"|w|_F={r['w_frobenius_norm_mean']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
