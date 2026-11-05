"""Tests for tools/prose_coordinate_audit.py.

They are written to catch the failure modes this tool's first version actually demonstrated, three of which were
found by running it against the real ledgers and disbelieving the output:

  * a coordinate allowed to supply its OWN needle (`MP-E10:3163` yielded the needle `E10=3163`, which fails
    against every line on earth and was scored content_false -- the citation scored false by a fragment of itself);
  * spacing normalisation counted as a citation defect (`LEARN_LR=0.35` vs a line reading `LEARN_LR = 0.35`);
  * a double `.parent` in the resolution call, which moved the relative-resolution root one directory up and
    turned 8 resolvable basename citations into "ambiguous_basename" -- a false report of under-specification.

And the two behaviours that matter most are asserted directly: report mode writes NOTHING, and a coordinate
without a recorded needle is REFUSED rather than judged.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pca", ROOT / "tools/prose_coordinate_audit.py")
pca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pca)

LEDGERS = sorted(p for p in (ROOT / "experiments").glob("*/registration.json"))


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A miniature repo: one ledger in experiments/FIX/, one target file in organs/.

    ROOT is patched rather than the paths threaded through, because the tool resolves citations against ROOT by
    design -- that is the behaviour under test.
    """
    (tmp_path / "experiments" / "FIX").mkdir(parents=True)
    (tmp_path / "organs").mkdir(parents=True)
    tgt = tmp_path / "organs" / "thing.py"
    tgt.write_text("line one\nLEARN_LR = 0.35\nline three\n", encoding="utf-8")
    monkeypatch.setattr(pca, "ROOT", tmp_path)
    led = tmp_path / "experiments" / "FIX" / "registration.json"
    return led, tgt


def write_ledger(led, entries: dict):
    led.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return led


def verdict_of(led, needle_free_only=False):
    out = {}
    for rec in pca.collect(led.read_text(encoding="utf-8"), led):
        out.setdefault(rec["coord"], []).append(pca.classify(dict(rec))["verdict"])
    return out


# ---------------------------------------------------------------- the refusal is the point
def test_a_coordinate_without_a_recorded_needle_is_refused_not_judged(sandbox):
    led, _ = sandbox
    write_ledger(led, {"note": "see organs/thing.py:2 for the value"})
    v = verdict_of(led)["organs/thing.py:2"]
    assert v == ["no_needle"], v
    # "for the value" is a prepositional phrase, not a claim about line 2. The tool must not turn it into one.
    rec = [x for x in pca.collect(led.read_text(encoding="utf-8"), led)][0]
    assert pca.classify(dict(rec))["verdict"] == "no_needle"
    assert "guessed referent" in pca.classify(dict(rec))["refused_because"]


def test_refusal_emits_no_truth_claim_at_all(sandbox):
    """A refused coordinate must not appear in any verdict that reads as true or false."""
    led, _ = sandbox
    write_ledger(led, {"note": "see organs/thing.py:2 for the value"})
    r = pca.report([led])
    assert r["by_verdict"].get("resolves_true") is None
    assert r["by_verdict"].get("content_false") is None


# ---------------------------------------------------------------- content checking works
def test_a_needle_on_the_cited_line_resolves_true(sandbox):
    led, _ = sandbox
    write_ledger(led, {"pointer": "organs/thing.py:2", "line_reads": "LEARN_LR = 0.35"})
    assert verdict_of(led)["organs/thing.py:2"] == ["resolves_true"]


def test_a_needle_elsewhere_is_content_false(sandbox):
    led, _ = sandbox
    write_ledger(led, {"pointer": "organs/thing.py:3", "line_reads": "LEARN_LR = 0.35"})
    assert verdict_of(led)["organs/thing.py:3"] == ["content_false"]


def test_spacing_around_operators_is_not_a_citation_defect(sandbox):
    """The ledger may record `LEARN_LR=0.35` about a line reading `LEARN_LR = 0.35`. That is the same claim."""
    led, _ = sandbox
    write_ledger(led, {"note": "the constant at organs/thing.py:2 reads LEARN_LR=0.35"})
    assert verdict_of(led)["organs/thing.py:2"] == ["resolves_true"]


def test_a_faraway_needle_is_drift_not_absence(sandbox):
    """Reported as a verdict only when the claim exists: the drift/absence split is the tool's most useful output."""
    led, tgt = sandbox
    tgt.write_text("line one\nline two\nline three\nLEARN_LR = 0.35\n", encoding="utf-8")
    write_ledger(led, {"pointer": "organs/thing.py:1", "line_reads": "LEARN_LR = 0.35"})
    rec = pca.classify(dict(pca.collect(led.read_text(encoding="utf-8"), led)[0]))
    assert rec["verdict"] == "content_false"
    tl = pca.target_lines(tgt)
    hits = [i for i, l in enumerate(tl, 1) if pca.canon("LEARN_LR = 0.35") in pca.canon(l)]
    assert hits == [4] and hits[0] - rec["line"] == 3


# ---------------------------------------------------------------- the three bugs, pinned
def test_a_coordinate_may_not_supply_its_own_needle(sandbox):
    led, _ = sandbox
    write_ledger(led, {"see": "MP-E10:3163"})
    needles = [x["needles"] for x in pca.collect(led.read_text(encoding="utf-8"), led)]
    for n in needles:
        assert not any("E10=" in s for s in n), n


def test_single_word_needles_are_too_weak_to_judge_with(sandbox):
    led, _ = sandbox
    # a backticked single word is not a content claim; treating it as one manufactures verdicts
    write_ledger(led, {"note": "the `scent` at organs/thing.py:1 is described"})
    assert verdict_of(led)["organs/thing.py:1"] == ["no_needle"]


def test_basename_citation_resolves_against_the_citing_ledgers_directory(sandbox):
    """The double-.parent regression: `thing.py:2` from experiments/FIX/ must resolve into organs/ by basename,
    and a same-directory basename must resolve relatively rather than being called ambiguous."""
    led, _ = sandbox
    (led.parent / "thing.py").write_text("alpha\nLEARN_LR = 0.35\n", encoding="utf-8")
    write_ledger(led, {"pointer": "thing.py:2", "line_reads": "LEARN_LR = 0.35"})
    rec = pca.classify(dict(pca.collect(led.read_text(encoding="utf-8"), led)[0]))
    assert rec["resolution_mode"] == "relative_to_citing_ledger"
    assert rec["verdict"] == "resolves_true"


# ---------------------------------------------------------------- report mode is read-only
def test_report_writes_nothing_to_any_ledger():
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in LEDGERS}
    r = pca.report(LEDGERS)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in LEDGERS}
    assert before == after
    assert r["nothing_written"] is True


def test_the_tool_states_in_its_own_docstring_that_it_does_not_authorise_repair():
    """The PI's condition, enforced by a test rather than by memory of the conversation."""
    d = pca.__doc__
    assert "DOES NOT AUTHORISE REPAIRING" in d
    assert "guessed referent is a new false citation wearing a checkmark" in d


def test_the_measured_split_is_reported_not_repaired():
    """The historical coordinates stay as they are: content_false must be > 0 while the ledgers are untouched.

    If a future change makes the tool silent about these, that is the tool being blunted, not the defects being
    cured -- so the assertion is that it still SEES them.
    """
    r = pca.report(LEDGERS)
    assert r["total_coordinates"] > 300
    assert r["by_verdict"].get("content_false", 0) > 0
    assert r["by_verdict"].get("no_needle", 0) > 0


# ---------------------------------------------------------------- forward enforcement
def test_gate_blocks_a_new_coordinate_without_a_needle(sandbox):
    led, _ = sandbox
    write_ledger(led, {"keep": "nothing new here"})
    before = led.read_text(encoding="utf-8")
    write_ledger(led, {"keep": "nothing new here",
                       "added": "the value lives at organs/thing.py:2"})
    n, bad = pca.gate(led, before_text=before)
    assert n == 1 and bad[0]["verdict"] == "no_needle"


def test_gate_passes_a_new_coordinate_that_carries_a_resolving_needle(sandbox):
    led, _ = sandbox
    write_ledger(led, {"keep": "nothing new here"})
    before = led.read_text(encoding="utf-8")
    write_ledger(led, {"keep": "nothing new here",
                       "added": {"pointer": "organs/thing.py:2", "line_reads": "LEARN_LR = 0.35"}})
    n, _ = pca.gate(led, before_text=before)
    assert n == 0


def test_gate_grandfathers_coordinates_already_present_in_the_comparison_state(sandbox):
    """Enforce forward, not backward: the 345 historical coordinates must not block a stamp."""
    led, _ = sandbox
    text = json.dumps({"old": "see organs/thing.py:9 for the value"}, indent=2)
    led.write_text(text, encoding="utf-8")
    n, _ = pca.gate(led, before_text=text)
    assert n == 0


def test_gate_reopens_a_coordinate_whose_citing_line_was_edited(sandbox):
    led, _ = sandbox
    before = json.dumps({"note": "organs/thing.py:2 is the constant"}, indent=2)
    led.write_text(before, encoding="utf-8")
    led.write_text(json.dumps({"note": "organs/thing.py:2 is the constant, definitely"}, indent=2), encoding="utf-8")
    n, bad = pca.gate(led, before_text=before)
    assert n == 1 and bad[0]["verdict"] == "no_needle"


def test_gate_never_blocks_a_declared_non_pointer(sandbox, monkeypatch):
    """A coordinate a human declared as not-a-pointer must pass the gate, or the allowlist is decorative.

    The allowlist is keyed on the ledger, so the sandbox needs its own entry: that is the mechanism under test,
    not the specific coordinates, which the next test checks against the real ledgers.
    """
    led, _ = sandbox
    rel = led.resolve().relative_to(pca.ROOT).as_posix()
    monkeypatch.setattr(pca, "NON_POINTERS", [
        {"ledger": rel, "coordinate": "MP-E10:4255", "marker": "quoted AS EXAMPLES", "reason": "test fixture"}])
    before = json.dumps({"keep": "x"}, indent=2)
    write_ledger(led, {"keep": "x", "note": "quoted AS EXAMPLES: MP-E10:4255"})
    n, bad = pca.gate(led, before_text=before)
    assert [b["coord"] for b in bad] == []
    assert n == 0
    recs = [pca.classify(dict(x)) for x in pca.collect(led.read_text(encoding="utf-8"), led)]
    assert [r["verdict"] for r in recs] == ["non_pointer"]


# ---------------------------------------------------------------- the real ledgers' declared non-pointers
def test_the_two_coordinates_the_pi_named_are_classified_non_pointer_not_false():
    """MP-E10:2538 (the plan's verbatim sentence) and the examples in the note. Neither may be reported as a
    defect to repair: the first is the subject of a correction, the second is the evidence of a class."""
    r = pca.report(LEDGERS)
    npv = [x for x in r["records"] if x["verdict"] == "non_pointer"]
    coords = {x["coord"] for x in npv}
    assert "MP-E10:2538" in coords, coords
    assert "MP-E10:4255" in coords, coords
    assert len(npv) >= 3
    # and the plan's own sentence is still verbatim in the ledger, i.e. untouched
    txt = (ROOT / "experiments/MP-E10/registration.json").read_text(encoding="utf-8")
    verbatim = ("| **PI ruling queue** | The numbered list of open decisions awaiting the Principal "
                "Investigator (11 items, 14 ledger keys, indexed at `MP-E10:2538`).")
    assert verbatim in txt


def test_ambiguous_basename_is_under_specified_not_missing():
    """A citation whose basename matches two files is a DIFFERENT defect from one whose file does not exist: the
    first needs the author to write the path, the second needs the file. Collapsing them would misdirect repair."""
    r = pca.report(LEDGERS)
    rows = [x for x in r["records"] if x["verdict"] == "ambiguous_basename"]
    assert all("basename_matches" in x["resolution_mode"] for x in rows)
    assert all(x["verdict"] != "target_missing" for x in rows)


def test_the_stamp_refuses_when_the_gate_fails_and_writes_nothing(monkeypatch, capsys):
    """The wiring is the enforcement. A stamp that proceeds after a failed gate is a rule nobody enforces, so
    this asserts the refusal happens AND that the ledger on disk is untouched by the attempt."""
    seal_spec = importlib.util.spec_from_file_location("rsa", ROOT / "tools/registration_seal.py")
    rsa = importlib.util.module_from_spec(seal_spec)
    seal_spec.loader.exec_module(rsa)
    led = LEDGERS[0]
    before = led.read_bytes()
    fake = {"coord": "organs/thing.py:9", "verdict": "no_needle", "ledger_line": 3, "citing_text": "x"}
    monkeypatch.setattr(rsa, "_pca_gate", lambda pca, p: (1, [fake]))
    monkeypatch.setattr("sys.argv", ["registration_seal.py", str(led)])
    rc = rsa.main()
    out = capsys.readouterr()
    assert rc == 1
    assert "REFUSING to stamp" in out.err
    assert "no_needle" in out.err
    assert led.read_bytes() == before, "a refused stamp must not have written a seal block"


def test_the_stamp_still_runs_the_gate_through_the_real_path(monkeypatch):
    """Prove main() consults the checker at all -- without this, deleting the call would keep every other test
    green, which is exactly how the previous seal-identity test managed to be wrong by construction."""
    seal_spec = importlib.util.spec_from_file_location("rsb", ROOT / "tools/registration_seal.py")
    rsa = importlib.util.module_from_spec(seal_spec)
    seal_spec.loader.exec_module(rsa)
    seen = []
    monkeypatch.setattr(rsa, "_pca_gate", lambda pca, p: seen.append(p.name) or (0, []))
    monkeypatch.setattr(rsa, "seal", lambda p: {})          # do not actually write a seal block in a test
    monkeypatch.setattr("sys.argv", ["registration_seal.py", str(LEDGERS[0])])
    rsa.main()
    assert seen == ["registration.json"], "the stamp path must consult the checker before it writes"

    seen.clear()
    monkeypatch.setattr("sys.argv", ["registration_seal.py", "--check", str(LEDGERS[0])])
    rsa.main()
    assert seen == [], "--check verifies an existing seal and must not gate, or checking would need HEAD to be clean"


def test_the_gate_on_the_real_ledgers_does_not_report_the_historical_class_as_new():
    """The whole point of forward-only enforcement: stamping today must not be blocked by 345 old citations.

    Run against the working copy vs HEAD. Anything it flags is something THIS step wrote, which is exactly the
    set the read-back rule is supposed to have made safe.
    """
    import subprocess
    for led in LEDGERS:
        head = subprocess.run(["git", "show", f"HEAD:{led.relative_to(ROOT).as_posix()}"], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8")
        if head.returncode != 0:
            continue
        n, bad = pca.gate(led, before_text=head.stdout)
        for b in bad:
            assert b["ledger"] == led.relative_to(ROOT).as_posix()
        assert n == 0, (f"{led.parent.name}: {n} new coordinate(s) without a resolving needle -> "
                        + "; ".join(f"{b['coord']} [{b['verdict']}] line {b['ledger_line']}" for b in bad[:6]))
