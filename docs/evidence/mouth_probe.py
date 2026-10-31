"""Read-only probe: why does the `mouth` class degrade into word-sampler output?

Generations 9 and 10 both report four `mouth` failures, all with
`source: 'meaning resonance'`, all emitting babble.  The code path is
organs/neural_language.py:3931-4004:

    mates = [m for m in word_patterns if _speakable(m) and m not in exclude]
    best  = max(mates, key=lambda m: _resonance(m, act))
    understands = res[best] >= reply_threshold
    if understands and wants_to:  utterance, source = best, "meaning resonance"

so the utterance is ONE resonance-maximal WORD, optionally extended to two words
by a bigram (:3984-3994) and optionally replaced by a `speak_sentence` chain
(:3998-4004, which appends " + chain" to the source).  This path was never a
sentence generator.

Measured per ask, each on its own freshly built brain in SCRATCH (the same
isolation `run_generation.run_ask` uses), so nothing here writes to the live
learner state and no core code is changed:
  - is the wanted word in `word_patterns` at all          (vocabulary)
  - its resonance RANK and score vs the emitted word      (ranking)
  - `res[best]` against `reply_threshold`                 (how weakly it passed)
  - whether the bigram and the chain fired                (rendering)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # docs/evidence/ -> repo root
sys.path.insert(0, str(ROOT))

from tools.converse import build                       # noqa: E402
from tools.run_generation import SCRATCH               # noqa: E402

SELECTION = ROOT / "tools" / "scripts_selection.json"

# (script, ask, wanted words) — the four `mouth` failures, from gen 9 and gen 10.
CASES = [
    ("sel-conjunction-and-absence",
     "name the wet thing that is not on the hook", ["scarf"]),
    ("sel-conjunction-and-absence",
     "which of them is wet and is not on the hook?", ["scarf"]),
    ("sel-exact-repeat",
     "repeat after me the copper bell turns twice",
     ["copper", "bell", "turns", "twice"]),
    ("sel-order-first-last",
     "which thing did i mention earlier than the kettle?", ["lantern"]),
]


def scripts_by_name() -> dict:
    d = json.loads(SELECTION.read_text(encoding="utf-8"))
    items = d if isinstance(d, list) else d.get("scripts", [])
    return {s["name"]: s for s in items}


def main() -> None:
    by_name = scripts_by_name()
    out = []
    for i, (name, ask, wanted) in enumerate(CASES):
        script = by_name[name]
        sd = SCRATCH / f"mouthprobe_{name}_{i}"
        if sd.exists():
            shutil.rmtree(sd)
        agent = build(sd, project_root=None)
        lang = agent.language

        tells = [t["say"] for t in script["turns"] if "say" in t]
        for say in tells:
            lang.hear(say, speaker="you")

        reply = lang.respond(ask, speaker="you")
        said = reply.get("utterance") or ""
        source = reply.get("source") or ""

        # Ranking diagnostic.  `respond` does not return `act`, so re-present the
        # same text to obtain it; this adds one binder row to a throwaway scratch
        # session and is noted as a caveat rather than hidden.
        heard = lang.hear(ask, speaker="you")
        act = heard.get("act") if isinstance(heard, dict) else None
        if act is None:                       # hear() can return act=None (:452)
            act = getattr(lang, "san_act", None)
        mates = [m for m in lang.word_patterns if lang._speakable(m)]
        res = {m: lang._resonance(m, act) for m in mates}
        ranked = sorted(res.items(), key=lambda kv: -kv[1])
        pos = {w: n + 1 for n, (w, _s) in enumerate(ranked)}

        row = {
            "script": name,
            "ask": ask,
            "wanted": wanted,
            "said": said,
            "said_words": len(said.split()),
            "source": source,
            "chain_fired": source.endswith("+ chain"),
            "reason": reply.get("reason"),
            "spoken": bool(reply.get("spoken")),
            "tells": len(tells),
            "vocabulary": len(mates),
            "reply_threshold": lang.reply_threshold,
            "phrase_threshold": lang.phrase_threshold,
            "max_sentence_words": lang.max_sentence_words,
            "best_resonance": reply.get("best_resonance"),
            "social_drive": reply.get("social_drive"),
            "top5": [[w, round(s, 4)] for w, s in ranked[:5]],
            "argmax_word": ranked[0][0] if ranked else None,
            "argmax_score": round(ranked[0][1], 4) if ranked else None,
            "emitted_is_argmax": bool(said.split()) and said.split()[0] == (
                ranked[0][0] if ranked else None),
            "wanted_in_vocabulary": {w: (w in res) for w in wanted},
            "wanted_rank": {w: pos.get(w) for w in wanted},
            "wanted_score": {w: (round(res[w], 4) if w in res else None)
                             for w in wanted},
        }
        out.append(row)
        print(json.dumps(row, ensure_ascii=False))
        shutil.rmtree(sd, ignore_errors=True)

    p = ROOT / "docs" / "evidence" / "mouth_probe.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    print("\nwrote", p)


if __name__ == "__main__":
    main()
