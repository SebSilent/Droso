
from __future__ import annotations

import ast
import io
import json
import keyword
import re
import sqlite3
import textwrap
from pathlib import Path

import numpy as np

DEFAULT_DB = Path("C:/Projects/HybridLLM/exocortex/snippet_vault.db")
MUTATIONS = ("REPLACE_NAME", "REPLACE_RETURN", "ADD_IMPORT", "WRAP_TRY_EXCEPT",
             "INJECT_ARGUMENT", "REPLACE_CONST")
_WORD = re.compile(r"[a-z][a-z0-9_]{1,30}")

class CodeAssembler:
    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = str(db_path)
        self._ids: list[str] = []
        self._code: dict[str, str] = {}
        self._lang: dict[str, str] = {}
        self._points: dict[str, list] = {}
        self._mat: np.ndarray | None = None
        self._lex: np.ndarray | None = None
        self.calls = 0

    def _load(self) -> None:
        if self._mat is not None or not Path(self.db_path).exists():
            return
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        cols = [r[1] for r in con.execute("PRAGMA table_info(snippets)")]
        has_lex = "lexvec" in cols
        rows = con.execute("SELECT id, language, code, embedding, points"
                           + (", lexvec" if has_lex else "")
                           + " FROM snippets").fetchall()
        con.close()
        mats, lexes = [], []
        for row in rows:
            sid, lang, code, blob, pts = row[:5]
            self._ids.append(sid)
            self._lang[sid], self._code[sid] = lang, code
            self._points[sid] = json.loads(pts)
            mats.append(np.load(io.BytesIO(blob), allow_pickle=False))
            if has_lex:
                lexes.append(np.load(io.BytesIO(row[5]), allow_pickle=False))
        self._mat = (np.stack(mats).astype(np.float32) if mats
                     else np.zeros((0, 1), np.float32))
        self._lex = (np.stack(lexes).astype(np.float32) if has_lex and lexes
                     else None)
        self._words = {}
        for sid, code in self._code.items():
            toks = set()
            for w in _WORD.findall(code.lower()):
                toks.update(p for p in w.split("_") if len(p) > 1)
            self._words[sid] = toks

    def stats(self) -> dict:
        self._load()
        return {"snippets": len(self._ids), "languages": sorted(set(self._lang.values())),
                "mutation_types": list(MUTATIONS), "db": Path(self.db_path).name}

    def retrieve_base_snippet(self, intent_vector, k: int = 3,
                              text: str | None = None) -> list[dict]:
        self._load()
        self.calls += 1
        if self._mat.shape[0] == 0:
            return []
        v = np.asarray(intent_vector, dtype=np.float32).ravel()[: self._mat.shape[1]]
        if v.shape[0] < self._mat.shape[1]:
            v = np.pad(v, (0, self._mat.shape[1] - v.shape[0]))
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = self._mat @ v
        if self._lex is not None:
            sims = 0.3 * sims + 0.7 * (self._lex @ v)
        if text:
            q = set()
            for w in _WORD.findall(str(text).lower()):
                q.update(p for p in w.split("_") if len(p) > 1)
            ov = np.array([len(q & self._words[s]) / (len(q | self._words[s]) + 1e-9)
                           for s in self._ids], dtype=np.float32)
            sims = 0.4 * sims + 0.6 * ov
        order = np.argsort(-sims)[:k]
        return [{"id": self._ids[i], "language": self._lang[self._ids[i]],
                 "code": self._code[self._ids[i]], "score": round(float(sims[i]), 3),
                 "points": self._points[self._ids[i]]} for i in order]

    @staticmethod
    def syntax_check(code: str, language: str = "python") -> bool:
        if language == "python":
            try:
                if "\x00" in code:
                    return False
                compile(code, "<assembled>", "exec")
                return True
            except (SyntaxError, ValueError):
                return False
        return bool(code.strip())

    @staticmethod
    def ast_to_code(tree: ast.AST) -> str:
        return ast.unparse(ast.fix_missing_locations(tree)) + "\n"

    def mutate_ast(self, code: str, mutation_type: str, target_value: str = "",
                   language: str = "python", idx: int = 0) -> dict:
        self.calls += 1
        if language != "python":
            return {"ok": False, "error": f"no AST mutator for {language}"}
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {"ok": False, "error": f"input not parseable: {exc}"}
        try:
            applied = getattr(self, "_" + mutation_type.lower())(tree, target_value, idx)
        except AttributeError:
            return {"ok": False, "error": f"unknown mutation {mutation_type}"}
        if not applied:
            return {"ok": False, "error": f"{mutation_type}: nothing matched "
                                          f"{target_value!r}"}
        out = self.ast_to_code(tree)
        if not self.syntax_check(out):
            return {"ok": False, "error": "internal: unparsed code failed syntax check"}
        return {"ok": True, "code": out, "applied": mutation_type,
                "target": target_value}

    def _replace_name(self, tree, value, idx=0):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_]\w*", value or ""):
            return False
        old = next((n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
        if old is None or old == value:
            return False
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == old:
                n.name = value
            elif isinstance(n, ast.Name) and n.id == old:
                n.id = value
            elif isinstance(n, ast.arg) and n.arg == old:
                n.arg = value
            elif isinstance(n, ast.keyword) and n.arg == old:
                n.arg = value
        return True

    def _replace_return(self, tree, value, idx=0):
        rets = [n for n in ast.walk(tree) if isinstance(n, ast.Return)
                and n.value is not None]
        node = rets[idx] if len(rets) > idx else (rets[0] if rets else None)
        if node is None or not value.strip():
            return False
        try:
            node.value = ast.parse(value, mode="eval").body
        except SyntaxError:
            return False
        return True

    def _replace_const(self, tree, value, idx=0):
        value = value.strip()
        if not value:
            return False
        try:
            new = ast.parse(value, mode="eval").body
        except SyntaxError:
            new = ast.Constant(value=value.strip("'\""))
        want = type(new.value) if isinstance(new, ast.Constant) else str
        consts = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and type(n.value) is want
                  and n.value != new.value]
        if len(consts) <= idx:
            return False
        consts[idx].value = new.value
        return True

    def _add_import(self, tree, value, idx=0):
        mod = (value or "os").strip().split()[0]
        if keyword.iskeyword(mod):
            return False
        have = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names}
        have |= {n.module.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom) and n.module}
        if mod in have or not re.fullmatch(r"[A-Za-z_][\w.]*", mod):
            return False
        tree.body.insert(0, ast.Import(names=[ast.alias(name=mod, asname=None)]))
        return True

    def _wrap_try_except(self, tree, value, idx=0):
        value = (value or "").strip()
        if value:
            fn = next((n for n in ast.walk(tree) if isinstance(
                n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == value), None)
            if fn is not None:
                handler = ast.ExceptHandler(
                    type=ast.Name(id="Exception", ctx=ast.Load()),
                    name=None, body=[ast.Return(value=None)])
                fn.body = [ast.Try(body=list(fn.body), handlers=[handler],
                                   orelse=[], finalbody=[])]
                return True
        target = next((n for n in reversed(tree.body)
                       if isinstance(n, (ast.Expr, ast.Assign))), None)
        if target is None:
            return False
        handler = ast.ExceptHandler(type=ast.Name(id="Exception", ctx=ast.Load()),
                                    name=None,
                                    body=[ast.Expr(ast.Call(
                                        func=ast.Name(id="print", ctx=ast.Load()),
                                        args=[ast.Constant(value="handled")],
                                        keywords=[]))])
        idx = tree.body.index(target)
        tree.body[idx:idx + 1] = [ast.Try(body=[target], handlers=[handler],
                                          orelse=[], finalbody=[])]
        return True

    def _inject_argument(self, tree, value, idx=0):
        name = (value or "").strip()
        fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
        if fn is None or not re.fullmatch(r"[A-Za-z_]\w*", name or ""):
            return False
        if name not in [a.arg for a in fn.args.args]:
            fn.args.args.append(ast.arg(arg=name, annotation=None))
        return True

    def _reparse(self, tree) -> dict:
        out = self.ast_to_code(tree)
        if not self.syntax_check(out):
            return {"ok": False, "error": "built code failed syntax check"}
        return {"ok": True, "code": out}

    def add_variable(self, code: str, name: str, value: str,
                     language: str = "python") -> dict:
        if language != "python":
            return {"ok": False, "error": "builder ops are python-only"}
        try:
            tree = ast.parse(code)
            val = ast.parse(value, mode="eval").body
        except (SyntaxError, ValueError) as exc:
            return {"ok": False, "error": f"unparseable: {exc}"}
        i = 0
        for n in tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                i = tree.body.index(n) + 1
        stmt = ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())],
                          value=val, lineno=1, col_offset=0)
        tree.body.insert(i, stmt)
        ast.fix_missing_locations(tree)
        return self._reparse(tree)

    def add_function(self, code: str, definition: str,
                     language: str = "python") -> dict:
        if language != "python":
            return {"ok": False, "error": "builder ops are python-only"}
        try:
            tree = ast.parse(code)
            fn = ast.parse(definition.strip()).body[0]
        except (SyntaxError, ValueError, IndexError) as exc:
            return {"ok": False, "error": f"unparseable definition: {exc}"}
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            return {"ok": False, "error": "definition is not a function/class"}
        tree.body.append(fn)
        ast.fix_missing_locations(tree)
        return self._reparse(tree)

    def modify_function(self, code: str, name: str, body: str,
                        language: str = "python") -> dict:
        """Replace the BODY of function `name` with parsed statements."""
        if language != "python":
            return {"ok": False, "error": "builder ops are python-only"}
        try:
            tree = ast.parse(code)
            stmts = ast.parse(textwrap.dedent(body)).body
        except (SyntaxError, ValueError) as exc:
            return {"ok": False, "error": f"unparseable body: {exc}"}
        if not stmts:
            return {"ok": False, "error": "empty body"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == name:
                node.body = stmts
                ast.fix_missing_locations(tree)
                return self._reparse(tree)
        return {"ok": False, "error": f"function {name!r} not found"}

    def add_condition(self, code: str, function: str, test: str,
                      body: str, language: str = "python") -> dict:
        """Guard `function` with a leading `if test:` block."""
        if language != "python":
            return {"ok": False, "error": "builder ops are python-only"}
        try:
            tree = ast.parse(code)
            t = ast.parse(test, mode="eval").body
            stmts = ast.parse(textwrap.dedent(body)).body
        except (SyntaxError, ValueError) as exc:
            return {"ok": False, "error": f"unparseable: {exc}"}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function:
                node.body.insert(0, ast.If(test=t, body=stmts, orelse=[]))
                ast.fix_missing_locations(tree)
                return self._reparse(tree)
        return {"ok": False, "error": f"function {function!r} not found"}

    @staticmethod
    def candidates_from_task(text: str) -> list[tuple[str, str]]:
        t = str(text)
        out: list[tuple[str, str]] = []
        for s in re.findall(r"'([^']+)'|\"([^\"]+)\"", t):
            val = s[0] or s[1]
            out.append(("REPLACE_CONST", repr(val)))
        for fn in re.findall(r"function\s+([a-z_][a-z0-9_]*)", t, re.I):
            out.append(("REPLACE_NAME", fn))
        for tri in re.findall(r"\b([a-z])\s*([*+/\-])\s*([a-z])\b", t):
            out.append(("REPLACE_RETURN", " ".join(tri)))
        for m in re.findall(r"\brange\s*\(?(\d+)", t, re.I) + \
                 re.findall(r"(\d+)\s+times", t, re.I):
            out.append(("REPLACE_CONST", m))
        for mod in re.findall(r"\b(os|sys|json|math|time|re|random|pathlib"
                              r"|subprocess|collections|itertools|datetime)\b", t):
            out.append(("ADD_IMPORT", mod))
        if re.search(r"try/except|try/except block|wrap", t, re.I):
            out.append(("WRAP_TRY_EXCEPT", ""))
        return list(dict.fromkeys(out))