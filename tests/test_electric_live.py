"""ELECTRIC live demo: teach in chat, restart, recall a paraphrase, admit ignorance.

C1/C2/C3 all rebuilt the organ INSIDE one interpreter and said so.  Every test here
drives a SEPARATE PROCESS, so "it survived a restart" means it survived a restart: the
only thing carried between lives is the file on disk.  That is the claim a user cares
about, and it is the claim the earlier docs could not make.

The teach/ask markers (+ and ?) are not ceremony.  A bare organ has interrogatives == []
and word_patterns == [], so respond() cannot tell a question from a statement -- test_
bare_organ_cannot_classify pins that as a measured limitation rather than letting it
masquerade as a working demo.  See tools/electric_chat.py's docstring.
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "electric_chat.py"
sys.path.insert(0, str(ROOT))

TEACH = "the scarf is on the hook"
PARAPHRASE = "where is the scarf?"          # same fact, different words, never taught
UNTAUGHT = "what is the scarf like?"        # subject known, relation never told


def say(text, state, *extra):
    """One utterance in its own process.  Returns the JSON line it printed."""
    p = subprocess.run([sys.executable, str(TOOL), "--state", str(state),
                        "--say", text, *extra],
                       capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert p.returncode == 0, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
    line = [l for l in p.stdout.splitlines() if l.startswith("{")][-1]
    return json.loads(line)


def post(url, obj, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------ e2e ----
def test_teach_restart_paraphrase_recall(tmp_path):
    """Life 1 is told a fact.  Life 2 is a different process and is asked in words
    it has never heard.  It must answer with the fact, from the keyed inventory."""
    st = tmp_path / "neural_lang.json"

    t = say("+" + TEACH, st)
    assert t["door"] == "hear"
    assert t["taught_this_turn"] == 1, f"teach did not enter the inventory: {t}"
    assert t["saved"] is True

    r = say("?" + PARAPHRASE, st)                      # <- RESTART: new process
    assert r["boot"]["loaded"] is True, f"state did not load: {r['boot']}"
    assert r["boot"]["inventory_at_boot"] == 1, \
        f"inventory lost across the restart: {r['boot']}"
    assert r["reply"] == TEACH, f"paraphrase not answered with the taught fact: {r}"
    assert r["source"] == "electric_taught", f"did not come from the inventory: {r}"
    assert r["taught_this_turn"] == 0, f"asking taught something: {r}"


def test_admits_ignorance_for_a_relation_never_told(tmp_path):
    """The honesty half.  `scarf` IS in the inventory (so he knows what he is being
    asked about) but no property was ever told for it -- the one case licensed as an
    admission rather than a guess or a silence."""
    st = tmp_path / "neural_lang.json"
    say("+" + TEACH, st)

    r = say("?" + UNTAUGHT, st)                        # <- RESTART
    assert r["licensed_refusal"] is True, f"no licensed refusal: {r}"
    assert r["source"] == "electric_absence", f"refusal came from elsewhere: {r}"
    assert "don't know" in r["reply"], f"did not say it does not know: {r}"
    assert r["reply"] != UNTAUGHT, f"echoed the question instead: {r}"
    # and the taught fact is still there -- an admission must not cost a memory
    assert r["inventory"] == 1, f"admitting ignorance disturbed the inventory: {r}"


def test_control_arm_flags_off_teaches_nothing(tmp_path):
    """ELECTRIC is behind flags.  With --no-electric the same sentence must not enter
    the inventory, so a battery run cannot be taught by an accidental chat."""
    st = tmp_path / "neural_lang.json"
    t = say("+" + TEACH, st, "--no-electric")
    assert t["boot"]["electric"] is False
    assert t["taught_this_turn"] == 0, f"taught with flags OFF: {t}"

    r = say("?" + PARAPHRASE, st, "--no-electric")
    assert r["boot"]["inventory_at_boot"] == 0, f"inventory exists with flags OFF: {r}"
    assert r["source"] != "electric_taught", f"keyed recall ran with flags OFF: {r}"


def test_bare_organ_cannot_classify_a_question(tmp_path):
    """PINNED LIMITATION, not a bug in the harness.  The house door respond() decides
    teach-vs-ask by looking for a learned interrogative (:4440).  A bare organ has none
    (interrogatives == [], word_patterns == []), so an unmarked question is HEARD and
    never answered.  If someone later 'fixes' this by classifying in Python, this test
    fails and the shortcut has to be a deliberate, documented choice."""
    st = tmp_path / "neural_lang.json"
    say("+" + TEACH, st)
    r = say(PARAPHRASE, st)                            # unmarked -> respond()
    assert r["door"] == "respond"
    assert r["spoken"] is False, f"bare organ answered via respond(): {r}"
    assert r["reason"] == "heard; no language learned yet", \
        f"reason changed -- re-measure the limitation: {r}"
    assert r["taught_this_turn"] == 0


# ------------------------------------------------------------- real HTTP ----
def test_http_chat_server_shutdown_and_restart(tmp_path):
    """The demo as a person would use it: a server on a port, a POST per turn, a
    clean /shutdown, then a brand new process that still remembers.  /shutdown exists
    because terminate() on Windows kills without running finally blocks -- a persistence
    claim that depended on that would be testing nothing."""
    st = tmp_path / "neural_lang.json"
    proc = subprocess.Popen([sys.executable, str(TOOL), "--state", str(st),
                             "--port", "0"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=str(ROOT))
    try:
        port = None
        t0 = time.time()
        while time.time() - t0 < 180:
            line = proc.stdout.readline()
            if not line:
                break
            if "ready port=" in line:
                port = int(line.split("ready port=")[1].split()[0])
                break
        assert port, f"server never came up: {line!r}"

        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(base + "/health", timeout=120) as h:
            assert json.loads(h.read().decode())["electric"] is True

        a = post(base + "/chat", {"text": "+" + TEACH})
        assert a["taught_this_turn"] == 1, a

        b = post(base + "/v1/chat/completions",
                 {"messages": [{"role": "user", "content": "?" + PARAPHRASE}]})
        assert b["choices"][0]["message"]["content"] == TEACH, b
        assert b["choices"][0]["electric"]["source"] == "electric_taught", b

        c = post(base + "/chat", {"text": "?" + UNTAUGHT})
        assert c["licensed_refusal"] is True, c

        s = post(base + "/shutdown", {})
        assert s["saved"] is True, s
    finally:
        proc.wait(timeout=180)
        assert st.exists(), "the session left no state file behind"

    # ---- and now the restart, in a process that never shared anything with it ----
    r = say("?" + PARAPHRASE, st)
    assert r["boot"]["loaded"] is True, r["boot"]
    assert r["boot"]["inventory_at_boot"] == 1, r["boot"]
    assert r["reply"] == TEACH, f"lost across a real server shutdown: {r}"
    assert r["source"] == "electric_taught", r


# ------------------------------------------------------ no global leakage ----
def test_demo_does_not_flip_the_class_defaults(tmp_path):
    """Battery runs read ELECTRIC off the CLASS, default False.  The demo sets it on an
    INSTANCE.  Importing the tool and building an organ must leave the class alone, or
    'ELECTRIC off for battery runs' becomes a sentence about intent instead of fact."""
    import organs.neural_language as nl
    import tools.electric_chat as ec

    assert nl.NeuralLanguage.ELECTRIC_TEACH is False
    assert nl.NeuralLanguage.ELECTRIC_ANSWER is False
    o = ec.build_organ(tmp_path / "never_written.json", True)
    assert o.ELECTRIC_TEACH is True and o.ELECTRIC_ANSWER is True
    assert nl.NeuralLanguage.ELECTRIC_TEACH is False, \
        "the demo leaked its flags onto the class"
    assert nl.NeuralLanguage.ELECTRIC_ANSWER is False


def test_serve_has_the_flag_and_is_off_without_it():
    """serve.py --electric must EXIST and must be opt-in.  Checked through the real
    argparse (--help exits before the house loads, so this costs no boot)."""
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "serve.py"), "--help"],
                       capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert p.returncode == 0, p.stderr
    assert "--electric" in p.stdout
    src = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    assert 'add_argument("--electric", action="store_true"' in src, \
        "flag must default to off, not to on"
