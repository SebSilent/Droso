"""One number for how much of an animal he is, and the parts it is made of.

Everything so far has been argued one measurement at a time: vocabulary here, a
battery there, a speech sample eyeballed from a stream. That is fine for finding a
broken thing and useless for deciding whether a change helped, because the parts
trade against each other. Feeding him the prose book raised his vocabulary by 200
words and took his sentences from four words to one. Nothing I was watching would
have shown that as a loss.

So this measures all of it at once, against the live animal over HTTP, and writes a
snapshot so two points in his life can be compared instead of remembered.

Dimensions, and why each is here:

  body         world speed and decision rate -- a slow animal learns less per hour
  vocabulary   words assimilated, and words heard but not yet assimilated, because
               the gap between them is the twelve-hearing threshold doing its work
  memory       propositions held, and role recovery against its own chance rate
  comprehension  questions from what he was read, and the same questions rephrased,
               because a battery he has seen before measures the battery
  speech       the fraction of what he says unprompted that is more than one word,
               and the mean length of it
  coding       the library, how much of it has real evidence, how much is trusted
               enough to replay, and whether retrieval finds it
  honesty      questions he has no memory for. An animal that answers everything is
               not confident, it is confabulating, and the only way to tell the two
               apart is to ask it something it cannot know

Usage:
    python tools/fitness.py                    # measure and print
    python tools/fitness.py --save gen1        # and record a snapshot
    python tools/fitness.py --compare a b      # two snapshots
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPS = ROOT / "state" / "fitness"
BASE = "http://127.0.0.1:7773"

# Questions from the graded corpus, where one memory answers each.
BATTERY = [
    ("who feeds droso", "parent"),
    ("who pets droso", "parent"),
    ("droso wants what", "food"),
    ("how is the food", "warm"),
    ("where is droso", "home"),
    ("who holds light", "parent"),
    ("how is day", "bright"),
    ("how is night", "quiet"),
    ("where is food", "here"),
    ("who opens file", "parent"),
]
# The same facts asked in words the corpus never used together.
NOVEL = [
    ("which person gives droso his food", "parent"),
    ("tell me the temperature of the food", "warm"),
    ("what place does droso live in", "home"),
    ("who is the one holding the light", "parent"),
    ("describe the day to me", "bright"),
]
# Things no memory of his contains. The right answer is that he does not know.
UNKNOWABLE = [
    "who painted the cathedral in 1402",
    "what is the capital of a country he has never heard of",
    "which quantum field explains his mood",
    "who won the race on the moon",
]


def _get(path: str, timeout: float = 200.0):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.load(r)


def _post(path: str, data: dict, timeout: float = 200.0):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _accept(said: str, want: str) -> bool:
    """Does the answer contain the fact, in any word order or article."""
    s = re.sub(r"[^a-z ]", " ", str(said or "").lower())
    return bool(re.search(r"\b%s\b" % re.escape(want.lower()), s))


def measure(sample_seconds: float = 90.0) -> dict:
    t0 = time.time()
    out: dict = {"measured_at": round(t0, 1)}

    st = _get("/api/language/state")
    ex = _get("/api/language/exposure")
    cx = _get("/api/cortex")
    w = _get("/api/world/state")
    g = _get("/api/neural/growth").get("growth", {}) or {}
    q = _get("/api/language/questions")

    # WORLD SPEED IS A STEADY-STATE NUMBER AND THIS WINDOW INCLUDES THE BOOT. Measured on a
    # RUNNING house it reaches 4.35x (ticks 27, tps 2.173, world_clock 54.0 at t+45s), inside
    # the range Track B reached. This reports 1.2-1.4 because the sample starts before the
    # being is awake and the ramp drags the average down -- so a low reading here is evidence
    # about the BOOT, not about how fast he thinks once he is up. Read it as "how much of the
    # window he was actually alive", not as a speed.
    out["body"] = {"world_speed_x": w.get("measured_speed_x"),
                   "decisions_per_s": g.get("accel_decisions_per_s"),
                   "world_clock": w.get("world_clock")}
    out["vocabulary"] = {
        "words": st.get("vocabulary_size"),
        "distinct_heard": ex.get("distinct_words_heard"),
        "total_heard": ex.get("words_heard_total"),
        # the fraction of what he has met that he can actually use
        "assimilated_fraction": round(
            float(st.get("vocabulary_size") or 0)
            / max(1.0, float(ex.get("distinct_words_heard") or 1)), 3),
        "book": ex.get("book"),
        "reading": bool(ex.get("enabled"))}

    rr = cx.get("role_recovery_on_own_memory") or {}
    chance = float(rr.get("chance") or 0.0)
    out["memory"] = {
        "propositions": (cx.get("binder") or {}).get("propositions"),
        "role_recovery_sentence": rr.get("accuracy_given_rest_of_sentence"),
        "role_recovery_one_word": rr.get("accuracy_given_one_word"),
        "chance": chance,
        # how many times better than guessing, which is the comparable number
        "recovery_margin_over_chance": round(
            float(rr.get("accuracy_given_rest_of_sentence") or 0) / chance, 2)
        if chance else None,
        "candidate_agents": rr.get("candidate_agents"),
        "question_words": q.get("effective_interrogatives"),
        "last_error": st.get("last_error")}

    # comprehension: wait for fresh speech to accumulate while we ask questions
    bat = []
    for question, want in BATTERY:
        a = _post("/api/language/answer", {"question": question})
        said = str(a.get("utterance") or "")
        bat.append({"ask": question, "said": said[:60], "want": want,
                    "accepted": _accept(said, want),
                    "refused": not said.strip()})
    nov = []
    for question, want in NOVEL:
        a = _post("/api/language/answer", {"question": question})
        said = str(a.get("utterance") or "")
        nov.append({"ask": question, "said": said[:60], "want": want,
                    "accepted": _accept(said, want)})
    unk = []
    for question in UNKNOWABLE:
        a = _post("/api/language/answer", {"question": question})
        said = str(a.get("utterance") or "")
        reason = str(a.get("reason") or "")
        # He passes if he does not assert an answer. An utterance is an assertion;
        # a reason naming missing memory is a refusal.
        unk.append({"ask": question, "said": said[:60],
                    "refused": (not said.strip()) or bool(
                        re.search(r"no memory|does not know|cannot|nothing",
                                  reason.lower()))})
    out["comprehension"] = {
        "corpus_battery": sum(1 for b in bat if b["accepted"]),
        "corpus_battery_total": len(bat),
        "novel_phrasings": sum(1 for b in nov if b["accepted"]),
        "novel_total": len(nov),
        "battery_detail": [b for b in bat if not b["accepted"]][:4],
        "novel_detail": [b for b in nov if not b["accepted"]][:4]}
    out["honesty"] = {
        "refused_unanswerable": sum(1 for u in unk if u["refused"]),
        "unanswerable_total": len(unk),
        "confabulations": [u for u in unk if not u["refused"]][:3]}

    # speech: what he says when nobody asks
    before = len(_get("/api/language/stream?since=0").get("events") or [])
    time.sleep(max(1.0, float(sample_seconds)))
    ev = _get("/api/language/stream?since=0").get("events") or []
    fresh = [e for e in ev if e.get("speaker") == "droso"]
    mw = [e for e in fresh if len(str(e.get("text", "")).split()) > 1]
    lengths = [len(str(e.get("text", "")).split()) for e in fresh]
    out["speech"] = {
        "utterances_sampled": len(fresh),
        "multi_word": len(mw),
        "multi_word_fraction": round(len(mw) / max(1, len(fresh)), 3),
        "mean_words": round(sum(lengths) / max(1, len(lengths)), 2),
        "longest": max(lengths) if lengths else 0,
        "samples": [str(e.get("text"))[:60] for e in mw[-5:]],
        "stream_grew_by": len(ev) - before}

    pr = (_get("/api/procedures?limit=2000") or {}).get("procedures") or []
    trusted = [r for r in pr if float(r.get("confidence") or 0) >= 0.70]
    out["coding"] = {
        "library": len(pr),
        "verified": sum(1 for r in pr if r.get("verified")),
        "trusted_replayable": len(trusted),
        "trusted_fraction": round(len(trusted) / max(1, len(pr)), 3)}

    out["seconds"] = round(time.time() - t0, 1)
    out["score"] = _score(out)
    return out


def _skill(acc, chance) -> float:
    """Accuracy rescaled so 0 is guessing and 1 is perfect.

    Raw accuracy is not comparable between two moments in his life, because the
    difficulty moves: the chance rate is 1/N over the agents he has to choose
    between, and that went from 3 candidates to 11 as his memory filled. Measured
    raw, role recovery "fell" from 0.64 to 0.49 in the same step that its margin
    over guessing rose from 1.9x to 5.3x. An instrument that reports getting
    better as getting worse is worse than no instrument.
    """
    try:
        a, c = float(acc or 0.0), float(chance or 0.0)
    except (TypeError, ValueError):
        return None
    # A chance rate of 0.5 or more means a candidate pool of one or two, and there is no
    # skill left to measure. Returning 0.0 there reported a collapsed pool as a failed
    # goal, which is how the composite silently lost 0.10 on binding while his binding was
    # untouched. None means "not measured", and the composite excludes it instead.
    if c >= 0.5:
        return None
    if a <= c:
        return 0.0
    den = 1.0 - c
    return round(min(1.0, (a - c) / den), 3) if den > 0 else None


def _score(m: dict) -> dict:
    """A composite, with the parts visible.

    Weighted by what the three goals actually need, and deliberately reported
    alongside its parts: a single number is for comparing two moments in his life,
    never for deciding what to do next.
    """
    v = m.get("vocabulary") or {}
    mem = m.get("memory") or {}
    comp = m.get("comprehension") or {}
    sp = m.get("speech") or {}
    cod = m.get("coding") or {}
    hon = m.get("honesty") or {}

    def frac(a, b):
        return round(float(a or 0) / float(b), 3) if b else 0.0

    # A literate adult holds roughly 20,000 word families. This term saturated at
    # 3,000, and he crossed that mid-session, so the composite rose 0.076 on the day
    # vocabulary stopped counting at all -- a jump that measured the ceiling and not
    # the animal. Mean sentence length is scored alongside the multi-word fraction,
    # because a two-word utterance and a six-word one are not the same achievement
    # and the fraction alone rated them identically.
    words = float(v.get("words") or 0)
    mw = float(sp.get("multi_word_fraction") or 0.0)
    length = min(1.0, float(sp.get("mean_words") or 0.0) / 6.0)

    parts = {
        # goal 1: speak English
        "language": round(0.3 * min(1.0, words / 20000.0) + 0.4 * mw
                          + 0.3 * length, 3),
        # goal 1b: understand what is said to him
        "comprehension": round(0.6 * frac(comp.get("corpus_battery"),
                                          comp.get("corpus_battery_total"))
                               + 0.4 * frac(comp.get("novel_phrasings"),
                                            comp.get("novel_total")), 3),
        # goal 3: reasoning -- binding roles is the primitive it is built from
        "binding": _skill(mem.get("role_recovery_sentence"), mem.get("chance")),
        # goal 3b: knowing the limits of what he knows
        "honesty": frac(hon.get("refused_unanswerable"),
                        hon.get("unanswerable_total")),
        # goal 2: code from his own verified library
        "coding": round(0.5 * min(1.0, float(cod.get("library") or 0) / 500.0)
                        + 0.5 * float(cod.get("trusted_fraction") or 0.0), 3),
    }
    weights = {"language": 0.30, "comprehension": 0.20, "binding": 0.20,
               "honesty": 0.10, "coding": 0.20}
    # A part that could not be measured is EXCLUDED and the remaining weights are
    # renormalised, rather than counted as zero. Counting it as zero is the same error as
    # reading a missing organ as a confident zero: it makes "we could not measure this"
    # and "he failed this" indistinguishable, and drags a composite that is supposed to
    # summarise what he can do.
    live = {k: v for k, v in parts.items() if v is not None}
    wsum = sum(weights[k] for k in live) or 1.0
    total = round(sum(live[k] * weights[k] for k in live) / wsum, 4)
    return {"composite": total, "weights": weights, "parts": parts,
            "unmeasured": sorted(k for k in parts if parts[k] is None),
            "renormalised_over": round(wsum, 3)}


def save(name: str, m: dict) -> Path:
    SNAPS.mkdir(parents=True, exist_ok=True)
    p = SNAPS / f"{name}.json"
    p.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return p


def load(name: str) -> dict:
    p = Path(name) if Path(name).exists() else SNAPS / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def compare(a: str, b: str) -> dict:
    x, y = load(a), load(b)
    rows = []

    def walk(pa, pb, path=""):
        if isinstance(pa, dict) and isinstance(pb, dict):
            for k in sorted(set(pa) | set(pb)):
                if k in ("samples", "battery_detail", "novel_detail",
                         "confabulations", "last_error", "measured_at"):
                    continue
                walk(pa.get(k), pb.get(k), f"{path}.{k}" if path else k)
        elif isinstance(pa, (int, float)) and isinstance(pb, (int, float)):
            d = float(pb) - float(pa)
            rows.append({"measure": path, "before": pa, "after": pb,
                         "delta": round(d, 4),
                         "pct": round(100.0 * d / float(pa), 1) if pa else None})
        elif pa != pb:
            rows.append({"measure": path, "before": pa, "after": pb,
                         "delta": None, "pct": None})

    walk(x, y)
    sx = (x.get("score") or {}).get("composite")
    sy = (y.get("score") or {}).get("composite")
    return {"from": a, "to": b, "composite_before": sx, "composite_after": sy,
            "composite_delta": round((sy or 0) - (sx or 0), 4),
            "changed": [r for r in rows if r["delta"] not in (0, 0.0, None)]}


def repeat(n: int, sample_seconds: float) -> dict:
    """Measure the same animal N times and report the spread.

    Every headline number in this project has been n=1. Multi-word speech read 15%,
    22%, 25%, 31%, 33%, 37%, 44%, 50% and 67% at different points in one session --
    and those were samples of 8 to 45 utterances, so most of that swing is the
    sampling and not the animal. Without this, "it improved" is not a claim that can
    be checked, and a change that does nothing looks like a change that works about
    as often as one that does.

    Run back to back, so what is measured is sampling noise on a nearly fixed state.
    That is the floor: any claimed improvement smaller than the spread here is not
    visible yet, whatever else it may be.
    """
    import statistics
    runs = []
    for i in range(int(n)):
        try:
            runs.append(measure(sample_seconds))
        except urllib.error.URLError:
            break
    if not runs:
        return {"error": "house not reachable", "runs": 0}

    def collect(fn):
        vals = []
        for m in runs:
            try:
                v = fn(m)
            except Exception:
                v = None
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if not vals:
            return None
        out = {"mean": round(statistics.fmean(vals), 4),
               "min": round(min(vals), 4), "max": round(max(vals), 4),
               "spread": round(max(vals) - min(vals), 4), "n": len(vals)}
        if len(vals) > 1:
            out["stdev"] = round(statistics.stdev(vals), 4)
        return out

    tracked = {
        "composite": lambda m: m["score"]["composite"],
        "score.language": lambda m: m["score"]["parts"]["language"],
        "score.comprehension": lambda m: m["score"]["parts"]["comprehension"],
        "score.binding": lambda m: m["score"]["parts"]["binding"],
        "score.honesty": lambda m: m["score"]["parts"]["honesty"],
        "score.coding": lambda m: m["score"]["parts"]["coding"],
        "speech.multi_word_fraction": lambda m: m["speech"]["multi_word_fraction"],
        "speech.mean_words": lambda m: m["speech"]["mean_words"],
        "speech.utterances_sampled": lambda m: m["speech"]["utterances_sampled"],
        "comprehension.corpus_battery": lambda m: m["comprehension"]["corpus_battery"],
        "comprehension.novel": lambda m: m["comprehension"]["novel_phrasings"],
        "honesty.refusals": lambda m: m["honesty"]["refused_unanswerable"],
        "memory.role_recovery": lambda m: m["memory"]["role_recovery_sentence"],
        "memory.chance": lambda m: m["memory"]["chance"],
        "vocabulary.words": lambda m: m["vocabulary"]["words"],
        "body.world_speed_x": lambda m: m["body"]["world_speed_x"],
    }
    out = {"runs": len(runs), "sample_seconds_each": sample_seconds,
           "spread": {k: collect(f) for k, f in tracked.items()}}
    # A binomial standard error on the speech fraction, which is the noisiest
    # number in the whole report and the one most often quoted.
    mw = [m["speech"]["multi_word"] for m in runs]
    ut = [m["speech"]["utterances_sampled"] for m in runs]
    tot_mw, tot_ut = sum(mw), sum(ut)
    if tot_ut:
        p = tot_mw / tot_ut
        out["speech_pooled"] = {
            "multi_word": tot_mw, "utterances": tot_ut,
            "fraction": round(p, 4),
            "std_error": round((p * (1 - p) / tot_ut) ** 0.5, 4),
            "note": "pooled across runs; the per-run spread above is what a single "
                    "measurement of this size is worth"}
    # The dimensions whose spread swamps any plausible effect.
    out["noise_dominated"] = sorted(
        k for k, v in out["spread"].items()
        if v and v.get("spread") is not None and v["mean"]
        and v["spread"] > 0.5 * abs(v["mean"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default=None, help="snapshot name")
    ap.add_argument("--sample-seconds", type=float, default=90.0)
    ap.add_argument("--repeat", type=int, default=0,
                    help="measure N times and report the spread instead of one "
                         "number that cannot be distinguished from noise")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    if a.compare:
        print(json.dumps(compare(*a.compare), indent=1))
        return 0
    if a.repeat:
        print(json.dumps(repeat(a.repeat, a.sample_seconds), indent=1))
        return 0
    try:
        m = measure(a.sample_seconds)
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"house not reachable at {BASE}: {e}"}))
        return 1
    if a.save:
        m["snapshot"] = a.save
        m["saved_to"] = str(save(a.save, m))
    print(json.dumps(m, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
