"""ELECTRIC -- the open-ended live-learning demo.

A user teaches several facts in natural language. The organism is then RESTARTED
(a brand-new organ, state loaded from disk) and asked the same facts in different
words. It must answer them, and it must say it does not know a fact it was never
told.

Run:  .venv\\Scripts\\python.exe tools\\electric_demo.py
      .venv\\Scripts\\python.exe tools\\electric_demo.py --control   (flags off)
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
from connectome.substrate import build_core_graph  # noqa: E402
from connectome.engine import HybridEngine  # noqa: E402
from organs.tokenizer import TokenizerOrgan  # noqa: E402

import os
os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")

# Teach a fact, then ask it back in DIFFERENT WORDS.
FACTS = [
    ("the scarf is on the hook",        "where is the scarf?"),
    ("the coat is in the hallway",      "where is the coat?"),
    ("the bell is copper",              "what is the bell like?"),
    ("the frost bites the latch",       "what bites the latch?"),
    ("the lantern is on the shelf",     "where did you put the lantern?"),
]
# Never taught. Subject IS in the inventory (so the organ knows what it is
# talking about) but the relation was never told -- the only case in which the
# organism is licensed to say it does not know.
ABSENT = [("the scarf is on the hook", "what is the scarf like?")]


def build(state_path, electric):
    nl.NeuralLanguage.ELECTRIC_TEACH = electric
    nl.NeuralLanguage.ELECTRIC_ANSWER = electric
    nl.NeuralLanguage.ABSENCE_INVENTORY = electric
    return nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                             TokenizerOrgan(), state_path=state_path)


def main():
    electric = "--control" not in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="electric_"))
    state = tmp / "neural_lang.json"
    print(f"ELECTRIC demo -- {'TREATMENT (flags ON)' if electric else 'CONTROL (flags OFF)'}")
    print(f"state: {state}\n")

    # ---------------- life 1: teach ----------------
    a = build(state, electric)
    for tell, _ in FACTS:
        a.hear(tell, speaker="you")
    for tell, _ in ABSENT:
        a.hear(tell, speaker="you")
    taught = dict(a._taught_says)
    print(f"taught {sum(len(v) for v in taught.values())} facts "
          f"about {len(taught)} subjects: {sorted(taught)}")
    saved = a.save_state(force=True)
    print(f"saved: {saved.get('saved')}")
    del a

    # ---------------- life 2: restart, then ask ----------------
    b = build(state, electric)
    loaded = b.load_state()
    print(f"\nrestart: loaded={loaded.get('loaded')} "
          f"taught_after_load={sum(len(v) for v in b._taught_says.values())}")

    print("\n--- PARAPHRASED QUESTIONS (facts taught in life 1, asked in life 2) ---")
    answered = 0
    for tell, ask in FACTS:
        r = b.answer(ask)
        said = str(r.get("utterance") or r.get("response") or "").strip()
        ok = bool(r.get("spoken")) and said and said != tell
        direct = r.get("source") == "electric_taught"
        answered += 1 if said and said != "" else 0
        print(f"  asked   {ask!r}")
        print(f"  taught  {tell!r}")
        print(f"  answer  {said!r}   [{'DIRECT' if direct else 'routed'}]")
        print()

    print("--- THE FACT WAS NEVER TOLD (must say it does not know) ---")
    knew = 0
    for tell, ask in ABSENT:
        r = b.answer(ask)
        said = str(r.get("utterance") or r.get("response") or "").strip()
        admits = bool(r.get("licensed_refusal")) and bool(r.get("spoken"))
        knew += 1 if admits else 0
        print(f"  asked   {ask!r}")
        print(f"  answer  {said!r}   [{'SAYS IT DOES NOT KNOW' if admits else 'silent/routed'}]")

    print(f"\n=== answered {answered}/{len(FACTS)} paraphrases | "
          f"admits-ignorance {knew}/{len(ABSENT)} ===")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
