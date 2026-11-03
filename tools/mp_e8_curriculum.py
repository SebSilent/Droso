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

WHAT IT REFUSES. Tiers 120 and 300. They do not exist as code, and a tool that silently interpolated
them would turn a named cost into an invisible one. Asking for tier 120 raises, with the measured
projection in the message.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
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
    n_items = sum(len(s) for s in sessions) + sum(len(p) for p in pairs)
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
        "n_items": n_items,
        "curriculum_sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
    }


def _frame(node: ast.AST):
    """One taught item: a tuple/list of strings, kept as strings, not evaluated."""
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_frame(e) for e in node.elts]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


def validate_tier(tier: int, cur: dict) -> None:
    if tier in TIERS_WITH_CODE:
        return
    proj = {120: ("24.1 min per full 3-arm run, 11,016 rows, 408 probes, 80 more items to author"),
            300: ("60.2 min per full 3-arm run, 27,540 rows, 1,020 probes, 260 more items to author")
            }.get(tier, "no projection registered for that tier")
    raise SystemExit(
        f"tier {tier} does not exist as code. The curriculum in {cur['source']} is {cur['n_items']} "
        f"items (measured: {cur['n_tell_frames']} tell-frames + {cur['n_qa_pairs']} QA pairs). "
        f"Building tier {tier} is authoring work with a measured cost: {proj}. "
        "See experiments/MP-E8/registration.json -> tiers and D-MPE8-03. "
        "This tool will not interpolate items to make a tier look finished.")


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, default=40)
    ap.add_argument("--out", default=None,
                    help="write the per-session manifest arms B and C consume")
    a = ap.parse_args()

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
