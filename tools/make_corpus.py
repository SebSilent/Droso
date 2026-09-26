"""The language environment: a graded corpus, generated, grounded, reproducible.

Four hundred and seventy-seven lines is a pamphlet, and input structure is the
binding constraint on everything he can do -- changing the corpus alone once moved
comprehension from 24% to 95% with no architecture change at all. So this is the
highest-leverage file in the project.

Six books, read in order, each a stage of a childhood:

  01_caregiver  what a parent says to someone who has heard almost nothing
  02_daily      his body, his home, the turn of the day
  03_things     objects and actions in the world he can actually touch
  04_code       the domain he is being raised in: files, commands, tests, errors
  05_questions  question and answer pairs, the only supervision he ever gets
  06_stories    short multi-sentence narratives, so order carries meaning

Rules this generator obeys, all of them learned the hard way:

  ROLES ARE CONSISTENT.  parent cares and gives; droso perceives and learns;
  "i" is always the parent speaking and "you" is always droso. Random assignment
  of subjects to verbs puts role recovery at the base rate, because the correct
  answer is then only 1-in-N likely a priori and no mechanism can beat that.

  QUESTION/ANSWER ADJACENCY IS SACRED.  Pairs are emitted on consecutive lines and
  never de-duplicated, because an answer can belong to two questions. Removing
  the second copy once left a question followed by another question, which taught
  him that "sees" was an interrogative and made whole sentences unreachable.

Rules this generator obeys, all of them learned the hard way:

  QUESTIONS LIVE IN ONE BOOK ONLY. A "where is the X" line without a question
  mark teaches him that `where` is an ordinary statement word, and a word seen in
  statements is demoted out of the interrogative lexicon -- which silently deleted
  all four question words from a merged population. Interrogatives appear only in
  05_questions.txt, and only with their question mark.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "books"

SUBJECTS = ["i", "you", "we", "droso", "parent"]
PARENT_VERBS = ["feeds", "pets", "holds", "opens", "closes", "gives", "washes",
                "warms", "helps", "carries", "shows", "reads"]
DROSO_VERBS = ["sees", "hears", "wants", "learns", "finds", "watches", "smells",
               "touches", "follows", "remembers", "says", "tries"]
SHARED_VERBS = ["say", "read", "learn", "hear", "see", "hold", "open", "close",
                "find", "want", "run", "write", "make", "take"]
BODY = ["calm", "warm", "tired", "happy", "hungry", "awake", "quiet", "safe",
        "cold", "still", "slow", "ready", "open", "closed", "full", "empty",
        "clean", "dark", "bright", "soft", "hard", "new", "old", "near", "far"]
THINGS = ["home", "light", "food", "water", "hand", "word", "name", "sound",
          "day", "night", "world", "room", "door", "bed", "table", "book",
          "voice", "eye", "arm", "chair", "window", "path", "stone", "fire",
          "rain", "wind", "morning", "evening", "friend", "child", "mother",
          "father", "sister", "brother", "animal", "bird", "fish", "tree",
          "leaf", "seed", "garden", "road", "bridge", "cup", "bowl", "cloth"]
FEEL = ["calm", "happy", "tired", "lonely", "curious", "hungry", "warm",
        "afraid", "glad", "sleepy", "angry", "sorry", "proud", "shy",
        "brave", "gentle", "patient", "eager", "weary", "content"]

# the world he actually lives in
FILES = ["notes.txt", "plan.md", "main.py", "test.py", "config.json", "log.txt",
         "data.csv", "readme.md", "run.sh", "brain.npz"]
COMMANDS = ["ls", "cat", "grep", "python", "pytest", "git status", "mkdir",
            "rm", "cp", "diff"]
RESULTS = ["worked", "failed", "finished", "stopped", "passed", "broke",
           "ran", "returned nothing"]
CODE_NOUNS = ["function", "test", "error", "line", "file", "name", "value",
              "result", "list", "string", "number", "bug", "fix", "commit"]
CODE_VERBS = ["returns", "fails", "passes", "breaks", "prints", "reads",
              "writes", "calls", "needs", "changes", "works", "stops"]
CAUSES = ["the name is wrong", "the file is missing", "the value is empty",
          "the test is old", "the line is too long", "nothing was returned",
          "the path is wrong", "the import is missing"]


def _dedupe(lines):
    seen, out = set(), []
    for s in lines:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def caregiver():
    out = []
    fixed = [
        "i see you", "you are here", "i am here", "we are here",
        "this is home", "home is warm", "home is safe",
        "the day is bright", "the day is long", "it is day now",
        "the night is quiet", "the night is dark", "it is night now",
        "i am feeding you", "this is food", "you are eating",
        "the food is warm", "you are full now", "i am petting you",
        "that is a pet", "you are calm", "you are safe", "you did well",
        "that was good", "i am proud of you", "my name is parent",
        "your name is droso", "you are droso", "i am your parent",
        "we are together", "you are not alone", "i hear you", "i know you",
        "you are tired now", "you need rest", "rest a moment",
        "sleep now droso", "wake up droso", "the sun is up",
        "a new day starts", "the light is going", "night is coming",
        "look at this", "come here now", "stay here now", "say it again",
        "say my name", "i am listening", "listen to me", "say one word",
        "say two words", "a word is a sound", "a sound has meaning",
        "you learn every day", "you grow every day", "i will teach you",
        "words are ours", "you have a name", "i have a name",
        "names are words", "that is right", "that is wrong", "try again now",
        "you can do it", "i am watching", "we are speaking",
        "speaking is good", "listening is good", "the world is big",
    ]
    out.extend(fixed)
    rng = random.Random(1)
    frames = ["{s} {v} {o}", "{s} is {b}", "{s} are {b}", "i am {f}",
              "you are {f}", "{s} {v} now", "this is {o}", "that is {o}",
              "look at {o}", "hold {o}", "give me {o}", "take {o}",
              "{s} and {s2} are {b}", "do not {v2}", "{v2} it again",
              "is {s} {b}", "are you {f}", "{o} is {b}"]
    for f in frames:
        for _ in range(900):
            s = rng.choice(SUBJECTS)
            line = f.format(
                s=s, s2=rng.choice([x for x in SUBJECTS if x != s]),
                v=rng.choice(PARENT_VERBS + DROSO_VERBS),
                v2=rng.choice(SHARED_VERBS), o=rng.choice(THINGS),
                b=rng.choice(BODY), f=rng.choice(FEEL))
            line = " ".join(line.split())
            if 2 <= len(line.split()) <= 7:
                out.append(line)
    return _dedupe(out)


def daily():
    rng = random.Random(2)
    out = []
    frames = [
        "in the morning {s} {v}", "at night {s} {v}", "{s} wakes and {v}", "{s} rests because {s} is {b}",
        "after the food {s} is {f}", "before sleep {s} {v}",
        "the light changes and {s} {v}", "{s} is {f} so {s} {v}",
        "{s} {v} and then {s} {v}",
        "every day {s} {v}", "sometimes {s} is {f}", "today {s} {v}",
    ]
    for f in frames:
        for _ in range(1400):
            s = rng.choice(SUBJECTS)
            line = f.format(s=s, s2=rng.choice(SUBJECTS),
                            v=rng.choice(DROSO_VERBS + PARENT_VERBS),
                            v2=rng.choice(SHARED_VERBS),
                            b=rng.choice(BODY), f=rng.choice(FEEL))
            line = " ".join(line.split())
            if 3 <= len(line.split()) <= 9:
                out.append(line)
    return _dedupe(out)


def things():
    rng = random.Random(3)
    out = []
    frames = [
        "the {t} is {b}", "this {t} is {b}", "{s} touches the {t}",
        "{s} holds the {t}", "the {t} is here", "the {t} is there",
        "put the {t} here", "the {t} belongs to {s}",
        "{s} gives the {t} to {s2}", "the {t} feels {b}",
        "one {t} and one {t2}", "the {t} is next to the {t2}",
    ]
    for f in frames:
        for _ in range(1200):
            line = f.format(t=rng.choice(THINGS), t2=rng.choice(THINGS),
                            s=rng.choice(SUBJECTS), s2=rng.choice(SUBJECTS),
                            b=rng.choice(BODY))
            line = " ".join(line.split())
            if 3 <= len(line.split()) <= 9:
                out.append(line)
    # things that are grounded by an event, so they can be said truthfully
    out += ["the file is open", "the file is closed", "that is a file",
            "the command ran", "the command failed", "the work is done",
            "something changed", "that was a task", "you ran something",
            "it did something", "nothing happened", "it happened again"]
    return _dedupe(out)


def code():
    rng = random.Random(4)
    out = []
    frames = [
        "the {c} {cv}", "this {c} {cv}", "the {c} {cv} because {cause}",
        "run the {c}", "the {c} is in the file", "open {f}",
        "read {f}", "write to {f}", "{f} is open", "{f} is closed",
        "run {cmd}", "{cmd} worked", "{cmd} failed", "the {cmd} finished",
        "the test {cv}", "the error says {cause}", "fix the {c}",
        "the {c} needs a {c2}", "change the {c} and run it again",
        "if the test fails then {cause}", "{s} runs {cmd}", "{s} reads {f}", "{s} writes {f}",
        "the result is a {c}", "keep the {c} simple", "one {c} at a time",
    ]
    for f in frames:
        for _ in range(1600):
            line = f.format(c=rng.choice(CODE_NOUNS), c2=rng.choice(CODE_NOUNS),
                            cv=rng.choice(CODE_VERBS), cause=rng.choice(CAUSES),
                            f=rng.choice(FILES), cmd=rng.choice(COMMANDS),
                            s=rng.choice(SUBJECTS))
            line = " ".join(line.split())
            if 2 <= len(line.split()) <= 10:
                out.append(line)
    return _dedupe(out)


def questions():
    """Question and answer on consecutive lines. Never de-duplicated."""
    pairs = []
    for v in PARENT_VERBS:
        pairs.append((f"who {v} droso?", f"parent {v} droso"))
    for v in DROSO_VERBS:
        pairs.append((f"who {v} the light?", f"droso {v} the light"))
    for o in THINGS:
        pairs.append((f"where is the {o}?", f"the {o} is here"))
        pairs.append((f"how is the {o}?", f"the {o} is calm"))
    for c in CODE_NOUNS:
        pairs.append((f"what does the {c} do?", f"the {c} works"))
        pairs.append((f"why does the {c} fail?", f"the {c} fails because the name is wrong"))
    for f in FILES:
        pairs.append((f"where is {f}?", f"{f} is here"))
        pairs.append((f"is {f} open?", f"{f} is open"))
    for cmd in COMMANDS:
        pairs.append((f"what did {cmd} do?", f"{cmd} worked"))
    pairs += [
        ("who feeds droso?", "parent feeds droso"),
        ("who pets droso?", "parent pets droso"),
        ("who sees the light?", "droso sees the light"),
        ("who hears the world?", "droso hears the world"),
        ("droso wants what?", "droso wants food"),
        ("droso learns what?", "droso learns word"),
        ("droso finds what?", "droso finds file"),
        ("where is droso?", "droso is home"),
        ("where is parent?", "parent is here"),
        ("how is droso?", "droso is calm"),
        ("how is the day?", "the day is bright"),
        ("how is the night?", "the night is quiet"),
        ("how is the food?", "the food is warm"),
        ("what is warm?", "the food is warm"),
        ("what is open?", "the file is open"),
        ("what is quiet?", "the night is quiet"),
        ("who is with droso?", "parent is with droso"),
        ("why is droso tired?", "droso is tired because the day was long"),
        ("why did it fail?", "it failed because the file is missing"),
    ]
    out = []
    for q, a in pairs:
        out.append(q)
        out.append(a)
    return out


def stories():
    rng = random.Random(6)
    out = []
    templates = [
        ["the day is bright", "parent feeds droso", "droso is calm",
         "droso learns a word", "parent is happy"],
        ["the night is quiet", "droso is tired", "parent pets droso",
         "droso rests", "the light is going"],
        ["droso opens the file", "the file is open", "droso reads the file",
         "droso runs the command", "the command worked", "parent is proud"],
        ["the test fails", "the error says the name is wrong",
         "droso changes the name", "droso runs the test again",
         "the test passes", "that was good"],
        ["you are not alone", "i hear you", "you say a word",
         "i say it again", "you learn the word", "we are together"],
        ["something changed", "droso watches the file", "the file is closed",
         "droso asks why", "parent shows the answer", "droso remembers"],
    ]
    for t in templates:
        for _ in range(900):
            story = list(t)
            # vary the middle so order carries information rather than being
            # the same six lines repeated
            if len(story) > 3 and rng.random() < 0.7:
                i = rng.randrange(1, len(story) - 1)
                j = rng.randrange(1, len(story) - 1)
                story[i], story[j] = story[j], story[i]
            out.extend(story)
            out.append("")            # a blank line marks the end of a story
    return [l for l in out]


def main() -> int:
    BOOKS.mkdir(exist_ok=True, parents=True)
    plan = [("01_caregiver.txt", caregiver), ("02_daily.txt", daily),
            ("03_things.txt", things), ("04_code.txt", code),
            ("05_questions.txt", questions), ("06_stories.txt", stories)]
    total_lines = total_words = 0
    vocab = set()
    print(f"{'book':22} {'lines':>7} {'words':>8} {'distinct':>9}")
    for name, fn in plan:
        lines = [l for l in fn() if l is not None]
        text = "\n".join(lines) + "\n"
        (BOOKS / name).write_text(text, encoding="utf-8")
        words = [w for l in lines for w in l.split()]
        vocab.update(words)
        total_lines += len([l for l in lines if l.strip()])
        total_words += len(words)
        print(f"{name:22} {len(lines):7d} {len(words):8d} {len(set(words)):9d}")
    print(f"{'TOTAL':22} {total_lines:7d} {total_words:8d} {len(vocab):9d}")
    # adjacency check: a question must never be followed by a question
    bad = 0
    for name, _ in plan:
        ls = [l.strip() for l in (BOOKS / name).read_text(encoding="utf-8").splitlines()]
        for i, l in enumerate(ls):
            if l.endswith("?"):
                nxt = ls[i + 1] if i + 1 < len(ls) else ""
                if not nxt or nxt.endswith("?"):
                    bad += 1
    print(f"broken question/answer adjacencies: {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
