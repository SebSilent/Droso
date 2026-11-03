"""G0-prime step 1a -- promote the master-plan text out of swept scratch into the tracked tree.

R10 (Master Plan v1.1 section 5) says nothing a registered number depends on may stay local-only.
The plan text the gates are written against had been extracted into `_tmp/`, which `.gitignore`
sweeps and `organs/tempstore.py` declares non-normative: "Nothing that must be consulted may live
here."

The resolution is a relocation, not a loosening. `_tmp/` stays ignored and swept -- un-ignoring it
would make a scratch directory normative and break the contract `organs/sandbox.py` relies on. The
artifact moves to `experiments/MP-E9/plan_extract/`, the tree the plan itself designates for program
artifacts (section 8.3), and it is sealed against the PDF it came from so any reader can re-derive
it without trusting this machine.

Run:  .venv/Scripts/python.exe tools/promote_plan_extract.py [--pdf PATH]
Re-runnable and idempotent: it rewrites the same bytes and the same hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parents[1]
DST_DIR = HERE / "experiments" / "MP-E9" / "plan_extract"

# The extractor, kept as source so the extraction is re-runnable rather than merely recorded.
EXTRACTOR = '''"""MP-E9 / G0-prime: extract the master-plan PDF to text (the pypdf dependency is logged in
experiments/G0-prime/registration.json as a session-added, non-harness tooling dep)."""
from pypdf import PdfReader

r = PdfReader(r"C:/Shared/DROSO_Master_Plan_v1_1.pdf")
text = "".join(f"\\n===== PAGE {i + 1} =====\\n" + (p.extract_text() or "")
               for i, p in enumerate(r.pages))
open("_tmp/DROSO_Master_Plan_v1_1.txt", "w", encoding="utf-8").write(text)
print("pages:", len(r.pages), "chars:", len(text), "words:", len(text.split()))
'''


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def lf(b: bytes) -> bytes:
    """Normalise to LF so the recorded hash is the file's own bytes on any checkout.

    This machine runs `core.autocrlf=true` with no `.gitattributes`, so a worktree file and the blob
    it came from do not have the same bytes. A seal that changes when you check the repository out is
    not a seal, so every hash here is taken over normalised content.
    """
    return b.replace(b"\r\n", b"\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=r"C:/Shared/DROSO_Master_Plan_v1_1.pdf")
    ap.add_argument("--txt", default=str(HERE / "_tmp/DROSO_Master_Plan_v1_1.txt"))
    a = ap.parse_args()

    src_txt = pathlib.Path(a.txt)
    if not src_txt.exists():
        print(f"[promote] MISSING {src_txt} -- re-extract from the PDF first (see extract_pdf.py)")
        return 1

    DST_DIR.mkdir(parents=True, exist_ok=True)
    body = lf(src_txt.read_bytes())
    (DST_DIR / "DROSO_Master_Plan_v1_1.txt").write_bytes(body)
    (DST_DIR / "extract_pdf.py").write_bytes(lf(EXTRACTOR.encode("utf-8")))

    pdf = pathlib.Path(a.pdf)
    manifest = {
        "document": "DROSO Master Plan v1.1 - The Live Brain Protocol (Amended)",
        "source_pdf_path": pdf.as_posix(),
        "source_pdf_present": pdf.exists(),
        "source_pdf_sha256": sha(pdf.read_bytes()) if pdf.exists() else None,
        "source_pdf_bytes": pdf.stat().st_size if pdf.exists() else None,
        "extracted_text_sha256_lf": sha(body),
        "extracted_text_bytes": len(body),
        "pages": 32,
        "words": len(body.decode("utf-8").split()),
        "extractor": "pypdf PdfReader, per-page extract_text(), joined with a page banner",
        "extractor_version": "pypdf 6.21.4",
        "extractor_script": "experiments/MP-E9/plan_extract/extract_pdf.py",
        "extractor_script_sha256_lf": sha(lf(EXTRACTOR.encode("utf-8"))),
        "known_extraction_limit": (
            "Table cell boundaries are partly garbled by text extraction -- headers and wrapped "
            "cells interleave, most visibly in Tables 4, 6, 7 and 8. Prose extracted cleanly. "
            "Where a table's row assignment is load-bearing it was verified against the "
            "repository, not against this text."
        ),
        "why_tracked_here": (
            "R10: a normative input to the gate. _tmp/ stays ignored and swept; the policy was not "
            "loosened, the artifact was relocated to the tree section 8.3 designates for program "
            "artifacts."
        ),
    }
    (DST_DIR / "PROVENANCE.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({k: manifest[k] for k in
                      ("source_pdf_sha256", "extracted_text_sha256_lf", "extracted_text_bytes",
                       "pages", "words")}, indent=2))
    print(f"[promote] -> {DST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
