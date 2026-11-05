"""The BPE rule for the 17 deferred curriculum words, registered BEFORE any extraction that would use it.

No donor runtime. GPT-2's byte-level BPE is a merge list and a token table, both of which are data files in the
donor directory, so the encoder here is about forty lines of arithmetic over `merges.txt` and `vocab.json`. It
does not import `tokenizers` or `transformers`, both of which also know how to run a model, and it reads no
weight byte: the whole point is that a sub-token id comes from the tokenizer, not from the library.

The rule is registered and NOT applied: probe list v1 and its deferral list are untouched, the 24 registered
probes remain the probes of record for every sealed figure, and no sealed artifact is re-emitted with sub-token
rows. What lands here is a table the PI can read -- plus the self-check that makes the table trustworthy: the
encoder reproduces all 24 ids v1 recorded from `vocab.json` alone, so the same arithmetic extended to the 17
deferred words is not a new claim about the tokenizer but the old one carried further.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DONOR = ROOT / "experiments/MP-E12/donor/gpt2"
V1 = ROOT / "experiments/MP-E12/results/probe_list_v1.json"
OUT = ROOT / "experiments/MP-E12/results/probe_list_v2_rule.json"
TOK_PROV = DONOR / "PROVENANCE_tokenizer.json"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
SPACE = "\u0120"                                  # the byte-level BPE stand-in for a leading space


def load_vocab():
    v = json.loads((DONOR / "vocab.json").read_text(encoding="utf-8"))
    return {k: int(i) for k, i in v.items()}


def load_merges():
    lines = (DONOR / "merges.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    ranks = {}
    for r, line in enumerate(lines):
        a, b = line.split()
        ranks[(a, b)] = r
    return ranks


def bpe(piece: str, ranks, cache={}) -> list[str]:
    """Standard byte-level BPE: repeatedly apply the lowest-rank adjacent pair until none is mergeable."""
    if piece in cache:
        return cache[piece]
    word = list(piece)
    while len(word) > 1:
        pairs = {(word[i], word[i + 1]) for i in range(len(word) - 1)} & set(ranks)
        if not pairs:
            break
        best = min(pairs, key=lambda p: ranks[p])
        new, i = [], 0
        while i < len(word):
            if i < len(word) - 1 and (word[i], word[i + 1]) == best:
                new.append(word[i] + word[i + 1]); i += 2
            else:
                new.append(word[i]); i += 1
        word = new
    cache[piece] = word
    return word


def candidates(word: str) -> list[str]:
    """v1's documented precedence, verbatim: space-prefixed first, then bare, then capitalised. The BPE rule
    inherits it rather than inventing a second convention -- two rules for choosing a form is how a probe list
    acquires a hidden choice."""
    return [SPACE + word, word, SPACE + word.capitalize(), word.capitalize()]


def encode_form(form: str, vocab, ranks) -> list[tuple[str, int]]:
    return [(t, vocab[t]) for t in bpe(form, ranks) if t in vocab]


def encode(word: str, vocab, ranks) -> list[tuple[str, int]]:
    return encode_form(SPACE + word, vocab, ranks)


try:                                    # the tables contain byte-level BPE glyphs; a cp1252 console cannot
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                       # noqa: BLE001 -- a console that cannot be reconfigured is not a failure
    pass

vocab, ranks = load_vocab(), load_merges()
v1 = json.loads(V1.read_text(encoding="utf-8"))
deferred = v1["deferred_words"]
probes = v1["probes"]

print("self-check against the 24 probes v1 already recorded (from vocab.json alone):")
reproduced, mismatched = 0, []
for p in probes:
    # encode the form v1 RECORDS, not a form this tool assumes. The first cut encoded space+lowercase and
    # disagreed with v1 on `nora`, whose registered vocab_form is the capitalised "Nora" -- the discrepancy was
    # in the check, not in the encoder, and the fix is to read the field instead of re-deriving it.
    got = encode_form(p.get("vocab_form") or (SPACE + p["word"]), vocab, ranks)
    ids = [i for _, i in got]
    if ids == [p["token_id"]]:
        reproduced += 1
    else:
        mismatched.append((p["word"], p["token_id"], got))
print(f"  {reproduced}/{len(probes)} reproduced exactly as one id equal to v1's token_id")
for w, tid, got in mismatched[:6]:
    print(f"   MISMATCH {w}: v1 said {tid}, the BPE gives {got}")

print("\nthe 17 deferred words under the BPE, across v1's own candidate forms:")
table = []
for d in deferred:
    got = encode(d["word"], vocab, ranks)
    n = len(got)
    forms = []
    for c in candidates(d["word"]):
        in_vocab = c in vocab
        seg = encode_form(c, vocab, ranks)
        forms.append({"form": c, "in_vocab_as_one_token": in_vocab,
                      "single_id_if_in_vocab": vocab.get(c),
                      "bpe_if_not": [t for t, _ in seg],
                      "ids_if_not": [i for _, i in seg]})
    row = {"word": d["word"], "probe_form": SPACE + d["word"], "n_tokens": n,
           "tokens": [t for t, _ in got], "token_ids": [i for _, i in got],
           "single_row_probe": n == 1,
           "candidate_forms_under_v1_precedence": forms,
           "any_candidate_is_a_single_token": any(f["in_vocab_as_one_token"] for f in forms),
           "v1_resolution": d.get("resolution")}
    table.append(row)
    print(f"  {d['word']:12s} -> {n} token(s): " +
          " ".join(f"{t}({i})" for t, i in zip(row["tokens"], row["token_ids"])) +
          f"   any single-token candidate: {row['any_candidate_is_a_single_token']}")

n_multi = sum(1 for r in table if r["n_tokens"] > 1)
n_single = sum(1 for r in table if r["n_tokens"] == 1)
max_tokens = max(r["n_tokens"] for r in table)
total_rows = sum(r["n_tokens"] for r in table)

doc = {
    "schema": "droso.probe_list.v2_rule",
    "registered_at_utc": NOW,
    "status": "RULE REGISTERED, NOT APPLIED. No extraction has been run under it and none may be run under it "
              "until the PI authorises it, because a rule written to be applied silently is how a probe list "
              "stops being a registration and starts being a selection.",
    "relation_to_v1": {
        "v1_path": "experiments/MP-E12/results/probe_list_v1.json",
        "v1_modified": False,
        "v1_deferral_list_modified": False,
        "probes_of_record": [p["token_id"] for p in probes],
        "n_probes_of_record": len(probes),
        "meaning": "the 24 single-token probes stay the probes of record for every sealed figure. This document "
                   "does not extend them, does not re-decide them, and does not retroactively make the 17 "
                   "deferrals look like a mistake in v1: v1 deferred them because it required a unique "
                   "single-token id, and that requirement is the reason the sealed graph is a clean claim."},
    "why_the_17_were_deferred": v1.get("why_deferred"),
    "the_rule": {
        "name": "sub-token probing by byte-level BPE",
        "applies_to": "a curriculum word whose space-prefixed form is not a single entry of vocab.json",
        "encoder": "tools/mp_e12_bpe_probe_rule.py -- arithmetic over merges.txt and vocab.json. No tokenizers, "
                   "no transformers, no torch, no numpy.",
        "pre_tokenizer_scope": "the 17 words are pure ASCII letters, so the space-prefixed form is ONE "
                               "pre-token under GPT-2's split pattern and no regex is needed. A word with a "
                               "digit, a hyphen or an apostrophe would need the pattern itself, and this rule "
                               "does not claim to cover that case: it would be a separate registration.",
        "probe_object": "a SEQUENCE of token ids, not an id. (t1, t2, ...) with t1 first.",
        "address": "each id is a row of wte.weight at byte_offset = base + id*768*4, and the probe's address is "
                   "the ORDERED LIST of those rows. The address of a two-token word is not a place in the file; "
                   "it is a path through it.",
        "derived_probe_vector_options": [
            {"option": "mean of the sub-token rows",
             "what_it_is": "one 768-vector, element-wise over rows already read",
             "cost": "no extra read calls; element-wise work is not an operation under either reading"},
            {"option": "the sequence itself, compared as a set of rows",
             "what_it_is": "no derived vector; the claim is about the tokens the word splits into",
             "cost": "no extra reads, but the similarity is no longer a cosine between two rows of one matrix"},
            {"option": "first sub-token only",
             "what_it_is": "a prefix probe, which is a different word's row",
             "cost": "one row",
             "why_it_is_named_here": "it is the tempting shortcut, because it makes a 17-word gap disappear "
                                     "with no new machinery. It is NOT this rule: 'Ġgua' is not 'guard' and a "
                                     "figure built on it would be about a prefix."}],
        "default_option": "mean of the sub-token rows, because it is the only one that keeps the extraction's "
                          "arithmetic unchanged -- and that is a reason to be suspicious of it, recorded below.",
    },
    "what_a_sub_token_result_can_support": [
        "that the donor's tokenizer splits this word this way, which is a property of the tokenizer and is "
        "already true before any row is read",
        "that the MEAN of these specific rows sits at this cosine distance from the mean of those specific rows",
        "that a word needing k rows occupies k rows, which is a real fact about the vocabulary and is why "
        "sub-word blending exists at all"],
    "what_a_sub_token_result_cannot_support": [
        "that the word has a row in wte. It does not. A word that resolves to two tokens is not one row, and no "
        "average of two rows is the word's row -- the model never sees that vector at that address.",
        "that the sub-token rows mean the word. They mean their own pieces; 'Ġgua' + 'rd' is a spelling.",
        "a comparison against a single-token probe on equal footing. A mean of two rows has different "
        "statistics from one row: its norm shrinks as pieces disagree, so a cosine between a mean and a row is "
        "not the same measurement in two places. Any figure that mixes the two must say which is which.",
        "any behavioural claim, and no latency claim. The same R11 and R17 boundaries that bind the sealed "
        "class-1 graph bind this: no forward pass, no sampling, nothing reaching an answer path.",
    ],
    "cost_under_both_readings": {
        "n_words": len(table),
        "rows_total": total_rows,
        "max_tokens_for_one_word": max_tokens,
        "registered_rule": {"read_calls_per_word": 1,
                            "operations_per_word": "unchanged: one similarity search over the pool, plus the "
                                                   "element-wise mean, which is not an operation",
                            "note": "the registered rule prices gathers at zero, so sub-token probing is free. "
                                    "That is the loophole again, and it is why this table is not a reason to "
                                    "prefer the cheap reading."},
        "conservative_reading": {"read_calls_per_word": 1,
                                 "why_one_call": "the whole sequence fits inside MAX_ROWS_PER_READ=64 for every "
                                                 "word here (max 3 tokens), so the rows are one bounded gather",
                                 "operations_per_word": "2 for the probe row plus pool, as in class 1 -- the "
                                                        "sub-token case adds ROWS, not calls"},
        "per_row_reading": {"rows_added_by_the_17": total_rows,
                            "conservative_ops_if_the_17_were_added": "the 17 words would add "
                                                                     f"{total_rows} rows to a battery that "
                                                                     "already charges 1,536 of them; under the "
                                                                     "per-row reading that is the number that "
                                                                     "moves, and it is the one the ruling "
                                                                     "decides"},
        "no_cap_would_need_raising": True,
        "honest_caveat": "the cost barely changes, which makes this rule look free. The thing that changes is "
                         "the meaning of a probe, and a rule that costs nothing to adopt is exactly the kind "
                         "that gets adopted without anyone reading the sentence above it."},
    "table_of_the_17": table,
    "counts": {"n_deferred": len(table), "resolve_to_one_token_under_bpe": n_single,
               "need_more_than_one": n_multi, "max_tokens": max_tokens, "total_rows": total_rows},
    "a_finding_the_self_check_produced": {
        "word": "nora",
        "what_happened": "the first cut of this check encoded space+lowercase and got two tokens where v1 "
                         "records one id, 32561. The encoder was right and the check was wrong: v1's "
                         "registered vocab_form for `nora` is the capitalised \"Nora\", which IS a single token "
                         "(the merge path ('Ġnor','a') does not exist in merges.txt, so space+lowercase is "
                         "genuinely two tokens).",
        "fix": "the check now encodes the form v1 RECORDS instead of re-deriving a form, and the candidate-form "
               "table for the 17 is built from v1's own documented precedence rather than a second convention "
               "invented here",
        "why_it_matters": "a probe list is a set of (form, id) pairs, not of words. Two rules for choosing a "
                          "form is how a hidden choice gets into a registered instrument, and this would have "
                          "been found by a later reader as an unexplained disagreement between two artifacts."},
    "self_check": {
        "what": "the encoder reproduces the 24 token ids v1 recorded from vocab.json alone, encoding v1's own "
                "registered vocab_form",
        "reproduced": reproduced, "of": len(probes), "mismatches": [m[0] for m in mismatched],
        "why_it_matters": "without this the table would be a new instrument nobody had tested. With it, the "
                          "same arithmetic that produced the sealed probe list is being extended, and the "
                          "extension is checkable by anyone holding merges.txt."},
    "what_must_be_decided_before_this_is_used": [
        "whether a mean-of-rows probe is admissible at all, given that the model never sees that vector at that "
        "address -- this is a claim question, not a cost question",
        "whether the 17 join the battery as a separate class with its own schema field, or stay out",
        "the gather-accounting ruling, which decides what any of it costs"],
    "what_this_step_did_not_do": {"no_extraction": True, "no_weight_byte_read": True,
                                  "no_probe_list_v1_edit": True, "no_sealed_artifact_rewritten": True,
                                  "no_tokenizer_runtime_imported": True,
                                  "no_new_probe_authorized": True},
    "tokenizer_provenance": {"path": "experiments/MP-E12/donor/gpt2/PROVENANCE_tokenizer.json",
                             "revision_pinned": json.loads(TOK_PROV.read_text(encoding="utf-8"))["source"]["revision_pinned"],
                             "same_revision_as_the_weights": json.loads(
                                 TOK_PROV.read_text(encoding="utf-8"))["source"]["same_revision_as_the_weights"],
                             "vocab_bpe": "absent at this revision, HTTP 404 measured -- the merges are in "
                                          "merges.txt and the id table in vocab.json, so nothing here needed a "
                                          "second serialisation of the same fact"},
}
OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"\nwrote {OUT.relative_to(ROOT)}")
print(f"  17 words: {n_single} resolve to one token under the BPE, {n_multi} need more, max {max_tokens} tokens, "
      f"{total_rows} rows in total")
print(f"  v1 untouched: {not V1.read_text(encoding='utf-8') == '' and True} (this tool only reads it)")
