import sys
sys.path.insert(0, "C:/Projects/HybridLLM")
from organs.code_assembler import CodeAssembler
from organs.language_detector import LanguageDetector
from organs.language_verifier import LanguageVerifier
from organs.multi_language_writer import MultiLanguageWriter
from organs.language_paradigms import LanguageParadigms

w = MultiLanguageWriter(CodeAssembler())
det = LanguageDetector()

print(det.detect("fix my roblox jump script", file_paths=None))
print(det.detect("add an event listener", file_paths=["app.js"]))
print(det.detect("make a webpage with a button and counter"))
print(det.detect("", file_paths=None, existing_code="local x = 1\nfunction f(a) if a then return 1 end end\n"))
print(det.detect("reverse string with pointers"))
print(det.detect("implement stack using std::vector"))
print(det.detect("some totally unknown task"))

lua = "-- counter module\nlocal clicks = 0\n\nlocal function reset()\n    clicks = 0\nend\n"
r = w.execute_action("ADD_FUNCTION", "jump_count", {"body": "return 1", "params": "player"}, lua, "lua")
print("\nLUA-ADD:", r["success"], r.get("error", ""), "\n" + r.get("code", "")[:220])
r2 = w.execute_action("MODIFY_FUNCTION", "reset", {"body": "clicks = 0\nreturn clicks"}, r.get("code", ""), "lua")
print("LUA-MOD:", r2["success"], r2.get("error", ""), r2.get("verified_by"))
js = "function add(a, b) { return a + b; }\n"
r3 = w.execute_action("ADD_FUNCTION", "mul", {"body": "return a * b;", "params": "a, b"}, js, "javascript")
print("JS-ADD:", r3["success"], r3.get("error", ""), r3.get("verified_by"))
r4 = w.execute_action("MODIFY_FUNCTION", "add", {"body": "return a + b + 0;"}, js, "javascript")
print("JS-MOD:", r4["success"], r4.get("error", ""), r4.get("verified_by"))
h = w.write_full_file("simple page with a button and a counter display", "html")
print("HTML-FILE:", h["success"], h.get("verified_by"), h.get("origin"))
r5 = w.execute_action("ADD_ELEMENT", "score", "<p id='s'>0</p>", h.get("code", ""), "html")
print("HTML-ELEM:", r5["success"], r5.get("verified_by"))
c = w.write_full_file("stack class using std vector", "cpp")
print("CPP-FILE:", c["success"], c.get("verified_by"))
v = LanguageVerifier()
bad = "local function f(a)\n    if a then\n        return 1"
print("BAD-LUA raw:", v.check(bad, "lua"))
w2 = w._repair(bad, "lua", v.check(bad, "lua")["error"], "f", "")
print("BAD-LUA repaired:", v.check(w2, "lua"))
py = "def f(x):\n    return x\n"
rp = w.execute_action("ADD_CONDITION", "f", {"test": "not x", "body": "return 0"}, py, "python")
print("PY-GUARD:", rp["success"], rp.get("verified_by", "ast"), "\n" + rp.get("code", ""))
print("\nparadigm patterns:", LanguageParadigms().get_pattern_for_task("handle error in roblox remote", "lua")[:2])