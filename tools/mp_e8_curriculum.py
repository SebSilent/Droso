"""MP-E8 shared curriculum: the one source of truth arms A, B and C all read.

WHY THIS EXISTS. The plan's design line says the three arms run "under identical curricula", and the
agent brief says arms B and C run in separate processes "with the same curriculum files arm A reads".
Arm A's curriculum is not a file: it is a pair of LITERAL LISTS inside tools/electric_learn_bench.py
(SESSIONS and PAIRS). So the honest options were to copy them into a new file, or to read them from
where they actually live. Copying was rejected for the reason run_generation.py:504 already gives for
the frozen tier -- "a copy is a second contract that can drift from the first, and then 'identical
curricula' would be measured against whatever the copy said." This module parses the real lists.

WHAT IT EMITS. A per-session item manifest plus a SHA-256 of the canonical serialization. Every arm's
artifact must carry that hash, so "arm B saw what arm A saw" is a comparison a reader can perform,
not a promise in a design doc.

WHAT IT REFUSES. An unregistered tier. Tier 40 is parsed from arm A's source; tiers 120 and 300 are
EMITTED by the construction rule below, under PI ruling D-MPE8-03 (2026-11-03), which permits
extending the item pool because the plan demands 120 and 300 taught items and 40 cannot be 120. What
the ruling forbids is changing what forgetting means, so the extension is bound to four constraints
and each one is CHECKED at emit time rather than asserted in a docstring:

  (a) same registered frame grammar -- new items are `who/what <verb>s the <object>` svo frames and
      QA pairs of those same shape classes, so the shape arbiter and probes_for() apply unchanged;
  (b) content-word closure -- every content word a new item introduces is taught by that item, and
      every probe ask is built from taught words, registered question words, or function words;
  (c) the probe matrix scales from the registered 136 at tier 40 and every tier keeps distractor rows
      defined as "not answerable from that tier's taught set";
  (d) the rule, the seed, the item counts and the distinct-subject-verb-pair count are registered
      before any run, and the emitted file is committed with its curriculum_sha256.

A tier that fails any check does not get emitted. `--check-tier` re-derives a tier from the rule and
compares hashes, so a committed tier file can be proved to be what the rule says and not hand-edited.

THE ACCEPTANCE RULE, stated once because it moved when 120 and 300 were emitted: a tier is accepted
only if it is authored as code (tier 40, parsed from arm A's own lists) OR a committed tier file
re-derives from the rule. A tier with neither is refused by every path, and the refusal names the cost
of adding one rather than just saying no. `--check-tier` on the code tier checks the source match, not
re-derivation -- the code tier is not emitted, and comparing it against the rule produced a false
MISMATCH alarm (measured) that would have read as "someone hand-edited tier 40".
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "tools" / "electric_learn_bench.py"
TIERS_WITH_CODE = (40,)


def _literal(name: str, tree: ast.AST):
    """The actual AST node for a module-level assignment, or None."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return node.value
    return None


def load(source_path: Path = BENCH) -> dict:
    """Parse SESSIONS and PAIRS out of arm A's own source. No import, no house, no side effects."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    sessions_node = _literal("SESSIONS", tree)
    pairs_node = _literal("PAIRS", tree)
    if sessions_node is None or pairs_node is None:
        raise SystemExit("SESSIONS/PAIRS not found as module-level literals in "
                         f"{source_path.name}: the curriculum moved and this tool is now wrong.")

    sessions = [[_frame(f) for f in grp.elts] for grp in sessions_node.elts]
    pairs = [[_frame(p) for p in grp.elts] for grp in pairs_node.elts]
    dist_node = _literal("DISTRACTORS", tree)
    distractors = [[_frame(t) for t in grp.elts] for grp in dist_node.elts] if dist_node else []
    n_items = sum(len(s) for s in sessions) + sum(len(p) for p in pairs)
    # The canonical form is {sessions: [[call-string]], pairs: [[[ask, answer]]]} -- distractors are
    # deliberately OUTSIDE the hash. Every generated tier must hash the same way or "the arms ran the
    # same curriculum" stops being a comparable claim across tiers.
    canon = json.dumps({"sessions": sessions, "pairs": pairs}, sort_keys=True)
    return {
        "source": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256_lf": hashlib.sha256(
            source_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "sessions": sessions,
        "pairs": pairs,
        "n_session_groups": len(sessions),
        "n_pair_groups": len(pairs),
        "n_tell_frames": sum(len(s) for s in sessions),
        "n_qa_pairs": sum(len(p) for p in pairs),
        "n_distractors": len(distractors),
        "n_items": n_items,
        "distractors": distractors,
        "curriculum_sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
    }


def _frame(node: ast.AST):
    """One taught item: a tuple/list of strings, kept as strings, not evaluated."""
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_frame(e) for e in node.elts]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


def _unregistered_tier_message(tier: int) -> str:
    """The refusal, and the price of not refusing. Shared by every path so one tier cannot get three
    different answers depending on which flag asked about it."""
    return (f"tier {tier} is not a registered tier at all. The authored tiers are {TIERS_AUTHORED}. "
            "This tool will not interpolate a fourth one to make a gate look finished. The cost of "
            "adding a tier is D-MPE8-03's four constraints, with the rule, the seed, the item counts "
            "and the distinct (subject, verb) pair count registered BEFORE any run, and the emitted "
            "file committed with its curriculum_sha256 -- not a number chosen to fill a gap.")


def validate_tier(tier: int, cur: dict) -> None:
    """Guard the arm-A-source parse path. Tiers 120/300 are not in arm A's source and never will be:
    they are emitted by build_tier() and read back from the emitted file."""
    if tier in TIERS_WITH_CODE:
        return
    if tier in TIERS_AUTHORED:
        raise SystemExit(
            f"tier {tier} is not parsed from {cur['source']} -- that file holds "
            f"{cur['n_items']} items and will not grow. Tier {tier} is EMITTED by the D-MPE8-03 "
            "construction rule: run --emit-tier to write it, or --check-tier to prove a committed "
            "tier file still re-derives from the rule and was not hand-edited.")
    raise SystemExit(_unregistered_tier_message(tier))


def sessions_for(tier: int, cur: dict) -> list:
    """Split the curriculum into the plan's three sessions per tier.

    At tier 40 the split is the existing group structure, which is what arm A already teaches: three
    SESSIONS groups of 8 frames, and the PAIRS groups distributed across them. No re-shuffling,
    because a different session boundary changes the interference curve, which is one of the two
    figures MP-E8 exists to produce.
    """
    validate_tier(tier, cur)
    out = []
    for i, sess in enumerate(cur["sessions"]):
        pairs_here = cur["pairs"][i] if i < len(cur["pairs"]) else []
        out.append({"session": i + 1, "tell_frames": sess, "qa_pairs": pairs_here,
                    "n_items": len(sess) + len(pairs_here)})
    return out


# ---------------------------------------------------------------- D-MPE8-03 extension ----
#
# The registered lexicon. Every word here is an ordinary English noun/verb that the frame teaches by
# using it, which is what constraint (b) requires: a word no arm could ever be taught is the stop
# condition, and it is avoided by construction rather than filtered after the fact.
#
# VERBS are restricted to lemmas whose third-person surface is lemma + "s". That is narrower than
# English (it excludes watch->watches, carry->carries) and the restriction is deliberate: probes_for()
# emits both f["verb"] and f["stem"] into different probe shapes, so a stem that does not relate to
# its surface by +s makes the fold shapes ambiguous about which word the item taught. The registered
# tier-40 item "carries"/"carry" already carries that ambiguity; new items do not add to it.
NAMES = ("Nora", "Mira", "Ivo", "the keeper", "the sailor", "the farmer", "the pilot",
         "the gardener", "the welder", "the clerk", "the mason", "the weaver", "the cooper",
         "the turner", "the smith")

NOUNS = ("anvil", "axle", "belt", "bolt", "bottle", "bucket", "buckle", "cage", "candle", "crate",
         "cradle", "drum", "faucet", "fence", "flare", "gauge", "gear", "girdle", "hinge", "horn",
         "jar", "keg", "lantern", "latch", "lock", "loom", "magnet", "mast", "nail", "oar", "pan",
         "peg", "post", "pulley", "raft", "rail", "reel", "ring", "rod", "sail", "scale", "screw",
         "shackle", "sign", "sling", "spool", "stair", "stake", "step", "stove", "strap", "stud",
         "tap", "tile", "torch", "tray", "tread", "tube", "urn", "valve", "vase", "vault", "veil",
         "wagon", "wick", "wire")

# Every lemma here takes a plain +s in the third person. brush/catch/sketch/stitch/touch/mix/polish
# were removed after measuring them against the lint below -- "the welder brushs the rail" is not
# English, and an ungrammatical tell is a curriculum no arm should be graded on.
VERBS = ("bend", "bind", "block", "bolt", "brace", "bridge", "bring", "build",
         "clamp", "clean", "clear", "clip", "close", "cool", "cover", "crank", "cut", "drill",
         "drop", "feed", "file", "fill", "fit", "fold", "guide", "hang", "heat", "hold",
         "hook", "lift", "light", "link", "lock", "lower", "mark", "mend", "oil", "open",
         "pack", "pin", "pipe", "post", "pour", "pull", "raise", "ring", "roll", "rove",
         "saw", "seal", "send", "set", "shift", "shine", "screw", "slide", "smooth",
         "sort", "spin", "stack", "stamp", "store", "support", "tape", "test", "tilt",
         "tie", "tile", "trail", "turn", "unroll", "unlock", "unveil", "wake", "warm",
         "weave", "weigh", "wind", "wipe", "wrap")

# Question words are NOT in SHAPE_FUNCTION_WORDS (measured: organs/neural_language.py:3237 does not
# list them), so they count as content words to the word-level grader. Tier 40 already puts "what"
# and "who" into every ask, so the closure check has to know about them explicitly or it would fail
# on the registered curriculum too.
QUESTION_WORDS = frozenset({"what", "who", "where", "when", "why", "how", "which"})

# Words deliberately excluded from every tier's taught set. These exist so constraint (c) can scale:
# a distractor ask built from one of them is unanswerable from ANY tier, which is the registered
# "harbor was never taught" device (tools/electric_learn_bench.py DISTRACTORS[9]).
NEVER_TAUGHT = ("harbor", "orchard", "cellar", "attic", "meadow", "chapel", "granary", "foothill")

SEED = 20261103          # the date of ruling D-MPE8-03, chosen so the seed is not a magic number
TIERS_AUTHORED = (40, 120, 300)


def _svo_call(subj: str, verb: str, obj: str) -> str:
    """One taught item, written the way arm A writes its own: a literal svo(...) call.

    The subject keeps its article when it is a thing and drops it when it is a name, because that is
    the registered pattern ("the dog bites the latch" / "Nora carries the lantern"), and the ask word
    follows it: 'what' for a thing, 'who' for a name.
    """
    is_name = not subj.startswith("the ") and subj[0].isupper()
    q = "who" if is_name else "what"
    phrase = subj if is_name else subj
    stem = verb
    surface = stem + "s"
    tell = f"{phrase} {surface} the {obj}"
    return (f"svo('{tell}', '{q}', '{subj.replace('the ', '')}', '{surface}', '{stem}', '{obj}')")


def build_tier(tier: int, seed: int = SEED) -> dict:
    """Emit a tier manifest under D-MPE8-03. Tier 40 is NOT regenerated -- it is parsed from arm A.

    New items are ADDED to the registered 40 rather than replacing them, so every registered item and
    every registered session boundary survives: the original 40 stay in the sessions arm A already
    teaches them in, because moving an item across a session boundary changes the interference curve,
    which is one of the two figures MP-E8 exists to produce.
    """
    base = load()
    if tier == 40:
        return base
    if tier not in TIERS_AUTHORED:
        raise SystemExit(f"tier {tier} is not an authored tier; the registered tiers are "
                         f"{TIERS_AUTHORED}. This tool will not invent a fourth one.")

    n_tell = tier * 3 // 5           # 40 -> 24, 120 -> 72, 300 -> 180  (the registered 3:2 tell:pair)
    n_pair = tier - n_tell           # 40 -> 16, 120 -> 48, 300 -> 120
    add_tell = n_tell - base["n_tell_frames"]
    add_pair = n_pair - base["n_qa_pairs"]

    # Lexicon lint, not a remembered word list: any lemma whose third person is NOT lemma+"s"
    # would be emitted as "mixs"/"polishs"/"drys". The surface==stem+"s" check downstream cannot
    # catch this because it generates the surface the same way, so the filter has to run on the
    # lemma itself before anything is drawn.
    bad = [v for v in VERBS if v.endswith(("s", "x", "z", "sh", "ch", "o"))
           or (v.endswith("y") and len(v) > 1 and v[-2] not in "aeiou")]
    if bad:
        raise SystemExit(f"these lemmas do not take a plain +s third person and would be emitted "
                         f"as ungrammatical surfaces: {bad}. Remove them or add an -es rule.")

    subjects = [s for s in NAMES] + [f"the {n}" for n in NOUNS]
    rng = random.Random(seed)
    combos = [(s, v, o) for s in subjects for v in VERBS for o in NOUNS
              if s.replace("the ", "") != o]
    rng.shuffle(combos)

    # Registered frames are unparsed svo(...) CALL STRINGS, not lists -- indexing them by position
    # silently yields characters, so every field goes through the same parser the emitted tiers use.
    used_pairs = set()
    used_sents = set()
    for s in base["sessions"]:
        for call in s:
            f = _frame_from_call(call)
            used_pairs.add((f["subj"], f["verb"]))      # verb is the SURFACE form
            used_sents.add(f["tell"])
    for p in base["pairs"]:
        for q, a in p:
            used_sents.add(a)

    # used_pairs holds SURFACE verbs because that is what the registered frames store ("bites");
    # the new items are drawn as lemmas, so the comparison is against lemma+"s". Comparing lemma to
    # surface would let "the anvil taps" and "the anvil taps the jar" both through as distinct.
    new_tells, new_pairs = [], []
    for s, v, o in combos:
        if len(new_tells) >= add_tell:
            break
        if (s.replace("the ", ""), v + "s") in used_pairs:
            continue
        used_pairs.add((s.replace("the ", ""), v + "s"))
        new_tells.append((s, v, o))
    for s, v, o in combos:
        if len(new_pairs) >= add_pair:
            break
        if (s.replace("the ", ""), v + "s") in used_pairs:
            continue
        used_pairs.add((s.replace("the ", ""), v + "s"))
        new_pairs.append((s, v, o))
    if len(new_tells) < add_tell or len(new_pairs) < add_pair:
        raise SystemExit(f"the registered lexicon cannot supply {add_tell} tells + {add_pair} pairs "
                         f"with distinct (subject, verb) pairs: got {len(new_tells)} + "
                         f"{len(new_pairs)}. This is D-MPE8-03's stop condition; nothing was emitted.")

    # Session distribution is exact arithmetic, not a fill loop: the registered tier has 8 tells per
    # session and 5/5/6 pairs, and each tier's per-session totals are tier/3 split 3:2. Both divide
    # evenly at 120 (24 tells + 16 pairs) and 300 (60 + 40), so no session boundary is fuzzy.
    sess = [{"session": i + 1,
             "tell_frames": list(g),
             "qa_pairs": [list(p) for p in base["pairs"][i]] if i < len(base["pairs"]) else []}
            for i, g in enumerate(base["sessions"])]
    t_per, p_per = n_tell // 3, n_pair // 3
    ti = pi = 0
    for i in range(3):
        for _ in range(t_per - len(sess[i]["tell_frames"])):
            s, v, o = new_tells[ti]; ti += 1
            sess[i]["tell_frames"].append(_svo_call(s, v, o))
        for _ in range(p_per - len(sess[i]["qa_pairs"])):
            s, v, o = new_pairs[pi]; pi += 1
            q = "who" if (not s.startswith("the ") and s[0].isupper()) else "what"
            sess[i]["qa_pairs"].append([f"{q} {v}s the {o}?", f"{s} {v}s the {o}"])
    if ti != len(new_tells) or pi != len(new_pairs):
        raise SystemExit(f"distribution lost items: {ti}/{len(new_tells)} tells, "
                         f"{pi}/{len(new_pairs)} pairs placed")

    # Distractors scale from the registered 12 (6 role_swap + 6 qword) at 0.3 per item. Each new one
    # is built from this tier's own vocabulary and then PROVED unanswerable against this tier's
    # taught set -- constraint (c) defines them as "not in that tier's taught set", so that is the
    # check, not a comment saying "no such tell".
    n_dist = len(base["distractors"]) * tier // 40
    dist = [list(d) for d in base["distractors"]]
    taught_sents = {_frame_from_call(c)["tell"] for s in sess for c in s["tell_frames"]} | \
                   {a[1] for s in sess for a in s["qa_pairs"]}
    # (verb, object) pairs this tier teaches -- the thing a role_swap must NOT match, or the
    # distractor becomes answerable and the tier's refusal rate means something else.
    vo_tier = set()
    for s in sess:
        for c in s["tell_frames"]:
            f = _frame_from_call(c)
            if f["kind"] == "svo":
                vo_tier.add((f["verb"], f["obj"]))
        for ask, ans in s["qa_pairs"]:
            m = re.match(r"(?:the )?([A-Za-z]+) (\w+s) the ([a-z]+)$", ans)
            if m:
                vo_tier.add((m.group(2), m.group(3)))
    pool = new_tells or combos
    i = 0
    while len(dist) < n_dist:
        s, v, o = pool[i % len(pool)]
        sc = s.replace("the ", "")
        q = "who" if (not s.startswith("the ") and s[0].isupper()) else "what"
        mode = i % 4
        if mode == 0:
            ask, why = f"{q} {v}s the {sc}", "the other direction is not taught"
        elif mode == 1:
            ask, why = f"why does the {sc} {v} the {o}", "no why path claimed"
        elif mode == 2:
            ask, why = f"how does the {sc} {v} the {o}", "no how path claimed"
        else:
            ask, why = f"where is the {NEVER_TAUGHT[(i // 4) % len(NEVER_TAUGHT)]}", \
                       "was never taught in any tier"
        if (ask not in {d[1] for d in dist}
                and (mode == 3 or (v + "s", sc) not in vo_tier)):
            dist.append(["qword" if mode else "role_swap", ask, why])
        i += 1
        if i > 100 * n_dist:
            raise SystemExit("distractor construction stalled: no unanswerable asks left to build")

    cur = _finish(base, sess, dist, tier, seed, n_dist)
    problems = check_tier(cur)
    if problems:
        raise SystemExit("tier %d FAILS its own construction constraints:\n  " % tier
                         + "\n  ".join(problems) + "\nNothing was emitted.")
    return cur


def _finish(base: dict, sess: list, dist: list, tier: int, seed: int, n_dist: int) -> dict:
    """Canonicalize exactly the way tier 40 is canonicalized: sha over {sessions, pairs} only.

    Distractors ride alongside in the manifest but are NOT in the hash, because the registered tier-40
    hash does not include them and a generated tier whose hash meant something different would make
    "the arms ran the same curriculum" an incomparable claim across tiers.
    """
    canon = json.dumps({"sessions": [[c for c in s["tell_frames"]] for s in sess],
                        "pairs": [[list(p) for p in s["qa_pairs"]] for s in sess]},
                       sort_keys=True)
    for s in sess:
        s["n_items"] = len(s["tell_frames"]) + len(s["qa_pairs"])
    n_tell = sum(len(s["tell_frames"]) for s in sess)
    n_pair = sum(len(s["qa_pairs"]) for s in sess)
    return {
        "schema": "droso.curriculum.v1",
        "tier": tier,
        "curriculum_sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
        "source": base["source"] if tier == 40 else f"{base['source']} + D-MPE8-03 rule",
        "source_sha256_lf": base["source_sha256_lf"],
        "n_items": n_tell + n_pair,
        "n_tell_frames": n_tell,
        "n_qa_pairs": n_pair,
        "n_distractors": len(dist),
        "sessions": sess,
        "distractors": dist,
        "construction": {
            "ruling": "D-MPE8-03",
            "rule": ("registered tier-40 items kept verbatim and in their original sessions; new items "
                     "are svo frames drawn from the registered lexicon (NAMES/NOUNS/VERBS in "
                     "tools/mp_e8_curriculum.py) by random.Random(seed).shuffle over every "
                     "(subject, verb, object) combination with subject != object, taken in shuffled "
                     "order, skipping any (subject, verb) pair already used; tells and pairs split "
                     "3:2 per session; distractors at 0.3 per item, each proved unanswerable against "
                     "this tier's taught set"),
            "seed": seed,
            "python_random": "random.Random(seed).shuffle -- Mersenne Twister, stable across "
                             "CPython versions; the seed and the interpreter version are both "
                             "recorded so the draw can be re-derived",
            "n_new_tell_frames": n_tell - base["n_tell_frames"],
            "n_new_qa_pairs": n_pair - base["n_qa_pairs"],
            "n_new_distractors": len(dist) - len(base["distractors"]),
        },
        "consumers_must_record": ("curriculum_sha256. Two arms that disagree on it did not run the "
                                  "same experiment, whatever their configs say."),
    }


# The three frame builders in arm A's source, and the argument ORDER each one takes. The order is
# not uniform -- obl() puts (tail, q, prep) where svo() puts (q, ..., obj) -- so this table is the
# only safe way to turn a call string back into the dict probes_for() consumes. Reading it from the
# bench's own source rather than retyping it: if a signature changes, this raises instead of
# silently building probes out of the wrong fields.
def _helper_signature() -> dict:
    tree = ast.parse(BENCH.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("svo", "obl", "intr"):
            out[node.name] = [p.arg for p in node.args.args]
    if set(out) != {"svo", "obl", "intr"}:
        raise SystemExit(f"frame builders changed shape in {BENCH.name}: found {sorted(out)}")
    return out


def _frame_from_call(call: str) -> dict:
    """svo('the anvil taps the jar', 'what', 'anvil', 'taps', 'tap', 'jar') -> that dict.

    Parsed, never eval'd: this file does not execute curriculum text as code. `kind` is the helper
    name, which is what probes_for() branches on."""
    node = ast.parse(call, mode="eval").body
    if not isinstance(node, ast.Call) or getattr(node.func, "id", "") not in ("svo", "obl", "intr"):
        raise SystemExit(f"tell frame is not a svo/obl/intr call: {call!r}")
    name = node.func.id
    args = [a.value for a in node.args]
    if len(args) != len(_helper_signature()[name]):
        raise SystemExit(f"{name}() called with {len(args)} args, source says "
                         f"{len(_helper_signature()[name])}: {call!r}")
    f = dict(zip(_helper_signature()[name], args))
    f["kind"] = name
    if name == "intr":
        f["q"] = "what"          # intr() supplies q itself; mirror that, do not guess
    return f


def taught_content(cur: dict) -> set:
    """Every content word this tier teaches, INCLUDING the stem each frame declares.

    The stem is taught explicitly, not derived: probes_for() asks with f["stem"] ("what does the dog
    bite") while the tell carries the surface form ("bites"), so the stem is part of what the item
    teaches and the word-level grader's trace set must contain it. Running organs.stemming over the
    surface forms instead was tried first and does not reduce them (measured: stem('cuts') is not
    'cut'), which would have made every probe in every tier look untaught.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import word_provenance as wp
    out = set()
    for s in cur["sessions"]:
        for call in s["tell_frames"]:
            f = _frame_from_call(call)
            out |= set(wp.content_words(f["tell"]))
            out.add(f["stem"])
        for ask, ans in s["qa_pairs"]:
            out |= set(wp.content_words(ans))
    return out


def check_tier(cur: dict) -> list:
    """Measure the four D-MPE8-03 constraints. Returns a list of violations; empty means emit."""
    import re
    problems = []
    tier = cur["tier"]
    base = load()

    # Constraint (a) binds the NEW items. The registered 40 are the baseline and are not re-proved:
    # three of them ("the lantern belongs to Mira", "the bell hangs on the wall", "the copper bell
    # rings") are obl/intransitive and would fail an svo-only check through no fault of this tier.
    reg_calls = {c for g in base["sessions"] for c in g}
    reg_pairs = {tuple(p) for g in base["pairs"] for p in g}
    for s in cur["sessions"]:
        for call in s["tell_frames"]:
            if call in reg_calls:
                continue
            f = _frame_from_call(call)
            tell, q, verb, stem = f["tell"], f["q"], f["verb"], f["stem"]
            if f["kind"] != "svo":
                problems.append(f"new item is not an svo frame ({f['kind']}): {tell!r}")
                continue
            if q not in ("what", "who"):
                problems.append(f"ask word {q!r} is not a registered shape class: {tell!r}")
            if verb != stem + "s":
                problems.append(f"surface {verb!r} is not stem {stem!r} + 's': {tell!r}")
            if not re.fullmatch(r"(the [a-z ]+|[A-Z][a-z]*) " + re.escape(verb) + r" the [a-z ]+",
                                tell):
                problems.append(f"tell leaves the registered grammar: {tell!r}")

    # distinct (subject, verb) pairs -- the count the ruling requires be registered.
    # Tells expose their fields, so their pairs are read from the frame. QA answers are prose and are
    # parsed by the svo grammar; the registered idiomatic ones ("it tolls at dusk", "two dogs sleep",
    # "she loves the lantern most") do not parse, and are counted and listed rather than silently
    # dropped, because "40 distinct pairs" has to say what it counted.
    pairs_seen, sents, unparsed = [], set(), []
    for s in cur["sessions"]:
        for call in s["tell_frames"]:
            f = _frame_from_call(call)
            pairs_seen.append((f["subj"], f["verb"]))
            sents.add(f["tell"])
        for ask, ans in s["qa_pairs"]:
            m = re.match(r"(?:the )?([A-Za-z]+) (\w+s) the ([a-z]+)$", ans)
            if m:
                pairs_seen.append((m.group(1).lower(), m.group(2)))
            else:
                unparsed.append(ans)
            sents.add(ans)
    n_items = cur["n_tell_frames"] + cur["n_qa_pairs"]
    # Two separate invariants, not one. A QA pair's answer is ALLOWED to be a taught tell's sentence
    # -- that is the re-ask device tier 40 is built on ('what bites the latch?' -> 'the dog bites the
    # latch', which is tell0.0) -- so counting distinct sentences across both classes would call the
    # registered curriculum 13 duplicates. What must be unique is each class within itself.
    tell_sents = [_frame_from_call(c)["tell"] for s in cur["sessions"] for c in s["tell_frames"]]
    pair_sents = [ans for s in cur["sessions"] for _ask, ans in s["qa_pairs"]]
    if len(set(tell_sents)) != len(tell_sents):
        problems.append(f"{len(tell_sents)} tells but {len(set(tell_sents))} distinct sentences")
    if len(set(pair_sents)) != len(pair_sents):
        problems.append(f"{len(pair_sents)} QA answers but {len(set(pair_sents))} distinct")
    cur["measured_reask"] = len(set(pair_sents) & set(tell_sents))
    # the enforceable half of the distinct-pair rule: no NEW item repeats a pair, registered or not
    new_pairs_seen = []
    for s in cur["sessions"]:
        for call in s["tell_frames"]:
            if call not in reg_calls:
                f = _frame_from_call(call)
                new_pairs_seen.append((f["subj"], f["verb"]))
        for ask, ans in s["qa_pairs"]:
            if (ask, ans) in reg_pairs:
                continue
            m = re.match(r"(?:the )?([A-Za-z]+) (\w+s) the ([a-z]+)$", ans)
            if m:
                new_pairs_seen.append((m.group(1).lower(), m.group(2)))
    if len(new_pairs_seen) != len(set(new_pairs_seen)):
        dup = sorted({p for p in new_pairs_seen if new_pairs_seen.count(p) > 1})
        problems.append(f"new items repeat a (subject, verb) pair: {dup[:6]}")
    reg_pair_set = set()
    for g in base["sessions"]:
        for call in g:
            f = _frame_from_call(call)
            reg_pair_set.add((f["subj"], f["verb"]))
    hit = [p for p in new_pairs_seen if p in reg_pair_set]
    if hit:
        problems.append(f"new items repeat a pair a registered item already teaches: {hit[:6]}")

    # registered tier-40 items must all still be here, unchanged and in the same session
    for i, g in enumerate(base["sessions"]):
        for f in g:
            if f not in cur["sessions"][i]["tell_frames"]:
                problems.append(f"registered item left session {i+1}: {f}")
    for i, g in enumerate(base["pairs"]):
        for p in g:
            if list(p) not in cur["sessions"][i]["qa_pairs"]:
                problems.append(f"registered QA pair left session {i+1}: {p}")

    # (b) content-word closure over the probe matrix built by arm A's OWN probe functions
    sys.path.insert(0, str(ROOT / "tools"))
    import electric_learn_bench as eb
    taught = taught_content(cur)
    # The stem counts as taught. probes_for() asks with f["stem"] ("what does the dog bite") while
    # the tell teaches the surface form ("bites"), so a closure check that only knew surface forms
    # would fail on the REGISTERED tier 40 for every single item. The house stems the same way
    # (organs/stemming.py), so the trace set is taught words plus their stems.
    sys.path.insert(0, str(ROOT))
    ok_words = taught | set(QUESTION_WORDS) | _function_words()
    reg_violations, new_violations = [], []
    reg_calls_set = reg_calls
    for s in cur["sessions"]:
        for call in s["tell_frames"]:
            bucket = reg_violations if call in reg_calls_set else new_violations
            for shape, ask in eb.probes_for(_frame_from_call(call)):
                bad = [w for w in _content(ask) if w not in ok_words]
                if bad:
                    bucket.append(f"probe shape {shape} asks with untaught words {bad}: {ask!r}")
        for ask, ans in s["qa_pairs"]:
            bucket = reg_violations if (ask, ans) in reg_pairs else new_violations
            for shape, a in eb.probes_for_pair(ask, ans):
                bad = [w for w in _content(a) if w not in ok_words]
                if bad:
                    bucket.append(f"pair shape {shape} asks with untaught words {bad}: {a!r}")
    # Inherited violations are REPORTED, not failed on. Constraint (b) binds what this ruling adds;
    # holding a generated tier to a stricter standard than the sealed tier 40 would make the tiers
    # incomparable, and silently deleting the registered 'how many dogs sleep' probe would change
    # the probe matrix arm A is sealed against.
    problems += new_violations
    cur["inherited_constraint_debt"] = {
        "note": ("these come from the sealed tier-40 items and are kept as they are: constraint (b) "
                 "binds the extension, not the baseline it extends"),
        "n": len(reg_violations), "examples": reg_violations[:8]}

    # (c) distractors must be unanswerable: at least one content word no item teaches, or a role
    # swap whose reverse sentence is not in the taught set
    # "<q> <verb> the <X>" asks who does <verb> to X, so it is answerable exactly when a taught item
    # has that verb with X as its OBJECT. Testing (subject, verb) instead would call the REGISTERED
    # distractor "what chases the mouse" answerable -- the mouse does chase something, just not the
    # mouse -- and would reject a device tier 40 already depends on.
    vo = set()
    for s in cur["sessions"]:
        for call in s["tell_frames"]:
            f = _frame_from_call(call)
            if f["kind"] == "svo":
                vo.add((f["verb"], f["obj"]))
    for kind, ask, why in cur["distractors"]:
        if kind == "role_swap":
            m = re.match(r"(?:what|who) (\w+s) the ([a-z]+)", ask)
            if m and (m.group(1), m.group(2)) in vo:
                problems.append(f"role_swap distractor is answerable: {ask!r}")
        elif not [w for w in _content(ask) if w not in taught]:
            problems.append(f"distractor has all-taught words and no untaught anchor: {ask!r}")

    # probe matrix size, measured with arm A's own probe builders
    n_probe = 0
    for s in cur["sessions"]:
        for c in s["tell_frames"]:
            n_probe += len(list(eb.probes_for(_frame_from_call(c))))
    n_probe += sum(2 for s in cur["sessions"] for _ in s["qa_pairs"])
    n_probe += len(cur["distractors"])
    cur["measured"] = {"n_probes": n_probe,
                       "n_items": n_items,
                       "n_distinct_subject_verb_pairs": len(set(pairs_seen)),
                       "n_qa_answers_not_parsed_as_svo": len(unparsed),
                       "qa_answers_not_parsed_as_svo": sorted(unparsed),
                       "n_taught_content_words": len(taught),
                       "n_distractors": len(cur["distractors"]),
                       "method_distinct_pairs": ("tells read from their frame fields; QA answers "
                                                 "matched against 'the? <subj> <verb>s the <obj>'; "
                                                 "registered idiomatic answers that do not match are "
                                                 "listed, not dropped")}
    naive = round(len(eb.PROBES) * tier / 40)
    cur["construction"]["probe_matrix"] = {
        "n_probes": n_probe, "naive_proportional_target": naive, "per_item": round(n_probe / tier, 4),
        "deviation_explained": (f"{n_probe - naive:+d} probes vs 136x{tier}/40 because constraint (a) "
                                f"allows only svo frames, while 3 of the registered 24 tells are obl/"
                                f"intransitive and yield 3 and 2 shapes instead of 4; the registered "
                                f"irregulars are kept, and their shapes are not reproducible under "
                                f"(a), so the matrix is proportional per class, not per total"),
    }
    return problems


def _function_words():
    """The house's own function-word set. organs.neural_language is a package module (it does
    `from .stemming import stem`), so it has to be imported through the package, not by putting
    organs/ on sys.path."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from organs.neural_language import NeuralLanguage
    return set(NeuralLanguage.SHAPE_FUNCTION_WORDS)


def _content(s):
    sys.path.insert(0, str(ROOT / "tools"))
    import word_provenance as wp
    return wp.content_words(s)


def tier_path(tier: int) -> Path:
    return ROOT / "experiments" / "MP-E8" / f"curriculum_tier{tier}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, default=40)
    ap.add_argument("--out", default=None,
                    help="write the per-session manifest arms B and C consume")
    ap.add_argument("--emit-tier", type=int, default=None,
                    help="author a tier under D-MPE8-03 and write it to --out (default: the "
                         "registered tier path). Refuses to emit if any constraint check fails.")
    ap.add_argument("--check-tier", type=int, default=None,
                    help="re-derive a committed tier from the rule and prove it was not hand-edited")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()

    if a.emit_tier:
        cur = build_tier(a.emit_tier, a.seed)
        op = Path(a.out) if a.out else tier_path(a.emit_tier)
        if not op.is_absolute():
            op = ROOT / op
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(cur, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        m = cur["measured"]
        print(f"[emit] tier {a.emit_tier}: {m['n_items']} items, "
              f"{m['n_distinct_subject_verb_pairs']} distinct (subject, verb) pairs, "
              f"{m['n_probes']} probes, {m['n_distractors']} distractors, "
              f"{m['n_taught_content_words']} taught content words, "
              f"{m['n_qa_answers_not_parsed_as_svo']} QA answers outside the svo grammar")
        print(f"[emit] curriculum_sha256={cur['curriculum_sha256']}  seed={a.seed}")
        print(f"[emit] wrote {op.relative_to(ROOT)} -- ALL CONSTRAINTS PASSED")
        return 0

    if a.check_tier:
        tier = a.check_tier
        path = tier_path(tier)
        if tier not in TIERS_AUTHORED:
            raise SystemExit(_unregistered_tier_message(tier))
        if not path.exists():
            raise SystemExit(
                f"tier {tier} is authored but {path.relative_to(ROOT).as_posix()} is not committed, so "
                "there is nothing here to re-derive. A tier is accepted only if it is authored as code "
                "OR a committed tier file re-derives from the rule -- an authored tier with no file is "
                "neither, and it will not be treated as if it were the file. Run --emit-tier to write "
                "it, then commit the file with its curriculum_sha256.")
        if tier in TIERS_WITH_CODE:
            # The code tier is not re-derived from the rule; it is parsed from arm A's source. Checking
            # it against build_tier() would report a false MISMATCH (measured: tier 40 did exactly that),
            # and a false alarm about hand-editing is not a cheap thing to leave in a sealed tool.
            committed = json.loads(path.read_text(encoding="utf-8"))
            base = load()
            if committed["curriculum_sha256"] != base["curriculum_sha256"]:
                print(f"[check] tier {tier}: committed {committed['curriculum_sha256'][:16]} vs arm A "
                      f"source {base['curriculum_sha256'][:16]}")
                print("[check] MISMATCH -- arm A's curriculum moved since this manifest was written.")
                return 1
            print(f"[check] tier {tier} is authored as code in {base['source']}: committed sha "
                  f"{committed['curriculum_sha256'][:16]} matches the source as it now stands.")
            print("[check] PASS (source match). This tier is parsed from code, not emitted by the "
                  "D-MPE8-03 rule, so re-derivation does not apply to it.")
            return 0
        committed = json.loads(path.read_text(encoding="utf-8"))
        fresh = build_tier(tier, a.seed)
        same = (committed["curriculum_sha256"] == fresh["curriculum_sha256"]
                and committed["sessions"] == fresh["sessions"]
                and committed["distractors"] == fresh["distractors"])
        print(f"[check] tier {a.check_tier}: committed sha "
              f"{committed['curriculum_sha256'][:16]} vs re-derived {fresh['curriculum_sha256'][:16]}")
        if not same:
            print("[check] MISMATCH -- the committed tier is not what the rule emits. It was edited, "
                  "or the rule or lexicon changed since it was written.")
            return 1
        print("[check] PASS: the committed file re-derives from the registered rule and seed, so the "
              "tier is data whose construction is reproducible, not a hand-written list.")
        return 0

    cur = load()
    validate_tier(a.tier, cur)
    sess = sessions_for(a.tier, cur)
    manifest = {
        "schema": "droso.curriculum.v1",
        "tier": a.tier,
        "curriculum_sha256": cur["curriculum_sha256"],
        "source": cur["source"],
        "source_sha256_lf": cur["source_sha256_lf"],
        "n_items": cur["n_items"],
        "n_tell_frames": cur["n_tell_frames"],
        "n_qa_pairs": cur["n_qa_pairs"],
        "sessions": sess,
        "consumers_must_record": ("curriculum_sha256. Two arms that disagree on it did not run the "
                                  "same experiment, whatever their configs say."),
    }
    print(f"tier {a.tier}: {cur['n_items']} items over {len(sess)} sessions "
          f"({', '.join(str(s['n_items']) for s in sess)}), "
          f"curriculum_sha256={cur['curriculum_sha256'][:16]}")
    for s in sess:
        print(f"  session {s['session']}: {len(s['tell_frames'])} tells + "
              f"{len(s['qa_pairs'])} QA pairs")
    if a.out:
        op = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        print(f"wrote {op.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
