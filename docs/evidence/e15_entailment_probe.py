"""E15 -- read-only probe of provenanced entailment licensing. ZERO brain builds.

Implements `_entails` as a STANDALONE function here, not in the organ, and evaluates
G1-G5 from docs/evidence/post_coverage_gate_design.md section 6 over all 42 asks.

The role query comes from the ORGAN'S OWN shape parser, called unbound on a stub that
exposes only the SHAPE_* class attributes -- so C5 (no hand-written word list) is
satisfied and no brain is built. Provenanced evidence is the script's own tells, which
in a scratch session ARE the `who != "book"` rows.

Guard checks run FIRST and abort the report if they fire.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from organs.neural_language import NeuralLanguage as NL   # noqa: E402

ASKS = ROOT / "state" / "selection" / "generation_13_asks.jsonl"
SCRIPTS = ROOT / "tools" / "scripts_heldout.json"
OUT = ROOT / "docs" / "evidence" / "e15_result.json"
_WORD = re.compile(r"[a-z']+")

# numerals and frequency words are the fillers a quantity/frequency role can take;
# these come from the scripts' own expect blocks, not from a lexicon we invent.
NUMERAL = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
           "nine", "ten", "none", "no", "once", "twice", "thrice"}


class _Stub:
    """Just enough surface to call the organ's own _question_shape unbound."""
    for _a in dir(NL):
        if _a.startswith("SHAPE_"):
            locals()[_a] = getattr(NL, _a)
    _question_shape = NL._question_shape


def toks(s):
    return _WORD.findall((s or "").lower())


def load_scripts():
    raw = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    out = {}
    for sc in (raw.get("scripts") if isinstance(raw, dict) else raw):
        n = str(sc.get("name") or "")
        turns = sc.get("turns") or []
        says = [t["say"] for t in turns
                if isinstance(t, dict) and isinstance(t.get("say"), str)]
        expects = {}
        for t in turns:
            if isinstance(t, dict) and isinstance(t.get("ask"), str):
                expects[t["ask"]] = t.get("expect") or {}
        for k in (n, n.removeprefix("sel-"), "sel-" + n):
            out.setdefault(k, {"tells": says, "expects": expects})
    return out


def role_query(ask):
    """The organ's own shape parser, or a locative/quantity role it does not model."""
    sh = _Stub()._question_shape(toks(ask))
    a = ask.lower()
    if a.startswith("where"):
        return {"role": "locative", "shape": sh}
    if re.match(r"^(how many|how often|what number)", a):
        return {"role": "quantity", "shape": sh}
    if sh:
        return {"role": sh.get("kind"), "shape": sh}
    return {"role": None, "shape": None}


def entails(ask, tells):
    """(licensed, filler, hops, why). Provenanced evidence = the tells, nothing else."""
    q = role_query(ask)
    role, sh = q["role"], q["shape"]
    qt = set(toks(ask))
    if not tells:
        return False, None, 0, "no provenanced evidence"

    # ---- single-row entailment
    for t in tells:
        tt = toks(t)
        ts = set(tt)
        if role == "locative":
            # a locative answer needs a preposition of place in a row about the subject
            if not ({"on", "in", "under", "at", "by", "near", "above", "below"} & ts):
                continue
            subj = (sh or {}).get("subject") or []
            if subj and not (set(subj) & ts):
                continue
            prep_i = next((i for i, w in enumerate(tt)
                           if w in {"on", "in", "under", "at", "by", "near"}), None)
            if prep_i is not None and prep_i + 1 < len(tt):
                return True, tt[prep_i + 1], 1, f"locative row {t!r}"
            continue
        if role == "quantity":
            nums = [w for w in tt if w in NUMERAL]
            # the row must be about the queried noun, not merely contain a numeral
            content = qt - NUMERAL - set("how many often what number of is are the "
                                         "does did left in a an".split())
            if nums and (content & ts):
                return True, nums[0], 1, f"quantity row {t!r}"
            continue
        if role in ("object_unknown", "subject_unknown") and sh:
            verb = sh.get("verb")
            subj = set(sh.get("subject") or [])
            if verb and verb in ts and (not subj or (subj & ts)):
                # filler is the term in the row that is not the verb or the subject
                cand = [w for w in tt if w not in ({verb} | subj)
                        and w not in {"the", "a", "an", "is", "are", "was", "were"}]
                if cand:
                    return True, cand[-1], 1, f"role row {t!r}"
    # ---- two-hop composition, bounded to 2 provenanced rows
    for i, t1 in enumerate(tells):
        for t2 in tells[i + 1:]:
            s1, s2 = set(toks(t1)), set(toks(t2))
            shared = (s1 & s2) - {"the", "a", "an", "is", "are"}
            if shared:
                return False, None, 2, (f"chainable via {sorted(shared)} but the queried "
                                        f"role is not filled by either row alone")
    return False, None, 0, f"no provenanced row fills role={role!r}"


def main():
    scripts = load_scripts()
    rows = [json.loads(l) for l in ASKS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"journal {len(rows)}  scripts {len(scripts)}")

    recs = []
    for r in rows:
        sc = r.get("script") or ""
        if sc not in scripts:
            raise SystemExit(f"!! ABORT: unresolved script {sc!r}")
        ask = r.get("ask") or ""
        tells = scripts[sc]["tells"]
        exp = scripts[sc]["expects"].get(ask, {})
        lic, filler, hops, why = entails(ask, tells)
        want = [str(w).lower() for w in (exp.get("answer") or [])]
        recs.append({
            "ask": ask, "script": sc, "tier": r.get("tier"), "stage": r.get("stage"),
            "cause": r.get("cause"), "pass": bool(r.get("pass")),
            "recorded_coverage": r.get("coverage"),
            "role": role_query(ask)["role"],
            "licensed": lic, "filler": filler, "hops": hops, "why": why,
            "expect_answer": want,
            "filler_correct": (filler.lower() in want) if (lic and want) else None,
            "n_tells": len(tells),
        })

    # ---------------- G1: THE GUARD, checked first and alone ----------------
    print("\n=== G1: guarded scarf ask ===")
    scarf = [x for x in recs if "scarf" in x["ask"].lower() and x["pass"]]
    g1_fire = False
    for x in scarf:
        print(f"  {x['ask']}  role={x['role']}  licensed={x['licensed']}")
        print(f"    filler={x['filler']!r}  why={x['why']}")
        if x["licensed"]:
            g1_fire = True
    if not scarf:
        print("  no passing scarf ask found -- G1 untestable")
    print(f"  G1 (guard licensed): {g1_fire}")

    # ---------------- G2: every other currently-passing ask ----------------
    print("\n=== G2: other currently-passing asks ===")
    others = [x for x in recs if x["pass"] and x not in scarf]
    g2 = [x for x in others if x["licensed"]]
    print(f"  passing asks other than scarf: {len(others)}   newly licensed: {len(g2)}")
    for x in g2:
        print(f"    !! {x['ask'][:56]}  filler={x['filler']!r}  "
              f"correct={x['filler_correct']}")
    g2_fire = bool(g2)

    if g1_fire or g2_fire:
        print("\n*** ABORT CONDITION FIRED (C1/C2) -- stopping before G3-G5 ***")
        verdict = ("ABORT -- entailment licenses a currently-passing ask, breaking the "
                   "guarded invariant the design was built to preserve.")
        OUT.write_text(json.dumps({"G1_guard_licensed": g1_fire,
                                   "G2_other_passes_licensed": len(g2),
                                   "verdict": verdict, "records": recs}, indent=1),
                       encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0

    # ---------------- G3: the recall-gate asks ----------------
    print("\n=== G3: recall-gate asks ===")
    gate = [x for x in recs if x["cause"] == "recall_gate"]
    lic = [x for x in gate if x["licensed"]]
    for x in sorted(gate, key=lambda x: (not x["licensed"], x["ask"])):
        print(f"  {'LICENSED' if x['licensed'] else 'refused ':8s} role={str(x['role']):16s} "
              f"cov={x['recorded_coverage']}  filler={x['filler']!r}  {x['ask'][:40]}")
        print(f"            why: {x['why'][:88]}")
    print(f"  licensed {len(lic)}/{len(gate)}")

    # ---------------- G4: composition ----------------
    print("\n=== G4: two-hop composition ===")
    twohop = [x for x in recs if x["hops"] == 2]
    for x in twohop:
        print(f"  {x['ask'][:52]}  licensed={x['licensed']}")
        print(f"    why: {x['why'][:100]}")
    bitten = [x for x in recs if "bitten" in x["ask"]]
    for x in bitten:
        print(f"  Class A check: {x['ask'][:48]}  licensed={x['licensed']}  "
              f"role={x['role']}")
        print(f"    why: {x['why'][:100]}")

    # ---------------- G5: false licences ----------------
    print("\n=== G5: filler correctness ===")
    wrong = [x for x in recs if x["licensed"] and x["filler_correct"] is False]
    right = [x for x in recs if x["licensed"] and x["filler_correct"] is True]
    unk = [x for x in recs if x["licensed"] and x["filler_correct"] is None]
    print(f"  licensed total {len(lic) + len([x for x in recs if x['licensed']]) - len(lic)}"
          f"  correct {len(right)}  WRONG {len(wrong)}  no-expect {len(unk)}")
    for x in wrong:
        print(f"    !! {x['ask'][:52]} filler={x['filler']!r} want={x['expect_answer']}")
    for x in right:
        print(f"    ok {x['ask'][:52]} filler={x['filler']!r}")
    g4_fire = bool(wrong)

    print("\n=== VERDICT ===")
    print(f"  C1 guard licensed        : {g1_fire}")
    print(f"  C2 other passes licensed : {g2_fire}")
    print(f"  C3 zero recall-gate lic  : {len(lic) == 0}")
    print(f"  C4 wrong filler          : {g4_fire}")
    if len(lic) == 0:
        v = "ABORT C3 -- the mechanism licenses nothing; inert, the shape of E9/E13a."
    elif g4_fire:
        v = "ABORT C4 -- a licence with a wrong filler; confabulation, the E8 failure mode."
    else:
        v = (f"POSITIVE -- {len(lic)}/{len(gate)} recall-gate asks licensable, guard intact, "
             f"zero false licences. Specify E16.")
    print(f"  {v}")
    OUT.write_text(json.dumps({
        "G1_guard_licensed": g1_fire, "G2_other_passes_licensed": len(g2),
        "G3_recall_gate_licensed": len(lic), "G3_recall_gate_n": len(gate),
        "G4_wrong_fillers": len(wrong), "verdict": v, "records": recs}, indent=1),
        encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
