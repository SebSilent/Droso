"""Terminal organ: shell command execution, allowlist-guarded."""

from __future__ import annotations

import subprocess

DEFAULT_ALLOWLIST = (
    "python", "pytest", "pip", "dir", "type", "echo", "ls", "cat", "head",
    "wc", "git", "where", "findstr",
)

class TerminalOrgan:
    """Run a shell command and return its output as a sensory payload.

    Safety: commands must start with an allowlisted program (configurable),
    run with a timeout, and return capped output. Nothing is ever streamed to
    the connectome except the finished, capped result.
    """

    def __init__(self, allowlist=DEFAULT_ALLOWLIST, timeout_s: int = 30,
                 max_output_chars: int = 4000, cwd: str | None = None):
        self.allowlist = tuple(allowlist)
        self.timeout_s = int(timeout_s)
        self.max_output_chars = int(max_output_chars)
        self.cwd = cwd

    def run(self, command: str) -> dict:
        cmd = command.strip()
        first = cmd.split()[0] if cmd else ""
        if first not in self.allowlist:
            return {"ok": False, "error": f"command {first!r} not in allowlist",
                    "allowed": list(self.allowlist)}
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                  timeout=self.timeout_s, cwd=self.cwd)
            out = (proc.stdout or "") + (proc.stderr or "")
            return {"ok": proc.returncode == 0, "returncode": proc.returncode,
                    "output": out[: self.max_output_chars], "truncated":
                    len(out) > self.max_output_chars}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {self.timeout_s}s"}
        except OSError as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}