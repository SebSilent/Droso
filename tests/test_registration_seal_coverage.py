"""Every registration under experiments/ must be sealed and anchored -- counted, never named.

WHY THIS TEST EXISTS AT ALL. The instruction that closed G2 was "re-stamp all three registrations",
and at the time it was written there were three. MP-E10's registration made it four, MP-E9's stamp was
skipped, and the full suite caught it as two failures in test_g0_prime_instruments.py -- but only
because that file happens to check MP-E9. Nothing in the repository said *every* registration. A test
that names four files fails in exactly the same way the next time an experiment opens, so this one
enumerates the directory and asserts on whatever it finds. The count is the invariant; the names are
not.

WHAT IT ASSERTS, in two independent halves:

  1. `registration_seal.check()` returns 0 for each registration -- no worktree drift, no index
     drift, and the anchor section passing, which is the half that caught MP-E9.
  2. Each registration's own recorded `git_head` contains each of its sealed blobs. This is asserted
     here rather than only inherited from check(), because "the seal names a commit that does not hold
     what it hashed" is the defect class the plan itself carries (the stale 0b5f191 anchor), and a test
     that only calls a helper cannot be read as covering it.

It does NOT assert that all registrations share one anchor. That is a property of a particular
close-out, not a rule: a later experiment legitimately stamps at a later commit, and demanding a single
anchor forever would be a test that fails for the wrong reason.
"""
import io
import json
import pathlib
import subprocess
import sys
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import registration_seal  # noqa: E402


def registrations():
    return sorted(ROOT.glob("experiments/*/registration.json"))


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr.strip()[:200]}"
    return r.stdout


def test_registrations_exist_to_be_checked():
    """Anti-vacuity. A glob that matches nothing would make every assertion below pass on emptiness."""
    regs = registrations()
    assert regs, (f"no experiments/*/registration.json found from {ROOT} -- this test would be "
                  f"green on nothing, which is the worst kind of green")
    # p.parent.name, not p.parents[1].name: registration.json's parent IS the experiment directory,
    # and printing the same word four times would make this line useless as a record of what was seen.
    print(f"[seal-coverage] {len(regs)} registrations enumerated: "
          + ", ".join(p.parent.name for p in regs))


def test_every_registration_seal_verifies():
    """Counted, not named: whatever is under experiments/ has to verify."""
    problems = []
    for path in registrations():
        rel = path.relative_to(ROOT).as_posix()
        reg = json.loads(path.read_text(encoding="utf-8"))
        hh = reg.get("harness_hashes") or {}
        if not hh.get("files"):
            problems.append(f"{rel}: no sealed files at all -- registered but never stamped")
            continue
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = registration_seal.check(path)
        if rc != 0:
            tail = [ln for ln in buf.getvalue().splitlines()
                    if ln.strip().startswith(("DRIFT", "MISSING", "INDEX-DRIFT", "[seal]"))]
            problems.append(f"{rel}: check() returned {rc} -- " + " | ".join(tail[-4:])[:400])
    assert not problems, "registrations that do not verify:\n  " + "\n  ".join(problems)


def test_every_registration_anchor_holds_its_own_blobs():
    """Each recorded git_head must hold each blob that seal hashed -- per registration, its own anchor."""
    problems = []
    for path in registrations():
        rel = path.relative_to(ROOT).as_posix()
        reg = json.loads(path.read_text(encoding="utf-8"))
        hh = reg.get("harness_hashes") or {}
        files = hh.get("files") or {}
        if not files:
            continue
        head = hh.get("git_head")
        if not head:
            problems.append(f"{rel}: no git_head -- the seal is anchored to nothing")
            continue
        # ls-tree reports the git BLOB id, which is a SHA-1; the registration's canonical hash is
        # `git_blob_sha1`, and `sha256_of_git_blob` is a separate field. Comparing the sha256 against
        # ls-tree -- which is what the first draft of this test did -- reports 127/127 absent and is
        # wrong in the loudest possible way, so the field is named here rather than guessed at.
        in_head = {}
        for line in git("ls-tree", "-r", head).splitlines():
            meta, sep, name = line.partition("\t")
            if not sep:
                continue
            parts = meta.split()
            if len(parts) >= 3 and parts[1] == "blob":
                in_head[name.replace("\\", "/")] = parts[2]
        absent = [f for f, e in files.items()
                  if e.get("git_blob_sha1") and in_head.get(f) != e["git_blob_sha1"]]
        if absent:
            problems.append(f"{rel}: {len(absent)}/{len(files)} sealed blobs absent from, or a "
                            f"different blob in, its own git_head {head[:9]} (stamped before being "
                            f"committed?), e.g. " + ", ".join(sorted(absent)[:3]))
    assert not problems, "anchors that do not hold:\n  " + "\n  ".join(problems)
