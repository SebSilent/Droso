"""A SYNTHETIC donor with the SHAPES of GPT-2 124M, and nothing else.

WHY THIS FILE EXISTS. MP-E12a's donor -- GPT-2 124M public weights -- is not on this machine, and the
plan opens the probe track the moment G0-prime closes (rule R4), which it has. The gap is physical, not
decisory: registration and instrument preparation need nothing that is missing. This builds the shape so
the three extractions can be executed, counted and unit-tested now, which is the same discipline
`tools/mp_e10_working_memory.py` uses with its hash-projected token vectors -- and that stand-in is what
found three properties of a sealed organ that 23 unit tests had missed.

WHAT IT IS NOT. It is not GPT-2. It is random float32 tensors with GPT-2 small's dimensions, tied
unembedding included because the tie is part of the shape. There is no library in it to read: no
association it produces means anything about language. Operation counts and matrix shapes are properties of
the code path and are therefore valid measurements here; confidences, neighbours and motifs are not, and
the probe artifact writes `donor_is_synthetic: true` in every field group so a number cannot be lifted
into a sentence about the flagship result by accident.

THE SHAPES ARE THE POINT, so they are checked, not assumed: `param_count` is computed from the config and
the sealed run compares it against the registered 124,439,808. If a dimension is wrong the budget of 24
operations was sized against something else and the whole calibration is void, which is a fact a reader is
entitled to see rather than a fact this file gets to hide.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# GPT-2 small (the 124M public checkpoint). n_positions is 1024, which is what the released wte/wpe pair
# actually is; the 1500 figure some notes carry is the trained maximum position count of the ORIGINAL 117M
# release path and would change wpe by 356k parameters. Registered here so the shape is auditable.
GPT2_124M = {"n_vocab": 50257, "n_positions": 1024, "n_embd": 768, "n_layer": 12,
             "n_head": 12, "d_head": 64, "mlp_inner": 3072}

# The unit-test shape: same keys, same tie, same per-layer structure, small enough to build in a millisecond.
TINY = {"n_vocab": 64, "n_positions": 16, "n_embd": 32, "n_layer": 2,
        "n_head": 2, "d_head": 8, "mlp_inner": 32}

REGISTERED_SEED = 1249
INIT_SCALE = 0.02  # what a GPT-2 checkpoint is initialised at; the scale is irrelevant to op counts and
                   # relevant only to keeping the tensors off the pathological range a zero would give.


def param_count(cfg: dict) -> int:
    """Parameters implied by a config, counted from the shapes -- not typed in from a model card."""
    per_layer = (2 * cfg["n_embd"]                                  # ln_1 weight + bias
                 + cfg["n_embd"] * (3 * cfg["n_embd"]) + 3 * cfg["n_embd"]   # c_attn weight + bias
                 + cfg["n_embd"] * cfg["n_embd"] + cfg["n_embd"]              # attn c_proj
                 + 2 * cfg["n_embd"]                                  # ln_2
                 + cfg["n_embd"] * cfg["mlp_inner"] + cfg["mlp_inner"]        # mlp c_fc
                 + cfg["mlp_inner"] * cfg["n_embd"] + cfg["n_embd"])          # mlp c_proj
    return (cfg["n_vocab"] * cfg["n_embd"] + cfg["n_positions"] * cfg["n_embd"]
            + cfg["n_layer"] * per_layer + 2 * cfg["n_embd"])         # + ln_f


def build_donor(cfg: dict = GPT2_124M, seed: int = REGISTERED_SEED) -> dict:
    """Random tensors in GPT-2's shapes. Returns a dict a probe can read and nothing else.

    The unembedding is TIED to wte, exactly as the donor is: there is no separate lm_head array, and the
    probe that reads successors reads wte. That tie is registered as a failure mode because it makes two
    of the three extractions read the same matrix.
    """
    rng = np.random.default_rng(seed)
    n, L, H, dh = cfg["n_embd"], cfg["n_layer"], cfg["n_head"], cfg["d_head"]

    def r(*shape):
        return (rng.standard_normal(size=shape, dtype=np.float32) * INIT_SCALE)

    donor = {
        "wte": r(cfg["n_vocab"], n),          # token embedding AND unembedding, tied
        "wpe": r(cfg["n_positions"], n),
        "ln_f_weight": r(n) + 1.0, "ln_f_bias": r(n),
        "layers": [],
    }
    for _ in range(L):
        donor["layers"].append({
            "ln_1_weight": r(n) + 1.0, "ln_1_bias": r(n),
            "c_attn_weight": r(n, 3 * n), "c_attn_bias": r(3 * n),
            "attn_c_proj_weight": r(n, n), "attn_c_proj_bias": r(n),
            "ln_2_weight": r(n) + 1.0, "ln_2_bias": r(n),
            "mlp_c_fc_weight": r(n, cfg["mlp_inner"]), "mlp_c_fc_bias": r(cfg["mlp_inner"]),
            "mlp_c_proj_weight": r(cfg["mlp_inner"], n), "mlp_c_proj_bias": r(n),
        })
    donor["config"] = dict(cfg)
    donor["head_shape"] = (H, dh)
    donor["is_synthetic"] = True
    donor["param_count"] = param_count(cfg)
    return donor


def shape_manifest(donor: dict) -> dict:
    """The arrays a probe may touch, with their shapes. Sealed, so the budget's referent is checkable."""
    cfg = donor["config"]
    out = {"config": dict(cfg), "param_count": donor["param_count"],
           "tensors": {"wte": list(donor["wte"].shape), "wpe": list(donor["wpe"].shape),
                       "ln_f_weight": list(donor["ln_f_weight"].shape)},
           "per_layer_tensors": {k: list(v.shape) for k, v in donor["layers"][0].items()},
           "n_layers": len(donor["layers"]), "n_head": cfg["n_head"], "d_head": cfg["d_head"],
           "unembedding_tied_to_wte": True}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiny", action="store_true", help="the small test shape instead of 124M")
    ap.add_argument("--out", default="", help="write the shape manifest here")
    a = ap.parse_args(argv)
    cfg = TINY if a.tiny else GPT2_124M
    donor = build_donor(cfg)
    m = shape_manifest(donor)
    m["registered_param_count_for_124M"] = 124439808
    m["param_count_matches_registered_124M"] = (donor["param_count"] == 124439808) if not a.tiny else "n/a (tiny)"
    if a.out:
        p = Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(m, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
