"""E21a -- read-only cue-dilution probe.

E20 found the one genuinely new mechanism: the SAME taught row is retrieved at rank 1
by one phrasing and not retrieved at all by another.

    how often does the bell turn?      -> `the copper bell turns twice` at rank 1
    how many times does the bell turn? -> row absent from the gate's nearest

Same row, same stem, different cue. The extra question-framing words (`many`, `times`)
retrieve corpus text about times and crowd the taught row out.

This probe tests, read-only, whether downweighting or removing generic question-framing
terms recovers the row -- and whether doing so moves the GUARDED ask, which is the
condition that killed E12a.

It builds a brain in SCRATCH and replays the scripted tells exactly as the harness does,
then calls the binder's own recall with two cues and compares ranks. It changes no organ
behaviour, no score, no genome, and writes nothing to live state.

Usage:  python docs/evidence/e21a_cue_dilution_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.converse import build  # noqa: E402
from tools.run_generation import SCRATCH  # noqa: E402

JOURNAL = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
HELDOUT = ROOT / "tools" / "scripts_heldout.json"
OUT = ROOT / "docs" / "evidence" / "e21a_cue_dilution.json"

# Generic question-framing terms: closed grammatical/interrogative classes only, no
# content vocabulary. E16a's D4 and E10's Finding 1 both forbid a hand-written
# content-word list; these are function words and interrogatives.
FRAMING = {"what", "which", "who", "whom", "whose", "where", "when", "why", "how",
           "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
           "done", "the", "a", "an", "of", "by", "in", "on", "at", "to", "for",
           "and", "or", "but", "not", "no", "it", "that", "this", "there", "i",
           "you", "me", "my", "your", "we", "they", "he", "she", "him", "her",
           "say", "said", "tell", "told", "mention", "mentioned", "often", "many",
           "much", "times", "time", "number", "about", "before", "after", "earlier",
           "last", "first", "true", "any", "ever", "left", "name", "thing", "things",
           "one", "both", "all", "than", "with"}


def words(s):
    return [w for w in str(s or "").lower().replace("?", " ").replace(",", " ")
            .replace(".", " ").replace("!", " ").split() if w]


def deframe(cue):
    return [w for w in cue if w not in FRAMING and len(w) > 2]


def load_tells():
    raw = json.loads(HELDOUT.read_text(encoding="utf-8"))
    out = {}
    for s in (raw.get("scripts") if isinstance(raw, dict) else raw):
        n = str(s.get("name") or "")
        tells = [t["say"] for t in (s.get("turns") or [])
                 if isinstance(t, dict) and isinstance(t.get("say"), str)]
        for k in (n, n.removeprefix("sel-"), "sel-" + n):
            out.setdefault(k, tells)
    return out


def rank_of(rows, target):
    """1-based rank of `target` (exact token match) in a recall result, else None."""
    tt = set(words(target))
    for i, r in enumerate(rows):
        d = r if isinstance(r, dict) else {}
        rt = set(str(x).lower() for x in (d.get("tokens") or []))
        if rt and rt == tt:
            return i + 1
    return None


def top_texts(rows, n=3):
    out = []
    for r in rows[:n]:
        d = r if isinstance(r, dict) else {}
        out.append(" ".join(str(x) for x in (d.get("tokens") or []))[:64])
    return out


def probe(agent, ask, cue_full, taught, k=200):
    binder = agent.language.cortex.binder
    full = binder.recall(cue_full, k=k) or []
    df = deframe(cue_full)
    de = binder.recall(df, k=k) or [] if df else []
    return {
        "ask": ask,
        "cue_full": cue_full,
        "cue_deframed": df,
        "removed": [w for w in cue_full if w not in df],
        "taught_row": taught,
        "rank_full": rank_of(full, taught),
        "rank_deframed": rank_of(de, taught),
        "n_full": len(full),
        "n_deframed": len(de),
        "top3_full": top_texts(full),
        "top3_deframed": top_texts(de),
    }


def main():
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    tells_by_script = load_tells()

    # The same-row pair E20 identified, plus the guarded ask as the control.
    TARGETS = [
        "how often does the bell turn?",
        "how many times does the bell turn?",
        "where did i say the scarf is?",          # GUARDED -- must not move
        "how often did i say the coat is wet?",
        "what is bitten by the frost?",
    ]
    sel = [r for r in rows if r.get("ask") in TARGETS]
    print(f"journal rows {len(rows)}; targets found {len(sel)}")

    out = {"targets": [], "guarded": None}
    for r in sel:
        ask = r["ask"]
        script = r.get("script")
        attr = r.get("attribution") or {}
        taught = attr.get("taught_row")
        cue = [str(x) for x in (r.get("required") or [])]
        if not taught or not cue:
            print(f"  SKIP {ask!r}: taught_row={taught!r} cue={cue}")
            continue

        tells = tells_by_script.get(script, [])
        if not tells:
            print(f"  SKIP {ask!r}: no tells for script {script!r}")
            continue

        sd = SCRATCH / f"e21a_{abs(hash(ask)) % 10**8}"
        agent = build(sd, project_root=None)
        for t in tells:
            agent.language.hear(t, speaker="you")

        rec = probe(agent, ask, cue, taught)
        rec["script"] = script
        rec["gate_coverage"] = r.get("coverage")
        rec["gate_nearest_top3"] = [str(x)[:64] for x in (r.get("nearest") or [])[:3]]
        rec["pass"] = bool(r.get("pass"))
        rec["recovered"] = (rec["rank_full"] is None and rec["rank_deframed"] is not None)
        rec["moved"] = rec["rank_full"] != rec["rank_deframed"]
        out["targets"].append(rec)
        if "scarf" in ask:
            out["guarded"] = rec

        print(f"\n  {ask!r}  (pass={rec['pass']}, gate cov={rec['gate_coverage']})")
        print(f"    taught row     : {taught!r}")
        print(f"    cue full       : {rec['cue_full']}")
        print(f"    cue deframed   : {rec['cue_deframed']}  removed={rec['removed']}")
        print(f"    rank full      : {rec['rank_full']}  (of {rec['n_full']})")
        print(f"    rank deframed  : {rec['rank_deframed']}  (of {rec['n_deframed']})")
        print(f"    RECOVERED      : {rec['recovered']}   moved: {rec['moved']}")
        print(f"    top3 full      : {rec['top3_full']}")
        print(f"    top3 deframed  : {rec['top3_deframed']}")
        print(f"    gate nearest   : {rec['gate_nearest_top3']}")

    # ---- verdict
    print("\n=== VERDICT ===")
    g = out["guarded"]
    recovered = [t for t in out["targets"] if t["recovered"]]
    print(f"  asks where de-framing RECOVERS the taught row: {len(recovered)}")
    for t in recovered:
        print(f"    + {t['ask']!r}: rank {t['rank_full']} -> {t['rank_deframed']}")
    if g:
        print(f"  GUARDED ask {g['ask']!r}: rank {g['rank_full']} -> {g['rank_deframed']}")
        guard_safe = (g["rank_full"] is not None and g["rank_deframed"] is not None
                      and g["rank_deframed"] <= g["rank_full"])
        print(f"  guarded rank unchanged-or-better: {guard_safe}")
        out["guarded_safe"] = guard_safe
    out["recovered"] = [t["ask"] for t in recovered]
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
