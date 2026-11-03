"""MP-E8 H3 descriptive observations -- DESCRIPTION ONLY.

Built under PI ruling D-MPE8-04: do not invent a fluency metric. H3 (fluency / open-ended
composition) has no instrument and stays NOT YET MEASURABLE for pass/fail, stated the way MP-E9
stated C4. What this file produces is two descriptive quantities per arm per depth per phase, with NO
threshold attached and no gate that reads them:

  mean_content_words_per_utterance   how much the arm puts into an answer
  type_token_ratio                   how varied what it puts out is

Why they are not a metric: a number with no registered threshold cannot fail, and inventing a
threshold after seeing the observations would be an R2 event wearing the costume of a metric. The
plan's H3 clause "the loss is recorded, not hidden" is satisfied by this record plus the absence of a
pass criterion. Gate G2's go criteria (plan line 690: complete, valid, sealed artifacts at all three
tiers, plus the forgetting/interference/exposure/cost figures) do not mention H3 at all.

Content words are not redefined here. tools/word_provenance.py owns that definition, because R9
grades against it and a second definition of "content word" would make the descriptive figure and the
truthfulness figure disagree by construction.

Run:
  .venv/Scripts/python.exe tools/mp_e8_describe.py --artifact <arm artifact.json> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tools"))

import word_provenance as wp

STATUS = ("DESCRIPTIVE, NON-GATING. No threshold, no pass/fail, not a go criterion. See "
          "experiments/MP-E8/registration.json metrics.H3_descriptive_only (ruling D-MPE8-04).")


def describe_rows(rows):
    said = [r.get("said") or "" for r in rows]
    spoke = [s for s in said if s.strip()]
    toks = [t for s in spoke for t in wp.tokens(s)]
    cw = [len(wp.content_words(s)) for s in spoke]
    return {
        "n_rows": len(rows),
        "n_utterances_nonempty": len(spoke),
        "mean_content_words_per_utterance": round(sum(cw) / len(cw), 4) if cw else None,
        "type_token_ratio": round(len(set(toks)) / len(toks), 4) if toks else None,
        # TTR is length-dependent: a two-word vocabulary repeated twice has TTR 1.0 and a 200-word
        # paragraph has TTR 0.4 without either being "less fluent". Publishing TTR without the token
        # count invites exactly that misreading, so the count travels with it.
        "tokens_total": len(toks),
        "distinct_tokens": len(set(toks)),
        "longest_utterance_tokens": max((len(wp.tokens(s)) for s in spoke), default=0),
    }


def walk_artifact(art):
    """Arm A nests probes[depth][phase] = list; arm B emits the same shape on purpose. Read whichever
    is present rather than trusting a filename."""
    out = {}
    for arm, abody in (art.get("arms") or {}).items():
        probes = abody.get("probes") or {}
        for depth, dbody in probes.items():
            if not isinstance(dbody, dict):
                continue
            for phase, rows in dbody.items():
                if isinstance(rows, dict):
                    rows = list(rows.values())
                if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
                    continue
                out[f"{arm}/{depth}/{phase}"] = describe_rows(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", action="append", required=True,
                    help="one arm artifact per flag; may repeat")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    blocks = {}
    for p in a.artifact:
        art = json.loads(Path(p).read_text(encoding="utf-8"))
        prov = art.get("provenance") or {}
        blocks[p] = {
            "status": STATUS,
            "git_head": prov.get("git_head"),
            "curriculum_sha256": prov.get("curriculum_sha256"),
            "flags_this_arm_ran": (art.get("arms") or {}).get("B", {}).get("arm_provenance", {})
                                  .get("electric_flags") or prov.get("electric_flags"),
            "description": walk_artifact(art),
        }

    doc = {"schema": "droso.mp_e8.description.v1",
           "status": STATUS,
           "gating": False,
           "measures": {
               "mean_content_words_per_utterance":
                   "mean over non-empty utterances of len(content_words(utterance)); content_words is "
                   "tools/word_provenance.py's, the same set R9 grades against",
               "type_token_ratio":
                   "distinct tokens / total tokens over an arm's non-empty utterances, published with "
                   "tokens_total because TTR without a length is unreadable",
           },
           "not_a_metric_because": "no registered threshold exists for either measure and none is "
                                   "being chosen here; H3 remains NOT YET MEASURABLE for pass/fail",
           "artifacts": blocks}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    for p, b in blocks.items():
        cells = list(b["description"])
        print(f"[describe] {p}: {len(cells)} cells, "
              f"e.g. {cells[0] if cells else '-'} -> "
              f"{b['description'][cells[0]]['mean_content_words_per_utterance'] if cells else '-'} "
              f"content words/utterance")
    print(f"[describe] written (NON-GATING description) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
