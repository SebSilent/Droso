"""MP-E10 ITEM 2: the licensed-absence hunt -- estimate the flip rate, with its n, without touching the answer path.

THE DEFECT, AS RECORDED (experiments/MP-E10/registration.json, key `licensed_absence_intermittence`, status
"OPEN -- NAMED, NOT CLOSED"): `tests/test_electric_fragment_guard.py::
test_the_guard_returns_the_licensed_absence_instead_of_the_fragment` fails intermittently -- the guard returns
a licensed absence, but WHICH absence it names moves. The assertion at tests/test_electric_fragment_guard.py:89
is `assert "asking" in str(out.get("reason"))` and the observed failure value was 'nothing he remembers has
that shape'. The safety property (`spoken is False`, `source != "arbiter head"`) held in every observation, so
this is a movement in a reason string, not a leak.

WHY A HUNT AND NOT A FIX: the fix edits the answer path, which published sealed evidence quotes, so it needs a
PI ruling; an agent edit is not authorised by the release that bought this run. What IS purchasable is the
rate. Two hypotheses were already tested and refuted (ordering -- no ordering plugin exists; PYTHONHASHSEED
alone -- a seed that failed once did not fail on the identical command next attempt). This tool therefore
measures the thing nobody has measured: how often it flips, over how many independent process contexts.

DESIGN, priced by the brief (docs/mp_e10_pi_decision_brief_consolidated.md:279-281, unit cost measured 12.6 s):
  * N repetitions of `pytest tests/test_electric_fragment_guard.py` as separate PROCESSES, because the defect
    is process-context-dependent and an in-process loop would measure a different thing;
  * PYTHONHASHSEED rotated deterministically over a fixed list so "varied seeds and contexts" is a property of
    the design rather than an accident of the machine;
  * every repetition records its own seed, exit code, wall-clock and the reason string pytest printed, so the
    flip is counted from output, not inferred from a return code alone;
  * a repetition whose failure is NOT the licensed-absence assertion is counted separately -- a run that
    mistakes some other failure for the flip is exactly the manufactured red this entry warns against.

Wilson 95% score interval is computed for the rate; with zero flips the artifact reports the rule-of-three
upper bound instead, which is the honest statement of "not observed in n".

USAGE
  py tools/mp_e10_licensed_absence_hunt.py --reps 200
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TEST_FILE = "tests/test_electric_fragment_guard.py"
TARGET_TEST = "test_the_guard_returns_the_licensed_absence_instead_of_the_fragment"
OUT_DEFAULT = "experiments/MP-E10/results/licensed_absence_flip_hunt.json"
SEEDS = ["0", "1", "2", "3", "4", "5", "6", "7"]
ASSERT_MARK = re.compile(r"assert\s+[\"']asking[\"']\s+in", re.I)
REASON_MARK = re.compile(r"AssertionError:\s*(.+)", re.I)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a proportion. Exact for k=0 it degenerates, so the caller also gets
    the rule-of-three bound; both are reported rather than one being chosen to look better."""
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = (z / den) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(max(0.0, centre - half) * 100, 4), round(min(1.0, centre + half) * 100, 4)]


def classify(out: str, rc: int):
    """Was THIS failure the licensed-absence flip? Decided from the printed assertion, not from rc.

    The reason is taken from the lines AROUND the matched assertion, not from the first `AssertionError:` in
    the output: if some other test in the file fails first, a whole-output search would attribute its message
    to the flip. The failure block is also kept verbatim, so a later reader can see what the guard actually
    said instead of trusting this parser.
    """
    if rc == 0:
        return "pass", None, None
    lines = out.splitlines()
    hit = next((i for i, ln in enumerate(lines) if ASSERT_MARK.search(ln)), None)
    if hit is None:
        return ("other_failure" if "failed" in out else "error"), None, None
    # Search FORWARD from the matched assertion first. The synthetic check caught the backward-only case:
    # when another test fails earlier in the same file, its `AssertionError:` line sits a few lines above ours
    # and would be attributed to the flip. The mixed case now reads our own message.
    after = lines[hit: hit + 6]
    before = lines[max(0, hit - 4): hit]
    reason = next((REASON_MARK.search(ln).group(1).strip() for ln in after if REASON_MARK.search(ln)),
                  next((REASON_MARK.search(ln).group(1).strip() for ln in before if REASON_MARK.search(ln)),
                       "(assertion fired, reason not parsed)"))
    window = before + after
    return "flip", reason, "\n".join(x.strip() for x in window)[:600]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args()
    out_p = ROOT / a.out
    if out_p.exists():
        print(f"REFUSED: {a.out} exists. A sealed artifact is never overwritten (R5).", file=sys.stderr)
        return 3

    t_all = time.time()
    reps = []
    reasons = Counter()
    kinds = Counter()
    print(f"[hunt] {a.reps} repetitions of {TEST_FILE} in separate processes, "
          f"PYTHONHASHSEED rotated over {SEEDS}", flush=True)
    for i in range(a.reps):
        seed = SEEDS[i % len(SEEDS)]
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        t0 = time.time()
        r = subprocess.run([PY, "-m", "pytest", TEST_FILE, "-q", "-p", "no:cacheprovider", "--tb=short"],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        dur = round(time.time() - t0, 2)
        blob = (r.stdout or "") + (r.stderr or "")
        kind, reason, excerpt = classify(blob, r.returncode)
        kinds[kind] += 1
        if reason:
            reasons[reason] += 1
        reps.append({"rep": i + 1, "pythonhashseed": seed, "rc": r.returncode, "seconds": dur,
                     "kind": kind, "reason_observed": reason, "failure_excerpt": excerpt,
                     "output_sha256": hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:16],
                     "summary_line": next((ln.strip() for ln in reversed(blob.splitlines())
                                           if re.search(r"\d+ (passed|failed)", ln)), "")})
        if kind == "flip":
            print(f"[hunt] rep {i + 1} (seed {seed}) FLIP -> {reason!r}  [{dur} s]", flush=True)
        elif (i + 1) % 20 == 0:
            print(f"[hunt] rep {i + 1}/{a.reps}: {dict(kinds)}  (last {dur} s)", flush=True)

    k = kinds["flip"]
    n = a.reps
    rate = k / n * 100.0
    ci = wilson(k, n)
    per_seed = {}
    for s in SEEDS:
        sub = [r for r in reps if r["pythonhashseed"] == s]
        per_seed[s] = {"reps": len(sub), "flips": sum(1 for r in sub if r["kind"] == "flip")}
    durs = sorted(r["seconds"] for r in reps)
    unit = {"min": durs[0], "median": durs[len(durs) // 2], "max": durs[-1],
            "mean": round(sum(durs) / len(durs), 2),
            "priced_unit_cost_seconds": 12.6,
            "priced_source": "docs/mp_e10_pi_decision_brief_consolidated.md:279-281 (measured this session, "
                             "not from a sealed artifact)"}

    out = {
        "experiment": "MP-E10",
        "item": "ITEM 2 -- the licensed-absence hunt: flip rate with its n",
        "generated_at_utc": now_utc(),
        "authorised_by": "PI release of the hold, 2026-11-05, priced exactly as the brief sets it",
        "what_was_measured": ("the proportion of independent process contexts in which the guard names a "
                              "licensed absence OTHER than the ask-licensed-absence the test asserts"),
        "test_under_repetition": {"file": TEST_FILE, "function": TARGET_TEST,
                                  "assertion_line": 89,
                                  "assertion": "assert \"asking\" in str(out.get(\"reason\"))"},
        "design": {"repetitions": n, "one_process_per_repetition": True,
                   "pythonhashseed_rotation": SEEDS,
                   "rotation_rule": "rep i uses SEEDS[i % 8], so every seed gets the same number of contexts",
                   "command": f"{PY} -m pytest {TEST_FILE} -q -p no:cacheprovider --tb=short",
                   "why_separate_processes": "the defect is process-context-dependent; an in-process loop "
                                             "would measure a different quantity"},
        "result": {
            "flips_observed": k,
            "n": n,
            "flip_rate_percent": round(rate, 4),
            "wilson_95_percent_interval": ci,
            "rule_of_three_upper_bound_percent": round(3.0 / n * 100, 4) if k == 0 else None,
            "passes": kinds["pass"],
            "failures_that_are_NOT_the_flip": kinds["other_failure"],
            "harness_errors": kinds["error"],
            "distinct_reason_strings_observed_on_flip": dict(reasons),
            "per_seed": per_seed,
            "safety_property_note": ("a flip is a change in WHICH licensed absence is named. `spoken is "
                                     "False` and `source != 'arbiter head'` are asserted at lines 87-88, "
                                     "BEFORE the reason assertion at line 89; if either of those had failed "
                                     "the failure would be classified here as other_failure, not flip, "
                                     "because the assertion that fired would not be the reason assertion."),
        },
        "timing": {"total_seconds": round(time.time() - t_all, 2),
                   "per_repetition_seconds": unit,
                   "budgeted_total_at_priced_unit": round(n * 12.6, 1)},
        "what_this_does_NOT_do": ("It does not fix anything. The fix edits organs/neural_language.py's answer "
                                  "path, which published sealed artifacts quote, and that edit needs a PI "
                                  "ruling -- this run buys the rate, not the change."),
        "repetitions": reps,
        "provenance": {"driver": "tools/mp_e10_licensed_absence_hunt.py",
                       "git_head_at_write": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                           capture_output=True, text=True).stdout.strip(),
                       "python": sys.version.split()[0], "platform": sys.platform},
    }
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n[hunt] FLIPS {k} of n={n} = {rate:.2f}%  Wilson95 {ci}  "
          f"rule-of-three<= {out['result']['rule_of_three_upper_bound_percent']}")
    print(f"[hunt] other failures {kinds['other_failure']}, errors {kinds['error']}, passes {kinds['pass']}")
    print(f"[hunt] reasons seen: {dict(reasons) or '(none -- no flip to print)'}")
    print(f"[hunt] total {out['timing']['total_seconds']} s; per-rep median "
          f"{unit['median']} s against the priced 12.6 s")
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
