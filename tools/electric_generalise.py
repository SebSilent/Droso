r"""ELECTRIC generalisation test: E1's 20 novel facts, asked back in a HELD-OUT
frame, after a real restart.

E1 (tools/teach_episode.py) measured the COST of teaching -- binder displacement --
and scored 2/20 correct. This measures the thing ELECTRIC claims: does a fact taught
once in one sentence come back when asked in words that sentence does not contain,
in a process that never heard it?

REUSES E1'S GENERATOR VERBATIM, deliberately. `generate()` draws content words from
the LIVE vocabulary and filters them with the ORGAN'S OWN closed-class sets
(teach_episode.py:81), verifies absence against the binder's own repeat key (:126),
and gives every fact a novel, semantically ARBITRARY proposition in the frame
'the {a} {v} the {b}'. Writing my own fact list would reintroduce exactly the bug
that file's docstring names -- fly_v2 bred a winner that happened to match a private
vocabulary the generator controlled. The 20 facts here are chosen by code I did not
write, from words the organism already knows, and cannot be guessed from corpus
priors.

ASKS ARE E1'S HELD-OUT FRAMES, not the training frame. Each fact gets one of:
    H1-reverse-role   'what {v} the {b}?'      -> answer is the SUBJECT
    H2-question-word  'which thing does the {a} {v}?'  -> answer is the OBJECT
    H3-passive        'what is {v} by the {a}?'        -> answer is the OBJECT
The training frame 'what does the {a} {v}?' is never asked: an ask that repeats the
tell's own word order tests recall of a sentence, not understanding of a fact.

GRADING IS E1'S, BY ROLE WORD, NOT BY STRING EQUALITY:
    correct         the required role's word is in what it said
    confabulation   a FORBIDDEN role's word is in what it said, and the required one
                    is not -- it answered with the wrong thing
    refusal         it spoke, and said it does not know
    silence         it said nothing
Confabulation is the only category that is worse than silence, so it is counted
separately and never folded into "not answered".

  py -3.10 tools/electric_generalise.py --facts 20 --seed 1
  py -3.10 tools/electric_generalise.py --facts 20 --seed 1 --control
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs import neural_language as nl  # noqa: E402
from connectome.engine import HybridEngine  # noqa: E402
from organs.tokenizer import TokenizerOrgan  # noqa: E402
from connectome.substrate import build_core_graph  # noqa: E402

# E1's generator, imported not copied -- if it changes, this test changes with it.
_spec = importlib.util.spec_from_file_location(
    "teach_episode", ROOT / "tools" / "teach_episode.py")
te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(te)

WORDS = re.compile(r"[a-z]{2,}")


def tokens(text):
    return set(WORDS.findall(str(text or "").lower()))


LIVE = ROOT / "state"


def seed_state(dest_dir: Path) -> Path:
    """Copy the TRAINED organism into a scratch directory.

    E1's generator draws its facts from `lang.word_patterns` and keeps only words the
    binder has postings for (teach_episode.py:116) -- a word with no postings is
    dropped from answer()'s must-set, so teaching with one would measure a refusal
    rather than a memory. A cold organ has 11,555 words and ZERO binder rows, so the
    pool comes back empty and there is no test. The trained state is the only honest
    source of a live vocabulary.

    The cortex sidecars are named after the state file, so the copy keeps the exact
    name `language_state.json`; renaming it silently loses the binder. Everything is
    written into the scratch dir, so live state is never touched.
    """
    import shutil
    for p in LIVE.glob("language_state*"):
        shutil.copy(p, dest_dir / p.name)
    for p in LIVE.glob("*.npz"):
        shutil.copy(p, dest_dir / p.name)
    return dest_dir / "language_state.json"


def build(state_path, electric, load=True):
    """Two flags on, or all three off. ABSENCE_INVENTORY rides with ELECTRIC because
    the licence detector and the taught inventory must agree, and because the control
    arm is the organism as it stood before this work."""
    nl.NeuralLanguage.ELECTRIC_TEACH = electric
    nl.NeuralLanguage.ELECTRIC_ANSWER = electric
    nl.NeuralLanguage.ABSENCE_INVENTORY = electric
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=state_path)
    if load:
        o.load_state()
    return o


def grade(fact, said, spoken):
    """E1's role-word grading. `answer_H` is the word that had to come back;
    `forbid_H` is the word that must NOT come back."""
    got = tokens(said)
    need = fact["answer_H"]
    forbid = [w for w in fact["forbid_H"] if w]
    if not spoken or not said:
        return "silence"
    if need in got:
        return "correct"
    if any(w in got for w in forbid):
        return "confabulation"
    if said.lower().startswith("i don't know"):
        return "refusal"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--control", action="store_true",
                    help="every flag off: the organism as it stood before ELECTRIC")
    ap.add_argument("--keep", action="store_true", help="print every fact")
    args = ap.parse_args()
    electric = not args.control

    tmp = Path(tempfile.mkdtemp(prefix="electric_gen_"))
    state = seed_state(tmp)
    arm = "TREATMENT (ELECTRIC on)" if electric else "CONTROL (all flags off)"
    print(f"ELECTRIC GENERALISATION -- {arm}")
    print(f"{args.facts} novel facts, seed {args.seed}, asked in a HELD-OUT frame "
          f"after a restart\n")

    # ------------------------------------------------ life 1: teach -----------
    a = build(state, electric)
    gen = te.generate(a, args.facts, args.seed)
    facts = gen["facts"]
    print(f"generator: pool {gen['pool_size']} live words, "
          f"{gen['attempts']} attempts, {gen['binder_collisions']} binder collisions")
    for f in facts:
        a.hear(f["tell"], speaker="you")
    taught = sum(len(v) for v in a._taught_says.values())
    print(f"taught {len(facts)} facts; _taught_says holds {taught}")
    saved = a.save_state(force=True)
    print(f"saved: {saved.get('saved')}")
    del a

    # ------------------------------------------------ life 2: restart ---------
    b = build(state, electric)
    loaded = b.load_state()
    rel = sum(len(v) for v in b._taught_says.values())
    print(f"restart: loaded={loaded.get('loaded')} taught_after_load={rel} "
          f"({'PERSISTED' if rel == taught else 'LOST'})\n")

    counts = {"correct": 0, "confabulation": 0, "refusal": 0, "silence": 0,
              "other": 0}
    by_frame = {}
    direct = 0
    rows = []
    for f in facts:
        r = b.answer(f["ask_H"])
        said = str(r.get("utterance") or r.get("response") or "").strip()
        spoken = bool(r.get("spoken"))
        k = grade(f, said, spoken)
        counts[k] += 1
        fr = f["frame_H"].split("-")[0]
        by_frame.setdefault(fr, {"total": 0, "correct": 0, "confabulation": 0,
                                 "refusal": 0, "silence": 0, "other": 0})
        by_frame[fr]["total"] += 1
        by_frame[fr][k] += 1
        is_direct = r.get("source") == "electric_taught"
        direct += 1 if is_direct else 0
        rows.append((f, k, said, is_direct, r))

    print("--- RESULT ---")
    total = len(facts)
    print(f"  correct         {counts['correct']:>3}/{total}")
    print(f"  confabulation   {counts['confabulation']:>3}/{total}   <- worse than silence")
    print(f"  refusal         {counts['refusal']:>3}/{total}")
    print(f"  silence         {counts['silence']:>3}/{total}")
    print(f"  other           {counts['other']:>3}/{total}")
    print(f"  answered from the taught inventory (source=electric_taught): {direct}")
    print(f"\n  by held-out frame:")
    for fr in sorted(by_frame):
        v = by_frame[fr]
        print(f"    {fr}  n={v['total']:>2}  correct {v['correct']:>2}  "
              f"confab {v['confabulation']:>2}  refusal {v['refusal']:>2}  "
              f"silence {v['silence']:>2}  other {v['other']:>2}")

    if args.keep:
        print("\n--- EVERY FACT ---")
        for f, k, said, is_direct, r in rows:
            print(f"[{k:>13}] {'D' if is_direct else ' '} "
                  f"{f['frame_H'].split('-')[0]} {f['ask_H']}")
            print(f"                taught {f['tell']!r}  need {f['answer_H']!r}  "
                  f"said {said[:78]!r}")

    out = ROOT / "docs" / "evidence" / (
        "electric_generalisation_treatment.json" if electric
        else "electric_generalisation_control.json")
    import json
    out.write_text(json.dumps({
        "arm": arm, "seed": args.seed, "facts": total, "counts": counts,
        "by_frame": by_frame, "direct_source": direct,
        "rows": [{"tell": f["tell"], "frame": f["frame_H"], "ask": f["ask_H"],
                  "need": f["answer_H"], "forbid": f["forbid_H"], "kind": k,
                  "said": s, "direct": d, "source": r.get("source"),
                  "stage": r.get("stage")} for f, k, s, d, r in rows],
    }, indent=1), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
