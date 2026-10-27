"""Forced-failure evidence for the end-of-run session save.

Task item: converse.py:748 calls state_hygiene.save_session_state unwrapped;
require_saved raises SystemExit on failure, so a failed save must propagate
out of main() and kill the process with a non-zero exit code and the reason
on stderr -- fatal-loud by construction.  This wrapper proves it by
execution, not by reading:

  mode=evidence  patch save_session_state to raise, run main() with stdin at
                 EOF (zero turns, straight to the save).  Expected: the
                 SystemExit escapes, exit code 1, "FATAL: session save
                 failed: forced for evidence" on stderr.
  mode=report    no patch, --save added: a real run whose fitness report
                 must carry the new "exocortex_churn" field.

Also exercises the exocortex guard watch added 2026-10-26 (second watched
root, informational churn line) in both modes.
"""
import sys

sys.path.insert(0, r"C:\Projects\HybridLLM")

import tools.state_hygiene as state_hygiene
import tools.converse as converse

mode = sys.argv[1] if len(sys.argv) > 1 else "evidence"

# The patch must be visible to converse: it does `from tools import
# state_hygiene`, binding the module object, so the attribute lookup at the
# call site resolves through this same module.
assert converse.state_hygiene is state_hygiene, "converse bound a different module"

if mode == "evidence":
    def boom(lang, what: str):
        raise SystemExit(f"FATAL: {what} save failed: forced for evidence")

    state_hygiene.save_session_state = boom
    print("wrapper: save_session_state patched to raise", flush=True)
    sys.argv = ["converse.py", "--beats", "1"]
else:
    print("wrapper: unpatched, --save report-field run", flush=True)
    sys.argv = ["converse.py", "--beats", "1", "--save", "probe"]

converse.main()
print("wrapper: main() returned -- the SystemExit did NOT escape", flush=True)