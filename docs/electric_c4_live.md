# ELECTRIC C4 — the live demo: teach in chat, restart, recall a paraphrase

```bash
.venv\Scripts\python.exe tools\electric_chat.py --state state\electric_chat\neural_lang.json
.venv\Scripts\python.exe tools\serve.py --electric --session-dir state\sessions\demo
.venv\Scripts\python.exe -m pytest tests\test_electric_live.py -q      # 7 passed, 38.6 s
```

**What a user can now do:** talk to the organism, tell it facts, close the window, open
it again, ask about that fact **in different words**, get the fact back — and ask about a
relation that was never told and get *"i don't know, scarf was told but no property was
ever told for scarf"*.

## 1. What was added

| file | what |
|---|---|
| `tools/electric_chat.py` | new — the demo door: HTTP chat server + `--say` one-shot |
| `tools/serve.py` | `--electric` flag (opt-in, default off) |
| `tests/test_electric_live.py` | new — 7 tests, every one a **separate process** |

Nothing else moved. No organ code changed. The guarded grader contract was not touched.

## 2. The restart is real this time

C2 and C3 both rebuilt the organ **inside one interpreter** and both docs said so. Here
each life is its own process: `--say` boots, `load_state()`s, serves one utterance,
saves, exits. Two `--say` calls share nothing but the file.

Two facts made this work, and one of them was a gap:

- `save_state(delta=True)` **still writes the json** (`:5015-5017`), and that json
  carries `taught_says` (`:4995`). A delta save skips the SAN and the chain, not the
  inventory — so serve.py's existing end-of-session delta save was already enough.
- `converse.build()` repoints **writes** into the session dir and **never reads them
  back**. So a second `serve.py` over the same `--session-dir` came up amnesiac even with
  the state on disk. `--electric` now calls `lang.load_state()` after the build; on the
  first life of a session that is a no-op returning `{"loaded": False}` (`:5082`).

Measured, across processes: `inventory_at_boot: 0` → taught → next process
`{"loaded": true, "inventory_at_boot": 1}` → `reply: "the scarf is on the hook"`,
`source: "electric_taught"`.

## 3. A finding I did not expect: a bare organism does not know what a question is

The intended design was one door for everything: `respond()`, the house's own call,
which routes by form — interrogative → `answer()` (`:4443`), statement → `hear()`
(`:4455`), and `hear()` is the only write site of the inventory (`:4347`).

**On a bare organ it silently fails.** Measured:

```
interrogatives = []      word_patterns = []
respond("where is the scarf?") -> spoken: False, reason: "heard; no language learned yet"
answer("where is the scarf?")  -> "the scarf is on the hook", source electric_taught
```

Both sets are *learned* — interrogatives from question/answer pairs (`:2440`), words from
corpus exposure — and the demo loads neither. So the routing test at `:4440` never fires
and a question is heard as a statement. Asking it correctly once does not help: after a
correct `answer()`, `interrogatives` is **still `[]`** — answering does not learn the
interrogative.

I did not fix this by sorting statements from questions in Python. That would put a
classifier in the demo that the demo exists to test. Instead the **speaker declares the
act**: `+` = telling (`hear()`), `?` = asking (`answer()`), unmarked = `respond()`. The
marker is stripped before the organ sees the text, so it enters neither the SAN, the
binder, nor the stored tell. Against the real house (11,555 words, learned
interrogatives) no marker is needed.

`test_bare_organ_cannot_classify_a_question` pins the silence and its exact reason
string, so if anyone later "fixes" it with a shortcut, the test fails and the shortcut
has to be a deliberate decision.

## 4. One real bug, caught by the test

`/shutdown` first called `self.server.shutdown()` **from inside a request handler**. This
server is single-threaded, so the handler runs inside `serve_forever`, and `shutdown()`
blocks until that loop reports itself stopped — a self-deadlock. The test hung 180 s on a
process politely waiting for itself. Fixed by shutting down from another thread. Two
stray processes from the failed run were killed.

`/shutdown` exists at all because `terminate()` on Windows kills without running `finally`
blocks: a persistence claim that depended on the shutdown hook would be testing nothing.

## 5. What the 7 tests actually assert

| test | assertion |
|---|---|
| teach → restart → paraphrase | inventory survives the boot (`inventory_at_boot == 1`), reply **equals** the taught tell, `source == electric_taught`, and asking teaches nothing |
| untaught relation | `licensed_refusal`, `source == electric_absence`, reply contains "don't know", reply is **not** an echo of the question, inventory undisturbed |
| control arm `--no-electric` | the same sentence enters nothing (`taught_this_turn == 0`), keyed recall never runs |
| bare organ / respond() | pinned limitation (§3) |
| HTTP server | real port, POST per turn, `/shutdown` saves, **new process** still recalls |
| no class leakage | `NeuralLanguage.ELECTRIC_*` still `False` after the demo builds an organ with them `True` on the instance |
| serve.py | `--electric` exists and is `action="store_true"` — opt-in, not default |

## 6. Not established

- **`serve.py --electric` was never run end-to-end.** It is flag-wired and
  argparse-tested only; booting the real house for a test is minutes and hundreds of MB.
  So "the live house demo works" is *not* verified here — what is verified is the same
  teach/answer/refusal machinery on a bare organ, plus the load-on-restart line the house
  needs. This is the main gap.
- **`respond()` on the bare organ is not ELECTRIC's fault** and is not evidence about the
  house, where interrogatives exist. §3's numbers are about a stateless organ.
- **Two facts, one subject.** The demo teaches one tell and probes it. C3's 15-fact/3-cycle
  result is the relevant longevity evidence; nothing here extends it.
- **No multi-turn conversation test**, no concurrency (single-threaded by design), no
  long-session memory growth check, no UI beyond JSON.
- **Marker UX is a workaround, not a feature.** The right fix for a bare organ is
  exposure to question/answer pairs, which is a learning question, not a demo question.
- Untouched, as ever: the `copper`/`bell` multi-relation modifier-keying limitation.

## 7. Flags and battery runs

ELECTRIC remains off by default in every path that measurement depends on: the class
attributes stay `False`, the demo sets them per-instance in its own process, and
`serve.py` needs `--electric` explicitly. `tests/test_electric_live.py` spawns
subprocesses, so it cannot mutate the parent interpreter's defaults even in principle —
and the leakage test asserts it cannot in practice either.

**Suite: 826 passed, 3 skipped, 5 warnings** (was 819; +7 new; **zero erosion**). Wall
clock 182 s → 218 s, all of it the new live tests booting real processes.
