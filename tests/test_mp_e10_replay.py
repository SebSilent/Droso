"""B.4 step 2: the replay entry, its registered gain, and its per-pass saturation guard.

These tests pin the RULING, not a preference. The gain must be unread off the teaching constant; the counters
must not move; the guard must void rather than warn. What they deliberately do NOT assert is that replay
improves retention -- that is H3, it is a timed measurement, and it has not run.
"""
from __future__ import annotations

import hashlib, math, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.sequence_organ import SequenceOrgan

VOCAB = [f"w{i:03d}" for i in range(60)]


def corpus(n=53, length=5):
    return [[VOCAB[(i * 7 + j * 3) % len(VOCAB)] for j in range(length)] for i in range(n)]


def teach(org, c, cycles=3):
    for _ in range(cycles):
        for seq in c:
            org.learn_sequence(seq)
    return org


def digest(org):
    """Deterministic state digest of the chain, the counters and the slot vocabularies."""
    h = hashlib.sha256()
    for i, ch in enumerate(org.chain):
        for a in sorted(ch):
            for b in sorted(ch[a]):
                h.update(f"{i}:{a}:{b}:{ch[a][b]:.12g}".encode())
    h.update(f"|{org.transitions}|{org.sequences_learned}|".encode())
    for s in org.slot_words:
        h.update((",".join(sorted(s))).encode())
    return h.hexdigest()


def set_entry(org, slot=0, a=1, b=2, value=3.9):
    org.chain[slot][a] = {b: value}


# ---------------------------------------------------------------- the gain is read off, not chosen
def test_replay_gain_is_the_teaching_constant_by_identity_not_a_copy():
    assert SequenceOrgan.REPLAY_GAIN is SequenceOrgan.LEARN_LR
    assert SequenceOrgan.REPLAY_GAIN == 0.35


def test_replay_ceiling_matches_the_literal_the_teaching_path_clamps_to():
    assert SequenceOrgan.REPLAY_CEILING == 4.0
    src = (ROOT / "organs" / "sequence_organ.py").read_text(encoding="utf-8")
    assert "row[key] = 4.0 if new > 4.0 else new" in src, "the teaching clamp is the value the guard names"


def test_gain_is_not_a_parameter_a_caller_can_pass():
    """If a caller could set the gain, consolidation would be tunable against an interference figure."""
    with pytest.raises(TypeError):
        SequenceOrgan(n_slots=4).replay_pass(gain=0.1)


# ---------------------------------------------------------------- the counters stay honest
def test_a_replay_pass_advances_neither_transitions_nor_sequences_learned():
    org = teach(SequenceOrgan(n_slots=8), corpus())
    before = (org.transitions, org.sequences_learned)
    org.replay_pass()
    assert (org.transitions, org.sequences_learned) == before
    r = org.replay_tier(passes=2)
    assert (org.transitions, org.sequences_learned) == before
    assert all(p["counters_advanced"] is False for p in r["per_pass"])
    assert r["transitions_after"] == before[0] and r["sequences_learned_after"] == before[1]


def test_replay_creates_no_new_pairs_the_tape_is_the_chain_itself():
    org = teach(SequenceOrgan(n_slots=8), corpus())
    n = org.stored_pairs()
    org.replay_tier()
    assert org.stored_pairs() == n


# ---------------------------------------------------------------- one pass IS what was registered
def test_one_pass_moves_every_stored_pair_by_exactly_one_increment():
    org = teach(SequenceOrgan(n_slots=8), corpus(), cycles=1)
    snap = {(i, a, b): w for i, ch in enumerate(org.chain) for a, row in ch.items() for b, w in row.items()}
    r = org.replay_pass()
    assert r["pairs_on_tape"] == len(snap) == r["pairs_advanced"]
    for (i, a, b), old in snap.items():
        assert org.chain[i][a][b] == pytest.approx(old + 0.35, abs=1e-9)


def test_entries_are_clamped_to_the_ceiling_and_never_pass_it():
    org = SequenceOrgan(n_slots=4)
    set_entry(org, value=3.95)
    org.replay_pass()
    assert org.chain[0][1][2] == 4.0


# ---------------------------------------------------------------- the guard voids, it does not warn
def test_an_entry_pushed_to_the_ceiling_makes_the_configuration_ceiling_limited_and_void():
    org = SequenceOrgan(n_slots=4)
    set_entry(org, value=3.9)
    r = org.replay_pass()
    assert r["ceiling_limited"] is True and r["void_for_H3"] is True
    assert r["entries_pushed_to_ceiling_this_pass"] == 1


def test_an_entry_already_at_the_ceiling_is_not_advanced_and_still_voids():
    """Conservative reading of the ruling: a saturated store cannot be read, whoever saturated it."""
    org = SequenceOrgan(n_slots=4)
    set_entry(org, value=4.0)
    r = org.replay_pass()
    assert r["entries_at_ceiling_before"] == 1
    assert r["pairs_advanced"] == 0
    assert org.chain[0][1][2] == 4.0
    assert r["void_for_H3"] is True


def test_replay_tier_stops_at_the_pass_that_voids_it_rather_than_deepening_the_saturation():
    org = SequenceOrgan(n_slots=4)
    set_entry(org, value=3.9)
    r = org.replay_tier(passes=5)
    assert r["passes_registered"] == 5 and r["passes_run"] == 1
    assert r["ceiling_limited"] is True and r["void_for_H3"] is True
    assert "absolute gates" in r["reason_void"]


# ---------------------------------------------------------------- the registered prediction
def test_two_passes_is_the_registered_schedule_and_accumulates_point_seven_zero():
    org = teach(SequenceOrgan(n_slots=8), corpus())
    assert SequenceOrgan.REPLAY_PASSES_PER_TIER == 2
    r = org.replay_tier()
    assert r["passes_run"] == 2
    assert r["predicted_max_accumulation_this_tier"] == pytest.approx(0.70)
    assert r["ceiling_limited"] is False


def test_the_prediction_holds_on_the_real_teaching_path_nothing_is_ceiling_limited():
    """Registered as a prediction so ceiling-limitation is predicted rather than discovered."""
    org = teach(SequenceOrgan(n_slots=8), corpus(), cycles=3)
    assert org.replay_pass()["ceiling_limited"] is False
    assert org.replay_pass()["ceiling_limited"] is False
    vals = [w for ch in org.chain for row in ch.values() for w in row.values()]
    assert max(vals) == pytest.approx(1.05 + 0.70)
    assert min(vals) == pytest.approx(1.05 + 0.70)     # uniform, exactly as the ruling states


def test_the_saturation_arithmetic_predicts_twelve_passes_from_a_fresh_store():
    assert math.ceil(4.0 / 0.35) == 12
    org = SequenceOrgan(n_slots=4)
    org.learn_sequence(["aa", "bb"])                   # one teaching increment: the pair starts at 0.35
    seen = []
    for i in range(12):
        r = org.replay_pass()
        seen.append(r["ceiling_limited"])
        if r["ceiling_limited"]:
            # The registered 12 counts INCREMENTS FROM AN EMPTY STORE: ceil(4.0 / 0.35) = 12. One of those
            # increments was the teaching call above, so the eleventh REPLAY pass completes it. Getting this
            # off by one in the other direction would mean the prediction in the ruling is wrong about its
            # own units, which is exactly what a test is for.
            assert i + 1 == 11, f"saturated on replay pass {i+1}; expected 11 replay passes + 1 teaching"
            break
    assert any(seen), "a store replayed every pass must eventually saturate -- the guard is not decorative"


# ---------------------------------------------------------------- what replay must never do
def test_replay_does_not_reach_into_the_generation_path_it_is_guarded_from():
    """The guard's purpose: an absolute-gate readout over a saturated store is not a measurement."""
    org = SequenceOrgan(n_slots=4)
    set_entry(org, value=4.0)
    r = org.replay_tier(passes=2)
    assert r["void_for_H3"] is True
    assert r["passes_run"] == 1, "a void configuration must not accumulate further passes"


def test_digest_is_stable_across_identical_runs_and_moves_when_replay_runs():
    c = corpus(8)
    a = digest(teach(SequenceOrgan(n_slots=6), c))
    b = digest(teach(SequenceOrgan(n_slots=6), c))
    assert a == b
    o = teach(SequenceOrgan(n_slots=6), c)
    o.replay_pass()
    assert digest(o) != a
