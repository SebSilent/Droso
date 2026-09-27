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


def encode(tests) -> str:
    """Tests as a check string. Each test is (stdin_text, expected_stdout)."""
    pairs = [[str(i), str(o)] for i, o in tests]
    return PREFIX + "\n" + json.dumps({"tests": pairs})


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


def outputs_match(got, expected) -> bool:
    """The rule above, in one place."""
    return str(got or "").split() == str(expected or "").split()
