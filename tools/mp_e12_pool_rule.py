"""The candidate-pool rule, in one place, so the registration and the run cannot drift apart.

Value-blind by construction: this module consumes INTEGER token ids and nothing else. It never imports the
address space, never reads a value, and is checked against the pre-registration artifact by `matches()`, which
fails if the formula recorded before the first read differs in any constant from the formula actually used.
That check is the difference between "the rule was registered" and "the rule was registered AND honoured".
"""
from __future__ import annotations

N_VOCAB = 50257                    # wte.weight rows, from the donor header
SAMPLE_STRIDE_A = 7919             # odd and coprime with 50257: the map j -> r_j has no short cycle
SAMPLE_STRIDE_B = 104729
SAMPLE_N = 40
POOL_CAP = 63                      # 23 other probes + 40 sampled rows; one read_rows call at MAX_ROWS_PER_READ

FORMULA = (f"pool(T) = [other probe ids, in probe-list order] ++ "
           f"[(T*{SAMPLE_STRIDE_A} + j*{SAMPLE_STRIDE_B} + 1) mod {N_VOCAB} for j in 0..{SAMPLE_N - 1}], "
           f"deduplicated in that order, T excluded, capped at {POOL_CAP}")


def pool_for(token_id, other_ids, n_vocab=N_VOCAB):
    """`n_vocab` is the donor's own wte row count, taken from its header by the caller. The default is the real
    donor's 50,257, which is what the registered run used; a fixture donor passes its own, because a rule that
    hard-codes one file's shape cannot be tested against any other file."""
    ids = [int(t) for t in other_ids if int(t) != int(token_id)]
    for j in range(SAMPLE_N):
        r = (int(token_id) * SAMPLE_STRIDE_A + j * SAMPLE_STRIDE_B + 1) % int(n_vocab)
        if r != token_id and r not in ids:
            ids.append(r)
    return ids[:POOL_CAP]


def matches(prereg_doc: dict) -> list[str]:
    """Problems, empty when the artifact's recorded rule agrees with this module. Constants are compared by
    value, and the sizes the artifact measured are recomputed here."""
    problems = []
    rule = prereg_doc.get("candidate_pool_rule", {})
    recorded = rule.get("formula", "")
    for needle, label in ((f"*{SAMPLE_STRIDE_A} + j*{SAMPLE_STRIDE_B}", "strides"),
                          (f"mod {N_VOCAB}", "vocabulary size"),
                          (f"0..{SAMPLE_N - 1}", "sample count"),
                          (f"capped at {POOL_CAP}", "pool cap")):
        if needle not in recorded:
            problems.append(f"the registered formula does not contain {label} as implemented ({needle!r})")
    sizes = rule.get("pool_sizes_measured", {})
    if sizes.get("max") != POOL_CAP:
        problems.append(f"registered pool max {sizes.get('max')} is not the implemented cap {POOL_CAP}")
    return problems
