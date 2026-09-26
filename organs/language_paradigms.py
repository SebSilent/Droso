
from __future__ import annotations

import re

class LanguageParadigms:
    PARADIGMS = {
        "python": {
            "function_definition": "def name(params): body",
            "class_definition": "class Name: methods",
            "error_handling": "try/except/finally",
            "iteration": "for item in iterable",
            "state_management": "class attributes or module variables",
            "async": "async def / await",
            "common_patterns": ["decorator", "context manager",
                                "list comprehension", "generator"],
        },
        "lua": {
            "function_definition": "function name(params) body end",
            "local_function": "local function name(params) body end",
            "table_as_object": "local obj = { field = v, method = "
                               "function(self) end }",
            "metatable": "setmetatable(obj, { __index = proto })",
            "coroutine": "coroutine.create / resume / yield",
            "error_handling": "pcall(fn) / xpcall(fn, handler)",
            "state_management": "locals in a closure or a module table",
            "roblox_specific": {
                "remote_event": "RemoteEvent:FireServer() / "
                                "OnServerEvent:Connect",
                "service_access": "game:GetService('ServiceName')",
                "instance_creation": "Instance.new('ClassName')",
                "connection": "signal:Connect(function() end)",
            },
            "common_patterns": ["module pattern", "closure",
                                "table inheritance", "event-driven"],
        },
        "javascript": {
            "function_definition": "function name(params) { body }",
            "arrow_function": "const name = (params) => { body }",
            "class_definition": "class Name { constructor() {} m() {} }",
            "async": "async function / await / Promise",
            "dom_manipulation": "document.querySelector / "
                                "addEventListener",
            "state_management": "closures / objects / classes",
            "error_handling": "try/catch/finally",
            "common_patterns": ["callback", "promise chain",
                                "event listener", "module"],
        },
        "html": {
            "document_structure": "<!DOCTYPE html><html><head></head>"
                                  "<body></body></html>",
            "form": "<form> with input elements",
            "canvas": "<canvas> with JavaScript drawing",
            "styling": "<style> block or inline styles",
            "interaction": "<script> block with event listeners",
            "common_patterns": ["semantic tags", "flex/grid layout",
                                "form validation", "canvas game loop"],
        },
        "c": {
            "function_definition": "return_type name(params) { body }",
            "struct": "struct Name { fields };",
            "pointer": "type *ptr = &var;",
            "memory": "malloc / free",
            "error_handling": "return codes / errno",
            "common_patterns": ["pointer arithmetic", "dynamic arrays",
                                "linked list", "file I/O"],
        },
        "cpp": {
            "function_definition": "return_type name(params) { body }",
            "class": "class Name { public: private: };",
            "template": "template<typename T>",
            "stl": "std::vector / std::map / std::string",
            "memory": "RAII / smart pointers",
            "error_handling": "exceptions (try/catch) or error codes",
            "common_patterns": ["RAII", "STL containers", "templates",
                                "inheritance"],
        },
    }

    def get_paradigms(self, language: str) -> dict:
        return self.PARADIGMS.get(str(language).lower(), {})

    def get_pattern_for_task(self, task_description: str,
                             language: str) -> list:
        t = str(task_description or "").lower()
        p = self.get_paradigms(language)
        out = []
        pairs = [("error", "error_handling"), ("exception", "error_handling"),
                 ("handle", "error_handling"), ("validate", "error_handling"),
                 ("function", "function_definition"),
                 ("method", "function_definition"),
                 ("state", "state_management"), ("track", "state_management"),
                 ("remember", "state_management"), ("count", "state_management"),
                 ("async", "async"), ("wait", "async"),
                 ("parallel", "async"),
                 ("class", "class_definition" if language != "cpp" else "class"),
                 ("object", "table_as_object" if language == "lua"
                  else "class_definition")]
        for word, key in pairs:
            if word in t and key in p and (key, p[key]) not in out:
                out.append((key, p[key]))
        if language == "lua" and "roblox" in t:
            for k, v in p.get("roblox_specific", {}).items():
                out.append((k, v))
        if language == "html" and ("game" in t or "canvas" in t) \
                and "canvas" in p:
            out.append(("canvas", p["canvas"]))
        return out

    @staticmethod
    def scaffold(language: str, kind: str, name: str = "item",
                 params: str = "", body: str = "", extra: str = "") -> str:
        language = str(language).lower()
        kind = str(kind).upper()
        body = str(body or "").strip()
        name = re.sub(r"[^A-Za-z0-9_]", "_", str(name or "item")) or "item"
        if language == "lua":
            if kind == "ADD_FUNCTION":
                return (f"local function {name}({params})\n"
                        + _indent(body or f"    -- {name}", "    ") + "\nend\n")
            if kind == "ADD_VARIABLE":
                return f"local {name} = {body or extra or '0'}\n"
            if kind == "ADD_CONDITION":
                return (f"if {body or 'cond'} then\n    return nil\nend\n")
            if kind == "ADD_METATABLE":
                return (f"{name} = {{}}\n{name}.__index = {name}\n"
                        f"function {name}.new()\n"
                        f"    return setmetatable({{}}, {name})\nend\n")
            if kind == "FILE":
                return ("-- lua module: " + str(extra or name) + "\n"
                        + (body or "")
                        + f"\nlocal M = {{}}\nM.{name} = {name}\n"
                        "return M\n")
        if language == "javascript":
            if kind == "ADD_FUNCTION":
                return (f"function {name}({params}) {{\n"
                        + _indent(body or f"// {name}", "    ") + "\n}\n")
            if kind == "ADD_VARIABLE":
                return f"const {name} = {body or extra or 'null'};\n"
            if kind == "ADD_CONDITION":
                return (f"if ({body or 'cond'}) {{\n    return null;\n}}\n")
            if kind == "ADD_EVENT_LISTENER":
                return (("const el = document.querySelector('"
                         + (extra or "#" + name) + "');\n"
                         "if (el) { el.addEventListener('click', "
                         "function (event) {\n    "
                         + (body or "// handler")
                         + "\n}); }\n"))
            if kind == "ADD_CLASS":
                return (f"class {name} {{\n    constructor() {{\n        "
                        + (body or "this.items = [];") + "\n    }\n}\n")
            if kind == "FILE":
                return ("// javascript: " + str(extra or name) + "\n"
                        + (body or "") + "\nmodule.exports = { "
                        + name + " };\n")
        if language == "html":
            if kind == "ADD_ELEMENT":
                return "<div id=\"" + name + "\">" + (body or "") + "</div>\n"
            if kind == "ADD_STYLE":
                return "<style>\n" + (body or "body { margin: 0; }") + "\n</style>\n"
            if kind == "ADD_SCRIPT":
                return "<script>\n" + (body or "// script") + "\n</script>\n"
            if kind == "FILE":
                return _HTML_DOC(str(extra or name), body)
        if language in ("c", "cpp"):
            inc = ("<iostream>\n<vector>\n" if language == "cpp"
                   else "<stdio.h>\n<stdlib.h>\n<string.h>\n")
            kw = "std::" if language == "cpp" else ""
            if kind == "ADD_FUNCTION":
                return (f"static int {name}({params or 'void'}) {{\n"
                        + _indent(body or f"// {name}", "    ") + "\n}\n")
            if kind == "ADD_VARIABLE":
                return f"static int {name} = {body or extra or '0'};\n"
            if kind == "ADD_CLASS":
                return _cpp_class(name, body)
            if kind == "FILE":
                return ("// " + language + ": " + str(extra or name)
                        + "\n#include " + inc + "\n" + (body or "") + "\n"
                        "int main(int argc, char** argv) {\n    return 0;\n}\n")
        return (f"// {language} {kind} {name}\n" + (body or "") + "\n")

    @staticmethod
    def function_openers(language: str) -> str:
        return {"lua": r"(?:local\s+)?function\s+{name}\s*\(",
                "javascript": r"(?:function\s+{name}|const\s+{name}\s*=\s*\([^)]*\)\s*=>|{name}\s*\()"
                , "c": r"\b\w[\w\s\*&:<>]*\b{name}\s*\(",
                "cpp": r"\b\w[\w\s\*&:<>]*\b{name}\s*\("}.get(language, "")

def _indent(text: str, pad: str) -> str:
    return "\n".join(pad + ln if ln.strip() else ln
                     for ln in str(text).splitlines()) or (pad + text)

def _HTML_DOC(title: str, body: str) -> str:
    return ("<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
            f"<title>{title}</title>\n<style>\n"
            "  body { margin: 0; font-family: sans-serif; background: #111;\n"
            "         color: #eee; display: flex; flex-direction: column;\n"
            "         align-items: center; }\n  canvas { background: #000; }\n"
            "</style>\n</head>\n<body>\n"
            + (body or "<canvas id=\"stage\" width=\"480\" height=\"320\">"
               "</canvas>") + "\n"
            "<script>\n(function () {\n    'use strict';\n    "
            + "var stage = document.getElementById('stage');\n    "
            "var ctx = stage && stage.getContext ? "
            "stage.getContext('2d') : null;\n    "
            "function frame() { if (ctx) { ctx.clearRect(0, 0, 480, 320); } "
            "requestAnimationFrame(frame); }\n    "
            "if (typeof requestAnimationFrame === 'function') "
            "{ requestAnimationFrame(frame); }\n})();\n</script>\n"
            "</body>\n</html>\n")

def _cpp_class(name: str, body: str) -> str:
    return (f"class {name} {{\npublic:\n"
            "    void push(int v) { items.push_back(v); }\n"
            "    int pop() { int v = items.back(); items.pop_back(); "
            "return v; }\n"
            "    bool empty() const { return items.empty(); }\n"
            "private:\n    std::vector<int> items;\n};\n"
            + (("\n" + body) if body else ""))