"""The program execution mode, judged by three controls -- every time it is touched.

A mode that has not been shown to REJECT a wrong answer is worse than no mode: it would admit
a corpus of tasks that can never be checked, which is exactly the failure the previous bridge
turned out to be (a positive control failing while both negative controls passed is what
exposed it).

So these three run against the REAL LocalSolver and REAL Sandbox, on the real execution path:

    a known-correct program   must PASS
    a known-wrong program     must FAIL
    a syntactically broken    must FAIL

The wrong answer here runs cleanly and prints the wrong thing, so it can only be caught by
actually comparing output -- not by an exit code, not by a syntax check.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.program_task import encode, outputs_match                 # noqa: E402

GOOD = "import sys\nn = int(sys.stdin.read().strip())\nprint(n * n)"
WRONG = "import sys\nn = int(sys.stdin.read().strip())\nprint(n + 1)"
BROKEN = "import sys\ndef f(:\n    pass\n"
NOISY = ("import sys\nn = int(sys.stdin.read().strip())\n"
         "print('  %d  ' % (n * n))\nprint()")            # trailing spaces + blank line


def _solver(tmp):
    from organs.sandbox import Sandbox
    from organs.local_solver import LocalSolver
    from organs.language_verifier import LanguageVerifier
    sb = Sandbox(project_root=tmp, workzone=os.path.join(tmp, "wz"),
                 auto_approve_writes=True)
    return LocalSolver(verifier=LanguageVerifier(), sandbox=sb,
                       min_confidence=0.7, trial_floor=0.35)


def test_the_three_controls():
    tmp = tempfile.mkdtemp(prefix="progmode-")
    s = _solver(tmp)
    check = encode([("3\n", "9\n"), ("5\n", "25\n")])

    ok, kind = s._verify_detail(GOOD, check)
    assert ok is True, f"the CORRECT program did not pass: {s._last_verify_error!r}"
    # The same kind a function-mode execution pass returns, so the promotion weights and the
    # harness's branch attribution are identical for both shapes.
    assert kind == "execution", kind

    ok2, _ = s._verify_detail(WRONG, check)
    assert ok2 is False, "the WRONG program passed -- this mode is vacuous"

    ok3, _ = s._verify_detail(BROKEN, check)
    assert ok3 is False, "a syntactically broken program passed"


def test_the_comparison_rule_is_deliberate_not_accidental():
    """Trailing newlines and spaces are the classic false negative in this style of judging.

    The rule is token-wise after stripping, stated in `program_task`, and pinned here so it
    cannot drift into something stricter by accident.
    """
    assert outputs_match("9\n", "9\n")
    assert outputs_match("9", "9\n")
    assert outputs_match(" 9 \n\n", "9")
    assert outputs_match("1 2\n3\n", "1 2 3")
    assert not outputs_match("9", "10")
    assert not outputs_match("", "9")

    tmp = tempfile.mkdtemp(prefix="progmode-")
    s = _solver(tmp)
    ok, kind = s._verify_detail(NOISY, encode([("3\n", "9\n")]))
    assert ok is True and kind == "execution", (ok, kind, s._last_verify_error)
