"""E26 -- v_frame, the question-verb exclusion, measured ALONE.

v_frame is a superset of v_synt: function words plus the question-framing verbs.
It gets its own generation and is compared against generation 21, the SAME
control E25 used -- never against generation 22 -- so each variant stays
attributable to one cut rather than to a stack.

The load-bearing test here is B8. `say`, `tell`, `name` and `repeat` are verbs,
and verbs are the word class most likely to be the thing a question is actually
about. If any of them is content in this battery, excluding it from the
denominator would let the organ answer a question it cannot support, which is
the exact failure mode E23 was refuted for.
"""
import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ORGAN = ROOT / "organs" / "neural_language.py"
HARNESS = ROOT / "tools" / "run_generation.py"
SEL = ROOT / "state" / "selection"

_SRC = ORGAN.read_text(encoding="utf-8")
_H = HARNESS.read_text(encoding="utf-8")

# Content words that appear in the 42-ask battery. If a question verb collides
# with one of these, B8 fires.
BATTERY_CONTENT = frozenset({
    "bell", "coat", "scarf", "kettle", "lantern", "basket", "door", "frost",
    "latch", "moon", "eggs", "metal", "copper", "hook", "thing", "word",
    "place", "number", "times", "turns", "bites", "holds", "wet", "dry",
    "left", "used", "carries", "opens", "cold", "warm", "heavy", "light",
})


def test_e26_frame_flag_default_off():
    i = _SRC.index("COVERAGE_EXCLUDE_FRAME = False")
    assert _SRC[:i].count("COVERAGE_EXCLUDE_FRAME") == 0


def _frozenset_at(src, marker, span=1500):
    """Parse `MARKER = frozenset({...})` out of source.

    `ast.literal_eval` cannot do this: `frozenset(...)` is a Call, not a
    literal, so the call has to be peeled off and only the brace expression
    evaluated. Three tests failed on exactly that before this helper existed.
    """
    i = src.index(marker)
    seg = src[i:i + span]
    seg = seg[:seg.index("})") + 2]
    body = seg.split("frozenset(", 1)[1]
    return set(ast.literal_eval(body[:body.rindex(")")]))


def test_e26_question_verbs_are_the_framing_verbs():
    assert _frozenset_at(_SRC, "QUESTION_VERBS = frozenset({", 400) == {
        "say", "said", "tell", "told", "mention", "mentioned",
        "name", "repeat"}


def test_e26_b8_no_question_verb_is_a_battery_content_word():
    """ABORT B8. The exclusion set must not contain content."""
    qv = _frozenset_at(_SRC, "QUESTION_VERBS = frozenset({", 400)
    overlap = qv & BATTERY_CONTENT
    assert not overlap, f"B8: question verbs collide with content: {overlap}"


def test_e26_b8_no_question_verb_is_a_function_word():
    """The two exclusion sets must be disjoint, or v_frame is double-counting."""
    qv = _frozenset_at(_SRC, "QUESTION_VERBS = frozenset({", 400)
    fw = _frozenset_at(_SRC, "SHAPE_FUNCTION_WORDS = frozenset({")
    assert not (qv & fw), f"overlap: {qv & fw}"


def test_e26_predicate_excludes_a_question_verb_when_frame_on():
    # `_coverage_excluded` is a MODULE-level pure function, deliberately not a
    # method, so it cannot reach for self or the binder. Import it as such.
    from organs.neural_language import _coverage_excluded
    from organs.neural_language import NeuralLanguage as NL
    qv = NL.QUESTION_VERBS
    assert _coverage_excluded("say", True, qv) is True
    assert _coverage_excluded("say", False, qv) is False
    # content is never excluded, whatever the flag
    for w in ("bell", "coat", "turns", "wet"):
        assert _coverage_excluded(w, True, qv) is False


def test_e26_frame_hook_is_in_the_must_loop():
    """The frame predicate must sit in the same `continue` as the synt one,
    inside the loop that builds `must` -- not somewhere that could add."""
    i = _SRC.index("COVERAGE_EXCLUDE_FRAME,")
    # the enclosing `if` opens just before the frame argument
    head = _SRC[max(0, i - 300):i]
    assert "_coverage_excluded(w, self.COVERAGE_EXCLUDE_SYNT" in head
    assert "known.add(w)" in head, "hook is not after the known.add(w) line"
    tail = _SRC[i:i + 900]
    assert "continue" in tail
    # between the hook and its `continue` nothing may be added to `must`
    between = tail[:tail.index("continue")]
    assert "must.add" not in between, "the frame branch adds to must"
    # and `must.add(w)` really does follow, on the non-excluded path
    assert "must.add(w)" in tail[tail.index("continue"):]


def test_e26_harness_stamps_frame_flag():
    assert 'CODE_FLAGS["coverage_exclude_frame"] = _frm' in _H
    assert 'CODE_FLAGS["coverage_exclude_synt"] = _syn' in _H


def test_e26_frame_implies_synt_because_it_is_a_superset():
    """v_frame = FUNCTION | QVERB, so 'frame' must turn on both exclusions."""
    i = _H.index('_syn = args.coverage_exclude in ("synt", "frame")')
    seg = _H[i:i + 400]
    assert '_frm = args.coverage_exclude == "frame"' in seg
    assert "COVERAGE_EXCLUDE_SYNT = _syn" in seg
    assert "COVERAGE_EXCLUDE_FRAME = _frm" in seg


def test_e26_harness_accepts_frame_choice():
    i = _H.index('ap.add_argument("--coverage-exclude"')
    seg = _H[i:i + 200]
    assert '"frame"' in seg and '"synt"' in seg


def test_e26_variants_are_never_stacked():
    """One --coverage-exclude value per run, so synt and frame cannot both be
    requested. The E26 arm is frame-only against the gen-21 control."""
    i = _H.index('ap.add_argument("--coverage-exclude"')
    seg = _H[i:i + 200]
    assert "nargs" not in seg
    assert "action=\"append\"" not in seg


# --------------------------------------------------------------------------
# Integration: generation 23 is the treatment arm.
# --------------------------------------------------------------------------

def _asks(p):
    return {(r["script"], r["ask"]): r
            for r in (json.loads(x) for x in
                      p.read_text(encoding="utf-8").splitlines() if x.strip())}


def _gen(p):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.integration
def test_e26_arms_differ_only_in_the_frame_flag():
    ctl, trt = SEL / "generation_21.jsonl", SEL / "generation_23.jsonl"
    if not (ctl.exists() and trt.exists()):
        pytest.skip("generation 21 or 23 not published yet")
    fc = _gen(ctl)["provenance"]["code_flags"]
    ft = _gen(trt)["provenance"]["code_flags"]
    # Gen 21 predates both flags, so missing keys mean off.
    differing = {k for k in set(fc) | set(ft)
                if fc.get(k, False) != ft.get(k, False)}
    assert differing == {"coverage_exclude_synt", "coverage_exclude_frame"}, \
        f"arms differ in more than the v_frame cut: {differing}"


@pytest.mark.integration
def test_e26_abort_conditions():
    ck, tk = SEL / "generation_21_asks.jsonl", SEL / "generation_23_asks.jsonl"
    gj = SEL / "generation_23.jsonl"
    if not (ck.exists() and tk.exists() and gj.exists()):
        pytest.skip("generation 21 or 23 not published yet")
    kc, kt, gt = _asks(ck), _asks(tk), _gen(gj)
    assert set(kc) == set(kt)

    # B1/B4: the guarded scarf ask still refuses, coverage None, reason identical.
    s = [k for k in kt if k[1] == "where did i say the scarf is?"][0]
    assert kt[s].get("pass") is True, "B1: the scarf stopped refusing"
    assert kt[s].get("coverage") is None, "B4: coverage computed for the scarf"
    assert kt[s]["reason"] == kc[s]["reason"], "B4: scarf reason changed"

    # B2/B3 from the published fitness block, not re-derived.
    rt = gt["fitness"]["regression"]
    assert rt["probe_guard_passed"] == rt["probe_guard_asked"] == 4, "B2"
    assert rt["frozen_lost_n"] == 0, "B3: frozen asks lost"
    assert gt["fitness"]["capability"]["passed"] >= 19, "B3"

    # B5: nothing the control answered may start refusing.
    lost = [k for k in kc if kc[k].get("pass") and not kt[k].get("pass")]
    assert not lost, f"B5: {len(lost)} answers subtracted: {lost}"
