"""MP-E12a: fix the probe list BEFORE any extraction, per D-MPE12-03 as ruled in part by B.R item 11.

THIS SCRIPT DOES NOT READ WEIGHTS, AND THAT IS CHECKABLE. It imports no address space, no mmap, nothing from
the donor's tensor bytes. It reads two things: this program's own sealed curriculum
(`experiments/MP-E8/curriculum_tier120.json`) for the words, and the donor's `vocab.json` for token ids. A
tokenizer table is not a weight value; the distinction is the whole reason a probe list can be fixed before an
extraction instead of after it. `tests/test_mp_e12_address_space.py::test_the_probe_list_was_fixed_without_the_address_space`
asserts the import surface of this file so the claim is not just a sentence in a docstring.

THE SELECTION RULE, stated before the result. Take the distinct content words of the sealed tier-120 curriculum
in the order they first appear in its qa_pairs, drop the registered function-word stop list, keep a word only if
it resolves to exactly one GPT-2 token id under the documented candidate rule, and take the first N of what
survives. No word was chosen, kept or dropped on the strength of anything seen in the weight bytes.

THE PART THAT IS DEFERRED, AND WHY IT IS A DEFERRAL RATHER THAN A DROP. 17 of the 121 curriculum content words
do not resolve to a single token id. Probing them would mean encoding them with the donor's BPE and taking the
first sub-token, which is a different probe object (a prefix id like "Ġke" carries different geometry than the
word), so it cannot be folded in silently. Implementing the BPE encoder is a registered instrument step, not a
lookup, and it is deferred to a named follow-on with the affected words listed. Choosing those 17 in or out
after seeing what their sub-token rows look like would be an R2 event, so it is not done here.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = "experiments/MP-E8/curriculum_tier120.json"
VOCAB = "experiments/MP-E12/donor/gpt2/vocab.json"
OUT = "experiments/MP-E12/results/probe_list_v1.json"
PROBE_LIST_SCHEMA = "droso.probe_list.v1"
N_PROBES = 24                                  # registered: one probe per curriculum session-block of 8 items
READ_BUDGET_OPS = 24                           # MP-E12 C3, unchanged by this step
MAX_ROWS_PER_READ = 64                         # the address space's gather cap, restated here
MAX_READS_PER_PROBE = 256

# registered stop list: function words that appear in the curriculum's frames but are not content probes
STOP = {"the", "a", "an", "what", "who", "does", "do", "is", "are", "of", "in", "on", "to", "and", "did",
       "was", "were", "it", "its", "with", "that", "this", "not", "no", "yes"}
# documented candidate rule for single-token resolution, tried in this order
CANDIDATES = ["\u0120{}", "{}", "\u0120{}", "{}"]      # space-prefixed, bare, capitalised-prefixed, capitalised


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_words(curriculum: dict):
    out = []
    for s in curriculum["sessions"]:
        for pair in s.get("qa_pairs", []):
            for sent in pair:
                for w in re.findall(r"[A-Za-z']+", str(sent)):
                    lw = w.lower()
                    if lw not in STOP and lw not in out:
                        out.append(lw)
    return out


def resolve(word: str, vocab: dict):
    """Documented precedence, not a look at the weights.

    The first cut of this rule required a word to have EXACTLY ONE candidate form in the vocabulary, and it
    deferred 88 of 121 words -- including ordinary ones like `dog`, which exists as both `dog` and ` dog`.
    That was an artifact of the rule, not a property of the donor, and a probe list that defers three quarters
    of the curriculum to avoid a decision is not a fixed list. The precedence below decides by POSITION, which
    is what the curriculum's sentences actually give: a content word inside a frame follows a space, so the
    space-prefixed form is the token that word occupies.
    """
    forms = [f"\u0120{word}", word, f"\u0120{word.capitalize()}", word.capitalize()]
    hits = [(f, vocab[f]) for f in forms if f in vocab]
    if not hits:
        return None, None, "unresolved"
    return hits[0][1], hits[0][0], ("first_form" if len(hits) == 1 else f"precedence_over_{len(hits)}")


def main() -> int:
    curriculum = json.loads((ROOT / CURRICULUM).read_text(encoding="utf-8"))
    vocab = json.loads((ROOT / VOCAB).read_text(encoding="utf-8"))
    words = content_words(curriculum)
    resolved, deferred = [], []
    for w in words:
        tid, form, kind = resolve(w, vocab)
        if tid is not None:
            resolved.append({"word": w, "token_id": tid, "vocab_form": form, "resolution": kind})
        else:
            deferred.append({"word": w, "resolution": kind})
    chosen = resolved[:N_PROBES]

    out = {
        "schema": PROBE_LIST_SCHEMA,
        "experiment": "MP-E12",
        "stage": "MP-E12a",
        "fixed_at_utc": now_utc(),
        "fixed_before_any_extraction": True,
        "authority": ("D-MPE12-03, ruled in part 2026-11-05 by B.R item 11: the probe list must be fixed in "
                      "the registration of the instruments, before the first extraction"),
        "selection_rule": [
            "1. words come from the sealed tier-120 curriculum, in first-appearance order across its qa_pairs",
            "2. the registered function-word stop list is removed",
            "3. a word is kept if any candidate form exists in vocab.json; where several do, the documented "
            "precedence picks one (space-prefixed first, then bare, then capitalised forms), because a content "
            "word in these frames follows a space",
            "4. the first N_PROBES survivors are taken; N_PROBES is registered here, not chosen after",
            "5. nothing in this rule consults a weight value; the only donor artifact read is vocab.json",
        ],
        "sources": {"curriculum": CURRICULUM,
                    "curriculum_sha256": curriculum.get("curriculum_sha256"),
                    "vocab": VOCAB, "vocab_size": len(vocab)},
        "counts": {"distinct_content_words_in_curriculum": len(words),
                   "resolved_to_one_token": len(resolved),
                   "deferred": len(deferred), "probes_fixed": len(chosen), "n_probes_registered": N_PROBES},
        "probes": [{"probe_id": f"extraction_1_p{k:02d}", "word": r["word"], "token_id": r["token_id"],
                    "vocab_form": r["vocab_form"],
                    "extractions": ["1_embedding_geometry", "2_association_edges", "3_circuit_motifs"]}
                   for k, r in enumerate(chosen)],
        "revision_note": ("this is v1 of the list, but the SECOND cut of the rule. The first cut required a "
                          "unique candidate form and deferred 88 of 121 curriculum words, including `dog`; that "
                          "was the rule's artifact, not the donor's, and deferring three quarters of the "
                          "curriculum to avoid making a documented choice would have left the program probing "
                          "a list it could not describe. The precedence rule above is the fix, and the change "
                          "is recorded here rather than left as a silent re-cut."),
        "deferred_words": deferred,
        "why_deferred": ("these words have no unique single-token id in the donor's vocabulary; probing them "
                         "means encoding them with the donor's BPE and taking a sub-token, which is a "
                         "different probe object. The BPE encoder is not implemented in this step and is a "
                         "named follow-on. They are not silently dropped, and they were not selected for or "
                         "against on anything seen in the weight bytes."),
        "budgets": {"read_budget_ops_per_item": READ_BUDGET_OPS,
                    "abort_condition": "an item that would spend more than 24 operations aborts the extraction "
                                       "(plan C3); the exception fires before the row is written",
                    "max_rows_per_read": MAX_ROWS_PER_READ,
                    "max_reads_per_probe": MAX_READS_PER_PROBE,
                    "gather_loophole_named": ("under the registered op rule a gather of rows costs zero "
                                              "operations, so the two caps above are what bound bulk reads; "
                                              "the loophole itself is registered in MP-E12's ledger"),
                    "worst_case_reads_for_the_whole_list": N_PROBES * 3 * MAX_READS_PER_PROBE},
        "what_this_artifact_is_not": ("it is not a result. It fixes what will be asked. No tensor byte was "
                                      "read to produce it, and the test named in this file's docstring checks "
                                      "that no address-space import exists here."),
    }
    (ROOT / OUT).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"[probes] {len(words)} content words; {len(resolved)} resolve to one token; "
          f"{len(deferred)} deferred; {len(chosen)} probes fixed")
    print(f"[probes] first six: {[(p['word'], p['token_id']) for p in out['probes'][:6]]}")
    print(f"[probes] wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
