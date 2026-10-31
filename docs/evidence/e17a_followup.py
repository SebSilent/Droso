"""E17a follow-up: does the design's polarity-refusal logic work when the entity is
indexed CORRECTLY? The main probe mis-extracted 'then two eggs break' as entity='break',
which hid the event from the fold and made E3 fire for the wrong reason."""
import importlib.util as iu
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = iu.spec_from_file_location("p", ROOT / "docs/evidence/e17a_counting_probe.py")
m = iu.module_from_spec(spec)
spec.loader.exec_module(m)

ev = [
    {"entity": "egg", "numeral": 4, "frame": "absolute", "verb": None,
     "place": "basket", "seq": 0, "who": "you",
     "raw": "there are four eggs in the basket"},
    {"entity": "egg", "numeral": 2, "frame": "event", "verb": "break",
     "place": None, "seq": 1, "who": "you", "raw": "then two eggs break"},
]

cur, det = m.fold(ev, "egg", "basket")
print("fold with CORRECT entity -> current=%r determinate=%r" % (cur, det))
for a in ["how many eggs are left in the basket?",
          "what number of eggs is left in the basket?",
          "how many eggs broke?"]:
    print("  %-46s -> %s" % (a, m.query(a, ev)))

print()
print("'twice' in NUM dict?      ", "twice" in m.NUM)
print("extract 'the copper bell turns twice':", m.extract_event("the copper bell turns twice", 0))
print("extract 'then two eggs break':        ", m.extract_event("then two eggs break", 1))
print("extract 'there are four eggs in the basket':",
      m.extract_event("there are four eggs in the basket", 0))
