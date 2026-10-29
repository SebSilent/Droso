r"""Score one fly's genome on the outside check, without editing the organ.

WHY A SHIM AND NOT A PATCH TO organs/neural_language.py. The organ is the house's
live brain; a genome is a candidate, not a committed rule, and the two must not
share a file. This module rewrites one classmethod for the lifetime of one
process and nothing else -- the file on disk is untouched, and a run without
FLY_GENOME is byte-for-byte the committed brain.

WHAT IT REPRODUCES. A genome is {head_index, extra_function, stem_verb}. Applied
to a subject span, fly_filler() (tools/fly_population.py) picks the word at
head_index from the content words before the verb, with the function-word set
widened by extra_function. The object branch is deliberately NOT overridden: no
genome under test today differs there, and a rule with no test is a guess.

IF THE GENOME EQUALS THE COMMITTED RULE (-1, no extras, stem_verb on) this
module changes NOTHING and says so. That is the point of the pass-through case:
generation 1's best IS the incumbent, so the outside check on it is a
REPRODUCTION test of the committed bar, not an experiment. Printing which case
ran is the difference between a control and a claim.

  set FLY_GENOME={"head_index":-1,"extra_function":[],"stem_verb":true,"seed":13}
  py -3.10 -c "import tools._genome_patch, runpy, sys; sys.argv=['heldout_eval','--independent','--journal','state/fitness/heldout_fly_g1.jsonl']; runpy.run_module('tools.heldout_eval', run_name='__main__')"
"""
from __future__ import annotations

import json
import os
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
from tools.fly_population import fly_filler  # noqa: E402

GENOME = json.loads(os.environ.get("FLY_GENOME") or "{}")
CALLS = {"shapes": 0, "changed": 0}
MODE = "unknown"


def install() -> str:
    global MODE
    if not GENOME:
        MODE = "no genome: committed brain, unmodified"
        print(f"[genome] {MODE}", flush=True)
        return MODE
    head = int(GENOME.get("head_index", -1))
    extras = tuple(GENOME.get("extra_function") or ())
    stem_verb = bool(GENOME.get("stem_verb", True))
    if head == -1 and not extras and stem_verb:
        MODE = (f"PASS-THROUGH: genome {json.dumps(GENOME, sort_keys=True)} is the "
                "committed rule, so this run reproduces the baseline exactly")
        print(f"[genome] {MODE}", flush=True)
        return MODE

    orig = nl.NeuralLanguage._shape_matches

    def patched(self, shape, tokens):
        got = orig(self, shape, tokens)
        if (shape or {}).get("kind") not in ("subject_unknown", "object_unknown"):
            return got
        CALLS["shapes"] += 1
        try:
            f = fly_filler(tokens, shape, GENOME)
        except Exception:
            return got
        if f is not None and f != got:
            CALLS["changed"] += 1
            return f
        return got

    nl.NeuralLanguage._shape_matches = patched
    MODE = (f"ACTIVE: genome {json.dumps(GENOME, sort_keys=True)} overrides the "
            "subject span's head")
    print(f"[genome] {MODE}", flush=True)
    return MODE


install()