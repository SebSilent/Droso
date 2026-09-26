
from __future__ import annotations

class UserInterfaceOrgan:
    def __init__(self, input_fn=None, output_fn=None, max_output_chars: int = 4000):
        import builtins
        self._input = input_fn or builtins.input
        self._output = output_fn or print
        self.max_output_chars = int(max_output_chars)

    def say(self, text: str) -> dict:
        out = text[: self.max_output_chars]
        self._output(out)
        return {"ok": True, "said": out}

    def ask(self, prompt: str) -> dict:
        self._output(prompt)
        reply = self._input()
        return {"ok": True, "reply": str(reply)}

    def report(self, payload: dict) -> dict:
        """Render a structured organ result for the human; returns what was shown."""
        lines = [f"{k}: {v}" for k, v in payload.items()]
        return self.say("\n".join(lines))