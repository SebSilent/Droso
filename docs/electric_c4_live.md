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

- **§3's numbers are from the bare organ; §8 is the real house.** Read §8 before §3 —
  the house routes correctly with no markers at all.
- **`respond()` on the bare organ is not ELECTRIC's fault** and is not evidence about the
  house, where interrogatives exist. §3's numbers are about a stateless organ.
- **Two facts, one subject.** The demo teaches one tell and probes it. C3's 15-fact/3-cycle
  result is the relevant longevity evidence; nothing here extends it.
- **No multi-turn conversation test**, no concurrency (single-threaded by design), no
  long-session memory growth check, no UI beyond JSON.
- **Marker UX is a workaround, not a feature.** The right fix for a bare organ is
  exposure to question/answer pairs, which is a learning question, not a demo question.
- Untouched, as ever: the `copper`/`bell` multi-relation modifier-keying limitation.

## 8. The real house, over HTTP, across three processes

`serve.py --electric --session-dir state\sessions\c4live2 --port 8138`, driven by
`_tmp/c4_drive.py` (POST to `/v1/chat/completions`, **no markers**). Boot: **15 s**,
11,555 words, 60,000 propositions, `ELECTRIC on: loaded=False taught facts=0`.

**The markers from §3 are not needed on the house.** `respond()` routed both acts
correctly, because the house has learned interrogatives. This closes the gap §6 used to
declare open.

**Life 1 — told** (raw: `docs/evidence/electric_c4_live_teach.json`):

| utterance | taught_this_turn | inventory | what it said |
|---|---|---|---|
| `the scarf is on the hook` (re-tell) | **0** | 1 | *(silent — "it understood but did not feel like speaking")* |
| `the lantern belongs to Mira` | 1 | 2 | `wroth ix` (source `meaning resonance + chain`) |
| `the ledger is under the desk` | 1 | 3 | *(silent)* |

Being taught and speaking are separate acts: the tell entered the inventory even on the
two turns it stayed silent about, and its spoken reply was free-associated, never the
tell. First-tell-wins held on the house: re-telling the scarf changed nothing.

`POST /shutdown` → `{"saved": true}`, then `[serve] session state written under …`.

**Life 2 — asked after a real restart** (`electric_c4_live_ask.json`): boot printed
**`ELECTRIC on: loaded=True taught facts=3 subjects=3`**.

| question | reply | source |
|---|---|---|
| `where is the scarf?` | **`the scarf is on the hook`** | `electric_taught` |
| `where is the ledger?` | **`the ledger is under the desk`** | `electric_taught` |
| `who does the lantern belong to?` | `mira` | `arbiter head` |
| `what is the scarf like?` | **`i don't know, scarf was told but no property was ever told for scarf`** | `electric_absence` |

**Life 3 — asked again** (`electric_c4_live_ask2.json`), same three facts loaded again
from disk: scarf and ledger recalled verbatim, the untaught relation admitted again — and
the lantern ask came back **silent**: `spoken: false`, `reason: "nothing he remembers has
that shape"`.

### What that lantern row is telling us

The reverse-role ask (`who does X belong to?`) **never reaches the keyed inventory** —
`_electric_answer` looks the subject up by its own key, and "lantern/belongs to" is keyed
under the possessor's frame, not the object's. This is the same limitation C3 measured
(2 of 15 facts fell off `electric_taught` on reverse-role asks) now seen on the house. And
what covers for it is the house's own associative retrieval, which is **not stable across
lives**: one life answered `mira` from `arbiter head`, the next said nothing. So the
honest summary is *forward* paraphrase recall is reliable and verbatim; **reverse-role
recall is not**, and nothing in ELECTRIC yet makes it so.

### Two telemetry bugs the house caught (both now fixed + tested)

1. **`--electric` surfaced nothing.** serve.py does not call `respond()` itself — it calls
   `session.ask()` (`:159` → `converse.py:288`, `speaker="you"`, correct) and builds the
   payload from `turn["reply"]`, which dropped every ELECTRIC field. The `door`/`source`/
   `inventory` fields in §2–§5 were **computed by `electric_chat.py`, never returned by
   `respond()`** — my earlier note that serve.py's payload already carried them was
   wrong. Added a `choice["electric"]` view, gated on the flag, so with `--electric` off
   the wire format is byte-identical (asserted).
2. **`taught_this_turn` lied on restart.** It diffed against 0, so the first turn of a
   restarted session reported the 3 facts it had *loaded* as if that turn had taught them.
   Now seeded from the loaded inventory;
   `test_serve_telemetry_does_not_report_loaded_facts_as_taught` drives
   `completion_payload` with a stub and asserts `taught_this_turn == 0`, and that no
   `electric` member appears with the flag off.

`licensed_refusal` is `null` on the house's admission row: it is a faithful pass-through
of a key the house's `answer()` dict does not carry on that path, while the bare-organ
harness computes it itself. The admission is identified on the house by
`source == electric_absence` plus its `reason`. I left the null rather than deriving a
second definition of the same word.

### A pre-existing guard report, not an ELECTRIC effect

Every serve life printed `[serve] live files untouched: False` with five paths, all named
`banc_brain.npz` under `live_learner\{current,staging,versions}`. That is the documented
no-op churn (debt entry 6) which serve.py tries to exclude — but the exclusion is
`m == "banc_brain.npz"` against a **relative path**, so it can never match, and the
`known` branch is dead code. It is not gated on `--electric` and would print identically
without it; no content drift was reported. I did not touch it: it is a reporting bug in a
guarded contract path, outside this task, and worth its own fix.

## 7. Flags and battery runs

ELECTRIC remains off by default in every path that measurement depends on: the class
attributes stay `False`, the demo sets them per-instance in its own process, and
`serve.py` needs `--electric` explicitly. `tests/test_electric_live.py` spawns
subprocesses, so it cannot mutate the parent interpreter's defaults even in principle —
and the leakage test asserts it cannot in practice either.

**Suite: 826 passed, 3 skipped, 5 warnings** (was 819; +7 new; **zero erosion**). Wall
clock 182 s → 218 s, all of it the new live tests booting real processes.
