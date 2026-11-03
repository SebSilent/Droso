"""WORD-LEVEL PROVENANCE GRADER -- R9: every content word an organism speaks must be traceable.

WHY THIS FILE EXISTS. The bench's own INVENTED class grades *sentences*: a reply is an invention when
no told sentence matches it. That is necessary and not sufficient, and the repository paid for the
difference. `ELECTRIC_ARBITER_TELL` routed three ungrammatical asks (`what the nora carry`, `what the
dog guard`, `what the bridge cross`) into `arbiter head`, and the house answered `says` -- a word in
none of the 27 told sentences, in none of the asks, and not even in the rows the arbiter drew from.
Those 16 rows graded `partial`, the bench reported `failures: []`, and the tool exited 0. By this
project's own ranking (`docs/electric_generalisation.md`) confabulation is the category worse than
silence, so an honest refusal that now utters an unsupported word is a regression the instrument
could not see.

THE RULE, from Master Plan v1.1 R9: every content word in every answer must trace to a taught row,
the ask itself, or an admitted source. One untraceable word is an abort condition.

THE ONE DESIGN DECISION THAT MAKES IT USABLE. The house narrates: it says `droso says where the bell
hang`. The frame word `says` is a report about speaking, not a claim about the world, and the bench
already strips it positionally in `norm()`. This grader imports that same tuple and that same strip
rather than restating it -- a grader that does not strip the frame fires on all 23 narration-frame
rows of the committed evidence, and 23 false aborts under a one-word-aborts rule would make the
grader unusable and read as a capability collapse. The strip is POSITIONAL, and position is exactly
the distinction the defect turns on: in `droso says where the bell hang` the word is the frame of a
report; in `says`, spoken as the entire answer, there is no frame and no residue, and the word is the
assertion.

CONTENT-WORD CLASS. `NeuralLanguage.SHAPE_FUNCTION_WORDS`, the organ's own explicit 86-word set.
Deliberately not a distributional rule: E10 tried the organ's `df * 4 <= n_mem` test as a
function-word proxy and it keeps `is` and `on`, because "document frequency here measures corpus
style, not lexical class" (`docs/evidence/e10_result.md`). `says` is not in the explicit set, so it
is a content word and is graded -- which is the behaviour R9 requires.

ADMITTED SOURCES, and why the refusal is a FORM and not a word list. The licensed absence reply is
built by the organ at `organs/neural_language.py:177` and spoken at `:4893` as
`i don't know, {subj} was told but no {rel} was ever told for {subj}`. Admitting the residue words of
that sentence (`know`, `told`, `ever`, `place`, ...) as a stopword-style list would whitelist
whatever the tool happened to say, which is circular -- and `place` is a content noun. Instead the
grader matches the *template*: the skeleton must match, the relation slot must be one of the three
classes `_absence_frame` can emit (`place`, `property`, `agent`), and the subject slot must be a word
the house was actually told. A refusal that says anything outside that form is graded as speech.

BOUNDS, stated as bounds.
  * The journal carries no retrieved-row text, so this grader answers "is this word in the taught
    set", not "is this word in the row the source named". The stricter reading is the follow-up and
    it needs a `row_text` field on the journal, not a change to this file.
  * It grades what the bench recorded. A word spoken on a path that writes no row is invisible here,
    exactly as it is to the bench.
  * It is a measurement. It changes no organ, no flag, no threshold and no class.

Run:  .venv/Scripts/python.exe tools/word_provenance.py [evidence.json] [--out results.json]
      .venv/Scripts/python.exe tools/word_provenance.py --validate   # the G0-prime pin, exits 1 on drift
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from organs.neural_language import NeuralLanguage          # noqa: E402
from tools.electric_learn_bench import REPORT_FRAMES, strip_report_frame  # noqa: E402

SCHEMA = "droso.word_provenance.v1"
EVIDENCE = pathlib.Path("docs/evidence/electric_learn_bench.json")

FUNCTION_WORDS = NeuralLanguage.SHAPE_FUNCTION_WORDS

# The three relation classes `_absence_frame` (organs/neural_language.py:125-156) can emit. Nothing
# else may appear in the relation slot of a licensed refusal.
ABSENCE_RELATIONS = frozenset({"place", "property", "agent"})

# The licensed refusal, as the organ builds it: :177 writes the reason, :4893 prefixes "i don't
# know, ". The subject is a single word because _absence_frame requires len(subj) == 1.
ABSENCE_FORM = re.compile(
    r"^i don't know, (?P<subj>[a-z0-9]+) was told but no (?P<rel>[a-z0-9]+) "
    r"was ever told for (?P=subj)$")


def tokens(s):
    """Lower-case word tokens, punctuation as separators. `don't` -> don, t."""
    return [w for w in re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).split() if w]


def content_words(s):
    """The words R9 grades. Function words are not assertions, so they are not traceable facts."""
    return [w for w in tokens(s) if w not in FUNCTION_WORDS]


def taught_content(told):
    """Content words of a set of sentences, function words removed."""
    out = set()
    for t in told or []:
        out.update(content_words(t))
    return out


def build_sets(doc):
    """Every trace set, from the document where it can be read and from the curriculum where it
    cannot. Older evidence files predate `taught_questions`, so the bench's own PAIRS is the fallback
    and the fallback is reported rather than hidden."""
    told = doc.get("told") or []
    tq = doc.get("taught_questions")
    source = "evidence.taught_questions"
    if tq is None:
        from tools.electric_learn_bench import PAIRS      # curriculum definition, not a guess
        tq = [q.lower() for s in PAIRS for q, _a in s]
        source = "tools.electric_learn_bench.PAIRS (fallback: file predates taught_questions)"
    answers = taught_content(told)
    questions = taught_content(tq)
    rows = [r for _k, r in probe_rows(doc)]
    heard = set()
    for r in rows:
        heard.update(content_words(r.get("ask")))
    return {"answers": answers, "questions": questions, "heard": heard,
            "taught_questions_source": source,
            "n_answer_words": len(answers), "n_question_words": len(questions)}


def frame_words():
    """The narration frame's own vocabulary, derived from the imported tuple -- never restated."""
    out = set()
    for f in REPORT_FRAMES:
        out.update(tokens(f))
    return out


FRAMES = frame_words()


def trace(word, sets, ask_words, row_words=None):
    """Where this word came from. Returns the trace class, or None when nothing licenses it.

    Order matters. `ask` first: a word the teacher just used on this turn is licensed by the ask.
    `taught_answer` next: a word of a sentence the house was told, which is the only class it may
    answer WITH. `taught_question` is traceable -- it was said to him -- but it is not answer material,
    so a reply built from a question he was taught is still reported, via `question_derived`.
    `heard_not_told` is the weakest claim: the word reached him only inside some OTHER question, so it
    is in his experience and is not something he was told.
    """
    if word in ask_words:
        return "ask"
    if row_words is not None and word in row_words:
        return "row"
    if word in sets["answers"]:
        return "taught_answer"
    if word in sets["questions"]:
        return "taught_question"
    if word in sets["heard"]:
        return "heard_not_told"
    return None


def audit_row(row, sets, strict_row=False):
    """Grade one spoken reply.

    Two severities, kept apart because they are different faults and the program treats them
    differently:
      UNTRACEABLE_ASSERTED -- a content word with no source at all. `says` is this class: not taught,
        not in the ask, not heard anywhere. It is asserted, and R9 aborts on it.
      UNTRACEABLE_HEARD -- a word that reached the house only inside some OTHER question. `which`,
        `who`, `why` are this class. It is in his experience and it is not something he was told, so
        the literal R9 rule still fails it, but it is question-word leakage from the remembered pool
        rather than an invented fact, and the bench already names that cross_echo.
    """
    said = str(row.get("said") or "")
    rec = {
        "ask": row.get("ask"),
        "said": said,
        "src": row.get("src"),
        "cls": row.get("cls"),
        "frame_stripped": False,
        "admitted": None,
        "graded_words": [],
        "untraceable": [],
        "heard_only": [],
        "question_derived": [],
        "verdict": "clean",
    }
    if not said.strip():
        rec["verdict"] = "silent"          # silence cannot confabulate
        return rec

    if row.get("src") == "electric_absence":
        m = ABSENCE_FORM.match(said.strip().lower())
        if (m and m.group("rel") in ABSENCE_RELATIONS
                and (m.group("subj") in sets["answers"] or m.group("subj") in sets["questions"])):
            rec["admitted"] = "absence_form"
            rec["verdict"] = "admitted_refusal"
            return rec
        # A refusal speaking outside the licensed form is graded as speech, not excused.
        rec["admitted"] = "absence_form_OUTSIDE"

    stripped = strip_report_frame(said)
    rec["frame_stripped"] = in_frame_position(said)
    ask_words = set(content_words(row.get("ask")))
    row_words = None
    if strict_row:
        row_words = (set(content_words(row.get("own") or ""))
                     | set(content_words(row.get("taught") or "")))

    for w in content_words(stripped):
        t = trace(w, sets, ask_words, row_words)
        rec["graded_words"].append(w)
        if t is None:
            rec["untraceable"].append(w)
        elif t == "heard_not_told":
            rec["heard_only"].append(w)
        elif t == "taught_question":
            rec["question_derived"].append(w)
        rec.setdefault("traces", {})[w] = t or "NONE"

    if rec["untraceable"]:
        rec["verdict"] = "UNTRACEABLE_ASSERTED"
    elif rec["heard_only"]:
        rec["verdict"] = "UNTRACEABLE_HEARD"
    return rec


def probe_rows(doc):
    """Every probe row, positionally, with its arm/depth/phase coordinates."""
    out = []
    for arm, a in sorted((doc.get("arms") or {}).items()):
        for depth, ph in sorted((a.get("probes") or {}).items(), key=lambda kv: str(kv[0])):
            for phase, rows in sorted(ph.items()):
                for i, r in enumerate(rows):
                    out.append((f"{arm}/d{depth}/{phase}[{i}]", r))
    return out


VERDICTS = ("clean", "silent", "admitted_refusal", "UNTRACEABLE_HEARD", "UNTRACEABLE_ASSERTED")


def audit(doc, strict_row=False):
    sets = build_sets(doc)
    rows = probe_rows(doc)
    recs, flagged = [], []
    for key, r in rows:
        rec = audit_row(r, sets, strict_row)
        rec["row"] = key
        recs.append(rec)
        if rec["verdict"].startswith("UNTRACEABLE"):
            flagged.append(rec)

    by_word = {}
    for rec in flagged:
        for w in rec["untraceable"] + rec["heard_only"]:
            sev = "asserted" if w in rec["untraceable"] else "heard"
            e = by_word.setdefault(w, {"rows": 0, "severity": set(), "asks": set(), "srcs": set()})
            e["rows"] += 1
            e["severity"].add(sev)
            e["asks"].add(rec["ask"])
            e["srcs"].add(rec["src"])

    return {
        "schema": SCHEMA,
        "rows_audited": len(rows),
        "trace_sets": {k: sets[k] for k in ("n_answer_words", "n_question_words",
                                            "taught_questions_source")},
        "frame_words": sorted(FRAMES),
        "content_word_class": "NeuralLanguage.SHAPE_FUNCTION_WORDS (explicit set, not the E10 "
                              "distributional rule)",
        "verdict_counts": {v: sum(1 for r in recs if r["verdict"] == v) for v in VERDICTS},
        "question_derived_rows": sum(1 for r in recs if r["question_derived"]),
        "untraceable_words": {w: {"rows": e["rows"], "severity": sorted(e["severity"]),
                                  "asks": sorted(e["asks"]),
                                  "srcs": sorted(str(s) for s in e["srcs"])}
                              for w, e in sorted(by_word.items())},
        "flagged_rows": [{"row": r["row"], "ask": r["ask"], "said": r["said"], "src": r["src"],
                          "cls": r["cls"], "verdict": r["verdict"],
                          "untraceable": r["untraceable"], "heard_only": r["heard_only"]}
                         for r in flagged],
        "audit_trail": recs if _FULL_TRAIL else None,
    }


_FULL_TRAIL = False


def in_frame_position(said):
    """True when the reply opens with the narration frame -- i.e. the frame words are framing a
    report, not being asserted. This is the whole distinction the says gap turns on."""
    s = str(said or "").lower().strip()
    return any(s.startswith(f) for f in REPORT_FRAMES)


def sets_from(doc):
    """The three pinned row sets G0-prime validates against, found by their recorded properties."""
    rows = probe_rows(doc)
    says = [(k, r) for k, r in rows if r.get("said") == "says"
            and r.get("src") == "arbiter head"]
    frame = [(k, r) for k, r in rows if in_frame_position(r.get("said"))]
    absence = [(k, r) for k, r in rows if r.get("src") == "electric_absence"]
    return says, frame, absence


def validate(doc):
    """The G0-prime checklist step 2, as a verdict rather than a paragraph.

    Three pinned sets, three expectations: every says-gap row flagged, ZERO false aborts on the
    narration-frame rows, every guarded-absence row admitted by form.
    """
    sets = build_sets(doc)
    says, frame, absence = sets_from(doc)
    says_audits = [audit_row(r, sets) for _k, r in says]
    frame_audits = [audit_row(r, sets) for _k, r in frame]
    abs_audits = [audit_row(r, sets) for _k, r in absence]
    says_flagged = [a for a in says_audits if a["verdict"] == "UNTRACEABLE_ASSERTED"]
    checks = {
        "says_rows_found": len(says),
        "says_rows_flagged_asserted": len(says_flagged),
        "says_distinct_asks": sorted({r["ask"] for _k, r in says}),
        "says_untraceable_words": sorted({w for a in says_flagged for w in a["untraceable"]}),
        "frame_rows_found": len(frame),
        "frame_rows_false_aborts": sum(1 for a in frame_audits
                                       if a["verdict"].startswith("UNTRACEABLE")),
        "absence_rows_found": len(absence),
        "absence_rows_admitted": sum(1 for a in abs_audits
                                     if a["verdict"] == "admitted_refusal"),
        "absence_rows_flagged": sum(1 for a in abs_audits
                                    if a["verdict"].startswith("UNTRACEABLE")),
    }
    checks["PASS"] = (len(says) > 0 and len(says) == len(says_flagged)
                      and checks["says_untraceable_words"] == ["says"]
                      and checks["frame_rows_false_aborts"] == 0
                      and len(absence) > 0
                      and checks["absence_rows_admitted"] == len(absence))
    return checks


def main() -> int:
    global _FULL_TRAIL
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence", nargs="?", default=str(EVIDENCE))
    ap.add_argument("--out", default=None)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--full-trail", action="store_true", help="keep every row's audit record")
    ap.add_argument("--strict-row", action="store_true",
                    help="also require the word to be in this item's own row")
    a = ap.parse_args()
    _FULL_TRAIL = a.full_trail

    doc = json.loads(pathlib.Path(a.evidence).read_text(encoding="utf-8"))
    if a.validate:
        c = validate(doc)
        print(json.dumps(c, indent=2, sort_keys=True))
        print("[grader] VALIDATION", "PASS" if c["PASS"] else "FAIL")
        return 0 if c["PASS"] else 1

    res = audit(doc, strict_row=a.strict_row)
    vc = res["verdict_counts"]
    print(f"[grader] {res['rows_audited']} rows | trace sets {res['trace_sets']}")
    print(f"[grader] verdicts {vc}")
    print(f"[grader] R9 violations: asserted={vc['UNTRACEABLE_ASSERTED']} "
          f"heard-not-told={vc['UNTRACEABLE_HEARD']} "
          f"total={vc['UNTRACEABLE_ASSERTED'] + vc['UNTRACEABLE_HEARD']}")
    for w, e in res["untraceable_words"].items():
        print(f"   {w!r}: {e['rows']} rows, severity {e['severity']}, src {e['srcs']}, "
              f"asks {e['asks']}")
    if a.out:
        p = pathlib.Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                     newline="\n")
        print(f"[grader] audit -> {p}")
    # Exit 1 on an ASSERTED untraceable word only. The heard-not-told class is reported, not fatal:
    # it is question-word leakage the bench already names cross_echo, and collapsing the two would
    # let the tool's own severity judgement hide inside its exit code.
    return 1 if vc["UNTRACEABLE_ASSERTED"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
