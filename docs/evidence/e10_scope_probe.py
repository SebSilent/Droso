"""E10 pre-flight probe: with BOTH filters on, does the wanted word win -- and does
the winner clear reply_threshold?

Four builds (~2 min) instead of the 84-build battery, run BEFORE E10 commits to it,
because the pre-registration predicts a specific failure: filtering the pool changes
WHICH word wins but not the scores, `res` is computed once over the full vocabulary,
and E9 measured the wanted words at 0.1221-0.4129 against a 0.55 bar. If that holds
the arm is silent and the battery would only confirm it expensively.

P2 -- `the`, `is`, `on` are ABSENT from the content-scoped pool (the filter engaged).
P3 -- BOTH attractor classes absent at once: corpus (`numbered`/`sold`/`agin`, removed
      by scope) and session function words (removed by content). Neither filter alone
      achieves this; that is the whole E10 hypothesis.
P4 -- the wanted word wins its content-scoped pool.
P7 -- the winner clears reply_threshold, i.e. the organ actually speaks.

Read-only: no core code changed, no live learner state touched, each ask on its own
freshly built brain in SCRATCH.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from organs.neural_language import NeuralLanguage          # noqa: E402
from tools.converse import build                           # noqa: E402
from tools.run_generation import SCRATCH                   # noqa: E402

SELECTION = ROOT / "tools" / "scripts_selection.json"

CASES = [
    ("sel-conjunction-and-absence",
     "name the wet thing that is not on the hook", ["scarf"], True),
    ("sel-conjunction-and-absence",
     "which of them is wet and is not on the hook?", ["scarf"], True),
    ("sel-exact-repeat",
     "repeat after me the copper bell turns twice",
     ["copper", "bell", "turns", "twice"], False),   # rendering-limited, not a target
    ("sel-order-first-last",
     "which thing did i mention earlier than the kettle?", ["lantern"], True),
]

CORPUS_ATTRACTORS = ["numbered", "sold", "agin"]
FUNCTION_WORDS = ["the", "is", "on"]


def scripts_by_name() -> dict:
    d = json.loads(SELECTION.read_text(encoding="utf-8"))
    items = d if isinstance(d, list) else d.get("scripts", [])
    return {s["name"]: s for s in items}


def main() -> None:
    NeuralLanguage.RESONANCE_SESSION_SCOPE = True
    NeuralLanguage.RESONANCE_CONTENT_SCOPE = True
    by_name = scripts_by_name()
    out = []
    for i, (name, ask, wanted, is_target) in enumerate(CASES):
        script = by_name[name]
        sd = SCRATCH / f"e10scope_{name}_{i}"
        if sd.exists():
            shutil.rmtree(sd)
        agent = build(sd, project_root=None)
        lang = agent.language
        assert lang.RESONANCE_SESSION_SCOPE is True
        assert lang.RESONANCE_CONTENT_SCOPE is True

        tells = [t["say"] for t in script["turns"] if "say" in t]
        for say in tells:
            lang.hear(say, speaker="you")

        full = [m for m in lang.word_patterns if lang._speakable(m)]
        session = lang._session_words()
        # What each filter does on its own, so the two halves stay separable.
        lang.RESONANCE_CONTENT_SCOPE = False
        scoped_only = lang._resonance_mates(ask)
        lang.RESONANCE_CONTENT_SCOPE = True
        pool = lang._resonance_mates(ask)

        reply = lang.respond(ask, speaker="you")
        said = reply.get("utterance") or ""

        heard = lang.hear(ask, speaker="you")
        act = heard.get("act") if isinstance(heard, dict) else None
        if act is None:
            act = getattr(lang, "san_act", None)
        res = {m: lang._resonance(m, act) for m in pool}
        ranked = sorted(res.items(), key=lambda kv: -kv[1])
        pos = {w: n + 1 for n, (w, _s) in enumerate(ranked)}
        thr = lang.reply_threshold
        top = ranked[0] if ranked else (None, 0.0)

        row = {
            "script": name,
            "ask": ask,
            "wanted": wanted,
            "is_target": is_target,
            "said": said,
            "source": reply.get("source") or "",
            "spoken": bool(reply.get("spoken")),
            "reason": reply.get("reason"),
            "full_pool": len(full),
            "session_words": len(session),
            "scope_only_pool": len(scoped_only),
            "content_scoped_pool": len(pool),
            # P2 -- the content filter engaged
            "P2_function_words_absent": {w: (w not in pool) for w in FUNCTION_WORDS},
            "P2_pass": all(w not in pool for w in FUNCTION_WORDS),
            # P3 -- both attractor classes gone at once
            "P3_corpus_absent": {a: (a not in pool) for a in CORPUS_ATTRACTORS},
            "P3_pass": (all(a not in pool for a in CORPUS_ATTRACTORS)
                        and all(w not in pool for w in FUNCTION_WORDS)),
            # P4 -- the wanted word wins
            "pool_top5": [[w, round(s, 4)] for w, s in ranked[:5]],
            "argmax": top[0],
            "argmax_score": round(top[1], 4),
            "wanted_rank": {w: pos.get(w) for w in wanted},
            "wanted_score": {w: (round(res[w], 4) if w in res else None) for w in wanted},
            "P4_wanted_wins": bool(ranked and any(w == top[0] for w in wanted)),
            # P7 -- and the winner actually clears the bar, so it speaks
            "reply_threshold": thr,
            "P7_winner_clears_threshold": bool(top[1] >= thr),
            # the pre-registered silence predictor, measured not assumed
            "best_wanted_score": max([v for v in
                                      (round(res[w], 4) for w in wanted if w in res)]
                                     or [0.0]),
        }
        row["predicted_silent"] = (not row["P7_winner_clears_threshold"])
        out.append(row)
        print(json.dumps(row, ensure_ascii=False))
        shutil.rmtree(sd, ignore_errors=True)

    NeuralLanguage.RESONANCE_SESSION_SCOPE = False
    NeuralLanguage.RESONANCE_CONTENT_SCOPE = False

    p = ROOT / "docs" / "evidence" / "e10_scope_probe.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    print("\nwrote", p)

    print("\n=== E10 PRE-FLIGHT VERDICT ===")
    for k in ("P2_pass", "P3_pass", "P4_wanted_wins", "P7_winner_clears_threshold"):
        vals = [bool(r[k]) for r in out]
        print("  %-30s %s  (%d/%d)" % (k, "ALL" if all(vals) else
                                       ("NONE" if not any(vals) else "MIXED"),
                                       sum(vals), len(vals)))
    silent = [r["ask"] for r in out if r["predicted_silent"]]
    print("  predicted silent: %d/%d" % (len(silent), len(out)))
    if all(r["P4_wanted_wins"] for r in out) and not any(
            r["P7_winner_clears_threshold"] for r in out):
        print("\n  ABORT CONDITION 4 MET: the ranking repair works and the score")
        print("  repair cannot -- every winner is below reply_threshold, so the")
        print("  organ stays silent. The battery would only confirm this at 84")
        print("  builds. reply_threshold is the binding constraint and E10 is")
        print("  forbidden from moving it.")


if __name__ == "__main__":
    main()
