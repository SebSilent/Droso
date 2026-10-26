"""Pre-run check for contamination-control script sets: corpus novelty.

The vocabulary gate (check_script_words.py) checks that a script's words
are owned.  It cannot check that the *fact* is corpus-novel: a control
set whose taught facts already sit in the training corpus has a cold
baseline that measures a corpus leak, not absent memory (the
accumulation_fresh flaw: the corpus row "brown coat so that it is all
torn" answers "how is the coat" and leaks "torn").

This gate scans the binder meta for propositions that share two or more
content stems with a single teaching -- a fact-level near-duplicate.
One shared word is not a fact (the corpus owns every script word by the
vocabulary gate's own requirement, so single-word co-occurrence is
inevitable); two shared content stems on one teaching is the taught
fact sitting in the corpus.

A hit means the set's cold baseline is corpus-informed: the set fails
before it runs, with the offending rows on the record.  A hit is
potential, not proven, contamination -- the row must also win recall to
leak, which the cold run itself measures -- so a green cold cell on a
flagged set is luck to be re-examined, not evidence of novelty.

For the seen set (tools/scripts.json) corpus co-occurrence is not a
flaw -- cold is allowed to know the corpus -- so run this gate on
control sets only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.stemming import stem  # noqa: E402

# Function words never count as content (the parser carries its own set
# for the same reason: stemming.STOPWORDS is narrower than needed).
FUNCTION = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "am", "do", "does", "did", "has", "have", "had", "of", "at", "in",
    "on", "to", "so", "that", "it", "its", "as", "and", "or", "but",
    "with", "for", "from", "by", "not", "no", "yes", "he", "she", "they",
    "i", "you", "we", "my", "your", "his", "her", "their", "this",
    "these", "there", "here", "what", "who", "where", "when", "how",
    "why", "which", "all", "will", "would", "can", "could", "just",
    "very", "so",
}


def content_stems(text):
    return {stem(w) for w in re.findall(r"[a-z']+", text.lower())
            if w not in FUNCTION}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scripts", required=True,
                    help="control-set scripts file to check")
    ap.add_argument("--meta",
                    default=str(ROOT / "state"
                                / "language_state.json.cortex.meta.json"),
                    help="binder meta JSON (propositions with tokens)")
    args = ap.parse_args()

    scripts = json.loads(
        Path(args.scripts).read_text(encoding="utf-8"))["scripts"]

    # The meta file is a single-line multi-megabyte JSON: read it with
    # json, never grep (grep silently skips single-line files).
    meta_path = Path(args.meta)
    propositions = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = [(p.get("who", ""), p.get("tokens", ""))
            for p in (propositions.values() if isinstance(propositions, dict)
                      else propositions)]

    contaminated = {}
    for s in scripts:
        teachings = []
        for t in s["turns"]:
            if "say" in t:
                stems = content_stems(t["say"])
                if len(stems) >= 2:
                    teachings.append((t["say"], stems))
        hits = []
        for who, tokens in rows:
            toks = content_stems(" ".join(tokens)
                                 if isinstance(tokens, list) else tokens)
            for say, stems in teachings:
                shared = toks & stems
                if len(shared) >= 2:
                    hits.append((who, tokens if isinstance(tokens, str)
                                 else " ".join(tokens), say, sorted(shared)))
                    break
        if hits:
            contaminated[s["name"]] = hits

    if contaminated:
        for name, hits in contaminated.items():
            print(f"CONTAMINATED {name}: {len(hits)} corpus row(s) share "
                  f"2+ content stems with a teaching:")
            for who, tokens, say, shared in hits[:5]:
                print(f"  {who}: {tokens}")
                print(f"    vs teaching \"{say}\" shared={shared}")
            if len(hits) > 5:
                print(f"  ... and {len(hits) - 5} more")
        raise SystemExit(1)
    print(f"corpus-novel: no proposition shares 2+ content stems with any "
          f"teaching ({Path(args.scripts).name})")
    print(f"scripts: {[s['name'] for s in scripts]}")


if __name__ == "__main__":
    main()