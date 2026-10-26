"""Re-key the mined fragments by their own vocabulary, not their source's.

The admission keying (admit_primitives.py, 2026-10-25) built each mined
entry's key as signature(src_task) + " mined". That surface is a strict
superset of the source entry's surface, so any query that recalls the source
scores the fragment identically and the margin gate (FUZZY_MARGIN_FLOOR)
reads the pair as a tie: measured on the live store (688), the probe query
"level nest zephyr quixotic" fell from WIN (0.418, no runner) to TIE
(0.410 vs 0.410) the moment the flatten fragment was banked. The fragment
shadowed its own source.

The fix is a re-key, not a matcher change: a procedure's key describes when
to use it, and a fragment has no task wording -- what it honestly owns is
its shape (the miner's kind, one of the six in mine_primitives.py) and its
own code words. So:

    key = signature(kind_phrase + " " + own_code_words)

where own_code_words are the identifiers and string-literal words of the
stored fragment -- params, builtins, the _cN slot names and the mined_*
function name excluded, identifiers split on underscores and camel case so
"isdigit" yields "digit". The superset relation with the source is gone:
the fragment can now win a recall only where its own vocabulary matches,
and the source keeps every query it ever won.

Deterministic, mechanical, and honest about what a fragment is: most of
these keys are jargon no real task uses ("accumulate append temp"), which
is the point -- the corpus either contains the fragment's vocabulary or it
does not, and that is measurable, not decidable by fiat.

Default prints the plan and touches nothing; --apply rewrites the keys in
place (dict key and the record's own "signature" field), after copying the
store to state/_learning_backup_before_rekey.json. Code, task wording,
confidence and counters are untouched; one summary event is appended to the
learning event log.
"""
import argparse
import ast
import builtins
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from organs.learning_loop import signature  # noqa: E402

STORE = Path("state/house_agent_learning.json")
EVENTS = Path("state/house_agent_learning_events.jsonl")
BACKUP = Path("state/_learning_backup_before_rekey.json")

# The six kinds of mine_primitives.py, spelled the way a reader would say
# them. "DP" is two letters and signature() keeps only 4+-character words,
# so it must be spelled out or the kind contributes nothing at all.
KIND_PHRASES = {
    "membership": "membership",
    "accumulate": "accumulate",
    "distinct-selection": "distinct selection",
    "interleave": "interleave",
    "char-shift": "char shift",
    "DP": "dynamic programming",
}

_BUILTINS = frozenset(dir(builtins))
_SLOT = re.compile(r"^_c\d+$")


def _split_ident(name: str) -> list[str]:
    """isdigit -> [is, digit]; char_order -> [char, order]; sdict -> [sdict]."""
    parts = []
    for piece in name.split("_"):
        for m in re.finditer(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+", piece):
            parts.append(m.group(0).lower())
    return parts


def own_words(wrapped: str, params: list[str]) -> set[str]:
    """The vocabulary the fragment itself contains: identifiers it reads or
    writes, attribute names it calls, and words inside its string literals.

    Excluded: the parameters (the caller's names, not the fragment's), the
    builtins (len and range say nothing about when to use this), the _cN
    slot names (admission plumbing), and the mined_* function name (it is
    the source slug -- keeping it would re-import the very vocabulary the
    re-key exists to remove).
    """
    # a parameter is dropped by its parts too: test_str must not yield "test"
    drop = set(_BUILTINS) | {p for name in params
                             for p in _split_ident(name)}
    words: set[str] = set()
    tree = ast.parse(wrapped)
    fn = tree.body[0]
    drop.add(fn.name)                       # mined_write_a_function_...
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            words.update(_split_ident(node.id))
        elif isinstance(node, ast.Attribute):
            words.update(_split_ident(node.attr))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for run in re.findall(r"[A-Za-z]{4,}", node.value):
                words.update(_split_ident(run))   # aeiouAEIOU -> aeiou
    return {w for w in words
            if len(w) >= 4 and not _SLOT.match(w) and w not in drop
            and "mined" not in w}


def mined_key(kind: str, wrapped: str, params: list[str]) -> str:
    phrase = KIND_PHRASES.get(kind)
    if phrase is None:
        raise ValueError(f"unknown kind {kind!r} (not one of the six, §6)")
    words = sorted(own_words(wrapped, params))
    return signature(phrase + " " + " ".join(words))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="rewrite the keys; default reports only")
    ap.add_argument("--store", default=str(STORE))
    args = ap.parse_args()

    state = json.loads(Path(args.store).read_text(encoding="utf-8"))
    store = state["procedures"]
    mined = {k: rec for k, rec in store.items()
             if rec.get("source") == "mined"}
    if not mined:
        print("no mined entries in", args.store)
        return 2

    plan = []
    for key, rec in mined.items():
        wrapped = rec["solutions"][0]["text"]
        params = [a.arg for a in ast.parse(wrapped).body[0].args.args
                  if not _SLOT.match(a.arg)]
        # the kind is not stored on the record; the admission report is its
        # record of provenance, matched by the source task's own wording
        report = json.loads(Path("_tmp/mine_report.json")
                            .read_text(encoding="utf-8"))
        src = next((e for e in report["admitted"]
                    if e["src_task"] == rec["task"]), None)
        if src is None:
            print(f"no report entry for {key!r}; refusing")
            return 2
        new = mined_key(src["kind"], wrapped, params)
        plan.append((key, new, rec, src["kind"], params))

    clash = [new for _, new, *_ in plan if new in store and
             new not in mined]
    dup = len({new for _, new, *_ in plan}) != len(plan)
    print(f"{len(plan)} mined entries:")
    for key, new, rec, kind, params in plan:
        print(f"  {kind:10} {key!r}")
        print(f"        -> {new!r}")
    if clash:
        print("refusing: new keys clash with existing entries:", clash)
        return 2
    if dup:
        print("refusing: two fragments would share one key")
        return 2

    if not args.apply:
        print("\nreport only; pass --apply to rewrite the keys")
        return 0

    shutil.copyfile(args.store, BACKUP)
    rebuilt = {}
    for k, rec in store.items():
        hit = next((p for p in plan if p[0] == k), None)
        if hit is None:
            rebuilt[k] = rec
            continue
        _, new, rec, _, _ = hit
        rec["signature"] = new
        rebuilt[new] = rec          # same position in insertion order
    state["procedures"] = rebuilt
    state["saved"] = round(time.time(), 1)
    Path(args.store).write_text(
        json.dumps({"procedures": rebuilt,
                    "adopted": state.get("adopted", {}),
                    "discarded": state.get("discarded", {}),
                    "min_confidence": state.get("min_confidence", 0.7),
                    "saved": state["saved"]},
                   indent=1, ensure_ascii=False),
        encoding="utf-8")
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": round(time.time(), 3),
                            "kind": "rekey_mined", "n": len(plan),
                            "backup": str(BACKUP)},
                           ensure_ascii=False) + "\n")
    print(f"\napplied: {len(plan)} mined entries re-keyed "
          f"(backup: {BACKUP})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())