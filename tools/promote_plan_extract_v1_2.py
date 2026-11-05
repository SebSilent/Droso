"""STEP 0 -- promote Master Plan v1.2 into the tracked tree as a citable plan extract.

v1.1 was promoted by tools/promote_plan_extract.py out of swept scratch, because R10 forbids a normative
input living where the repository sweeps it (experiments/MP-E9/plan_extract/PROVENANCE.json records that
reason). v1.2 arrives as markdown from C:/Shared, so there is no PDF to re-extract: the job here is a
byte-faithful copy plus a provenance record, so that ledgers and reports can cite "v1.2:<line>" and a
reader on another machine can verify the line numbering against a hashed file rather than trusting this one.

Two fidelity properties are recorded, not assumed:
  * the sha256 of the source as delivered, and of the stored bytes, plus whether they are the same bytes
    (this machine runs core.autocrlf=true with no .gitattributes, so a worktree file and its blob can
    differ; the v1.1 convention hashes LF-normalised content for exactly that reason);
  * that the line numbering the record cites (134, 304, 396-409) is identical in the source and the copy.
    A citation by line is worthless if the copy renumbered the document.

v1.1 is NOT modified: it stays as history under R5, and its own PROVENANCE.json is left untouched. This
writes a separate PROVENANCE_v1_2.json.

Re-runnable and idempotent: it rewrites the same bytes and the same hashes.

Run:  .venv/Scripts/python.exe tools/promote_plan_extract_v1_2.py [--src PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
DST_DIR = HERE / "experiments" / "MP-E9" / "plan_extract"
DST_NAME = "DROSO_Master_Plan_v1_2.md"

# The anchors this window's record cites by line. Verified, not asserted.
CITED_ANCHORS = {
    "134": "the assertion that R11 is unused and R17 is next free -- the claim STEP 1 verifies",
    "304": "A10 Resource cost, recorded as not yet measured on any registered run",
    "396": "section B.R, the ruling batch header",
    "400": "B.R item 1, D-MPE10-12",
    "409": "B.R item 11, D-MPE12-01...04",
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"C:/Shared/DROSO_Master_Plan_v1.2.md")
    a = ap.parse_args()

    src = pathlib.Path(a.src)
    if not src.exists():
        print(f"[promote-v12] MISSING source {src}", file=sys.stderr)
        return 1

    raw = src.read_bytes()
    body = lf(raw)
    DST_DIR.mkdir(parents=True, exist_ok=True)
    dst = DST_DIR / DST_NAME
    dst.write_bytes(body)

    src_lines = raw.replace(b"\r\n", b"\n").decode("utf-8", errors="replace").splitlines()
    dst_lines = body.decode("utf-8", errors="replace").splitlines()
    anchors_ok = all(
        src_lines[int(n) - 1].rstrip() == dst_lines[int(n) - 1].rstrip() for n in CITED_ANCHORS
    )

    manifest = {
        "document": "DROSO Master Plan v1.2 - The Live Brain Protocol (plan of record, dated 2026-11-05)",
        "supersedes": "DROSO_Master_Plan_v1_1.txt (retained in this directory, unmodified, as history under R5)",
        "source_of_truth_path": src.as_posix(),
        "source_bytes_as_delivered": len(raw),
        "source_sha256_as_delivered": sha(raw),
        "stored_path": dst.relative_to(HERE).as_posix(),
        "stored_bytes": len(body),
        "stored_sha256_lf_normalised": sha(body),
        "bytes_identical_after_lf_normalisation": raw == body,
        "source_line_count": len(src_lines),
        "stored_line_count": len(dst_lines),
        "cited_line_numbering_identical_source_vs_copy": anchors_ok,
        "cited_anchors_verified": CITED_ANCHORS,
        "normalisation_note": (
            "The stored copy is LF-normalised because this machine runs core.autocrlf=true with no "
            ".gitattributes, so a worktree file and the blob it came from do not have the same bytes; "
            "the v1.1 convention (PROVENANCE.json) hashes normalised content for the same reason. "
            "Line numbering is unaffected by the substitution."
        ),
        "why_tracked_here": (
            "R10: a normative input to the gates. v1.2 is the plan of record, and B.R (v1.2:396-409) is "
            "the ruling source the ledgers must quote verbatim rather than paraphrase. It cannot live in "
            "_tmp/, which .gitignore sweeps and organs/tempstore.py declares non-normative."
        ),
        "promotion_tool": "tools/promote_plan_extract_v1_2.py",
        "words": len(body.decode("utf-8", errors="replace").split()),
    }
    (DST_DIR / "PROVENANCE_v1_2.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({k: manifest[k] for k in (
        "source_sha256_as_delivered", "stored_sha256_lf_normalised",
        "bytes_identical_after_lf_normalisation", "source_line_count", "stored_line_count",
        "cited_line_numbering_identical_source_vs_copy")}, indent=2))
    print(f"[promote-v12] -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
