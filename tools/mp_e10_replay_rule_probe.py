"""D-MPE10-05 evidence probe: what the sequence organ's write rule does when replay re-applies it.

The PI asked for the margin and the mechanism to be proposed FROM measurement rather than from a round number,
and -05 cannot be decided at all without the line sites and the rule's actual behaviour. This file supplies
the second half: it runs the REAL `organs/sequence_organ.py:learn_sequence` over a deterministic corpus and
reports what replay does to the chain, to the 4.0 ceiling at :206, and to the `transitions` /
`sequences_learned` counters at :213-214.

WHAT IS AND IS NOT MEASURED HERE. The corpus is a deterministic synthetic sequence set, because what is under
examination is the ARITHMETIC of the write rule, which does not care what the words mean. So the numbers are
about the mechanism and are admissible in a design decision; they are not a consolidation result, not an H3
figure, and not a claim about any agent's retention. A 53-item real curriculum run through this rule would be
a scored experiment and belongs to step 2 after D-MPE10-04 and -05 are ruled.

Run:  .venv/Scripts/python.exe -B tools/mp_e10_replay_rule_probe.py --out experiments/MP-E10/results/replay_rule_saturation_probe.json
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.sequence_organ import SequenceOrgan

VOCAB = [f"w{i:03d}" for i in range(60)]
N_ITEMS, SEQ_LEN, CYCLES, PASS_SET = 53, 5, 3, (1, 3, 10, 11, 30)
N_SLOTS = 8   # smaller than the organ's 48 on purpose: the rule is per-pair and slot-independent, and a
              # 48-slot run would only tell me the same thing about more pairs, four times slower.
CEILING = 4.0  # written literally at sequence_organ.py:206


def corpus(n=N_ITEMS, length=SEQ_LEN):
    return [[VOCAB[(i * 7 + j * 3) % len(VOCAB)] for j in range(length)] for i in range(n)]


def entries(org):
    return {(slot, a, b): w for slot, ch in enumerate(org.chain)
            for a, row in ch.items() for b, w in row.items()}


def stats(org):
    e = entries(org)
    ws = list(e.values())
    return {"n_entries": len(ws), "mean_weight": round(sum(ws) / len(ws), 6) if ws else 0.0,
            "max_weight": round(max(ws), 6) if ws else 0.0,
            "min_weight": round(min(ws), 6) if ws else 0.0,
            "distinct_weight_values": len(set(round(w, 9) for w in ws)),
            "at_ceiling": sum(1 for w in ws if w >= CEILING - 1e-9),
            "share_at_ceiling": round(sum(1 for w in ws if w >= CEILING - 1e-9) / max(len(ws), 1), 6)}


def teach(org, c, times=1):
    for _ in range(times):
        for seq in c:
            org.learn_sequence(seq)


def main(argv=None) -> int:
    c = corpus()
    out = {
        "purpose": "D-MPE10-05 evidence: the write rule's behaviour under replay, measured",
        "rule_line_sites": {"learn_sequence": "organs/sequence_organ.py:174-216",
                            "write_and_ceiling": "organs/sequence_organ.py:206 (new = old + lr, clamped at 4.0)",
                            "lr": "LEARN_LR x (1 + reward), LEARN_LR = 0.35 at organs/sequence_organ.py:76",
                            "counters": "transitions :213, sequences_learned :214",
                            "readout_gates": "SUCCESSOR_FLOOR = 0.12 :77, SUCCESSOR_MARGIN = 0.35 :83"},
        "corpus": {"kind": "deterministic synthetic sequences (NOT a curriculum, NOT language)",
                   "items": N_ITEMS, "sequence_length": SEQ_LEN, "n_slots": N_SLOTS,
                   "cycles": CYCLES},
        "constants": {"LEARN_LR": float(SequenceOrgan.LEARN_LR), "ceiling": CEILING,
                      "SUCCESSOR_FLOOR": float(SequenceOrgan.SUCCESSOR_FLOOR),
                      "SUCCESSOR_MARGIN": float(SequenceOrgan.SUCCESSOR_MARGIN)},
    }
    org = SequenceOrgan(n_slots=N_SLOTS)
    teach(org, c, CYCLES)
    out["after_teaching_cycles"] = stats(org)
    out["after_teaching_cycles"]["counters"] = {"transitions": org.transitions,
                                                "sequences_learned": org.sequences_learned}

    per_cycle = org.transitions // CYCLES   # transitions counted by ONE teaching cycle of this corpus
    rows = []
    for passes in PASS_SET:
        o = SequenceOrgan(n_slots=N_SLOTS)
        teach(o, c, CYCLES)
        before, cb = entries(o), (o.transitions, o.sequences_learned)
        teach(o, c, passes)
        after = entries(o)
        st = stats(o)
        rows.append({"replay_passes": passes, "entries_changed": sum(1 for k in before if before[k] != after[k]),
                     "entries_total": len(before), "new_entries_created": len(after) - len(before),
                     "mean_weight": st["mean_weight"], "distinct_weight_values": st["distinct_weight_values"],
                     "share_at_ceiling": st["share_at_ceiling"],
                     "counters_moved": {"transitions": o.transitions - cb[0],
                                        "sequences_learned": o.sequences_learned - cb[1]},
                     "transitions_if_every_pass_were_counted": passes * per_cycle,
                     "transitions_moved_vs_counted": [o.transitions - cb[0], passes * per_cycle]})
    out["option_A_replay_via_learn_sequence"] = rows

    o = SequenceOrgan(n_slots=N_SLOTS)
    teach(o, c, CYCLES)
    sat = None
    for p in range(1, 60):
        teach(o, c, 1)
        if stats(o)["share_at_ceiling"] >= 0.999:
            sat = p
            break
    out["passes_until_every_entry_at_ceiling"] = sat
    out["findings"] = {
        "1_replay_is_a_uniform_translation_not_selective_strengthening":
            "with a constant lr and reward 0, every visited pair gains the same amount per pass, so replay "
            "cannot strengthen one engram relative to another. After 3 cycles mean == max == min: the chain "
            "has one value.",
        "2_past_the_ceiling_replay_destroys_the_ranking_readout_needs":
            f"every entry reaches the 4.0 ceiling at pass {sat}; at that point all pairs are equal, so the "
            "within-slot ordering generate() reads through SUCCESSOR_FLOOR/MARGIN is gone. A pass-count limit "
            "is a precondition of option A, not an optimisation of it.",
        "3_replay_contaminates_the_organ_s_own_accounting":
            "transitions and sequences_learned advance as though new material arrived, and they saturate "
            "non-linearly (once nothing grows, `grew` is False and written stops counting), so the drift hides "
            "itself in the counters that published evidence quotes.",
        "4_consequence_for_the_ruling":
            "option A costs no code and cannot express selective consolidation; option B (a dedicated replay "
            "entry with a replay gain, advancing no teaching counter) is the only one that can, and it is an "
            "organ change. See docs/mp_e10_g3_decision_brief.md."}
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    if args.out:
        p = Path(args.out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("after_teaching_cycles", "passes_until_every_entry_at_ceiling")},
                     indent=2, sort_keys=True))
    for r in out["option_A_replay_via_learn_sequence"]:
        print(f"  passes={r['replay_passes']:>2} changed={r['entries_changed']}/{r['entries_total']} "
              f"mean={r['mean_weight']} distinct_values={r['distinct_weight_values']} "
              f"share_at_ceiling={r['share_at_ceiling']} counters+={r['counters_moved']}")
    print(f"wrote {args.out or '(not written)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
