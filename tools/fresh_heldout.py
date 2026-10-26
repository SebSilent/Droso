"""Fresh held-out set: probe for library absence, then baseline.

The set is shaped by the six-kind taxonomy (the same kinds the diagnosis
named) plus outside tasks, but every task is probed against the live library
first: a task whose wording recalls a stored procedure is swapped for its
backup, so the baseline measures generation, not replay. The probe table and
any swaps are recorded in the report. learn=False throughout: nothing banks.

Probe fix 2026-10-25: recall_procedure returns a Recalled object (slots:
confidence, signature, ...), not a dict; the old probe did
`getattr(rec, "data", rec)` and then `.get(...)`, which raised
AttributeError on every real hit and marked seen tasks unseen (the
count_digits/count_upper rows of the first baseline run). The probe now
reads the attributes directly, and a recall probe that *errors* counts as
seen: an unmeasurable freshness check must not wave a task through.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FRESH = [
    {"name": "count_digits", "kind": "membership", "group": "fresh",
     "task": "write a function count_digits(s) counting how many characters "
             "in a string are digits",
     "check": "assert count_digits('a1b2c3') == 3\n"
              "assert count_digits('no digits') == 0\n"
              "assert count_digits('2026') == 4"},
    {"name": "strip_vowels", "kind": "membership", "group": "fresh",
     "task": "write a function strip_vowels(s) returning the string with all "
             "vowels (a, e, i, o, u) removed, case-insensitively, keeping "
             "every other character and its case",
     "check": "assert strip_vowels('hello') == 'hll'\n"
              "assert strip_vowels('XYZ') == 'XYZ'\n"
              "assert strip_vowels('AeIoU') == ''"},
    {"name": "cumulative_max", "kind": "accumulate", "group": "fresh",
     "task": "write a function cumulative_max(items) returning, for each "
             "position, the largest value seen so far, as a list of the same "
             "length",
     "check": "assert cumulative_max([1, 3, 2, 5]) == [1, 3, 3, 5]\n"
              "assert cumulative_max([4]) == [4]\n"
              "assert cumulative_max([]) == []"},
    {"name": "first_unique", "kind": "distinct-selection", "group": "fresh",
     "task": "write a function first_unique(items) returning the first item "
             "that occurs exactly once in the list, or None if there is none",
     "check": "assert first_unique([1, 2, 2, 3, 3]) == 1\n"
              "assert first_unique(['a', 'b', 'b']) == 'b'\n"
              "assert first_unique([7, 7]) is None"},
    {"name": "rarest", "kind": "distinct-selection", "group": "fresh",
     "task": "write a function rarest(items) returning the least frequent "
             "item; if several tie, return the one whose first occurrence "
             "comes first",
     "check": "assert rarest([1, 1, 2, 2, 3]) == 3\n"
              "assert rarest(['a', 'b', 'b', 'a']) == 'a'\n"
              "assert rarest([5]) == 5"},
    {"name": "merge_alternating", "kind": "interleave", "group": "fresh",
     "task": "write a function merge_alternating(a, b) taking elements "
             "alternately from two lists until both are exhausted, appending "
             "any leftovers of the longer list in order",
     "check": "assert merge_alternating([1, 2, 3], ['a', 'b']) == "
              "[1, 'a', 2, 'b', 3]\n"
              "assert merge_alternating([], [1]) == [1]\n"
              "assert merge_alternating([1, 2], []) == [1, 2]"},
    {"name": "caesar", "kind": "char-shift", "group": "fresh",
     "task": "write a function caesar(s, k) shifting each letter k places "
             "later in the alphabet with wraparound, preserving case, leaving "
             "every other character unchanged",
     "check": "assert caesar('abc', 1) == 'bcd'\n"
              "assert caesar('XYZ', 2) == 'ZAB'\n"
              "assert caesar('aB!', 1) == 'bC!'"},
    {"name": "min_coins", "kind": "DP", "group": "fresh",
     "task": "write a function min_coins(amount, coins) returning the fewest "
             "number of coins from the list that sum exactly to amount, or -1 "
             "if impossible; coins may be reused",
     "check": "assert min_coins(6, [1, 3, 4]) == 2\n"
              "assert min_coins(11, [1, 5, 6]) == 2\n"
              "assert min_coins(7, [2, 4]) == -1\n"
              "assert min_coins(0, [1, 2]) == 0"},
    {"name": "is_prime", "kind": "outside", "group": "fresh",
     "task": "write a function is_prime(n) returning True if n is a prime "
             "number, False otherwise",
     "check": "assert is_prime(2) is True\n"
              "assert is_prime(1) is False\n"
              "assert is_prime(97) is True\n"
              "assert is_prime(100) is False"},
    {"name": "transpose", "kind": "outside", "group": "fresh",
     "task": "write a function transpose(rows) transposing a list of "
             "equal-length lists",
     "check": "assert transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]\n"
              "assert transpose([[1]]) == [[1]]\n"
              "assert transpose([[1, 2], [3, 4], [5, 6]]) == "
              "[[1, 3, 5], [2, 4, 6]]"},
    {"name": "validate_parens", "kind": "outside", "group": "fresh",
     "task": "write a function validate_parens(s) returning True if every '(' "
             "in the string is closed by a later ')' in the right order, "
             "False otherwise",
     "check": "assert validate_parens('()()') is True\n"
              "assert validate_parens('(()') is False\n"
              "assert validate_parens(')(') is False\n"
              "assert validate_parens('') is True"},
    {"name": "distance", "kind": "outside", "group": "fresh",
     "task": "write a function distance(p, q) returning the Euclidean "
             "distance between two 2D points given as tuples",
     "check": "assert distance((0, 0), (3, 4)) == 5.0\n"
              "assert distance((1, 1), (1, 1)) == 0.0\n"
              "assert distance((2, 3), (2, 3)) == 0.0"},
]

BACKUPS = {
    "count_digits": [
        {"name": "count_upper", "kind": "membership", "group": "fresh",
         "task": "write a function count_upper(s) counting how many "
                 "characters in a string are uppercase letters",
         "check": "assert count_upper('Hello World') == 2\n"
                  "assert count_upper('abc') == 0\n"
                  "assert count_upper('ABC') == 3"},
        {"name": "mask_digits", "kind": "membership", "group": "fresh",
         "task": "write a function mask_digits(s) replacing every digit with "
                 "'#' and leaving every other character unchanged",
         "check": "assert mask_digits('a1b2') == 'a#b#'\n"
                  "assert mask_digits('abc') == 'abc'\n"
                  "assert mask_digits('') == ''"},
    ],
    "strip_vowels": [
        {"name": "mask_digits", "kind": "membership", "group": "fresh",
         "task": "write a function mask_digits(s) replacing every digit with "
                 "'#' and leaving every other character unchanged",
         "check": "assert mask_digits('a1b2') == 'a#b#'\n"
                  "assert mask_digits('abc') == 'abc'\n"
                  "assert mask_digits('') == ''"},
    ],
    "cumulative_max": [
        {"name": "cumulative_product", "kind": "accumulate", "group": "fresh",
         "task": "write a function cumulative_product(items) returning the "
                 "running product of the list, as a list of the same length",
         "check": "assert cumulative_product([1, 2, 3]) == [1, 2, 6]\n"
                  "assert cumulative_product([4]) == [4]\n"
                  "assert cumulative_product([]) == []"},
    ],
    "first_unique": [
        {"name": "second_smallest", "kind": "distinct-selection",
         "group": "fresh",
         "task": "write a function second_smallest(items) returning the "
                 "second smallest distinct value in the list, or None if "
                 "there are fewer than two distinct values",
         "check": "assert second_smallest([3, 1, 4, 1, 5]) == 3\n"
                  "assert second_smallest([7, 7]) is None\n"
                  "assert second_smallest([2, 1]) == 2"},
    ],
    "rarest": [
        {"name": "mode_value", "kind": "distinct-selection", "group": "fresh",
         "task": "write a function mode_value(items) returning the most "
                 "frequent item; if several tie, return the one whose first "
                 "occurrence comes first",
         "check": "assert mode_value([1, 2, 2, 3]) == 2\n"
                  "assert mode_value(['a', 'b', 'a', 'b']) == 'a'\n"
                  "assert mode_value([5]) == 5"},
    ],
    "merge_alternating": [
        {"name": "spread", "kind": "interleave", "group": "fresh",
         "task": "write a function spread(items, filler) inserting filler "
                 "between every pair of adjacent elements",
         "check": "assert spread([1, 2, 3], '-') == [1, '-', 2, '-', 3]\n"
                  "assert spread([1], '-') == [1]\n"
                  "assert spread([], '-') == []"},
    ],
    "caesar": [
        {"name": "atbash", "kind": "char-shift", "group": "fresh",
         "task": "write a function atbash(s) mapping each letter to its "
                 "mirror in the alphabet (a<->z, b<->y, and so on), "
                 "preserving case, leaving every other character unchanged",
         "check": "assert atbash('abc') == 'zyx'\n"
                  "assert atbash('Za') == 'Az'\n"
                  "assert atbash('a1!') == 'z1!'"},
    ],
    "min_coins": [
        {"name": "climb_stairs", "kind": "DP", "group": "fresh",
         "task": "write a function climb_stairs(n) returning the number of "
                 "distinct ways to climb n stairs taking 1 or 2 steps at a "
                 "time",
         "check": "assert climb_stairs(1) == 1\n"
                  "assert climb_stairs(2) == 2\n"
                  "assert climb_stairs(3) == 3\n"
                  "assert climb_stairs(5) == 8"},
    ],
    "is_prime": [
        {"name": "to_binary", "kind": "outside", "group": "fresh",
         "task": "write a function to_binary(n) returning the binary "
                 "representation of a non-negative integer as a string "
                 "without a leading zero",
         "check": "assert to_binary(5) == '101'\n"
                  "assert to_binary(0) == '0'\n"
                  "assert to_binary(8) == '1000'"},
        {"name": "sum_digits", "kind": "outside", "group": "fresh",
         "task": "write a function sum_digits(n) returning the sum of the "
                 "decimal digits of a non-negative integer",
         "check": "assert sum_digits(123) == 6\n"
                  "assert sum_digits(0) == 0\n"
                  "assert sum_digits(9) == 9"},
    ],
    "transpose": [
        {"name": "word_lengths", "kind": "outside", "group": "fresh",
         "task": "write a function word_lengths(s) returning the length of "
                 "each word in the string, as a list, splitting on spaces",
         "check": "assert word_lengths('a bc def') == [1, 2, 3]\n"
                  "assert word_lengths('') == []\n"
                  "assert word_lengths('hi') == [2]"},
        {"name": "reverse_words", "kind": "outside", "group": "fresh",
         "task": "write a function reverse_words(s) reversing the order of "
                 "the words in the string, single-spaced",
         "check": "assert reverse_words('a b c') == 'c b a'\n"
                  "assert reverse_words('hi') == 'hi'\n"
                  "assert reverse_words('  ') == ''"},
    ],
    "validate_parens": [
        {"name": "sum_digits", "kind": "outside", "group": "fresh",
         "task": "write a function sum_digits(n) returning the sum of the "
                 "decimal digits of a non-negative integer",
         "check": "assert sum_digits(123) == 6\n"
                  "assert sum_digits(0) == 0\n"
                  "assert sum_digits(9) == 9"},
        {"name": "reverse_words", "kind": "outside", "group": "fresh",
         "task": "write a function reverse_words(s) reversing the order of "
                 "the words in the string, single-spaced",
         "check": "assert reverse_words('a b c') == 'c b a'\n"
                  "assert reverse_words('hi') == 'hi'\n"
                  "assert reverse_words('  ') == ''"},
    ],
    "distance": [
        {"name": "to_binary", "kind": "outside", "group": "fresh",
         "task": "write a function to_binary(n) returning the binary "
                 "representation of a non-negative integer as a string "
                 "without a leading zero",
         "check": "assert to_binary(5) == '101'\n"
                  "assert to_binary(0) == '0'\n"
                  "assert to_binary(8) == '1000'"},
        {"name": "word_lengths", "kind": "outside", "group": "fresh",
         "task": "write a function word_lengths(s) returning the length of "
                 "each word in the string, as a list, splitting on spaces",
         "check": "assert word_lengths('a bc def') == [1, 2, 3]\n"
                  "assert word_lengths('') == []\n"
                  "assert word_lengths('hi') == [2]"},
    ],
}


def _rec_dict(rec):
    """recall_procedure returns Recalled (attribute slots) or a dict."""
    if isinstance(rec, dict):
        return rec
    if hasattr(rec, "confidence"):
        return {"confidence": getattr(rec, "confidence", None),
                "task": str(getattr(rec, "signature", ""))[:70]}
    return rec


def probe(solver, task):
    hits = {}
    best = None
    try:
        rec = solver.recall_procedure(task, min_confidence=0.35)
        if rec is not None:
            d = _rec_dict(rec)
            hits["recall"] = {"conf": (d or {}).get("confidence"),
                              "task": str((d or {}).get("task", ""))[:70]}
    except Exception as e:
        hits["recall"] = {"error": f"{type(e).__name__}: {e}"[:80]}
    try:
        best_rec = solver.recall_procedure(task, min_confidence=0.0)
        if best_rec is not None:
            d = _rec_dict(best_rec)
            best = (d or {}).get("confidence")
    except Exception:
        best = None
    hits["best_raw_conf"] = best
    try:
        pats = solver.query_patterns(task) or []
        hits["patterns"] = [{"conf": p.get("confidence"),
                             "key": str(p.get("key", ""))[:50]}
                            for p in pats[:3]]
    except Exception as e:
        hits["patterns"] = [{"error": f"{type(e).__name__}: {e}"[:80]}]
    return hits


def seen(hits):
    rec = hits.get("recall")
    if isinstance(rec, dict):
        if "error" in rec:
            return True  # unmeasurable: treat as seen, never run it
        if rec.get("conf") is not None:
            return True
    pats = hits.get("patterns")
    return bool(pats and isinstance(pats, list) and pats
                and not pats[0].get("error"))


def main():
    from tools.task_battery import _build, run
    router, solver, learning, sb = _build(True)
    store = getattr(learning, "store", {})
    # LearningLoop.store IS the procedures dict (signature -> record); the
    # old .get("procedures") read counted 0, which made no_learn_guard_held
    # a trivial 0 == 0. Provenance-only fix: the probe and the battery run
    # read the store through the solver and were never affected.
    store_before = len(store) if isinstance(store, dict) else 0
    probe_table = {}
    final = []
    for slot in FRESH:
        cands = [slot] + BACKUPS.get(slot["name"], [])
        chosen, table = None, []
        for cand in cands:
            h = probe(solver, cand["task"])
            table.append({"name": cand["name"], "hits": h, "seen": seen(h)})
            if chosen is None and not seen(h):
                chosen = cand
        probe_table[slot["name"]] = table
        if chosen is None:
            print(f"[fresh] {slot['name']}: every candidate seen in library "
                  f"-- slot dropped")
            continue
        if chosen["name"] != slot["name"]:
            print(f"[fresh] {slot['name']}: primary seen in library -> "
                  f"swapped to {chosen['name']}")
        final.append(chosen)
    # The fresh tasks must not be in the battery file either.
    battery_src = (ROOT / "tools" / "task_battery.py").read_text(
        encoding="utf-8")
    for item in final:
        assert f'"{item["name"]}"' not in battery_src, \
            f"{item['name']} already in the battery"
    print(f"[fresh] final set: {len(final)} tasks -> "
          f"{[i['name'] for i in final]}")
    res = run(only=None, learn=False, use_oracle=False, provider="ollama",
              tasks=final)
    store_after = len(store) if isinstance(store, dict) else 0
    report = {"probe": probe_table, "final": [i["name"] for i in final],
              "result": res}
    raw = ROOT / "_tmp" / "fresh_baseline.json"
    raw.write_text(json.dumps(report, indent=1, default=str),
                   encoding="utf-8")
    wrapped = {
        "measured_at": time.time(),
        "script": "tools/fresh_heldout.py",
        "learn": False,
        "use_oracle": False,
        "provider": "ollama",
        "oracle_mode": res.get("oracle_mode"),
        "store_procedures_before": store_before,
        "store_procedures_after": store_after,
        "no_learn_guard_held": store_before == store_after,
        "report": report,
    }
    out = ROOT / "state" / "fitness" / "fresh_baseline.json"
    out.write_text(json.dumps(wrapped, indent=1, default=str),
                   encoding="utf-8")
    print(f"[fresh] report -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())