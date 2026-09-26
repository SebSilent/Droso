from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USAGE_FILE = ROOT / "exocortex" / "api_usage.json"

OFFLINE_ENV = "HYBRIDLLM_OFFLINE"

class NoAPIKeyError(RuntimeError):
    """Raised instead of fabricating an answer. Subclasses RuntimeError so
    `except RuntimeError` at a call boundary catches it, and the message says
    which knob to turn."""

PROVIDERS = {
    "openai": {"base": "https://api.openai.com/v1", "model": "gpt-4o-mini",
               "auth": "bearer", "temp": (0.0, 2.0),
               "env": ("OPENAI_API_KEY",)},
    "anthropic": {"base": "https://api.anthropic.com/v1/messages",
                  "model": "claude-3-5-haiku-latest", "auth": "x-api-key",
                  "temp": (0.0, 1.0), "env": ("ANTHROPIC_API_KEY",)},
    "groq": {"base": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "auth": "bearer",
             "temp": (0.0, 2.0), "env": ("GROQ_API_KEY",)},
    "openrouter": {"base": "https://openrouter.ai/api/v1",
                   "model": "meta-llama/llama-3.3-70b-instruct",
                   "auth": "bearer", "temp": (0.0, 2.0),
                   "env": ("OPENROUTER_API_KEY",)},
    "qwen": {"base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "model": "qwen-plus", "auth": "bearer", "temp": (0.0, 2.0),
             "env": ("DASHSCOPE_API_KEY", "QWEN_API_KEY")},
    "zai": {"base": "https://api.z.ai/api/coding/paas/v4",
            "model": "glm-5.3-flash", "auth": "bearer", "temp": (0.01, 0.99),
            "env": ("ZAI_API_KEY", "ZHIPUAI_API_KEY"),
            "chat_path": "/chat/completions", "reasoning_model": True,
            "plan": "coding-plan-subscription"},
    "zai-paas": {"base": "https://api.z.ai/api/paas/v4",
                 "model": "glm-5.3-flash", "auth": "bearer",
                 "temp": (0.01, 0.99), "env": ("ZAI_API_KEY",),
                 "chat_path": "/chat/completions", "reasoning_model": True,
                 "plan": "per-token-balance"},
    "ollama": {"base": None, "model": "qwen2.5-coder:1.5b", "auth": "bearer",
               "temp": (0.0, 2.0), "env": ("OLLAMA_API_KEY",)},
    # Ollama Cloud: the same company's hosted models behind an OpenAI-compatible
    # wrapper at https://ollama.com/v1. Distinct from the local daemon above, which
    # needs a model pulled onto the disk; this one needs a key and nothing else.
    # deepseek-v4.1-flash is a 1M-context reasoning model at $0.15/$0.60 per Mtok,
    # which matters here because the oracle is billed per new problem and the whole
    # design is to ask it as rarely as possible.
    "ollama_cloud": {"base": "https://ollama.com/v1",
                     "model": "deepseek-v4.1-flash", "auth": "bearer",
                     "temp": (0.0, 2.0), "env": ("OLLAMA_CLOUD_API_KEY",),
                     "chat_path": "/chat/completions"},
}

SYSTEM_DEFAULT = ("You are a knowledge oracle for a program-synthesis agent. "
                  "Answer the question only, in at most a few sentences or one "
                  "code fragment. Never restate the question. "
                  "Do not call tools, execute commands, or take actions: you are "
                  "a source of text, not an agent. If an action seems needed, "
                  "describe it in one line instead of performing it.")

AGENTIC_PHRASES = [
    r"you (?:can|may|should) (?:now )?(?:use|call|invoke) (?:your |the )?"
    r"(?:tools?|functions?|apis?)",
    r"feel free to (?:run|execute|use the terminal|write files?)",
    r"you (?:have|are given) (?:access to|a) (?:a )?(?:shell|terminal|sandbox)"
    r"[\w ,.]{0,30}",
    r"act as an agent[\w\W]{0,60}",
    r"use an agentic (?:mode|loop)[\w\W]{0,40}",
    r"(?:call|invoke) (?:the )?(?:tool|function) [a-z_]\w*",
    r"execute this command[\w\W]{0,40}",
    r"run (?:this|the following) (?:command|script|shell)[\w\W]{0,40}",
]

TOOL_CALL_PATTERNS = [
    ("execute_command", re.compile(
        r"(?m)^\s*(?:\$|>)\s+(?P<cmd>(?:rm|mv|cp|chmod|chown|curl|wget|npm|pip|"
        r"python|node|git|docker|make|cargo|sudo|del|remove-item|set-content)"
        r"\b[^\n]{0,160})\s*$")),
    ("execute_command", re.compile(
        r"(?im)\b(?:i(?:'m| am)? now going to|let me|i will|i'll|i need to)"
        r"\s+(?:now |immediately |first |just )?(?P<cmd>(?:run|execute|apply|"
        r"create|delete|write|edit) [^\n]{3,120})")),
    ("tool_json", re.compile(
        r'(?s)\{\s*"(?:name|tool|function)"\s*:\s*"(?P<name>[^"]{1,60})"'
        r'\s*,\s*"(?:arguments|args|input|parameters)"\s*:\s*\{')),
    ("tool_json", re.compile(
        r'(?m)^\s*"tool_calls"\s*:\s*\[')),
]

AGENTIC_RE = [re.compile(p, re.I) for p in AGENTIC_PHRASES]

def placeholder_key(s: str) -> bool:
    """True when a string looks like an unfilled template ("${API_KEY}",
    "your_api_key_here") rather than a credential. Shared by the oracle's
    key cleaning and the house's credential-store writes, so a placeholder can
    never be STORED either -- refusing at the oracle would be too late, the
    junk would already be sitting in the user's credential file.
    """
    s = str(s or "").strip()
    if not s:
        return False
    if s.startswith(("${", "{{", "%", "<", "$[", "@@")):
        return True
    low = s.lower()
    return any(p in low for p in ("your", "changeme", "replace", "todo",
                                  "xxx", "none", "null", "api_key",
                                  "apikey", "enter", "put_", "<")) \
        and len(s) < 24

def fit_to_budget(oracle, prompt: str, want: int) -> int:
    """How many completion tokens this prompt can actually pay for.

    Asking for more than the per-query ceiling produces a refusal, not a longer
    answer -- and an organ that fails on its own arithmetic is worse than one
    that asks for a smaller piece and says so. Both the language organ and the
    autotraining teacher use this, so the rule is stated once.
    """
    b = getattr(oracle, "budget", None)
    per_query = int(getattr(b, "per_query", 0) or 0)
    if per_query <= 0:
        return int(want)
    room = per_query - estimate_tokens(str(prompt)) - 16
    return max(0, min(int(want), room))

def estimate_tokens(text: str) -> int:
    """len/4 with word-boundary awareness.

    Not a tokenizer. tiktoken is not a dependency here, so every number
    produced by this function is labelled `token_source: "estimate"` all the way
    to the report; a budget decision made on an estimate that was presented as
    an exact count is how you get a surprise bill.
    """
    if not text:
        return 0
    words = len(re.findall(r"\S+", text))
    chars = len(text)
    return max(1, int(0.75 * words + chars / 8.0))

class Budget:
    """Three ceilings. `check` is consulted BEFORE a request is sent."""

    def __init__(self, per_query=300, per_task=1500, per_day=50000):
        self.per_query = int(per_query)
        self.per_task = int(per_task)
        self.per_day = int(per_day)
        self.task_spent = 0
        self.day_spent = 0
        self.day = date.today().isoformat()

    def roll_day(self):
        today = date.today().isoformat()
        if today != self.day:
            self.day, self.day_spent = today, 0
        return self.day

    def start_task(self):
        self.roll_day()
        self.task_spent = 0

    def check(self, want_tokens: int) -> str | None:
        """None means allowed; otherwise the reason it is not."""
        self.roll_day()
        if want_tokens > self.per_query:
            return f"query_budget_exceeded ({want_tokens} > {self.per_query})"
        if self.task_spent + want_tokens > self.per_task:
            return f"task_budget_exceeded ({self.task_spent + want_tokens} > " \
                   f"{self.per_task})"
        if self.day_spent + want_tokens > self.per_day:
            return f"day_budget_exceeded ({self.day_spent + want_tokens} > " \
                   f"{self.per_day})"
        return None

    def commit(self, want_tokens: int):
        self.roll_day()
        self.task_spent += want_tokens
        self.day_spent += want_tokens

    def remaining(self) -> dict:
        self.roll_day()
        return {"per_query": self.per_query,
                "task_remaining": max(0, self.per_task - self.task_spent),
                "day_remaining": max(0, self.per_day - self.day_spent),
                "day": self.day}

class APIOracle:
    """One seam between the connectome and whatever answers it."""

    def __init__(self, provider: str = "openai", model: str | None = None,
                 api_key: str | None = None, base_url: str | None = None,
                 budget: Budget | None = None, timeout: float = 60.0,
                 usage_path: Path | None = None,
                 transport=None, sandbox=None, execute_tool_calls: bool = False,
                 thinking: str | None = None):
        self.provider = (provider or "openai").lower()
        if self.provider not in PROVIDERS:
            self._spec = dict(PROVIDERS["openai"])
            self.custom_provider = True
        else:
            self._spec = dict(PROVIDERS[self.provider])
            self.custom_provider = False
        self.model = model or self._default_model()
        raw_key = api_key if api_key is not None else self._env_key()
        self.key_placeholder = None
        self.api_key = self._clean_key(raw_key)
        self.base_url = base_url or self._default_base()
        self.timeout = float(timeout)
        self.thinking = (thinking or "disabled").lower() \
            if self._spec.get("reasoning_model") else (thinking or "default").lower()
        self.budget = budget or Budget()
        self.usage_path = Path(usage_path) if usage_path else USAGE_FILE
        self.transport = transport
        self.calls = 0
        self.errors = 0
        self.tokens_prompt = 0
        self.tokens_completion = 0
        self.tokens_reasoning = 0
        self.last_error = None
        self.history: list[dict] = []
        self.sandbox = sandbox
        self.execute_tool_calls = bool(execute_tool_calls)
        self.interceptions = 0
        self.stripped_fragments = 0
        self.tool_calls_seen = 0
        self.tool_calls_executed = 0
        self.tool_calls_cancelled = 0
        self.tool_calls_adapted = 0
        self.tool_log: list[dict] = []

    PLACEHOLDERS = ("your", "changeme", "replace", "todo", "xxx", "none",
                    "null", "api_key", "apikey", "enter", "put_", "<")

    def _clean_key(self, key):
        """Treat an unfilled config template as *no key*, not as a credential.

        `${API_KEY}` copied straight out of a design brief would otherwise go on
        the wire as `Authorization: Bearer ${API_KEY}`, and the user gets a 401
        that reads like a revoked key instead of the missing value it is. The
        same logic rejects "your_api_key_here". A stub key used by a test with an
        injected transport ("sk-test") is still believed, because there the
        caller knows exactly what it is doing.
        """
        s = str(key or "").strip()
        if not s:
            return None
        if placeholder_key(s):
            self.key_placeholder = s
            return None
        return s

    def _env_key(self):
        if os.environ.get(OFFLINE_ENV):
            return None
        for name in self._spec.get("env", ()):
            if os.environ.get(name):
                return os.environ[name]
        for k in ("LLM_API_KEY", "OPENAI_API_KEY"):
            if os.environ.get(k) and self.provider in ("openai", "custom"):
                return os.environ[k]
        return None

    def _default_model(self):
        return self._spec.get("model", "gpt-4o-mini")

    def _default_base(self):
        if self.provider == "ollama":
            return os.environ.get("OLLAMA_BASE_URL",
                                  "http://127.0.0.1:11434/v1")
        if self.provider == "openai":
            return os.environ.get("OPENAI_BASE_URL") or self._spec["base"]
        return self._spec["base"]

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def offline(self) -> bool:
        """HYBRIDLLM_OFFLINE fences this process away from every provider.

        It exists because a real credential now lives in the shipped config, so
        "the tests pass" and "the tests billed the account" were one accident
        apart. A test that needs an answered call injects `transport=` and is
        unaffected; one that does not gets a refusal, never a fabricated answer.
        """
        return bool(os.environ.get(OFFLINE_ENV)) and self.transport is None

    @property
    def mode(self) -> str:
        if not self.api_key:
            return "blocked"
        return "offline" if self.offline else "live"

    def require_key(self, what: str = "the oracle") -> None:
        """The single place that decides whether to raise. Kept separate from
        `mode` so an organ can ask "can I use you?" without triggering an
        exception on a probe."""
        if not self.api_key:
            raise NoAPIKeyError(
                f"No API key configured. Run `python credentials.py set model` "
                f"(model.api_key lives in your user profile's credential "
                f"store now, never in the repo), or export a provider env var "
                f"such as ZAI_API_KEY. ({what}: provider={self.provider}, "
                f"model={self.model}; no synthetic fallback exists.)")

    def build_prompt(self, question: str, context: str = "",
                     style: str | None = None,
                     max_context_chars: int = 1200) -> str:
        """Compact prompt. Context is trimmed to the sentences that actually
        share tokens with the question -- sending the whole file because it was
        handy is where token budgets die."""
        q = str(question).strip()
        if context:
            keep = self._relevant(context, q, max_context_chars)
            if keep:
                q = f"Context:\n{keep}\n\nQuestion: {q}"
        if style:
            q = f"{q}\n\nAnswer in this style: {style}"
        return q

    @staticmethod
    def _relevant(context: str, question: str, limit: int) -> str:
        words = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}", question.lower()))
        sents = re.split(r"(?<=[.!?])\s+|\n", context)
        scored = []
        for i, s in enumerate(sents):
            if not s.strip():
                continue
            hits = len(words & set(re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}",
                                              s.lower())))
            if hits:
                scored.append((hits, i, s.strip()))
        scored.sort(key=lambda t: (-t[0], t[1]))
        out, used = [], 0
        for _, _, s in scored:
            if used + len(s) > limit:
                break
            out.append(s)
            used += len(s)
        return "\n".join(out)

    def query(self, question: str, context: str = "", max_tokens: int = 180,
              temperature: float = 0.0, purpose: str = "oracle",
              style: str | None = None) -> dict:
        """Ask one thing. Returns a dict that always says how it was answered.

        Raises NoAPIKeyError (a RuntimeError) when no credential is configured:
        there is nothing honest to return in that case except an exception, and
        a dict with ok=False is too easy for a caller to read as "try again".
        """
        self.require_key(f"query purpose={purpose}")
        if self.offline:
            self.errors += 1
            self.last_error = "offline_mode"
            return {"ok": False, "text": "", "mode": "offline",
                    "provider": self.provider, "model": self.model,
                    "purpose": purpose,
                    "reason": f"offline_mode: {OFFLINE_ENV} is set, so no "
                              "provider call was made. Inject transport="}
        question, stripped = self._strip_agentic_instructions(question)
        if stripped:
            self.stripped_fragments += len(stripped)
        prompt = self.build_prompt(question, context, style=style)
        pt = estimate_tokens(prompt)
        want = pt + int(max_tokens)
        why = self.budget.check(want)
        if why:
            self.errors += 1
            self.last_error = why
            return {"ok": False, "text": "", "mode": self.mode,
                    "reason": why, "purpose": purpose, "prompt": prompt,
                    "prompt_tokens_est": pt}
        self.calls += 1
        t0 = time.perf_counter()
        res = self._live(prompt, max_tokens, temperature)
        lat = time.perf_counter() - t0
        ct = int(res.get("completion_tokens_est", 0) or 0)
        self.budget.commit(pt + ct)
        self.tokens_prompt += pt
        self.tokens_completion += ct
        self.tokens_reasoning += int(res.get("reasoning_tokens", 0) or 0)
        out = {"ok": bool(res.get("ok")), "text": res.get("text", ""),
               "mode": self.mode, "provider": self.provider,
               "model": res.get("model", self.model), "purpose": purpose,
               "prompt_tokens_est": pt, "completion_tokens_est": ct,
               "token_source": res.get("token_source", "estimate"),
               "latency_s": round(lat, 4), "max_tokens": max_tokens,
               "thinking": self.thinking,
               "prompt_sha": hashlib.sha256(
                   f"{self.provider}|{self.model}|{prompt}".encode()).hexdigest()[:16]}
        for k in ("prompt_tokens_actual", "reasoning_tokens", "finish_reason"):
            if res.get(k) is not None:
                out[k] = res[k]
        if stripped:
            out["agentic_instructions_stripped"] = stripped[:6]
        calls = self._detect_tool_calls(out.get("text", ""))
        if calls:
            out["text"], out["interception"] = self._intercept_tool_calls(
                out["text"], calls, purpose)
            self.interceptions += 1
        if not out["ok"]:
            out["reason"] = res.get("reason", "unknown")
            self.last_error = out["reason"]
            self.errors += 1
        self.history.append({k: out[k] for k in
                             ("ok", "mode", "purpose", "prompt_tokens_est",
                              "completion_tokens_est", "latency_s")})
        self._persist(out)
        return out

    def _strip_agentic_instructions(self, prompt: str):
        """Remove phrasing that tries to hand this call agentic authority.

        Applied to the question, never to `context`: context is source code, and
        deleting substrings from code to satisfy a style rule would corrupt the
        thing being reasoned about. Returns (clean_text, [removed_fragments]) so
        the removal is visible in the response rather than silent.
        """
        text = str(prompt or "")
        removed: list[str] = []
        for rx in AGENTIC_RE:
            def _cut(m):
                frag = re.sub(r"\s+", " ", m.group(0)).strip()
                if frag:
                    removed.append(frag[:120])
                return ""
            text = rx.sub(_cut, text)
        return re.sub(r"[ ]{2,}", " ", text).strip(), removed

    def _detect_tool_calls(self, response) -> list[dict]:
        """Find a response that is trying to act instead of answering."""
        text = response.get("text") if isinstance(response, dict) else str(response or "")
        if not text:
            return []
        found, seen = [], set()
        for kind, rx in TOOL_CALL_PATTERNS:
            for m in rx.finditer(text):
                cmd = (m.groupdict().get("cmd") or "").strip()
                name = (m.groupdict().get("name") or "").strip()
                sig = (kind, cmd or name, m.start() // 200)
                if sig in seen:
                    continue
                seen.add(sig)
                found.append({"type": "execute_command" if kind == "execute_command"
                              else "tool_json",
                              "command": cmd or None, "name": name or None,
                              "raw": m.group(0).strip()[:200],
                              "at": m.start()})
        self.tool_calls_seen += len(found)
        return found

    def _is_safe_command(self, command: str) -> bool:
        """Pure policy question, answered by the fence -- not by the oracle's own
        opinion, which would be the model grading its own homework."""
        if self.sandbox is None or not str(command or "").strip():
            return False
        try:
            return bool(self.sandbox.check_command(command).get("allow"))
        except Exception:
            return False

    def _intercept_tool_calls(self, text: str, calls: list[dict], purpose: str):
        """Decide each attempted action: execute, adapt, or cancel.

        * execute -- only when a human opted in (`execute_tool_calls`) *and* the
          sandbox's own policy allows the command. The result is spliced in as
          observation text, not as a new instruction.
        * adapt  -- a write-shaped call becomes a single connectome action item
          (path + content), so the file lands through the sandbox's approval
          queue rather than straight from the model.
        * cancel -- everything else. The model's claim is deleted from the text
          and replaced by a line the connectome can act on, because leaving
          "I will now run rm -rf build" inside an answer that some later step
          concatenates into a prompt is how one agent's prose becomes another's
          instruction.
        """
        decisions = []
        for c in calls:
            d = {"type": c["type"], "command": c.get("command"),
                 "name": c.get("name"), "decision": "cancel", "reason": "", "exit": None}
            cmd = c.get("command") or ""
            if c["type"] == "tool_json":
                d["reason"] = ("structured tool call in prose output: the oracle "
                               "has no tools; ask the connectome instead")
                self.tool_calls_cancelled += 1
            elif not self.execute_tool_calls:
                d["reason"] = ("execution disabled (execute_tool_calls=False): the "
                               "connectome decides, not the model")
                self.tool_calls_cancelled += 1
            elif self.sandbox is None:
                d["reason"] = "no sandbox attached; refusing to run a model's command"
                self.tool_calls_cancelled += 1
            elif self._is_safe_command(cmd):
                if self.sandbox is not None:
                    r = self.sandbox.execute_command(cmd, timeout=min(30.0, self.timeout))
                    d["decision"] = "execute"
                    d["exit"] = r.get("returncode", r.get("exit_code"))
                    d["reason"] = "allowed by sandbox policy"
                    d["output"] = str(r.get("output", r.get("stdout", "")))[:600]
                    self.tool_calls_executed += 1
            else:
                d["decision"] = "cancel"
                d["reason"] = "blocked by sandbox policy: " + str(
                    self.sandbox.check_command(cmd).get("reason", ""))[:120]
                self.tool_calls_cancelled += 1
            if c["type"] != "tool_json" and d["decision"] == "cancel" and \
                    re.search(r"\b(write|create|edit)\b[^\n]{0,40}\bfile\b", cmd, re.I):
                d["decision"] = "adapt"
                d["adapted_to"] = "connectome_write_action"
                d["reason"] = ("rewritten as a connectome action: a file write must "
                               "pass the approval queue, not the response text")
                self.tool_calls_adapted += 1
            decisions.append(d)
            self.tool_log.append(dict(d, purpose=purpose, t=time.time()))
        self.tool_log = self.tool_log[-200:]
        cleaned = text
        for c in calls:
            if c.get("raw"):
                cleaned = cleaned.replace(c["raw"], "")
        lines = [re.sub(r"\s+", " ", cleaned).strip()] if cleaned.strip() else []
        for d in decisions:
            if d["decision"] == "execute":
                lines.append(f"[observed: {d['command']} -> exit {d['exit']}] "
                             f"{d.get('output', '')[:400]}")
            else:
                lines.append(f"[suppressed: the oracle attempted "
                             f"{d['command'] or d['name'] or 'a tool call'!r} and "
                             f"the connectome chose {d['decision']} -- {d['reason']}]")
        return "\n".join(x for x in lines if x), {"calls": decisions, "mode": (
            "execute_allowed" if self.execute_tool_calls
            else "journal_and_cancel")}

    def _headers(self) -> dict:
        if self._spec.get("auth") == "x-api-key":
            return {"x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _clamp_temperature(self, temperature: float) -> float:
        """Keep sampling inside the range the vendor documents.

        Z.AI states the range is (0, 1) and that temperature=0 "is not
        applicable"; this file's default is 0.0 for determinism. Clamping to the
        low end (0.01) preserves the intent -- near-greedy -- without sending an
        out-of-contract request and reading the rejection as a network fault.
        """
        lo, hi = self._spec.get("temp", (0.0, 2.0))
        return min(max(float(temperature), lo), hi)

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        if self.transport is not None:
            return self.transport(url, headers, payload)
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    @staticmethod
    def _provider_error(resp) -> str | None:
        """Some gateways return a JSON error body with a 200. Read it, don't
        report an empty answer as a mystery."""
        if not isinstance(resp, dict):
            return None
        err = resp.get("error")
        if isinstance(err, dict):
            return f"{err.get('code') or err.get('type')}: " \
                   f"{str(err.get('message'))[:160]}"
        if err:
            return str(err)[:200]
        if resp.get("code") and not resp.get("choices") and not resp.get("content"):
            return f"{resp.get('code')}: {str(resp.get('message'))[:160]}"
        return None

    def _live(self, prompt: str, max_tokens: int, temperature: float) -> dict:
        temp = self._clamp_temperature(temperature)
        try:
            if self.provider == "anthropic":
                payload = {"model": self.model, "max_tokens": max_tokens,
                           "temperature": temp,
                           "system": SYSTEM_DEFAULT,
                           "messages": [{"role": "user", "content": prompt}]}
                resp = self._post(self.base_url, self._headers(), payload)
                err = self._provider_error(resp)
                if err:
                    return {"ok": False, "text": "", "reason": f"provider_error: {err}"}
                text = "".join(b.get("text", "")
                               for b in resp.get("content", []))
                usage = resp.get("usage", {}) or {}
                return {"ok": bool(text.strip()), "text": text.strip(),
                        "completion_tokens_est":
                            int(usage.get("output_tokens", 0) or 0) or
                            estimate_tokens(text),
                        "reasoning_tokens": 0,
                        "token_source": "provider" if usage else "estimate",
                        "model": resp.get("model", self.model)}
            payload = {"model": self.model, "max_tokens": max_tokens,
                       "temperature": temp,
                       "messages": [{"role": "system",
                                     "content": SYSTEM_DEFAULT},
                                    {"role": "user", "content": prompt}]}
            if "qwen" in str(self.model).lower() or \
                    str(self.provider).lower().startswith("qwen"):
                # Qwen3 thinks by default on the compatible-mode endpoint, and a
                # thinking trace in a NON-streaming call stalls past any sane
                # timeout: measured 60 s with zero completion tokens returned,
                # while a 26-token answer came back in 2.0 s. The teacher's job
                # is eight short sentences, not a reasoning trace.
                payload["enable_thinking"] = False
            if self._spec.get("reasoning_model") and \
                    self.thinking in ("enabled", "disabled"):
                t = self.thinking
                if str(self.provider).lower().startswith("zai") or \
                        "glm" in str(self.model).lower():
                    # GLM-5.3 removed "disabled" outright: thinking is always on
                    # and the level lives in a separate reasoning_effort field
                    # (low / high / max). The documented migration is exactly
                    # this -- type "enabled" plus effort, where "low" replaces the
                    # removed "disabled". Sending {"type": "low"} or {"type":
                    # "disabled"} both come back as http_400 1210, which is why
                    # every teacher call had ever been made failed.
                    payload["thinking"] = {"type": "enabled"}
                    payload["reasoning_effort"] = {"disabled": "low",
                                                   "enabled": "high"}.get(t, t)
                else:
                    payload["thinking"] = {"type": t}
            path = self._spec.get("chat_path", "/chat/completions")
            resp = self._post(self.base_url.rstrip("/") + path,
                              self._headers(), payload)
            err = self._provider_error(resp)
            if err:
                return {"ok": False, "text": "", "reason": f"provider_error: {err}"}
            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            text = (msg.get("content") or "").strip()
            # THE FIELD IS NAMED DIFFERENTLY BY DIFFERENT PROVIDERS. ollama_cloud's
            # deepseek-v4.1-flash puts the hidden trace in `reasoning`; the OpenAI
            # convention is `reasoning_content`. Reading only the second meant the field
            # that would have NAMED the failure was silently discarded, and every
            # budget-exhausted call came back looking like an empty completion. Measured:
            # the trace is 2,052-2,764 chars of visible-in-the-payload text that the old
            # parser threw away.
            reasoning = str(msg.get("reasoning_content") or msg.get("reasoning") or "")
            usage = resp.get("usage", {}) or {}
            details = usage.get("completion_tokens_details") or {}
            rt = int(details.get("reasoning_tokens", 0) or 0)
            ct = int(usage.get("completion_tokens", 0) or 0)
            out = {"ok": bool(text), "text": text,
                   "completion_tokens_est": ct or estimate_tokens(text),
                   "reasoning_tokens": rt,
                   "finish_reason": choice.get("finish_reason"),
                   "token_source": "provider" if usage else "estimate",
                   "model": resp.get("model", self.model)}
            if reasoning:
                out["reasoning_chars"] = len(reasoning)
            if usage.get("prompt_tokens"):
                out["prompt_tokens_actual"] = int(usage["prompt_tokens"])
            if not text:
                if rt or reasoning:
                    out["reason"] = ("thinking_ate_the_budget: reasoning_tokens="
                                     f"{rt or 'unknown'} of max_tokens={max_tokens}; "
                                     "raise max_tokens or set thinking='disabled'")
                elif choice.get("finish_reason") == "content_filter":
                    out["reason"] = "content_filter"
                elif choice.get("finish_reason") == "length":
                    # A reasoning model that spent the whole budget on a trace the
                    # provider does not report lands exactly here: finish_reason
                    # "length", completion_tokens == max_tokens, no content. That is
                    # TRUNCATED, not empty, and the two need different fixes -- the
                    # first needs a bigger budget, the second needs a different prompt.
                    out["reason"] = (f"truncated_by_max_tokens: the {max_tokens}-token "
                                     "budget was spent before any visible answer")
                else:
                    out["reason"] = "empty_completion"
            return out
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300] \
                if hasattr(e, "read") else ""
            reason = f"http_{e.code}"
            try:
                parsed = json.loads(body)
                err = self._provider_error(parsed) or \
                    self._provider_error(parsed.get("error", {}))
                if err:
                    reason = f"http_{e.code} {err}"
            except Exception:
                pass
            return {"ok": False, "text": "", "reason": reason,
                    "detail": body}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return {"ok": False, "text": "",
                    "reason": f"transport_error:{type(e).__name__}",
                    "detail": str(e)[:200]}
        except Exception as e:
            return {"ok": False, "text": "", "reason": f"parse_error",
                    "detail": f"{type(e).__name__}: {e}"[:200]}

    def _persist(self, out: dict):
        try:
            self.usage_path.parent.mkdir(exist_ok=True)
            rec = {"ts": round(time.time(), 3), "mode": out["mode"],
                   "ok": out["ok"], "purpose": out["purpose"],
                   "prompt_tokens_est": out["prompt_tokens_est"],
                   "completion_tokens_est": out["completion_tokens_est"],
                   "latency_s": out["latency_s"]}
            with open(self.usage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    def start_task(self):
        """Reset the per-task ceiling. Callers at task granularity, not here:
        a query() that silently reset the task budget would make the per-task
        cap meaningless."""
        self.budget.start_task()

    def stats(self) -> dict:
        return {"mode": self.mode, "provider": self.provider,
                "model": self.model, "base_url": self.base_url,
                "has_key": self.has_key,
                "key_source": ("store/env" if self.api_key else
                               ("placeholder" if self.key_placeholder else "none")),
                "plan": self._spec.get("plan", "per-token"),
                "thinking": self.thinking,
                "temperature_range": list(self._spec.get("temp", (0.0, 2.0))),
                "calls": self.calls,
                "errors": self.errors, "last_error": self.last_error,
                "key_placeholder_detected": self.key_placeholder,
                "tokens_prompt_est": self.tokens_prompt,
                "tokens_completion_est": self.tokens_completion,
                "tokens_reasoning": self.tokens_reasoning,
                "budget": self.budget.remaining(),
                "token_source": "estimate (no tiktoken dependency)",
                "interceptions": self.interceptions,
                "agentic_phrases_stripped": self.stripped_fragments,
                "tool_calls": {"seen": self.tool_calls_seen,
                               "executed": self.tool_calls_executed,
                               "cancelled": self.tool_calls_cancelled,
                               "adapted": self.tool_calls_adapted},
                "tool_execution": (
                    "opt-in and sandbox-gated (execute_tool_calls="
                    + str(self.execute_tool_calls) + ", sandbox="
                    + ("attached" if self.sandbox else "none") + ")"),
                "known_providers": sorted(PROVIDERS)}

def oracle_from_block(cfg: dict | None, block: str = "model",
                      defaults_from: str = "model", **over) -> APIOracle:
    """Build an oracle from one config block, falling back to another.

    The autotraining teacher uses this: its own provider/key/model/base_url when
    present, otherwise the main `model` block's -- because "different teacher" is
    a real configuration and "same teacher" is the default, and neither should
    need a second copy of the plumbing (which is how a teacher ends up silently
    dialling openai/gpt-4o-mini with a Z.AI key).
    """
    cfg = cfg or {}
    src = dict(cfg.get(block, {}) or {})
    base = dict(cfg.get(defaults_from, {}) or {}) if defaults_from != block else {}
    explicit = src.get("api_key")
    for k in ("provider", "base_url"):
        if not src.get(k):
            src[k] = base.get(k)
    for k in ("model", "name"):
        if not src.get(k):
            src[k] = base.get(k)
    key = explicit
    if key is None and "api_key" not in src:
        from credentials import get_key
        key = get_key(block, provider=src.get("provider"))
    if key is None and "api_key" not in src:
        key = base.get("api_key")
        if key is None and "api_key" not in base and defaults_from != block:
            from credentials import get_key
            key = get_key(defaults_from, provider=src.get("provider"))
    b = dict(src.get("api_budget") or base.get("api_budget") or {})
    kw = {"provider": src.get("provider", "openai"),
          "model": src.get("model") or src.get("name"),
          "api_key": key, "base_url": src.get("base_url"),
          "thinking": src.get("thinking"),
          "budget": Budget(per_query=b.get("max_tokens_per_query", 300),
                           per_task=b.get("max_tokens_per_task", 1500),
                           per_day=b.get("max_tokens_per_day", 50000))}
    kw.update({k: v for k, v in over.items() if v is not None})
    return APIOracle(**kw)

def oracle_from_config(cfg: dict | None = None, **over) -> APIOracle:
    """Build from config/hybrid_config.json's `model` block."""
    return oracle_from_block(cfg, "model", defaults_from="model", **over)