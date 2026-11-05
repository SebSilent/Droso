"""A prose-coordinate checker at Tier B: it asserts that a citation's RECORDED claim sits at the cited line.

WHAT A PROSE COORDINATE IS. A ledger string that names `some/file.json:1234` inside prose, as opposed to a
structural pointer object `{"file": ..., "line": ...}`. The structural kind is already audited elsewhere; this
tool exists because that audit returns clean on prose by construction -- a wrong line number in a 5,000-line file
is almost always still a valid line number, so a range check cannot see the defect class at all.

WHAT IT CHECKS. For every prose coordinate, the ledger must itself state what the cited line holds -- a "needle".
The needle is taken from a closed list of sources (see NEEDLE_SOURCES). The tool then reads the named file and
asserts the needle appears on the cited line. Verdicts:

    resolves_true      every recorded needle is on the cited line
    content_false      none of them is
    content_partial    some are, some are not
    no_needle          REFUSED: the coordinate carries no recorded claim, so there is nothing to check
    target_missing     the named file does not exist
    line_beyond_end    the cited line is past the end of the file
    non_pointer        declared by a human, in an explicit allowlist, as not a pointer at all

IT DOES NOT AUTHORISE REPAIRING ANYTHING. This is a reporter. It writes no file in report mode -- that is
asserted by hashing every input before and after the walk, not merely intended. The historical coordinates stay
exactly as they are, registered as a measured class. A stale citation is evidence about the state it was written
into, and a mechanical shift turns a false citation into a different false citation that can no longer be checked
against that state.

WHY IT REFUSES INSTEAD OF GUESSING. A coordinate with no recorded needle gets the verdict `no_needle` and nothing
else. The tool will not infer a referent from context, from proximity, or from what the author probably meant,
because a guessed referent is a new false citation wearing a checkmark. The refusal is the point: it converts an
unfalsifiable claim into a visible gap, which is the only honest outcome available for that 38%.

FORWARD ENFORCEMENT, NOT BACKWARD. `--gate PATH` compares the working copy of a ledger against its bytes at HEAD
and fails if a coordinate present now but not then lacks a resolvable needle. Coordinates that already existed at
HEAD are grandfathered by that comparison -- they are reported, never blocked. This is what makes the rule
enforceable without a backfill pass, and it is the reason no historical citation is silently rewritten.

Usage:
    python tools/prose_coordinate_audit.py                 # report over every ledger
    python tools/prose_coordinate_audit.py --json           # same, machine-readable
    python tools/prose_coordinate_audit.py --gate experiments/MP-E12/registration.json
    python tools/prose_coordinate_audit.py --pricing        # the six citations this week's fixes named
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COORD = re.compile(r"(?P<file>[A-Za-z0-9_.\-/\\\\]+?\.(?:json|py|md|txt|csv|jsonl|log)):(?P<line>\d+)")
# LEDGER SHORTHAND. `MP-E10:2538` and `G0-prime:118` are how the plan and these ledgers cite one another. They
# carry no extension, so an extension-required pattern silently misses them -- and the two coordinates the PI
# named as deliberate non-pointers are BOTH shorthand. Supporting them is what puts them in reach of a verdict
# instead of in the blind spot of a regex.
SHORT = re.compile(r"(?P<led>G0-prime|MP-E\d+(?:[abc])?|G[0-6])\s*:\s*(?P<line>\d+)")
SHORT_DIR = {"G0-prime": "experiments/G0-prime/registration.json"}

# Needle sources, in priority order. The list is CLOSED on purpose: a needle the ledger did not record is a
# needle this tool is not allowed to invent.
NEEDLE_SOURCES = (
    "line_reads", "needle", "quote", "quoted_text", "content", "content_claim",
    "cited_as", "text_at_pointer", "plan_line_verbatim", "line_reads_verbatim",
)

# Coordinates that are NOT pointers, declared by a human with a reason. Keyed by (ledger, the citing line's exact
# text, coordinate) so an allowlist entry can never shield the same coordinate when it appears as a real citation
# elsewhere. Nothing here is inferred: an entry exists only because a person read the line and said so.
MP10 = "experiments/MP-E10/registration.json"
NON_POINTERS: list[dict] = [
    # Declared by a human who read the line, not inferred by a pattern. Each entry names the ledger, the
    # coordinate, and the distinctive text that marks its citing line as a QUOTATION rather than a pointer.
    # Auto-repairing any of these would destroy the evidence the sentence exists to carry.
    {"ledger": MP10, "coordinate": "MP-E10:2538", "marker": "PI ruling queue",
     "reason": ("inside the plan's own sentence, preserved verbatim at the plan_line_verbatim key. The coordinate "
                "is the plan's pointer, and the correction's subject is that it went stale -- rewriting it here "
                "would edit the sealed plan extract through the back door")},
    {"ledger": MP10, "coordinate": "MP-E10:4255", "marker": "quoted AS EXAMPLES",
     "reason": "named in this ledger as an example of a pointer that lands on an unrelated line"},
    {"ledger": MP10, "coordinate": "G0-prime:118", "marker": "other two, evidenced",
     "reason": "inside the note enumerating which pointers still resolve and which do not -- evidence, not a route"},
    {"ledger": MP10, "coordinate": "MP-E8:4427", "marker": "other two, evidenced", "reason": "as above"},
    {"ledger": MP10, "coordinate": "MP-E9:2631", "marker": "other two, evidenced", "reason": "as above"},
    {"ledger": MP10, "coordinate": "MP-E8:4388", "marker": "other two, evidenced", "reason": "as above"},
    {"ledger": MP10, "coordinate": "MP-E12:2060", "marker": "other two, evidenced", "reason": "as above"},
    {"ledger": MP10, "coordinate": MP10 + ":3305", "marker": "other two, evidenced",
     "reason": "the range `:3305-3308` is cited to locate a rendering defect being described, not to assert a claim about line 3305"},

    # Quoted AS EXAMPLES on 2026-11-05, in the two blocks that register this tool's own measurement. Same
    # convention as MP-E10:4255 above, and the same reason: the coordinate is the thing being described, not a
    # route the reader should take. Each entry is keyed to its marker, so the phrase has to be on the citing line.
    {"ledger": "experiments/MP-E12/registration.json", "coordinate": "MP-E12/registration.json:2060",
     "marker": "quoted AS EXAMPLES", "reason": "the plan's evidence column, quoted to show what it points at"},
    {"ledger": MP10, "coordinate": "MP-E10:2538", "marker": "quoted AS EXAMPLES",
     "reason": "named as one of the 12 SHORT-form coordinates the earlier audit could not collect"},
    {"ledger": MP10, "coordinate": "G0-prime:118", "marker": "quoted AS EXAMPLES", "reason": "as above"},
    {"ledger": MP10, "coordinate": "MP-E10:3163", "marker": "quoted AS EXAMPLES",
     "reason": "named as the case that produced the self-supplied-needle bug"},

    # The plan's G5 row, quoted verbatim into MP-E12's ledger on 2026-11-05. The row ENDS with its own source
    # pointers, so quoting the plan faithfully necessarily quotes three coordinates. Same handling as the plan's
    # queue sentence in MP-E10: the quote is the evidence, and editing it to satisfy a checker would destroy the
    # thing the correction is about.
    {"ledger": "experiments/MP-E12/registration.json", "coordinate": "MP-E12/registration.json:2060",
     "marker": "BLOCKED on an external input",
     "reason": "inside the plan extract's G5 row, preserved verbatim; the plan's pointer, not this ledger's"},
    # NO entry for the row's other two pointers, and that is deliberate. The evidence column reads
    # `MP-E12/registration.json:2060`, `:1990`, `:1936-1939` -- the last two are bare continuations with no file
    # name, so COORD never collects them and an entry naming them in full form could match nothing. An allowlist
    # line that looks like it shields a coordinate but cannot fire is worse than no line: it advertises coverage
    # that does not exist. The shorthand blind spot is stated in the note instead of papered over here.
]

INLINE_ASSIGN = re.compile(r"\b([A-Z][A-Z0-9_]{2,}(?:\.[A-Za-z_][A-Za-z0-9_]{0,31}){0,2})\s*(?:=|:)\s*"
                           r"(-?\d+(?:\.\d+)?|\"[^\"]{1,60}\"|'[^']{1,60}'|[A-Za-z_][A-Za-z0-9_.\-]{0,40})")
BACKTICK = re.compile(r"`([^`\n]{3,200})`")
CLAIM_VERBS = re.compile(r"\b(reads|holds|says|contains|reads:|states)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def canon(s: str) -> str:
    """Whitespace-insensitive around operators and separators.

    Without this the tool manufactures defects: a ledger that records `LEARN_LR=0.35` about a line reading
    `LEARN_LR = 0.35` was scored ABSENT by the first version, i.e. the matcher's own normalisation was counted as
    a citation error in the ledgers. Spacing is not a claim.
    """
    s = norm(s)
    s = re.sub(r"\s*([=:,])\s*", r"\1", s)
    return s


def ledger_paths() -> list[Path]:
    return sorted(p for p in (ROOT / "experiments").glob("*/registration.json"))


def resolve_target(file_ref: str, citing: Path) -> tuple[Path | None, str]:
    """Resolve a cited path three ways, in a fixed order, and report which one worked."""
    p = (ROOT / file_ref)
    if p.exists():
        return p, "as_written"
    p = (citing.parent / file_ref)
    if p.exists():
        return p, "relative_to_citing_ledger"
    base = Path(file_ref).name
    hits = [q for q in ROOT.rglob(base) if q.is_file() and ".git" not in q.parts and "venv" not in q.parts]
    if len(hits) == 1:
        return hits[0], "unique_basename"
    return None, f"unresolved({len(hits)}_basename_matches)"


def target_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def needles_from_dict(enclosing: dict, coord_text: str) -> list[str]:
    """Rule R1: a sibling key in the enclosing object records the claim. Values only, never guessed keys."""
    out = []
    for k in NEEDLE_SOURCES:
        v = enclosing.get(k)
        if isinstance(v, str) and norm(v) and norm(v) != norm(coord_text):
            out.append(v)
        elif isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str) and norm(x) and norm(x) != norm(coord_text))
    return out


MIN_NEEDLE_CHARS = 12
MIN_NEEDLE_WORDS = 2


def strong_enough(n: str) -> bool:
    """A needle must be a claim, not a word. `said`, `told`, `scent` are not content assertions -- treating them
    as needles turns a refusal into a verdict the evidence does not support, which is the failure this tool
    exists to prevent. Too weak is refused, exactly like absent."""
    w = len(n.split())
    return len(n.strip()) >= MIN_NEEDLE_CHARS or w >= MIN_NEEDLE_WORDS + 2


def needles_from_string(s: str, coord_text: str) -> list[str]:
    """Rules R2 and R3: a claim recorded inline on the citing string.

    R2 takes an `IDENTIFIER = value` fragment sitting in the same clause as the coordinate. R3 takes a backticked
    fragment. Both are literal text the ledger already carries.

    THE COORDINATE MUST NOT BE ALLOWED TO SUPPLY ITS OWN NEEDLE. The first version of this extractor matched
    `MP-E10:3163` as `IDENT = value` and emitted the needle `E10=3163`, which then "failed" against every line
    on earth: the citation was scored false by a fragment of itself. Fragments overlapping the coordinate, or
    whose value is a number appearing inside the coordinate, are discarded.
    """
    out: list[str] = []
    spans = [m.span() for m in COORD.finditer(s)] + [m.span() for m in SHORT.finditer(s)]

    def overlaps(sp):
        return any(a <= sp[0] < b or a < sp[1] <= b for a, b in spans)

    for m in INLINE_ASSIGN.finditer(s):
        if overlaps(m.span()):
            continue
        # Only the SPAN test rejects a self-derived needle. An earlier version also rejected any value whose
        # characters appeared in the coordinate text, which discarded `REPLAY_PASSES_PER_TIER = 2` because the
        # cited line number 4426 contains a "2" -- a guard so blunt it deleted real claims.
        out.append(m.group(0))            # the literal text as the ledger wrote it, not a re-spaced rebuild
    for m in BACKTICK.finditer(s):
        frag = m.group(1)
        if COORD.search(frag) or SHORT.search(frag) or norm(frag) == norm(coord_text) or overlaps(m.span()):
            continue
        if len(frag.split()) <= 25:
            out.append(frag)
    seen, uniq = set(), []
    for n in out:
        if strong_enough(n) and norm(n) not in seen:
            seen.add(norm(n))
            uniq.append(n)
    return uniq


def needles_from_dict_only(enclosing: dict, coord_text: str) -> list[str]:
    """R1 needles are recorded by a key, so they are not subject to the strength floor -- but they must not be a
    copy of the coordinate either."""
    out = []
    for n in needles_from_dict(enclosing, coord_text):
        if norm(n) != norm(coord_text) and coord_text not in n:
            out.append(n)
    return out


def walk(node, trail, acc, enclosing=None):
    """Collect every prose coordinate, carrying the object it lives in so sibling needle keys are available.

    `enclosing` is the dict whose value this string is. A sibling `line_reads` / `needle` / `quote` key is the
    ledger's OWN record of what the cited line holds -- the strongest needle source there is, and the one the
    first version of this tool missed.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, f"{trail}.{k}" if trail else str(k), acc, node)
    elif isinstance(node, list):
        for i, e in enumerate(node):
            walk(e, f"{trail}[{i}]", acc, enclosing)
    elif isinstance(node, str):
        for m in COORD.finditer(node):
            acc.append({"coord": m.group(0), "file": m.group("file"), "line": int(m.group("line")),
                        "site": trail, "string": node, "enclosing": enclosing or {}, "style": "extension"})
        for m in SHORT.finditer(node):
            led = m.group("led")
            f = SHORT_DIR.get(led) or f"experiments/{led}/registration.json"
            acc.append({"coord": m.group(0), "file": f, "line": int(m.group("line")),
                        "site": trail, "string": node, "enclosing": enclosing or {}, "style": "shorthand",
                        "shorthand_for": led})
    return acc


def locate(lines: list[str], rec: dict) -> int | None:
    """Find the physical ledger line holding THIS string, not merely the first line mentioning the coordinate.

    A coordinate like `registration.json:3325` can appear on forty lines; the string it was written inside is
    unique enough to pin the right one. Matching the JSON-escaped value is what makes this exact.
    """
    esc = json.dumps(rec["string"][:120], ensure_ascii=False)[1:-1]
    for i, l in enumerate(lines, 1):
        if rec["coord"] in l and (esc[:60] in l or rec["string"][:60].replace('"', "'") in l):
            return i
    for i, l in enumerate(lines, 1):
        if rec["coord"] in l:
            return i
    return None


def needles_for(rec: dict) -> tuple[list[str], list[str]]:
    """All recorded needles at this site, plus the rule names they came from. Never a guess."""
    needles, rules = [], []
    r1 = needles_from_dict_only(rec["enclosing"], rec["coord"])
    if r1:
        needles += r1
        rules.append("R1_sibling_key")
    r23 = needles_from_string(rec["string"], rec["coord"])
    if r23:
        needles += r23
        rules.append("R2/R3_inline")
    seen, uniq = set(), []
    for n in needles:
        if norm(n) not in seen:
            seen.add(norm(n))
            uniq.append(n)
    return uniq, rules


def collect(text: str, path: Path) -> list[dict]:
    """Every prose coordinate in one ledger, located on a physical line, with the needles recorded at its site."""
    lines = text.splitlines()
    acc = walk(json.loads(text), "", [])
    out, seen = [], set()
    for rec in acc:
        ln = locate(lines, rec)
        key = (rec["coord"], ln, rec["site"])
        if key in seen:
            continue
        seen.add(key)
        rec["ledger_line"] = ln
        try:
            rec["ledger"] = path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            rec["ledger"] = path.as_posix()
        rec["citing_text"] = lines[ln - 1] if ln else ""
        rec["needles"], rec["needle_rules"] = needles_for(rec)
        out.append(rec)
    return out


def classify(rec: dict) -> dict:
    """One coordinate, one verdict. No needle means refusal, never a guess."""
    coord = rec["coord"]
    for a in NON_POINTERS:
        if (a["ledger"] == rec["ledger"] and a["coordinate"] == coord
                and a["marker"] in rec.get("string", "")):
            rec["verdict"] = "non_pointer"
            rec["why"] = a["reason"]
            rec["declared_by_marker"] = a["marker"]
            return rec
    # pass the ledger FILE, not its directory: resolve_target takes .parent itself. Handing it a directory here
    # silently moved the relative-resolution root one level up and turned resolvable basename citations into
    # "ambiguous_basename" -- 15 of them, in the first version of this tool.
    tpath, mode = resolve_target(rec["file"], ROOT / rec["ledger"])
    rec["resolution_mode"] = mode
    if tpath is None:
        # "as written it names no file here" splits in two, and the two need different repairs.
        rec["verdict"] = "ambiguous_basename" if "basename_matches" in mode else "target_missing"
        return rec
    tl = target_lines(tpath)
    if rec["line"] > len(tl):
        rec["verdict"] = "line_beyond_end"
        rec["target_len"] = len(tl)
        return rec
    rec["target_len"] = len(tl)
    rec["line_text"] = tl[rec["line"] - 1].strip()
    needles = rec["needles"]
    if not needles:
        rec["verdict"] = "no_needle"          # REFUSED. Nothing is asserted about truth here.
        rec["refused_because"] = ("the coordinate carries no recorded content claim; this tool does not infer a "
                                  "referent, because a guessed referent is a new false citation wearing a checkmark")
        return rec
    # A needle recorded as one long sentence may quote a line that wraps or reorders. Full-string match is the
    # strong hit; a match on one of its comma/clause fragments is a PARTIAL hit and is reported as such rather
    # than promoted to true or demoted to false. Refusing to collapse that distinction is what keeps the verdict
    # honest: 56 "false" from a matcher this blunt would have been a worse instrument than no instrument.
    line = canon(rec["line_text"])
    full, part = 0, 0
    for n in needles:
        if canon(n) in line:
            full += 1
        else:
            clauses = [canon(c) for c in re.split(r"[,;]| -- | — ", n) if len(canon(c)) >= 12]
            if any(c in line for c in clauses):
                part += 1
    rec["needles_hit"], rec["needles_clause_hit"], rec["needles_total"] = full, part, len(needles)
    if full == len(needles):
        rec["verdict"] = "resolves_true"
    elif full or part:
        rec["verdict"] = "content_partial"
    else:
        rec["verdict"] = "content_false"
    return rec


def report(paths: list[Path]) -> dict:
    # The read-only promise is CHECKED, not asserted: every input is hashed before and after the walk, and a
    # difference means this tool wrote something it was told not to write.
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    allrec = []
    for p in paths:
        for rec in collect(p.read_text(encoding="utf-8"), p):
            allrec.append(classify(rec))
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    counts: dict[str, int] = {}
    for r in allrec:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    modes: dict[str, int] = {}
    for r in allrec:
        modes[r.get("resolution_mode", "not_resolved")] = modes.get(r.get("resolution_mode", "not_resolved"), 0) + 1
    rules: dict[str, int] = {}
    for r in allrec:
        if r["verdict"] == "no_needle":
            rules["no_needle"] = rules.get("no_needle", 0) + 1
        else:
            for x in r.get("needle_rules", ["none"]):
                rules[x] = rules.get(x, 0) + 1
    styles: dict[str, int] = {}
    for r in allrec:
        styles[r.get("style", "?")] = styles.get(r.get("style", "?"), 0) + 1
    return {"total_coordinates": len(allrec), "by_verdict": counts, "by_resolution_mode": modes,
            "by_style": styles, "by_needle_rule": rules,
            "by_ledger": {p.parent.name: sum(1 for r in allrec
                                             if r["ledger"] == p.resolve().relative_to(ROOT).as_posix())
                          for p in paths},
            "nothing_written": before == after, "records": allrec}


def gate(path: Path, before_text: str | None = None) -> tuple[int, list[dict]]:
    """Forward enforcement: a coordinate that is new since HEAD must carry a needle that resolves.

    `before_text` lets a test supply the comparison state directly; when it is None the state is HEAD, which is
    what the write path uses. The comparison is (coordinate, citing line text), so an EDIT to an existing citing
    line re-opens that line's coordinates for checking -- the rule binds the step that touches the sentence, not
    merely the step that first mentions a number.
    """
    if before_text is None:
        head_r = subprocess.run(["git", "show", f"HEAD:{path.as_posix()}"], cwd=str(ROOT),
                                capture_output=True, text=True, encoding="utf-8")
        before_text = head_r.stdout if head_r.returncode == 0 else ""
    before_keys = set()
    if before_text:
        for rec in collect(before_text, path):
            before_keys.add((rec["coord"], norm(rec["citing_text"])))
    bad = []
    for rec in collect(path.read_text(encoding="utf-8"), path):
        if (rec["coord"], norm(rec["citing_text"])) in before_keys:
            rec["grandfathered"] = True
            continue
        c = classify(dict(rec))
        if c["verdict"] not in ("resolves_true", "non_pointer"):
            bad.append(c)
    return len(bad), bad


PRICING = [
    # The six prose coordinates this week's fixes named, each with the claim the fix asserted about it. Recorded
    # here so the tool's value is measured against real defects rather than argued about.
    {"citation": "experiments/MP-E10/registration.json:4426", "claim": "REPLAY_PASSES_PER_TIER = 2"},
    {"citation": "experiments/MP-E10/registration.json:3325", "claim": "rows_moved"},
    {"citation": "experiments/MP-E10/registration.json:3305", "claim": "the floor"},
    {"citation": "experiments/MP-E10/registration.json:3262", "claim": "harness_hashes"},
    {"citation": "experiments/MP-E10/registration.json:2174", "claim": "bytes_worktree"},
    {"citation": "experiments/MP-E10/registration.json:2273", "claim": "the queue"},
]


def pricing() -> dict:
    """Would this tool have caught the six? Answered by running it, not by remembering."""
    rows = []
    for p in PRICING:
        f, ln = p["citation"].rsplit(":", 1)
        tp = ROOT / f
        tl = target_lines(tp)
        text = tl[int(ln) - 1].strip() if int(ln) <= len(tl) else ""
        rec = {"coord": p["citation"], "file": f, "line": int(ln), "ledger": tp,
               "citing_text": "", "string": p["claim"], "needles": [p["claim"]]}
        c = classify(rec)
        rows.append({"citation": p["citation"], "claim_the_fix_asserted": p["claim"],
                     "what_the_line_actually_holds": text[:120],
                     "verdict_with_the_humans_claim": c["verdict"],
                     "would_the_tool_have_had_a_needle_at_write_time": bool(needles_from_string(p["claim"], p["citation"]))})
    return {"the_six": rows, "note": "the claim column is what the fix NEEDED the line to hold; the tool checks it "
                                     "against what the line holds, which is the only honest price signal"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", metavar="LEDGER", help="forward enforcement: fail if a coordinate new since HEAD has no resolving needle")
    ap.add_argument("--pricing", action="store_true", help="run the tool against the six citations this week's fixes named")
    ap.add_argument("--show-refusals", action="store_true")
    a = ap.parse_args()

    if a.gate:
        n, bad = gate(ROOT / a.gate)
        print(f"GATE {a.gate}: {n} new prose coordinate(s) without a resolving needle")
        for b in bad[:20]:
            print(f"  {b['coord']}  verdict={b['verdict']}  at ledger line {b['ledger_line']}")
            print(f"     citing: {b['citing_text'][:130]}")
        return 1 if n else 0

    if a.pricing:
        print(json.dumps(pricing(), indent=2)[:6000])
        return 0

    paths = ledger_paths()
    r = report(paths)
    if a.json:
        Path("experiments/MP-E12/results/prose_coordinate_audit.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"prose coordinates found: {r['total_coordinates']}   nothing_written: {r['nothing_written']}")
    for k, v in sorted(r["by_verdict"].items(), key=lambda x: -x[1]):
        print(f"  {k:22s} {v:4d}  ({100.0*v/max(1,r['total_coordinates']):.1f}%)")
    print("by ledger:", r["by_ledger"])
    if a.show_refusals:
        for x in r["records"]:
            if x["verdict"] in ("content_false", "content_partial", "non_pointer", "ambiguous_basename",
                                "target_missing"):
                print(f"\n  {x['coord']}  [{x['verdict']}]  ledger line {x['ledger_line']}  mode {x['resolution_mode']}")
                print(f"     needles: {x.get('needles')}")
                print(f"     line holds: {x.get('line_text','')[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
