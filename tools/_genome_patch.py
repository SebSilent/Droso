r"""Apply one fly's genome to the shared organ for the life of one process.

TWO GENOME SHAPES, and the difference matters for what the outside check can say:

  v1  {head_index, cut_at, rel_head}   tools/fly_population.py
  v2  {w_pos, w_prep, w_first, w_len, w_count}   tools/fly_v2.py

The organ consumes a genome as a HEAD RULE: `_shape_matches` is replaced by the
fly's own, so the arbiter names the head the fly's weights choose. That is the
whole of what the real answer path can express today.

`w_count` is NOT applied, and the reason is not convenience: the organ has no
count branch -- `_question_shape` returns None for `how many`, which is exactly
what C5 measured -- so there is nothing to switch on. Applying it would mean
writing a count shape into the organ, i.e. building the capability inside the
measurement. So the fly is scored on the genes the real path can carry, and the
report says which gene was left behind.

  FLY_GENOME='{"w_pos":1.0,...}' py -3.10 -c "import tools._genome_patch, runpy, sys;
  sys.argv=['heldout_eval','--independent','--journal','state/fitness/heldout_best.jsonl'];
  runpy.run_module('tools.heldout_eval', run_name='__main__')"
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402

GENOME = json.loads(os.environ.get("FLY_GENOME") or "{}")
IS_V2 = "w_pos" in GENOME
CALLS = {"shapes": 0, "changed": 0, "vetoes_respected": 0,
         "veto_examples": []}
MODE = "unknown"


def head_of(tokens, shape):
    if IS_V2:
        from tools.fly_v2 import fly_head
        return fly_head(tokens, shape, GENOME)
    from tools.fly_population import fly_filler
    return fly_filler(tokens, shape, GENOME)


def install() -> str:
    global MODE
    if not GENOME:
        MODE = "no genome: committed brain, unmodified"
        print(f"[genome] {MODE}", flush=True)
        return MODE

    base_equal = (not IS_V2 and GENOME.get("head_index") == -1
                  and not GENOME.get("extra_function")
                  and GENOME.get("stem_verb", True))
    if base_equal:
        MODE = ("PASS-THROUGH: genome is the committed rule, so this run "
                "reproduces the baseline exactly")
        print(f"[genome] {MODE}", flush=True)
        return MODE

    orig = nl.NeuralLanguage._shape_matches

    allow_override = str(os.environ.get("FLY_ALLOW_VETO_OVERRIDE", "0")) \
        .strip().lower() in ("1", "on", "true", "yes")

    def patched(self, shape, tokens):
        got = orig(self, shape, tokens)
        if (shape or {}).get("kind") not in ("subject_unknown", "object_unknown"):
            return got
        CALLS["shapes"] += 1
        try:
            f = head_of(tokens, shape)
        except Exception:
            return got
        if got is None:
            # THE ORGAN REFUSED. A head rule names a head inside a span the
            # matcher already accepted; it does not get to supply a span the
            # matcher rejected. Returning `f` here scores the ABSENCE OF A
            # GUARD as capability -- that is the defect this replaces, and it
            # is what produced the 7/24. The disagreement is reported instead.
            if f is not None:
                CALLS["vetoes_respected"] += 1
                if len(CALLS["veto_examples"]) < 20:
                    CALLS["veto_examples"].append(
                        {"shape": (shape or {}).get("kind"),
                         "fly_would_say": f,
                         "tokens": " ".join(str(t) for t in tokens)[:120]})
                if not allow_override:
                    return None
                return f
            return None
        if f is not None and f != got:
            CALLS["changed"] += 1
            return f
        return got

    nl.NeuralLanguage._shape_matches = patched
    applied = "head rule" if IS_V2 else "head rule"
    skipped = ("w_count left unapplied: the organ has no count branch"
               if IS_V2 else "")
    MODE = (f"ACTIVE v{'2' if IS_V2 else '1'}: {applied} overridden; {skipped}")
    print(f"[genome] {MODE}", flush=True)
    print(f"[genome] {json.dumps(GENOME, sort_keys=True)}", flush=True)

    import atexit

    def _summary():
        print(f"[genome] spans scored {CALLS['shapes']}, head changed "
              f"{CALLS['changed']}, vetoes respected "
              f"{CALLS['vetoes_respected']} (organ refused, fly would have "
              f"answered: reported, not returned)", flush=True)
        for ex in CALLS["veto_examples"]:
            print(f"[genome] veto: {ex['fly_would_say']!r} on "
                  f"{ex['shape']} over {ex['tokens']!r}", flush=True)

    atexit.register(_summary)
    return MODE


install()