"""E20: read-only cue-construction probe for population (a).

E19 found four failing asks where the correct taught row is resident and a plain
content-word probe query ranks it 1st or 2nd, yet the ask still fails at the recall
gate. E19 could not say why, because it never observed the cue the gate builds.

It turns out the cue is already journaled: `required` IS the gate's `must` list, and
`nearest` is the candidate list that cue retrieved. So this probe needs no new
instrumentation and no organ change -- it reads generation 19 and cross-references
three quantities the harness already recorded:

  * `required`            -- the exact cue terms the gate built for this ask
  * `nearest`             -- what that cue actually retrieved, in rank order
  * `attribution.taught_row` -- the authoritative text of the expected taught row,
                               resolved by E19 from the scripted tells

and answers the question E20 was asked: does the cue OMIT required taught terms, or
INCLUDE them while the row still loses?

It also corrects an E19 error. `nearest_has_taught` was computed with
`startswith("droso:")`, but journal `nearest` entries are bare text with no
who-prefix at all, so that test could never match and its "0" was an artifact. Here
membership is tested by exact string equality against `taught_row`.

Read-only. No brain builds, no organ change, no score, no genome.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
OUT = Path(__file__).with_suffix(".json")

# Question-syntax terms: they appear in the ask but cannot appear in a declarative
# taught tell, so a cue containing them asks the row for words it does not have.
SYNTAX = {"what", "which", "who", "whom", "whose", "where", "when", "why", "how",
          "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
          "done", "the", "a", "an", "of", "by", "in", "on", "at", "to", "for",
          "and", "or", "but", "not", "no", "it", "that", "this", "there", "i",
          "you", "me", "my", "your", "we", "they", "he", "she", "him", "her",
          "say", "said", "tell", "told", "mention", "mentioned", "often", "many",
          "times", "number", "about", "before", "after", "earlier", "last",
          "first", "true", "any", "ever", "left", "name", "thing", "things",
          "one", "both", "all", "than", "with", "held", "bitten"}


def main():
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Correct the E19 prefix bug across the whole journal first.
    alln = [str(n) for r in rows for n in (r.get("nearest") or [])]
    prefix_check = {
        "total_nearest_entries": len(alln),
        "with_droso_prefix": sum(1 for n in alln if n.startswith("droso:")),
        "with_book_prefix": sum(1 for n in alln if n.startswith("book:")),
        "with_any_who_prefix": sum(1 for n in alln if ":" in n.split()[0] if n.split()),
    }

    gate = [r for r in rows
            if r.get("cause_all") == "recall_gate"
            and (r.get("attribution") or {}).get("taught_row")]

    out = {"journal": str(JOURNAL.relative_to(ROOT)),
           "prefix_check": prefix_check,
           "gate_asks_with_known_taught_row": len(gate),
           "asks": [],
           "verdict": {}}

    omit_cue = 0
    include_but_lose = 0
    include_and_retrieve = 0

    for r in gate:
        a = r["attribution"]
        taught = str(a["taught_row"])
        near = [str(n) for n in (r.get("nearest") or [])]
        cue = sorted(str(x) for x in (r.get("required") or []))
        tw = set(taught.split())
        cueset = set(cue)

        in_near = taught in near
        rank = (near.index(taught) + 1) if in_near else None

        taught_in_cue = sorted(tw & cueset)
        taught_not_in_cue = sorted(tw - cueset)
        cue_unmatchable = sorted(cueset - tw)
        cue_unmatchable_syntax = sorted(t for t in cue_unmatchable if t in SYNTAX)
        cue_unmatchable_content = sorted(t for t in cue_unmatchable if t not in SYNTAX)

        # The E20 question: does the cue omit taught terms, or include them?
        # "Omit" means a content word of the taught row is absent from the cue, so
        # the gate never asked for it.
        omits = bool(taught_not_in_cue)
        if omits:
            omit_cue += 1
            verdict = "cue_omits_taught_terms"
        elif in_near:
            include_and_retrieve += 1
            verdict = "cue_includes_and_row_is_retrieved"
        else:
            include_but_lose += 1
            verdict = "cue_includes_but_row_still_loses"

        out["asks"].append({
            "ask": r.get("ask"),
            "coverage": r.get("coverage"),
            "cue_required": cue,
            "taught_row": taught,
            "taught_count": a.get("taught_count"),
            "e19_probe_rank": a.get("taught_rank"),
            "taught_words_in_cue": taught_in_cue,
            "taught_words_omitted_from_cue": taught_not_in_cue,
            "cue_terms_taught_row_cannot_match": cue_unmatchable,
            "of_which_syntax": cue_unmatchable_syntax,
            "of_which_content": cue_unmatchable_content,
            "taught_row_in_gate_nearest": in_near,
            "taught_row_gate_rank": rank,
            "gate_nearest_top3": near[:3],
            "verdict": verdict,
        })

    out["verdict"] = {
        "cue_omits_taught_terms": omit_cue,
        "cue_includes_but_row_still_loses": include_but_lose,
        "cue_includes_and_row_is_retrieved": include_and_retrieve,
    }

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    print("=== E19 prefix-bug correction ===")
    for k, v in prefix_check.items():
        print(f"  {k}: {v}")
    print(f"\n=== gate asks with a known taught row: {len(gate)} ===")
    for rec in out["asks"]:
        print(f"\n  {rec['ask']!r}")
        print(f"    verdict      : {rec['verdict']}")
        print(f"    coverage     : {rec['coverage']}")
        print(f"    cue/required : {rec['cue_required']}")
        print(f"    taught row   : {rec['taught_row']!r} (count {rec['taught_count']}, "
              f"E19 probe rank {rec['e19_probe_rank']})")
        print(f"    taught words IN cue      : {rec['taught_words_in_cue']}")
        print(f"    taught words OMITTED     : {rec['taught_words_omitted_from_cue']}")
        print(f"    cue terms row can't match: {rec['cue_terms_taught_row_cannot_match']}")
        print(f"      syntax : {rec['of_which_syntax']}")
        print(f"      content: {rec['of_which_content']}")
        print(f"    row in gate nearest? {rec['taught_row_in_gate_nearest']} "
              f"(rank {rec['taught_row_gate_rank']})")
        print(f"    gate nearest top3: {rec['gate_nearest_top3']}")

    print(f"\n=== VERDICT TALLY ===")
    for k, v in out["verdict"].items():
        print(f"  {k}: {v}")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
