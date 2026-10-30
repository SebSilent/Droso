"""Classify the generalisation failures by mechanism, empirically.

Reads the live learned sets and puts each failing question form through the real
_question_shape and is_interrogative, so the classification is measured rather than
inferred from source. Read-only: sealed session, nothing saved.

  py -3.10 docs/evidence/answer_path_probe.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.converse import build  # noqa: E402

# The forms that fail, with the form that passes beside each, from the probe tier and
# the open tier across four episodes.
CASES = [
    ("what turns twice?",                                    "PASSES"),
    ("which thing turns twice?",                             "fails recall"),
    ("which of them is wet and is not on the hook?",          "fails mouth"),
    ("what does the frost bite?",                            "PASSES"),
    ("what is bitten by the frost?",                         "fails recall"),
    ("what is held by the thing the frost bites?",           "fails recall"),
    ("how many times does the bell turn?",                   "fails recall"),
    ("how often does the bell turn?",                        "fails recall"),
    ("the bell turns how often?",                            "PASSES"),
    ("what number of eggs is left in the basket?",           "fails recall"),
    ("what did i tell you about before the kettle?",         "fails recall"),
    ("which thing did i mention earlier than the kettle?",   "fails mouth"),
    ("does the door hold the frost?",                        "fails gating"),
    ("is the frost held by the door?",                       "fails gating"),
    ("name the wet thing that is not on the hook",           "fails mouth"),
    ("repeat after me the copper bell turns twice",          "fails mouth"),
]

sd = ROOT / "state" / "sessions" / "_answer_path_probe"
if sd.exists():
    shutil.rmtree(sd)
agent = build(sd)
lang = agent.language

print("LEARNED SETS")
print(f"  interrogatives ({len(lang.interrogatives)}): "
      f"{sorted(lang.interrogatives)}")
print(f"  question_roles ({len(lang.question_roles)}): "
      f"{sorted(lang.question_roles)}")
print(f"  answer_types   ({len(lang.answer_types)}): "
      f"{sorted(lang.answer_types)}")
print(f"  statement_words: {len(lang.statement_words)}")

import organs.neural_language as nl
print("\nSHAPE CONSTANTS")
for n in ("SHAPE_DO_SUPPORT", "SHAPE_COPULAS", "SHAPE_LOCATIVE_PREPS"):
    print(f"  {n}: {sorted(getattr(nl.NeuralLanguage, n))}")
print(f"  SHAPE_FUNCTION_WORDS ({len(nl.NeuralLanguage.SHAPE_FUNCTION_WORDS)}): "
      f"{sorted(nl.NeuralLanguage.SHAPE_FUNCTION_WORDS)}")

print("\nPER-FORM DIAGNOSIS")
print(f"{'form':52s} {'inter?':7s} {'echo?':6s} {'shape':16s} known")
for text, known in CASES:
    toks = [t for t in lang.tokenizer.tokenize(text) if t]
    try:
        inter = lang.is_interrogative(toks)
    except Exception as e:
        inter = f"ERR {e}"
    try:
        echo = lang._is_echo_request(toks)
    except Exception as e:
        echo = f"ERR {e}"
    try:
        sh = lang._question_shape(toks)
        shs = "-" if sh is None else sh.get("kind")
    except Exception as e:
        shs = f"ERR {e}"
    print(f"{text[:52]:52s} {str(inter):7s} {str(echo):6s} {shs:16s} {known}")

print("\nWHICH-WORD COVERAGE: does the shape parser's literal tuple decide it?")
for w in ("what", "which", "who", "where", "how", "when", "why", "name"):
    toks = [t for t in lang.tokenizer.tokenize(f"{w} turns twice") if t]
    sh = lang._question_shape(toks)
    print(f"  {w:7s} interrogative={str(lang.is_interrogative(toks)):5s} "
          f"shape={'-' if sh is None else sh.get('kind')}")

print("\nPASSIVE: is there any handling at all?")
for text in ("what is bitten by the frost", "what is held by the door",
             "what does the frost bite"):
    toks = [t for t in lang.tokenizer.tokenize(text) if t]
    sh = lang._question_shape(toks)
    print(f"  {text:34s} -> {'-' if sh is None else json.dumps(sh)[:80]}")

shutil.rmtree(sd, ignore_errors=True)
