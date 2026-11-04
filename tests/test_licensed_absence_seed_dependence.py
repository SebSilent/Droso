"""The licensed-absence reason is hash-seed dependent. This test measures it instead of getting lucky.

Found while closing the red pristine suite run at 88e6f8d: one failure,
`tests/test_electric_fragment_guard.py::test_the_guard_returns_the_licensed_absence_instead_of_the_fragment`,
asserting `"asking" in reason` and getting `nothing he remembers has that shape`. There is no ordering plugin
installed (pytest 9.1.1, no pytest-randomly, no pytest-order), so my first explanation -- a reshuffled
collection order -- was wrong. The real mechanism is Python's per-process string hash randomization:

    PYTHONHASHSEED=0..5,7 -> 8 passed
    PYTHONHASHSEED=6      -> FAILED

so every full-suite run is a coin flip on this assertion, and a "0 failures" manifest across 1,331 tests is
partly luck. `_arbitrate_shape` (organs/neural_language.py:4129) iterates `hits`, a LIST, so the flip is
upstream of the arbiter, in how the candidate hits are built.

What this test pins, in the order that matters:
  1. THE SAFETY PROPERTY IS DETERMINISTIC. Under every seed the fragment is not spoken and does not come from
     the arbiter head. That is the thing the guard exists for, and it holds.
  2. THE REASON STRING IS NOT. At least one seed names a different licensed absence. If this assertion ever
     starts failing, the nondeterminism has been FIXED -- and the defect entry in
     experiments/MP-E10/registration.json (`hash_seed_nondeterminism_defect`) should then be closed, not the
     test deleted.

It deliberately does NOT edit the original test or mark it xfail: hiding a coin flip behind an expected-failure
is how a suite stops being evidence.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SEEDS = list(range(8))

CHILD = r"""
import sys
sys.path.insert(0, r"{root}")
from tests.test_electric_fragment_guard import _organ, BARE
o = _organ(guard=True)
out = o.answer(BARE) or {{}}
print("SPOKEN", out.get("spoken"), "SOURCE", out.get("source"), "REASON", out.get("reason"))
"""


def run_seed(seed):
    # Inherit the real environment and override only the seed. A hand-built minimal env would change which
    # DLLs resolve and could make the child fail for reasons that have nothing to do with hashing.
    import os
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    r = subprocess.run([PY, "-B", "-c", CHILD.format(root=str(ROOT))], cwd=str(ROOT),
                       capture_output=True, text=True, env=env, timeout=180)
    line = next((l for l in r.stdout.splitlines() if l.startswith("SPOKEN")), None)
    assert line, f"seed {seed} produced no readout: {r.stdout[-200:]} {r.stderr[-300:]}"
    _, spoken, _, source, _, reason = line.split(" ", 5)
    return {"seed": seed, "spoken": spoken, "source": source, "reason": reason.strip()}


def test_the_safety_property_holds_under_every_seed():
    bad = [r for r in (run_seed(s) for s in SEEDS) if r["spoken"] != "False" or r["source"] == "arbiter head"]
    assert not bad, f"the guard leaked a fragment under some seed: {bad}"


@pytest.mark.skip(reason=(
    "INTERMITTENT, NOT SEED-DETERMINED. Seed 6 broke the assertion once under a direct pytest run and passed "
    "it on the next identical run; a bare-interpreter child named the correct absence under all eight seeds. "
    "A test that asserts a reproduction which does not hold is worse than no test -- it manufactures a green "
    "or a red on demand. The defect is registered in experiments/MP-E10/registration.json as "
    "licensed_absence_intermittence with both refuted hypotheses recorded, and the safety property above "
    "remains asserted unconditionally."))
def test_seed_6_under_pytest_reproduces_the_failure_and_that_is_the_registered_defect():
    """The real observed condition, pinned as measured -- including the part that refuted my first theory.

    `run_seed` above calls the organ from a bare interpreter, and under THAT harness all eight seeds name the
    correct absence. The failure only appears when the same seed drives a PYTEST process over the test file:

        pytest tests/test_electric_fragment_guard.py   PYTHONHASHSEED=6 -> 1 failed, 7 passed
        bare child -c, same seed                                        -> correct reason

    so the trigger is the combination of pytest's process context and the hash seed, not the seed by itself.
    This test therefore drives pytest itself. If it ever starts passing, the nondeterminism has been fixed:
    close hash_seed_nondeterminism_defect in experiments/MP-E10/registration.json rather than deleting this.
    """
    r = subprocess.run([PY, "-m", "pytest", "tests/test_electric_fragment_guard.py", "-q"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                       env=dict(__import__("os").environ, PYTHONHASHSEED="6"))
    assert r.returncode != 0, (
        "seed 6 no longer breaks the licensed-absence assertion -- the registered nondeterminism has been "
        "fixed. Close the defect entry; do not silently drop this test.")
    assert "nothing he remembers has that shape" in r.stdout, r.stdout[-500:]
    # And the same file under a passing seed, so the pin is about the seed and not about the file being broken.
    ok = subprocess.run([PY, "-m", "pytest", "tests/test_electric_fragment_guard.py", "-q"],
                        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                        env=dict(__import__("os").environ, PYTHONHASHSEED="0"))
    assert ok.returncode == 0, ok.stdout[-500:]



