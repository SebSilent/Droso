from organs.api_oracle import estimate_tokens

class ContextManager:
    def __init__(self, max_context_tokens: int = 8000, response_reserve: int = 600,
                 tokenizer=None, sandbox=None, summarise_lines: int = 12,
                 tail_lines: int = 4):
        self.max_tokens = int(max_context_tokens)
        self.response_reserve = int(response_reserve)
        self.estimate = tokenizer or estimate_tokens
        self.sandbox = sandbox
        self.summarise_lines = int(summarise_lines)
        self.tail_lines = int(tail_lines)
        self.built = 0
        self.truncations = 0
        self.dropped_parts = 0
        self.summaries = 0
        self.tokens_kept = 0
        self.tokens_dropped = 0
        self.last: dict = {}

    @property
    def budget(self) -> int:
        return max(64, self.max_tokens - self.response_reserve)

    def build_context(self, task_description: str, relevant_files=None,
                      previous_attempts=None, constraints: str = "",
                      extra: str = "") -> str:
        """Back-compat with the migration brief: returns the prompt text.
        `build()` returns the same text plus the accounting."""
        return self.build(task_description, relevant_files, previous_attempts,
                          constraints=constraints, extra=extra)["prompt"]

    def build(self, task_description: str, relevant_files=None,
              previous_attempts=None, constraints: str = "",
              extra: str = "") -> dict:
        parts: list[str] = []
        used = 0
        dropped: list[dict] = []
        summarised: list[str] = []
        notes: list[str] = []

        def add(text: str, label: str, hard: bool = False) -> bool:
            nonlocal used
            cost = self.estimate(text)
            if used + cost <= self.budget:
                parts.append(text)
                used += cost
                return True
            if hard:
                room = max(0, self.budget - used)
                keep = self._clip_lines(text, room)
                if keep:
                    parts.append(keep)
                    used += self.estimate(keep)
                    if self.estimate(keep) < cost:
                        notes.append(f"{label} clipped to {self.estimate(keep)} "
                                     f"of {cost} est tokens")
                return False
            dropped.append({"part": label, "tokens_est": cost})
            return False

        task = str(task_description or "").strip()
        add(f"TASK: {task}", "task", hard=True)
        add("CONSTRAINTS: " + (constraints or
            "Return only what was asked. No preamble. If something is unknown, "
            "say so instead of guessing."), "constraints", hard=True)
        if extra:
            add(extra, "extra")

        seen = set()
        for a in list(previous_attempts or [])[-3:][::-1]:
            err = str((a or {}).get("error") if isinstance(a, dict) else a)
            err = err.strip()[:400]
            if not err or err in seen:
                continue
            seen.add(err)
            add(f"PREVIOUS ATTEMPT FAILED: {err}", "attempt")

        for f in (relevant_files or []) if relevant_files else []:
            path, content = self._unpack_file(f)
            content = str(content or "")
            cost = self.estimate(content)
            room = self.budget - used
            if content and cost <= max(room, 0) // 2 and cost <= room:
                add(f"FILE: {path}\n{content}", "file")
                continue
            if room <= 32:
                dropped.append({"part": f"file:{path}", "tokens_est": cost,
                                "why": "no room left in budget"})
                continue
            summary = self.summarise_file(content, max_tokens=max(32, room // 2))
            scost = self.estimate(summary)
            if scost <= self.budget - used:
                add(f"FILE SUMMARY: {path}\n{summary}", "summary")
                summarised.append(str(path))
                if scost < cost:
                    notes.append(f"{path} summarised {cost} -> {scost} est tokens")
            else:
                dropped.append({"part": f"file:{path}", "tokens_est": cost,
                                "why": "did not fit even summarised"})

        prompt = "\n\n".join(parts)
        dropped_for_fit = 0
        while parts and self.estimate("\n\n".join(parts)) > self.budget:
            parts.pop()
            dropped_for_fit += 1
        if dropped_for_fit:
            notes.append(f"{dropped_for_fit} part(s) dropped to fit the budget")
            self.dropped_parts += dropped_for_fit
            dropped.append({"part": "low-priority-tail",
                            "tokens_est": dropped_for_fit,
                            "why": "joined prompt exceeded budget"})
        prompt = "\n\n".join(parts)
        over = self.estimate(prompt) - self.budget
        if over > 0:
            prompt = self._clip_lines(prompt, self.budget)
            self.truncations += 1
            notes.append(f"prompt hard-clipped by {over} est tokens")
        final = self.estimate(prompt)
        self.built += 1
        self.tokens_kept += final
        self.tokens_dropped += sum(d.get("tokens_est", 0) for d in dropped)
        self.dropped_parts += len(dropped)
        self.summaries += len(summarised)
        out = {"prompt": prompt, "tokens_est": final, "budget": self.budget,
               "max_tokens": self.max_tokens,
               "response_reserve": self.response_reserve,
               "utilization": round(final / max(1, self.budget), 3),
               "dropped": dropped, "notes": notes,
               "summarised": summarised,
               "truncated": bool(dropped or summarised or over > 0),
               "token_source": "injected tokenizer" if tokenizer_is_real(
                   self.estimate) else "estimate(chars/4)"}
        self.last = out
        return out

    @staticmethod
    def _unpack_file(f):
        if isinstance(f, (tuple, list)) and len(f) == 2:
            return str(f[0]), f[1]
        if isinstance(f, dict):
            return str(f.get("path", f.get("name", "?"))), \
                f.get("content", f.get("text", ""))
        return str(f), ""

    def summarise_file(self, content: str, max_tokens: int = 200,
                       path: str = "") -> str:
        """Keep the head (imports, signatures), the definitions, and a couple of
        tail lines, packed to the token budget by *lines*.

        The obvious implementation -- `summary[:len(summary)-100]` in a loop --
        cuts mid-identifier and can leave a prompt ending in `def `, which is
        worse than fewer lines: it reads like a complete file that happens to be
        unreadable.
        """
        lines = str(content or "").splitlines()
        if not lines:
            return ""
        budget = max(16, int(max_tokens))
        head = lines[:self.summarise_lines]
        defs = [l for l in lines[self.summarise_lines:]
                if l.strip().startswith(("def ", "class ", "function ", "func ",
                                         "pub ", "export "))][:8]
        tail = lines[-self.tail_lines:] if len(lines) > self.summarise_lines \
            else []
        out, used, omitted = [], 0, 0
        seen = set()
        for group in (head, defs, tail):
            for l in group:
                if l in seen:
                    continue
                seen.add(l)
                c = self.estimate(l)
                if used + c > budget:
                    omitted += 1
                    continue
                out.append(l.rstrip())
                used += c
        text = "\n".join(out)
        while out and self.estimate(text + (f"\n... [{omitted} lines omitted]"
                                           if omitted else "")) > budget:
            out.pop()
            omitted += 1
            text = "\n".join(out)
        if omitted:
            text += f"\n... [{omitted} more lines omitted" \
                    f"{' from ' + path if path else ''}]"
        return text

    def _clip_lines(self, text: str, token_budget: int) -> str:
        out, used = [], 0
        for l in str(text).splitlines():
            c = self.estimate(l)
            if used + c > token_budget:
                break
            out.append(l)
            used += c
        if not out and token_budget > 0:
            s = str(text).strip()
            mark = "...[clipped]"
            n = min(len(s), max(8, token_budget * 4))
            while n > 8 and self.estimate(s[:n] + mark) > token_budget:
                n = max(8, n - max(1, n // 6))
            if self.estimate(s[:n] + mark) > token_budget:
                return ""
            return s[:n] + (mark if len(s) > n else "")
        return "\n".join(out)

    def gather_files(self, paths, per_file_tokens: int = 600) -> list:
        """Read candidate files via the sandbox when there is one. The context
        manager should not be a side door for reading ~/.ssh into a prompt."""
        out = []
        for p in list(paths or [])[:8]:
            if self.sandbox is not None:
                r = self.sandbox.read_file(p)
                if not r.get("success"):
                    out.append((str(p), ""))
                    continue
                body = r.get("content", "")
            else:
                body = ""
            keep = self._clip_lines(body, per_file_tokens)
            out.append((str(p), keep))
        return out

    def stats(self) -> dict:
        return {"prompts_built": self.built, "max_context_tokens":
                self.max_tokens, "budget": self.budget,
                "response_reserve": self.response_reserve,
                "truncated_prompts": self.truncations,
                "summarised_files": self.summaries,
                "dropped_parts": self.dropped_parts,
                "tokens_kept_est": self.tokens_kept,
                "tokens_dropped_est": self.tokens_dropped,
                "last_tokens_est": (self.last or {}).get("tokens_est"),
                "last_utilization": (self.last or {}).get("utilization"),
                "last_dropped": [d.get("part") for d in
                                 (self.last or {}).get("dropped", [])][:6],
                "token_source": (self.last or {}).get("token_source",
                                                      "estimate(chars/4)"),
                "reads_through_sandbox": self.sandbox is not None}

def tokenizer_is_real(fn) -> bool:
    """True only if the injected estimator is not the chars/4 fallback. Cost
    claims must not be laundered into looking like provider usage."""
    return getattr(fn, "__name__", "") != "estimate_tokens"