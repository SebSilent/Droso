"""Stamp and verify the harness hashes a registration promises (R2, and plan B.0 step 1).

A registration that names its harness by a hash somebody typed from memory is a claim. This computes
them and re-checks them, so "committed and sealed" (B.1 step 6) is a falsifiable statement rather than
an aspiration.

WHAT THE SEAL HASHES, and the proof behind it (G0-prime fix #2)
---------------------------------------------------------------
This machine runs `core.autocrlf=true` with no `.gitattributes` -- docs/HANDOVER.md lists both as
standing conditions. So a file's worktree bytes and the git blob it came from are different byte
strings, and a seal over raw worktree bytes does NOT verify after commit+checkout. docs/HANDOVER.md's
published hash for the pre-flag snapshot is exactly that: the CRLF worktree hash.

Measured here, on the tracked 1.4 MB evidence file:

    worktree bytes            1,473,837  (CRLF)
    CRLF folded to LF         1,421,862  == the HEAD blob, byte for byte
    git hash-object           38b74ede... == the index blob  (autocrlf clean IS applied)
    git hash-object --no-filters 2f850ad4... (the CRLF bytes -- NOT checkout-stable)
    sha256(HEAD blob)         318eb8c2d4fa5125... == sha256(LF-normalised worktree)

Two hashes are therefore recorded, and they are the same content seen two ways:

  * `git_blob_sha1` -- `git hash-object`, which applies the same conversion `git add` would. Stable
    across checkouts on any platform, and directly comparable to `git ls-files -s` once committed.
  * `sha256_lf` -- sha256 over CRLF-folded-to-LF bytes. Proven above to equal sha256 of the blob, so
    it is equally checkout-stable, and it is the algorithm this program already uses elsewhere.

`--check` verifies BOTH, and additionally asserts the equivalence (sha256 of the git blob == the
recorded sha256_lf) so the seal cannot drift away from what git actually stores.

Option (b), adding a `.gitattributes` to pin line endings, was NOT taken: it changes line-ending
behaviour for the whole repository, which is a policy decision for the PI, not an artifact of this
gate. The raw worktree hash is still recorded where it differs, so a reader holding an old hash can
tell whether they have the same artifact.

Run:  .venv/Scripts/python.exe tools/registration_seal.py experiments/MP-E9/registration.json
      .venv/Scripts/python.exe tools/registration_seal.py <registration.json> --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST = [
    "tools/electric_learn_bench.py",
    "tools/word_provenance.py",
    "tools/bench_noise_floor.py",
    "tools/derive_pre_flag_snapshot.py",
    "tools/promote_plan_extract.py",
    "tools/registration_seal.py",
    "tools/freeze_env.py",
    # The instrument that DECIDES the noise-floor verdict. It was missing from the first seal, and it
    # is the file that carried the coordinate-count bug -- the one artifact most in need of pinning
    # was the one not pinned.
    "tools/noise_floor_report.py",
    # Produces the sealed suite baseline (B.1 step 4). Its OUTPUT, results/suite_manifest.json, is added
    # to this list only once the file exists: check() reads a never-written artifact as MISSING -> DRIFT,
    # which would fail the seal test for the wrong reason. The ordering is recorded, not discovered.
    "tools/suite_manifest.py",
    # The sealed suite baseline itself. Added only now that the file exists -- see the note above.
    "experiments/G0-prime/results/suite_manifest.json",
    # MP-E9's harness, its tests, and the wiring-validation artifact. Listed here because all three are
    # committed in the same commit as this line: a manifest entry for an uncommitted file makes the
    # index cross-check fail on `in_index != total`, which is the correct outcome but the wrong reason.
    "tools/mp_e9_gate.py",
    "tests/test_mp_e9_gate.py",
    "experiments/MP-E9/results/gate_validation.json",
    # PRE-1: the organs/ design step, the test that enforces it, and the battery instrument that
    # gives H4 a measured state. All three are committed in the same commit as this line. The
    # document is sealed because it is a GATE, not a note: unsealed, it can be edited or deleted
    # with no signal, and the constraint it states stops being falsifiable.
    "experiments/MP-E9/organs_precondition.md",
    "tests/test_mp_e9_precondition.py",
    "tools/mp_e9_battery.py",
    # H4's measured battery state, and the gate verdict that consumed it. Added only now that both
    # files exist -- check() reads a never-written artifact as MISSING -> DRIFT. The battery journal
    # itself is NOT here: generations 9001-9006 are synthetic scratch and were deleted after
    # extraction, so the artifact carries the per-chunk journal hashes instead.
    "experiments/MP-E9/results/battery_pre_flag.json",
    "experiments/MP-E9/results/gate_validation_with_battery.json",
    # The 42 rows behind battery_pre_flag.json. The scratch generation journals were deleted --
    # state/selection/ is the tracked lineage and generations 9001-9006 never happened -- so this
    # is what makes H4's battery numbers recomputable from rows instead of trusted.
    "experiments/MP-E9/results/battery_pre_flag_rows.jsonl",
    "tests/test_word_provenance.py",
    "tests/test_g0_prime_instruments.py",
    "experiments/G0-prime/tier_protocol.json",
    "experiments/G0-prime/failure_taxonomy.json",
    "experiments/G0-prime/registration.json",
    "experiments/G0-prime/decision.md",
    "experiments/G0-prime/results/requirements.lock.txt",
    "experiments/MP-E9/baselines/bench_pre_arbiter_tell_HEAD.json",
    "experiments/MP-E9/baselines/bench_pre_arbiter_tell_HEAD.manifest.json",
    "experiments/MP-E9/registration.json",
    "experiments/MP-E9/plan_extract/PROVENANCE.json",
    "experiments/MP-E9/plan_extract/extract_pdf.py",
    # The noise-floor evidence. The clones are 1.4 MB each and regenerable, but the gate claim in
    # decision.md ("11 rows of 3,672 move; 1 graded") is computed from them, and an unverifiable
    # number in a gate record is worse than a large file.
    "experiments/G0-prime/results/noise_floor/noise_floor.json",
    "experiments/G0-prime/results/noise_floor/per_arm_breakdown.json",
    "experiments/G0-prime/results/noise_floor/clone_1.json",
    "experiments/G0-prime/results/noise_floor/clone_2.json",
    "experiments/G0-prime/results/noise_floor/clone_3.json",
    "experiments/G0-prime/results/word_provenance_audit.json",
    "docs/evidence/electric_learn_bench.json",
    "requirements.txt",
    "organs/neural_language.py",
]


def git(*a) -> str:
    r = subprocess.run(["git", *a], cwd=str(HERE), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def blob_bytes(path: pathlib.Path) -> bytes | None:
    """The bytes git WOULD store for this file, obtained by hashing then cat-file-ing the blob.

    Going through git rather than folding line endings by hand means the seal follows whatever
    conversion the repository's own configuration specifies -- autocrlf today, a .gitattributes if one
    is ever added.
    """
    sha1 = git("hash-object", str(path))
    if not sha1:
        return None
    r = subprocess.run(["git", "cat-file", "blob", sha1], cwd=str(HERE), capture_output=True)
    return r.stdout if r.returncode == 0 else None


def entry(rel: str) -> dict:
    p = HERE / rel
    if not p.exists():
        return {"status": "MISSING"}
    raw = p.read_bytes()
    bb = blob_bytes(p)
    e = {
        "git_blob_sha1": git("hash-object", str(p)) or None,
        "sha256_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "bytes_worktree": len(raw),
        "line_endings": "CRLF" if b"\r\n" in raw else "LF",
    }
    if bb is not None:
        e["bytes_blob"] = len(bb)
        e["sha256_of_git_blob"] = hashlib.sha256(bb).hexdigest()
        # The equivalence that makes both hashes the same content seen two ways. If this ever stops
        # holding, the repository's conversion rules changed and every recorded seal must be re-taken.
        e["blob_equals_lf_normalised"] = (bb == raw.replace(b"\r\n", b"\n"))
        if e["sha256_lf"] != e["sha256_of_git_blob"]:
            e["status"] = "SEAL_BASIS_MISMATCH"
    else:
        # NOT A FAILURE. `git hash-object` on an UNTRACKED file computes the blob id the file would
        # get, but without -w it does not write the object, so `cat-file` cannot return it. The blob
        # hash above is still the correct prediction and is still checkout-stable; only the second,
        # independent confirmation is unavailable until the file is committed. Recorded as pending
        # rather than as a mismatch -- a seal tool that cries wolf is a seal tool people start
        # ignoring.
        e["sha256_of_git_blob"] = None
        e["blob_content_check"] = ("PENDING: file is not in the object database (untracked); "
                                   "git_blob_sha1 is the predicted blob and remains valid; this "
                                   "field fills in after commit")
    return e


def seal(reg_path: pathlib.Path) -> dict:
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    hh = reg.setdefault("harness_hashes", {})
    files = hh.get("files") or {}
    # Union, not replacement: an existing manifest entry must never be dropped by a re-stamp, and a
    # newly written artifact must be picked up without anybody remembering to add it by hand.
    targets = list(dict.fromkeys(list(files) + DEFAULT_MANIFEST))

    # A registration cannot seal its own bytes: writing the seal into the file changes the file, so the
    # entry is stale the instant it is written and --check would report permanent self-inflicted drift.
    # The self-entry is dropped and the fact recorded, rather than left as a DRIFT line that trains
    # readers to ignore the checker.
    self_rel = str(reg_path.resolve().relative_to(HERE.resolve())).replace("\\", "/")
    targets = [t for t in targets if t != self_rel]
    hh["self_excluded"] = {
        "path": self_rel,
        "why": ("a file listing its own hash is stale the moment the hash is written; --check can "
                "never be clean otherwise. Its content is still pinned transitively by the artifacts "
                "that cite it, and by git history."),
    }

    # THE TWO-NODE VERSION OF THE SAME BUG, found by measurement, not by reading. G0-prime's manifest
    # listed MP-E9/registration.json and MP-E9's listed G0-prime/registration.json. Each ledger sealed
    # the other's bytes, so stamping A invalidated B's record of A and re-stamping B invalidated A again:
    # NO finite sequence of stamps makes both fresh, and `--check` on one is only ever clean by accident
    # of ordering. The rule that dissolves it is the one already applied to the self-reference: a
    # registration seals instruments and artifacts, never another registration. A ledger pinned by a
    # second ledger proves nothing about the world -- it only proves the two agree with each other.
    # Each registration is still pinned by git history and by the tests that read it.
    regs = [t for t in targets if t.endswith("registration.json")]
    if regs:
        targets = [t for t in targets if not t.endswith("registration.json")]
    hh["registrations_excluded"] = {
        "paths": sorted(regs),
        "why": ("registrations are ledgers, not evidence. Two registrations that seal each other form a "
                "cycle no stamp sequence can satisfy, so cross-registration entries are dropped and the "
                "fact is recorded here rather than left as a DRIFT that never clears."),
    }

    sealed = {f: entry(f) for f in targets}
    missing = [f for f, v in sealed.items() if v.get("status") == "MISSING"]
    mismatched = [f for f, v in sealed.items() if v.get("status") == "SEAL_BASIS_MISMATCH"]

    hh["files"] = sealed
    hh["sealed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    hh["git_head"] = git("rev-parse", "HEAD")
    hh["git_dirty"] = bool(git("status", "--porcelain"))
    # `git_dirty` alone is too blunt to act on: stamping G0-prime dirties the tree, so stamping MP-E9
    # immediately after reports dirty -- and the file that made it dirty is a registration, which NO
    # seal hashes. What threatens the anchor is uncommitted bytes among the files this seal actually
    # lists, so that is what gets measured, path-scoped, rather than a flag that cries wolf and gets
    # ignored. Both are recorded: the blunt one for the historical field, the precise one for the verdict.
    dirty_sealed = [ln.split()[-1].replace("\\", "/")
                    for ln in git("status", "--porcelain", "--", *targets).splitlines() if ln.strip()]
    hh["git_dirty_sealed"] = sorted(set(dirty_sealed))
    # The ordering rule, written by the tool rather than by prose someone might not read. The seal
    # records the CURRENT HEAD as the commit it is anchored to, so the only way that anchor can contain
    # the bytes being hashed is for the bytes to be committed first. Stamping a dirty tree produces a
    # seal that names a commit which does not contain its own artifacts -- unfalsifiable, and the same
    # defect class as the plan's stale 0b5f191. `git_dirty` above is the tell; `anchor` below is the test.
    hh["stamp_ordering"] = {
        "rule": ("COMMIT FIRST, THEN STAMP, THEN COMMIT THE STAMP. Never stamp while a file this seal "
                 "hashes is uncommitted -- that is what git_dirty_sealed reports, not mere tree dirt."),
        "why": ("git_head is the commit the seal claims to describe. If the sealed bytes are still "
                "uncommitted when the stamp is taken, git_head names a commit that does not contain "
                "them, and there is no checkout you can verify the seal against."),
        "procedure": [
            "1. commit the artifacts (tools/, tests/, results/)",
            "2. run registration_seal.py <registration.json>   # git_head now contains those blobs",
            "3. commit the registration (the stamp itself)",
            "4. registration_seal.py <registration.json> --check   # must be clean at that HEAD",
        ],
        "this_stamp_found_uncommitted_bytes_among_sealed_files": sorted(set(dirty_sealed)),
        "note": ("git_dirty_sealed is the field to act on. A non-empty list means at least one file this "
                 "seal hashes is not yet in the commit it names -- the seal is anchored to a commit that "
                 "cannot reproduce it. Stamping a second registration right after the first is NOT that "
                 "case, because registrations are excluded from every seal."),
        "checked_by": "registration_seal.py --check (anchor section) and "
                      "tests/test_g0_prime_instruments.py::test_registration_head_contains_its_sealed_files",
    }
    hh["seal_basis"] = {
        "chosen": "(a) seal the git blob, not the worktree bytes",
        "canonical": ["git_blob_sha1 (git hash-object, autocrlf clean applied)",
                      "sha256_of_git_blob"],
        "also_recorded": ["sha256_lf (equal to sha256_of_git_blob, proven per file)",
                          "bytes_worktree", "line_endings"],
        "rejected": "(b) a .gitattributes pinning eol -- it changes line-ending behaviour "
                    "repository-wide, which is a policy decision, not a gate artifact",
        "why": "core.autocrlf=true with no .gitattributes means worktree bytes != blob bytes, so a "
               "worktree-byte seal cannot verify after commit+clone. Verified on the tracked 1.4 MB "
               "evidence file: worktree 1,473,837 CRLF bytes, blob 1,421,862 LF bytes, and "
               "`git hash-object` returns the index blob, so the conversion is applied.",
        "verification": "tools/registration_seal.py --check recomputes both and asserts they agree",
    }
    hh["note"] = ("Hashes are checkout-stable by construction. See seal_basis and the module docstring "
                  "for the measurement behind it. reseal_history records every superseded value.")
    reg_path.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    if missing:
        print(f"[seal] WARNING missing files: {missing}")
    if mismatched:
        print(f"[seal] WARNING seal-basis mismatch (blob != LF-normalised): {mismatched}")
    return sealed


def check(reg_path: pathlib.Path) -> int:
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    files = reg.get("harness_hashes", {}).get("files", {})
    bad = []
    resolved = []
    for f, was in files.items():
        now = entry(f)
        if now.get("status") == "MISSING":
            bad.append((f, "missing"))
            continue
        if now.get("git_blob_sha1") != was.get("git_blob_sha1"):
            bad.append((f, f"blob {str(was.get('git_blob_sha1'))[:10]} -> "
                           f"{str(now.get('git_blob_sha1'))[:10]}"))
        elif was.get("sha256_of_git_blob") is None and now.get("sha256_of_git_blob") is not None:
            # NOT DRIFT. The seal recorded PENDING because the file was untracked when it was written
            # (git hash-object predicts a blob id but does not write the object, so the independent
            # sha256 confirmation was unavailable). Now that it is committed the value has RESOLVED.
            # sha1 agreeing while sha256 "disagrees" against a recorded None is this transition, and
            # calling it a hash collision is a false alarm that would make every post-commit check fail
            # -- which is exactly what happened on the first run of this gate's seal after committing.
            resolved.append(f)
        elif now.get("sha256_of_git_blob") != was.get("sha256_of_git_blob"):
            bad.append((f, "sha256 of blob disagrees while sha1 agrees -- hash collision or a "
                           "mis-recorded seal"))
        elif not now.get("blob_equals_lf_normalised", True):
            bad.append((f, "blob is no longer the LF-normalised worktree: the repository's "
                           "conversion rules changed under the seal"))
    for f, why in bad:
        print(f"  DRIFT {f}: {why}")
    if resolved:
        print(f"  {len(resolved)} file(s) sealed while UNTRACKED had their pending sha256 RESOLVED "
              f"after commit -- sha1 agrees, so the seal holds; re-stamp to record the confirmation:")
        for f in resolved[:6]:
            print(f"    RESOLVED {f}")
        if len(resolved) > 6:
            print(f"    ... {len(resolved) - 6} more")
    ok = len(files) - len(bad)
    print(f"[seal] {ok}/{len(files)} files match the registration on the git blob")
    if files:
        # Cross-check against the index for whatever is committed: the strongest available statement,
        # because it compares the seal to what git actually holds rather than what it would hold.
        # This block used to be gated on `not bad`, so it was SKIPPED whenever the worktree had drifted
        # -- i.e. exactly when its information was most wanted, and the new regression test then failed
        # for lack of a line to parse. An accounting that runs only on sunny days is not accounting.
        idx = git("ls-files", "-s", "--", *files)
        # `git ls-files -s` prints "<mode> <sha> <stage>\t<path>". The old parse did l.split() and keyed
        # the dict on r[0] -- THE MODE -- so all 100644 files collapsed into one key: the line always
        # printed "1 of N are in the git index", `f in committed` was never true, and the drift loop
        # compared NOTHING. A check that cannot fail is worse than no check, because it reads like
        # coverage. Path is taken from after the tab, sha from the second field, stage 0 only.
        committed = {}
        for line in idx.splitlines():
            if not line.strip():
                continue
            meta, sep, path = line.partition("\t")
            if not sep:
                continue
            parts = meta.split()
            if len(parts) < 2 or parts[2:3] != ["0"]:
                continue
            committed[path.replace("\\", "/")] = parts[1]
        drift = [(f, files[f].get("git_blob_sha1"), committed[f])
                 for f in files if f in committed
                 and files[f].get("git_blob_sha1") != committed[f]]
        print(f"[seal] {len(committed)} of {len(files)} are in the git index; "
              f"{len(drift)} disagree with their index blob")
        for f, a, b in drift:
            print(f"  INDEX-DRIFT {f}: sealed {a[:10]} vs index {b[:10]}")

        # THE ANCHOR. The two checks above compare the seal to the worktree and to the index -- both of
        # which are LOCAL, mutable state. Neither can answer the only question that makes a seal
        # falsifiable: does the commit this registration NAMES actually contain the bytes it HASHES?
        # Stamping a dirty tree answers "no", and every check above still passes, because the worktree
        # agrees with itself. That is how both registrations came to record 698a6d3 while hashing files
        # that commit has never seen -- the same defect class as the plan's stale 0b5f191.
        head = reg.get("harness_hashes", {}).get("git_head") or ""
        anchor_bad = []
        in_head = {}
        if head:
            for line in git("ls-tree", "-r", head, "--", *files).splitlines():
                meta, sep, path = line.partition("\t")
                if not sep:
                    continue
                parts = meta.split()
                if len(parts) >= 3 and parts[1] == "blob":
                    in_head[path.replace("\\", "/")] = parts[2]
        else:
            anchor_bad.append(("<git_head>", "no commit recorded -- seal is anchored to nothing"))
        for f, was in files.items():
            want = was.get("git_blob_sha1")
            got = in_head.get(f)
            if got is None:
                anchor_bad.append((f, f"absent from {head[:9]}: stamped before it was committed"))
            elif want and got != want:
                anchor_bad.append((f, f"sealed {want[:10]} but {head[:9]} holds {got[:10]}"))
        print(f"[seal] anchor: {len(files) - len(anchor_bad)}/{len(files)} sealed blobs are present, "
              f"byte for byte, in git_head {head[:9] or '(none)'}")
        for f, why in anchor_bad[:12]:
            print(f"  HEAD-MISSING {f}: {why}")
        if len(anchor_bad) > 12:
            print(f"  ... {len(anchor_bad) - 12} more")
        # Three kinds of disagreement, all fatal: worktree drift, index drift, and an anchor that does
        # not hold. Worktree drift used to return 1 by never reaching this line; an unanchored seal used
        # to return 0 because nothing looked.
        return 1 if (bad or drift or anchor_bad) else 0
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("registration")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    p = pathlib.Path(a.registration)
    if not p.is_absolute():
        p = HERE / p
    if a.check:
        return check(p)
    sealed = seal(p)
    for f, m in sorted(sealed.items()):
        print(f"  {str(m.get('git_blob_sha1'))[:12]}  {m.get('line_endings','?'):4s}  "
              f"{str(m.get('sha256_of_git_blob'))[:12]}  {f}")
    print(f"[seal] stamped {len(sealed)} files into {p.relative_to(HERE).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
