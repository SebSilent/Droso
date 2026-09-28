"""The program-shaped task: stdin in, stdout out, judged by comparison.

WHY THIS EXISTS. Competitive-programming problems are PROGRAMS. The function contract --
`code + "\\n\\n" + check`, where the check calls a function -- cannot represent one, and not
because the check is written badly: the candidate's module-level code executes FIRST, so a
program that reads stdin hits real, empty stdin and dies before any check gets a turn. That
was measured, with a positive control failing while both negative controls passed.

So the shape is carried in the CHECK string as a header plus the tests. One definition, here,
because the ingestion tool and the solver must not each invent their own idea of what a
program task looks like -- every serious bug in this codebase recently has been two functions
disagreeing about the shape of one object.

THE COMPARISON RULE IS DELIBERATE, NOT ACCIDENTAL. Judged token-wise after stripping:

    got.split() == expected.split()

Trailing newlines and trailing spaces are the standard source of false negatives in this
style of judging, and every competitive judge normalises them. Token-wise also ignores
intra-line spacing, which is the right trade for this corpus -- the expected outputs are
whitespace-separated integers and words -- and the wrong trade for anything where layout is
the answer. That is a deliberate choice, recorded here rather than discovered later.
"""
from __future__ import annotations

import json

PREFIX = "#!program-task"


def encode(tests, strict: bool = False) -> str:
    """Tests as a check string. Each test is (stdin_text, expected_stdout).

    `strict=True` marks a problem whose LAYOUT is part of the answer -- a column-padded
    table or grid, where collapsing whitespace would let a flattened answer pass. It is a
    per-problem property, not a change to the general rule: 2 of the 149 admitted problems
    need it, and the other 24 multi-line ones are per-test-case line breaks that judges treat
    as whitespace, so token-wise comparison is faithful for them.
    """
    pairs = [[str(i), str(o)] for i, o in tests]
    body = {"tests": pairs}
    if strict:
        body["strict"] = True
    return PREFIX + "\n" + json.dumps(body)


def decode_meta(text) -> dict:
    """{"tests": [(stdin, expected)], "strict": bool}. Empty tests if not a program task."""
    raw = str(text or "").lstrip()
    if not raw.startswith(PREFIX):
        return {"tests": [], "strict": False}
    try:
        data = json.loads(raw[len(PREFIX):].strip())
    except ValueError:
        return {"tests": [], "strict": False}
    out = []
    for pair in (data.get("tests") or []):
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            out.append((str(pair[0]), str(pair[1])))
    return {"tests": out, "strict": bool(data.get("strict"))}


def is_program_task(text) -> bool:
    return str(text or "").lstrip().startswith(PREFIX)


def decode(text) -> list:
    """[(stdin, expected)] or [] if this is not a program task."""
    raw = str(text or "").lstrip()
    if not raw.startswith(PREFIX):
        return []
    body = raw[len(PREFIX):].strip()
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out = []
    for pair in (data.get("tests") or []):
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            out.append((str(pair[0]), str(pair[1])))
    return out


def outputs_match(got, expected, strict: bool = False) -> bool:
    """The rule above, in one place -- plus the layout-preserving rule where it is needed.

    strict: compare LINE BY LINE, each line's trailing whitespace removed and trailing blank
    lines dropped. That keeps internal spacing and the number of lines, while still tolerating
    the two things that are genuinely presentation and not answer: a line's trailing spaces
    and a final newline. Exact equality would reject correct answers for those.
    """
    if not strict:
        return str(got or "").split() == str(expected or "").split()
    a = [l.rstrip() for l in str(got or "").splitlines()]
    b = [l.rstrip() for l in str(expected or "").splitlines()]
    while a and not a[-1].strip():
        a.pop()
    while b and not b[-1].strip():
        b.pop()
    return a == b
