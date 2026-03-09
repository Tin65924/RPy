"""
transpiler/generator.py — The core Luau code generator.

Architecture
------------
CodeEmitter   — tracks indentation, writes lines, returns the final string.
GeneratorContext — carries per-compilation state (scope depth, flags, runtime
                   usage tracking, import info).
LuauGenerator — ast.NodeVisitor subclass; the visit_* methods emit Luau.

Public API
----------
    result = generate(transform_result, flags)
    # result.code  → str (Luau source)
    # result.runtime_helpers  → set[str] (helpers used)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional

from transpiler.errors import UnsupportedFeatureError, InternalError
from transpiler.ast_utils import (
    get_line, node_name,
    is_range_call, unpack_range_args,
    needs_bool_shim, fold_constant_binop,
)
from transpiler.transformer import TransformResult, ScopeMap, ImportInfo
from transpiler.type_inferrer import TypeMap, infer_types
from transpiler.node_registry import get_statement_handler, get_expression_handler
from transpiler.runtime_snippets import get_used_snippets

# ---------------------------------------------------------------------------
# Compiler flags (mirrors CLI flags)
# ---------------------------------------------------------------------------

from transpiler.flags import CompilerFlags

# ---------------------------------------------------------------------------
# CodeEmitter — indentation-aware line writer
# ---------------------------------------------------------------------------

class CodeEmitter:
    """
    Tracks indentation depth and accumulates Luau source lines.

    Usage:
        e = CodeEmitter()
        e.line("local x = 5")
        e.indent()
        e.line("print(x)")
        e.dedent()
        print(e.getvalue())
    """
    INDENT = "\t"

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._depth: int = 0

    def line(self, text: str) -> None:
        """Emit one line at the current indent level."""
        if text:
            self._lines.append(self.INDENT * self._depth + text)
        else:
            self._lines.append("")   # blank line

    def blank(self) -> None:
        self._lines.append("")

    def indent(self) -> None:
        self._depth += 1

    def dedent(self) -> None:
        self._depth = max(0, self._depth - 1)

    def getvalue(self) -> str:
        return "\n".join(self._lines)

# ---------------------------------------------------------------------------
# Per-compilation context
# ---------------------------------------------------------------------------

@dataclass
class GeneratorContext:
    emitter: CodeEmitter
    flags: CompilerFlags
    scope_map: ScopeMap
    import_info: ImportInfo
    filename: str | None = None
    type_map: TypeMap = field(default_factory=TypeMap)
    # Tracks names already declared *at this depth* so we know local vs bare
    _declared: dict[int, set[str]] = field(default_factory=dict)
    _scope_depth: int = 0
    # Runtime helpers used (drives selective require at file top)
    runtime_used: set[str] = field(default_factory=set)

    def use_runtime(self, name: str) -> str:
        """Mark a runtime helper as used and return its name."""
        self.runtime_used.add(name)
        return name

    @property
    def depth(self) -> int:
        return self._scope_depth

    def enter_scope(self) -> None:
        self._scope_depth += 1
        self._declared.setdefault(self._scope_depth, set())

    def exit_scope(self) -> None:
        self._declared.pop(self._scope_depth, None)
        self._scope_depth -= 1

    def declare(self, name: str) -> bool:
        """
        Declare *name* at current depth.
        Returns True if this is the first declaration (→ emit `local`).
        """
        bucket = self._declared.setdefault(self._scope_depth, set())
        if name in bucket:
            return False
        bucket.add(name)
        return True

    def is_declared(self, name: str) -> bool:
        return name in self._declared.get(self._scope_depth, set())

    # Stack tracking active loops and their break flag variable names (if any)
    _loop_break_flags: list[str] = field(default_factory=list)

    def push_loop(self, break_flag: str = "") -> None:
        self._loop_break_flags.append(break_flag)

    def pop_loop(self) -> None:
        self._loop_break_flags.pop()

    def get_current_break_flag(self) -> str:
        if self._loop_break_flags:
            return self._loop_break_flags[-1]
        return ""

# ---------------------------------------------------------------------------
# GenerateResult
# ---------------------------------------------------------------------------

@dataclass
class GenerateResult:
    code: str
    runtime_helpers: set[str]

# ---------------------------------------------------------------------------
# Operator maps
# ---------------------------------------------------------------------------

_BINOP_MAP = {
    ast.Add:      "+",
    ast.Sub:      "-",
    ast.Mult:     "*",
    ast.Div:      "/",
    ast.Mod:      "%",
    ast.Pow:      "^",
    ast.BitAnd:   "&",
    ast.BitOr:    "|",
    ast.BitXor:   "~",
    ast.LShift:   "<<",
    ast.RShift:   ">>",
    # FloorDiv and MatMult handled specially below
}

_UNARYOP_MAP = {
    ast.USub:   "-",
    ast.UAdd:   "+",
    ast.Not:    "not ",
    ast.Invert: "~",
}

_CMPOP_MAP = {
    ast.Eq:    "==",
    ast.NotEq: "~=",
    ast.Lt:    "<",
    ast.LtE:   "<=",
    ast.Gt:    ">",
    ast.GtE:   ">=",
}

# ---------------------------------------------------------------------------
# LuauGenerator — the visitor
# ---------------------------------------------------------------------------

class LuauGenerator(ast.NodeVisitor):
    """
    Walks a Python AST and emits Luau source code via the CodeEmitter.

    visit_* methods for STATEMENTS return None (they emit to ctx.emitter).
    expr()  method for EXPRESSIONS returns a Luau string.
    """

    def __init__(self, ctx: GeneratorContext) -> None:
        self.ctx = ctx
        self.e = ctx.emitter

    # -----------------------------------------------------------------------
    # Docstring helpers
    # -----------------------------------------------------------------------

    def _is_docstring(self, node: ast.AST) -> Optional[str]:
        """Check if a node is a docstring (standalone string constant)."""
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                return node.value.value
        return None

    def _emit_docstring(self, text: str) -> None:
        """Emit multiline docstring as Luau --[[ comments.]]"""
        trimmed = text.strip()
        if not trimmed:
            return
        
        if "\n" in trimmed:
            self.e.line("--[[")
            for line in text.splitlines():
                # Preserve the original structure but strip minimal shared indent
                self.e.line(f"    {line}")
            self.e.line("]]")
        else:
            self.e.line(f"-- {trimmed}")

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------

    def visit(self, node: ast.AST) -> None:
        """Custom visitor that prefers registry over methods."""
        # Inject source reference comment if enabled (Section 3)
        if self.ctx.flags.source_refs and isinstance(node, ast.stmt):
            line = getattr(node, "lineno", None)
            if line is not None:
                fname = self.ctx.filename or ""
                self.e.line(f"-- source: {fname}:{line}")

        # Registry (Phase 14 refactor)
        try:
            handler = get_statement_handler(node)
            handler(node, self.ctx)
            return
        except UnsupportedFeatureError:
            pass
        
        # Fallback to standard visit_* methods
        super().visit(node)

    def visit_Module(self, node: ast.Module) -> None:
        body = node.body
        
        # Handle module docstring
        if body and self._is_docstring(body[0]):
            self._emit_docstring(self._is_docstring(body[0])) # type: ignore
            body = body[1:]

        for stmt in body:
            self.visit(stmt)

        # Phase 14: Emit return table for ModuleScripts
        if self.ctx.flags.script_type == "module":
            exports = sorted(list(self.ctx._declared.get(0, set())))
            self.e.blank()
            if exports:
                export_dict = ", ".join(f"{name} = {name}" for name in exports)
                self.e.line(f"return {{ {export_dict} }}")
            else:
                self.e.line("return {}")

    # -----------------------------------------------------------------------
    # Expressions — return Luau strings
    # -----------------------------------------------------------------------

    def expr(self, node: ast.expr) -> str:
        """Dispatch an expression node; always returns a string."""
        # Check registry first (Phase 14 refactor)
        try:
            handler = get_expression_handler(node)
            res = handler(node, self.ctx)
            return res if res is not None else ""
        except UnsupportedFeatureError:
            pass

        # Fallback to method-driven dispatch
        method = f"_expr_{type(node).__name__}"
        handler = getattr(self, method, None)
        if handler is None:
            raise UnsupportedFeatureError(
                node_name(node), line=get_line(node)
            )
        return handler(node)

    def _expr_Constant(self, node: ast.Constant) -> str:
        v = node.value
        if v is None:
            return "nil"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
            return f'"{escaped}"'
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, bytes):
            raise UnsupportedFeatureError("bytes literal", line=get_line(node))
        raise InternalError(f"Unknown Constant type: {type(v)}", line=get_line(node))

    # Python builtin → Luau name.  Values starting with "py_" are runtime
    # helpers that get registered via use_runtime() on first reference.
    _BUILTIN_REMAP = {
        "len":   "py_len",
        "str":   "py_str",
        "int":   "py_int",
        "float": "py_float",
        "bool":  "py_bool",
        "set":   "py_set_new",
        "print": "print",     # native in Luau, no runtime shim
        "sorted": "py_sorted",
        "enumerate": "py_enumerate",
        "zip": "py_zip",
        "reversed": "py_reversed",
        "abs": "math.abs",
        "min": "math.min",
        "max": "math.max",
        "type": "typeof",
    }

    def _expr_Name(self, node: ast.Name) -> str:
        mapped = self._BUILTIN_REMAP.get(node.id)
        if mapped is not None:
            if mapped.startswith("py_"):
                self.ctx.use_runtime(mapped)
            return mapped
        return node.id

    def _expr_BinOp(self, node: ast.BinOp) -> str:
        # Phase 12: constant folding — pre-evaluate numeric literals at compile time
        folded = fold_constant_binop(node)
        if folded is not None:
            # Emit the pre-computed value directly (avoids runtime arithmetic)
            if isinstance(folded, float) and folded.is_integer():
                return str(int(folded))
            return repr(folded)

        left = self.expr(node.left)
        right = self.expr(node.right)
        op_type = type(node.op)

        if op_type is ast.FloorDiv:
            return f"math.floor({left} / {right})"
        if op_type is ast.MatMult:
            raise UnsupportedFeatureError("@ (matrix multiply)", line=get_line(node))

        # String concatenation: Python `+` on strings → Luau `..`
        if op_type is ast.Add:
            if self._is_string_context(node.left) or self._is_string_context(node.right):
                return f"({left} .. {right})"
            return f"({left} + {right})"

        op = _BINOP_MAP.get(op_type)
        if op is None:
            raise UnsupportedFeatureError(node_name(node.op), line=get_line(node))
        return f"({left} {op} {right})"

    def _is_string_context(self, node: ast.expr) -> bool:
        """Heuristic: True if node is statically known to be a string."""
        return isinstance(node, ast.Constant) and isinstance(node.value, str)

    def _expr_UnaryOp(self, node: ast.UnaryOp) -> str:
        op = _UNARYOP_MAP.get(type(node.op))
        if op is None:
            raise UnsupportedFeatureError(node_name(node.op), line=get_line(node))
        operand = self.expr(node.operand)
        return f"({op}{operand})"

    def _expr_BoolOp(self, node: ast.BoolOp) -> str:
        op = "and" if isinstance(node.op, ast.And) else "or"
        parts = [self.expr(v) for v in node.values]
        return f" {op} ".join(parts)

    def _expr_Compare(self, node: ast.Compare) -> str:
        parts: list[str] = []
        left = self.expr(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.expr(comparator)
            op_type = type(op)
            if op_type in _CMPOP_MAP:
                parts.append(f"({left} {_CMPOP_MAP[op_type]} {right})")
            elif op_type is ast.In:
                helper = self.ctx.use_runtime("py_contains")
                parts.append(f"{helper}({right}, {left})")
            elif op_type is ast.NotIn:
                helper = self.ctx.use_runtime("py_contains")
                parts.append(f"(not {helper}({right}, {left}))")
            elif op_type is ast.Is:
                parts.append(f"({left} == {right})")
            elif op_type is ast.IsNot:
                parts.append(f"({left} ~= {right})")
            else:
                raise UnsupportedFeatureError(node_name(op), line=get_line(node))
            left = right
        return " and ".join(parts)

    def _expr_IfExp(self, node: ast.IfExp) -> str:
        cond = self._bool_expr(node.test)
        a = self.expr(node.body)
        b = self.expr(node.orelse)
        return f"({cond} and {a} or {b})"

    # -------------------------------------------------------------------
    # Data structure literals (Phase 5)
    # -------------------------------------------------------------------

    def _expr_List(self, node: ast.List) -> str:
        elts = [self.expr(e) for e in node.elts]
        return "{" + ", ".join(elts) + "}"

    def _expr_Tuple(self, node: ast.Tuple) -> str:
        # Tuples are represented as Lua tables (same as lists)
        elts = [self.expr(e) for e in node.elts]
        return "{" + ", ".join(elts) + "}"

    def _expr_Dict(self, node: ast.Dict) -> str:
        pairs: list[str] = []
        for key, value in zip(node.keys, node.values):
            if key is None:
                # {**other_dict} — dict unpacking
                raise UnsupportedFeatureError("dict unpacking (**)", line=get_line(node))
            k = self.expr(key)
            v = self.expr(value)
            # Luau dict syntax: [key] = value for computed keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                # String keys can use short field syntax if valid identifiers
                name = key.value
                if name.isidentifier():
                    pairs.append(f"{name} = {v}")
                else:
                    pairs.append(f"[{k}] = {v}")
            else:
                pairs.append(f"[{k}] = {v}")
        return "{" + ", ".join(pairs) + "}"

    # -------------------------------------------------------------------
    # Subscript / Slice (Phase 5)
    # -------------------------------------------------------------------

    def _expr_Subscript(self, node: ast.Subscript) -> str:
        obj = self.expr(node.value)
        slc = node.slice

        # Slice → py_slice(obj, start, stop, step)
        if isinstance(slc, ast.Slice):
            return self._emit_slice(obj, slc)

        # Simple index → obj[idx + 1]  (0→1 correction for numeric indices)
        idx = self.expr(slc)
        # Optimise when idx is a literal integer
        if isinstance(slc, ast.Constant):
            if isinstance(slc.value, int):
                return f"{obj}[{slc.value + 1}]"
            if isinstance(slc.value, str):
                return f"{obj}[{idx}]"
        
        # Negative index: Python supports arr[-1], Lua doesn't natively.
        # We use a runtime helper for safety.
        if isinstance(slc, ast.UnaryOp) and isinstance(slc.op, ast.USub):
            helper = self.ctx.use_runtime("py_index")
            return f"{helper}({obj}, {idx})"
            
        # Fallback: if we are sure it's a number, we do +1. 
        # For now, RPy assumes Subscript on list/tuple is numeric by default
        # but --typed mode might help. For a general fix, if the key is likely string, 
        # we omit +1.
        return f"{obj}[{idx} + 1]"

    def _emit_slice(self, obj: str, slc: ast.Slice) -> str:
        """Emit py_slice(obj, start, stop, step) for slice operations."""
        helper = self.ctx.use_runtime("py_slice")
        lower = self.expr(slc.lower) if slc.lower else "nil"
        upper = self.expr(slc.upper) if slc.upper else "nil"
        step = self.expr(slc.step) if slc.step else "nil"
        return f"{helper}({obj}, {lower}, {upper}, {step})"

    def _expr_Slice(self, node: ast.Slice) -> str:
        # Standalone Slice node (shouldn't appear outside Subscript, but safety)
        raise InternalError("Slice node outside of Subscript", line=get_line(node))

    # -------------------------------------------------------------------
    # Comprehensions (Phase 5)
    # -------------------------------------------------------------------

    def _expr_ListComp(self, node: ast.ListComp) -> str:
        """
        [expr for x in iter if cond]
        →  (function() local _r = {} for _, x in ipairs(iter) do
               if cond then table.insert(_r, expr) end  end  return _r  end)()
        """
        return self._emit_comprehension(node.elt, node.generators, is_dict=False)

    def _expr_DictComp(self, node: ast.DictComp) -> str:
        """
        {k: v for ...}
        →  (function() local _r = {} for ... do _r[k] = v end return _r end)()
        """
        return self._emit_dict_comprehension(node.key, node.value, node.generators)

    def _expr_Set(self, node: ast.Set) -> str:
        """{1, 2, 3} → py_set_new({1, 2, 3})"""
        helper = self.ctx.use_runtime("py_set_new")
        elts = ", ".join(self.expr(e) for e in node.elts)
        # Use a Lua table literal here; py_set_new will convert it to a set object
        return f"{helper}({{{elts}}})"

    def _emit_comprehension(self, elt: ast.expr, generators: list, is_dict: bool) -> str:
        """Generate an IIFE for a list comprehension."""
        parts: list[str] = ["(function()"]
        parts.append(" local _r = {}")
        for gen in generators:
            iterable = self.expr(gen.iter)
            if isinstance(gen.target, ast.Name):
                var = gen.target.id
                if is_range_call(gen.iter):
                    start, stop, step = unpack_range_args(gen.iter)
                    start_s = self.expr(start)
                    stop_s = self.expr(stop)
                    if isinstance(stop, ast.Constant) and isinstance(stop.value, int):
                        stop_luau = str(stop.value - 1)
                    else:
                        stop_luau = f"({stop_s} - 1)"
                    if step:
                        step_s = self.expr(step)
                        parts.append(f" for {var} = {start_s}, {stop_luau}, {step_s} do")
                    else:
                        parts.append(f" for {var} = {start_s}, {stop_luau} do")
                else:
                    helper = self.ctx.use_runtime("py_iter")
                    parts.append(f" for _, {var} in {helper}({iterable}) do")
            elif isinstance(gen.target, ast.Tuple) and len(gen.target.elts) == 2:
                k = gen.target.elts[0]
                v = gen.target.elts[1]
                k_s = k.id if isinstance(k, ast.Name) else "_k"
                v_s = v.id if isinstance(v, ast.Name) else "_v"
                parts.append(f" for {k_s}, {v_s} in pairs({iterable}) do")
            else:
                raise UnsupportedFeatureError(
                    "complex comprehension target", line=get_line(gen)
                )
            # Conditions (if clauses)
            for cond_node in gen.ifs:
                cond = self._bool_expr(cond_node)
                parts.append(f" if {cond} then")

        # Body
        val = self.expr(elt)
        parts.append(f" table.insert(_r, {val})")

        # Close ifs and fors (reverse order)
        for gen in reversed(generators):
            for _ in gen.ifs:
                parts.append(" end")
            parts.append(" end")
        parts.append(" return _r")
        parts.append(" end)()")
        return "".join(parts)

    def _emit_dict_comprehension(self, key: ast.expr, value: ast.expr, generators: list) -> str:
        """Generate an IIFE for a dict comprehension."""
        parts: list[str] = ["(function()"]
        parts.append(" local _r = {}")
        for gen in generators:
            iterable = self.expr(gen.iter)
            if isinstance(gen.target, ast.Name):
                var = gen.target.id
                if is_range_call(gen.iter):
                    start, stop, step = unpack_range_args(gen.iter)
                    start_s = self.expr(start)
                    stop_s = self.expr(stop)
                    if isinstance(stop, ast.Constant) and isinstance(stop.value, int):
                        stop_luau = str(stop.value - 1)
                    else:
                        stop_luau = f"({stop_s} - 1)"
                    if step:
                        step_s = self.expr(step)
                        parts.append(f" for {var} = {start_s}, {stop_luau}, {step_s} do")
                    else:
                        parts.append(f" for {var} = {start_s}, {stop_luau} do")
                else:
                    helper = self.ctx.use_runtime("py_iter")
                    parts.append(f" for _, {var} in {helper}({iterable}) do")
            elif isinstance(gen.target, ast.Tuple) and len(gen.target.elts) == 2:
                k_node = gen.target.elts[0]
                v_node = gen.target.elts[1]
                k_s = k_node.id if isinstance(k_node, ast.Name) else "_k"
                v_s = v_node.id if isinstance(v_node, ast.Name) else "_v"
                parts.append(f" for {k_s}, {v_s} in pairs({iterable}) do")
            else:
                raise UnsupportedFeatureError(
                    "complex comprehension target", line=get_line(gen)
                )
            for cond_node in gen.ifs:
                cond = self._bool_expr(cond_node)
                parts.append(f" if {cond} then")

        k = self.expr(key)
        v = self.expr(value)
        parts.append(f" _r[{k}] = {v}")

        for gen in reversed(generators):
            for _ in gen.ifs:
                parts.append(" end")
            parts.append(" end")
        parts.append(" return _r")
        parts.append(" end)()")
        return "".join(parts)

    # -------------------------------------------------------------------
    # Method call interception (Phase 5)
    # -------------------------------------------------------------------

    # Map of Python method names → runtime helper names
    _METHOD_REMAP = {
        # list methods
        "append":  "py_append",
        "pop":     "py_pop",
        "insert":  "py_insert",
        "remove":  "py_remove",
        "index":   "py_index_of",
        "sort":    "py_sort",
        "reverse": "py_reverse",
        "extend":  "py_extend",
        "copy":    "py_copy",
        "count":   "py_count",
        # dict methods
        "keys":    "py_keys",
        "values":  "py_values",
        "items":   "py_items",
        "get":     "py_get",
        "update":  "py_update",
        "setdefault": "py_setdefault",
        # string methods
        "split":   "py_split",
        "join":    "py_join",
        "strip":   "py_strip",
        "lstrip":  "py_lstrip",
        "rstrip":  "py_rstrip",
        # set methods
        "add":     "py_set_add",
        "discard": "py_set_discard",
        "clear":   "py_set_clear",
        "union":   "py_set_union",
        "intersection": "py_set_intersection",
        "difference": "py_set_difference",
        "upper":   "py_upper",
        "lower":   "py_lower",
        "replace": "py_replace",
        "find":    "py_find",
        "startswith": "py_startswith",
        "endswith": "py_endswith",
        "format":  "py_format",
    }

    def _expr_Call(self, node: ast.Call) -> str:
        # Intercept method calls: obj.method(args) → rt_helper(obj, args)
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in self._METHOD_REMAP:
                rt_name = self._METHOD_REMAP[method]
                helper = self.ctx.use_runtime(rt_name)
                obj = self.expr(node.func.value)
                args = [self.expr(a) for a in node.args]
                return f"{helper}({obj}, {', '.join(args)})" if args else f"{helper}({obj})"

        func = self.expr(node.func)
        args = [self.expr(a) for a in node.args]
        for kw in node.keywords:
            if kw.arg is None:
                raise UnsupportedFeatureError("**kwargs unpacking", line=get_line(node))
            args.append(self.expr(kw.value))
        return f"{func}({', '.join(args)})"

    def _expr_Attribute(self, node: ast.Attribute) -> str:
        obj = self.expr(node.value)
        return f"{obj}.{node.attr}"

    def _expr_Lambda(self, node: ast.Lambda) -> str:
        params = self._format_args(node.args)
        body = self.expr(node.body)
        return f"(function({params}) return {body} end)"

    def _expr_JoinedStr(self, node: ast.JoinedStr) -> str:
        """
        f"hello {name}, you are {age}" → ("hello " .. tostring(name) .. ", you are " .. tostring(age))
        """
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                escaped = value.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                parts.append(f'"{escaped}"')
            elif isinstance(value, ast.FormattedValue):
                # The inner expression, coerced to string via tostring()
                inner = self.expr(value.value)
                if value.format_spec is not None:
                    # Format specs like {x:.2f} — use string.format
                    helper = self.ctx.use_runtime("py_format")
                    fmt = self.expr(value.format_spec)
                    parts.append(f"{helper}({inner}, {fmt})")
                else:
                    helper = self.ctx.use_runtime("py_str")
                    parts.append(f"{helper}({inner})")
            else:
                parts.append(self.expr(value))
        if not parts:
            return '""'
        return "(" + " .. ".join(parts) + ")"

    def _expr_Starred(self, node: ast.Starred) -> str:
        return f"...{self.expr(node.value)}"

    # -----------------------------------------------------------------------
    # Bool-context wrapper  (respects --fast flag)
    # -----------------------------------------------------------------------

    def _bool_expr(self, node: ast.expr) -> str:
        """Return Luau expression suitable for a boolean context (if/while)."""
        if self.ctx.flags.fast or not needs_bool_shim(node):
            return self.expr(node)
        helper = self.ctx.use_runtime("py_bool")
        return f"{helper}({self.expr(node)})"

    # -----------------------------------------------------------------------
    # Statements — emit to emitter, return None
    # -----------------------------------------------------------------------

    def visit_Expr(self, node: ast.Expr) -> None:
        """Bare expression statement (e.g. a function call by itself)."""
        self.e.line(self.expr(node.value))

    def visit_Assign(self, node: ast.Assign) -> None:
        value = self.expr(node.value)
        for target in node.targets:
            self._emit_assignment(target, value, value_node=node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        target = self.expr(node.target)  # type: ignore[arg-type]
        value = self.expr(node.value)
        op_type = type(node.op)
        if op_type is ast.Add and self._is_string_context(node.value):
            self.e.line(f"{target} = {target} .. {value}")
            return
        if op_type is ast.FloorDiv:
            self.e.line(f"{target} = math.floor({target} / {value})")
            return
        op = _BINOP_MAP.get(op_type, "?")
        self.e.line(f"{target} = {target} {op} {value}")

    def _emit_assignment(self, target: ast.expr, value: str,
                         value_node: ast.expr | None = None) -> None:
        if isinstance(target, ast.Name):
            is_new = self.ctx.declare(target.id)
            if is_new:
                if self.ctx.flags.typed and value_node is not None:
                    t = self.ctx.type_map.get_var(target.id, self.ctx.depth)
                    if t != "any":
                        self.e.line(f"local {target.id}: {t} = {value}")
                    else:
                        self.e.line(f"local {target.id} = {value}")
                else:
                    self.e.line(f"local {target.id} = {value}")
            else:
                self.e.line(f"{target.id} = {value}")
        elif isinstance(target, ast.Attribute):
            obj = self.expr(target.value)  # type: ignore[arg-type]
            self.e.line(f"{obj}.{target.attr} = {value}")
        elif isinstance(target, ast.Subscript):
            obj = self.expr(target.value)  # type: ignore[arg-type]
            slc = target.slice
            if isinstance(slc, ast.Constant) and isinstance(slc.value, int):
                self.e.line(f"{obj}[{slc.value + 1}] = {value}")
            elif isinstance(slc, ast.UnaryOp) and isinstance(slc.op, ast.USub):
                # Negative index assignment
                idx = self.expr(slc)  # type: ignore[arg-type]
                self.e.line(f"{obj}[#({obj}) + 1 + {idx}] = {value}")
            else:
                idx = self.expr(slc)  # type: ignore[arg-type]
                self.e.line(f"{obj}[{idx} + 1] = {value}")
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Tuple unpacking:  a, b = expr  →  local a, b = table.unpack(...)
            names = []
            for elt in target.elts:
                if isinstance(elt, ast.Name):
                    is_new = self.ctx.declare(elt.id)
                    names.append(elt.id)
                    if is_new:
                        # We'll declare with local below
                        pass
            lhs = ", ".join(names)
            self.e.line(f"local {lhs} = table.unpack({value})")
        else:
            raise UnsupportedFeatureError(
                f"assignment target {node_name(target)}", line=get_line(target)
            )

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            name = self.expr(target)  # type: ignore[arg-type]
            self.e.line(f"{name} = nil")

    def visit_Pass(self, node: ast.Pass) -> None:
        self.e.line("-- pass")

    def visit_Break(self, node: ast.Break) -> None:
        flag = self.ctx.get_current_break_flag()
        if flag:
            self.e.line(f"{flag} = true")
        self.e.line("break")

    def visit_Continue(self, node: ast.Continue) -> None:
        self.e.line("continue")  # Luau supports continue natively

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            self.e.line("return")
        else:
            self.e.line(f"return {self.expr(node.value)}")

    def visit_Assert(self, node: ast.Assert) -> None:
        test = self._bool_expr(node.test)
        if node.msg:
            msg = self.expr(node.msg)
            self.e.line(f"assert({test}, {msg})")
        else:
            self.e.line(f"assert({test})")

    # -----------------------------------------------------------------------
    # If / elif / else
    # -----------------------------------------------------------------------

    def visit_If(self, node: ast.If) -> None:
        cond = self._bool_expr(node.test)
        self.e.line(f"if {cond} then")
        self.e.indent()
        for stmt in node.body:
            self.visit(stmt)
        self.e.dedent()
        self._emit_orelse(node.orelse)

    def _emit_orelse(self, orelse: list) -> None:
        if not orelse:
            self.e.line("end")
        elif len(orelse) == 1 and isinstance(orelse[0], ast.If):
            # elif branch
            sub = orelse[0]
            cond = self._bool_expr(sub.test)
            self.e.line(f"elseif {cond} then")
            self.e.indent()
            for stmt in sub.body:
                self.visit(stmt)
            self.e.dedent()
            self._emit_orelse(sub.orelse)
        else:
            self.e.line("else")
            self.e.indent()
            for stmt in orelse:
                self.visit(stmt)
            self.e.dedent()
            self.e.line("end")

    # -----------------------------------------------------------------------
    # While
    # -----------------------------------------------------------------------

    def visit_While(self, node: ast.While) -> None:
        cond = self._bool_expr(node.test)
        break_flag = f"_break_{self.ctx.depth}" if node.orelse else ""
        if break_flag:
            self.e.line(f"local {break_flag} = false")
        
        self.ctx.push_loop(break_flag)
        self.e.line(f"while {cond} do")
        self.e.indent()
        for stmt in node.body:
            self.visit(stmt)
        self.e.dedent()
        self.e.line("end")
        self.ctx.pop_loop()
        
        if node.orelse:
            self.e.line(f"if not {break_flag} then")
            self.e.indent()
            for stmt in node.orelse:
                self.visit(stmt)
            self.e.dedent()
            self.e.line("end")

    # -----------------------------------------------------------------------
    # For
    # -----------------------------------------------------------------------

    def visit_For(self, node: ast.For) -> None:
        target = node.target
        break_flag = f"_break_{self.ctx.depth}" if node.orelse else ""
        if break_flag:
            self.e.line(f"local {break_flag} = false")
            
        self.ctx.push_loop(break_flag)

        if is_range_call(node.iter):
            # Numeric for loop
            start, stop, step = unpack_range_args(node.iter)  # type: ignore[arg-type]
            start_s = self.expr(start)
            stop_s = self.expr(stop)

            # Luau numeric for is inclusive, Python range stop is exclusive.
            # Adjust: stop_s - 1 (simplified when stop is a literal int)
            if isinstance(stop, ast.Constant) and isinstance(stop.value, int):
                stop_luau = str(stop.value - 1)
            else:
                stop_luau = f"({stop_s} - 1)"

            var = target.id if isinstance(target, ast.Name) else "_i"
            self.ctx.declare(var)

            if step is not None:
                step_s = self.expr(step)
                self.e.line(f"for {var} = {start_s}, {stop_luau}, {step_s} do")
            else:
                self.e.line(f"for {var} = {start_s}, {stop_luau} do")
        else:
            # Generic for — use ipairs for list iteration
            # `for x in iterable` → `for _, x in ipairs(iterable) do`
            iterable = self.expr(node.iter)

            if isinstance(target, ast.Tuple) and len(target.elts) == 2:
                # `for k, v in dict.items()` → `for k, v in pairs(dict) do`
                # (handled as a special case — dict.items() returns pairs-able)
                k = target.elts[0]
                v = target.elts[1]
                k_s = k.id if isinstance(k, ast.Name) else "_k"
                v_s = v.id if isinstance(v, ast.Name) else "_v"
                self.ctx.declare(k_s)
                self.ctx.declare(v_s)
                self.e.line(f"for {k_s}, {v_s} in pairs({iterable}) do")
            elif isinstance(target, ast.Name):
                var = target.id
                self.ctx.declare(var)
                helper = self.ctx.use_runtime("py_iter")
                self.e.line(f"for _, {var} in {helper}({iterable}) do")
            else:
                raise UnsupportedFeatureError(
                    "complex for-loop target", line=get_line(node)
                )

        self.e.indent()
        self.ctx.enter_scope()
        for stmt in node.body:
            self.visit(stmt)
        self.ctx.exit_scope()
        self.e.dedent()
        self.e.line("end")
        self.ctx.pop_loop()

        if node.orelse:
            self.e.line(f"if not {break_flag} then")
            self.e.indent()
            for stmt in node.orelse:
                self.visit(stmt)
            self.e.dedent()
            self.e.line("end")

    # -----------------------------------------------------------------------
    # Functions
    # -----------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = node.name
        body = node.body

        # Handle function docstring (Emit BEFORE the header)
        if body and self._is_docstring(body[0]):
            self._emit_docstring(self._is_docstring(body[0])) # type: ignore
            body = body[1:]

        is_new = self.ctx.declare(name)
        prefix = "local function" if is_new else "function"

        if self.ctx.flags.typed:
            params = self._format_args_typed(node.args)
            ret_type = self.ctx.type_map.get_return(name)
            if ret_type != "any":
                self.e.line(f"{prefix} {name}({params}): {ret_type}")
            else:
                self.e.line(f"{prefix} {name}({params})")
        else:
            params = self._format_args(node.args)
            self.e.line(f"{prefix} {name}({params})")

        self.e.indent()
        self.ctx.enter_scope()
        for arg in node.args.args:
            self.ctx.declare(arg.arg)
        if node.args.vararg:
            self.ctx.declare(node.args.vararg.arg)
        for stmt in body:
            self.visit(stmt)
        self.ctx.exit_scope()
        self.e.dedent()
        self.e.line("end")
        self.e.blank()

    visit_AsyncFunctionDef = lambda self, node: (_ for _ in ()).throw(  # type: ignore[assignment]
        UnsupportedFeatureError("async/await", line=get_line(node))
    )

    def _format_args(self, args: ast.arguments) -> str:
        params: list[str] = [a.arg for a in args.args]
        if args.vararg:
            params.append("...")
        return ", ".join(params)

    def _format_args_typed(self, args: ast.arguments) -> str:
        """Format function args with type annotations when in --typed mode."""
        params: list[str] = []
        for a in args.args:
            t = self.ctx.type_map.get_var(a.arg, self.ctx.depth + 1)
            if t != "any":
                params.append(f"{a.arg}: {t}")
            else:
                params.append(a.arg)
        if args.vararg:
            params.append("...")
        return ", ".join(params)

    # -----------------------------------------------------------------------
    # Imports (resolved by transformer; we emit require() here if needed)
    # -----------------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        # Transformer would have raised already; this is a safety net
        raise UnsupportedFeatureError("import", line=get_line(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        level = node.level

        if level == 0 and module == "roblox":
            # SDK passthrough — no Luau code needed
            return

        if level >= 1:
            # Relative import → require()
            for alias in node.names:
                local_name = alias.asname or alias.name
                req_path = self.ctx.import_info.relative_reqs.get(local_name, local_name)
                is_new = self.ctx.declare(local_name)
                kw = "local " if is_new else ""
                self.e.line(f"{kw}{local_name} = require({req_path})")
            return

        raise UnsupportedFeatureError(
            f"from {module} import ...", line=get_line(node)
        )

    # -----------------------------------------------------------------------
    # Classes (Phase 6) — metatable OOP pattern
    # -----------------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = node.name
        body = node.body

        # Handle class docstring (Emit BEFORE the header)
        if body and self._is_docstring(body[0]):
            self._emit_docstring(self._is_docstring(body[0])) # type: ignore
            body = body[1:]

        self.ctx.declare(name)

        # Decorators — raise
        if node.decorator_list:
            raise UnsupportedFeatureError("decorator", line=get_line(node))

        # Inheritance: single base only
        if len(node.bases) > 1:
            raise UnsupportedFeatureError("multiple inheritance", line=get_line(node))

        if node.bases:
            base = self.expr(node.bases[0])
            self.e.line(f"local {name} = setmetatable({{}}, {{__index = {base}}})")
        else:
            self.e.line(f"local {name} = {{}}")
        self.e.line(f"{name}.__index = {name}")
        self.e.blank()

        self.ctx.enter_scope()
        self.ctx.declare(name)  # class name inside its own scope

        for stmt in body:
            if isinstance(stmt, ast.FunctionDef):
                self._emit_method(name, stmt)
            elif isinstance(stmt, ast.Assign):
                # Class-level attributes: Foo.x = value
                value = self.expr(stmt.value)
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        self.e.line(f"{name}.{target.id} = {value}")
            elif isinstance(stmt, ast.Pass):
                self.e.line("-- pass")
            else:
                self.visit(stmt)

        self.ctx.exit_scope()
        self.e.blank()

    def _emit_method(self, class_name: str, node: ast.FunctionDef) -> None:
        """Emit a method definition for a class."""
        method = node.name
        args = node.args.args
        body = node.body

        # Handle method/constructor docstring (Emit BEFORE the header)
        if body and self._is_docstring(body[0]):
            doc = self._is_docstring(body[0])
            if doc:
                self._emit_docstring(doc)
            body = body[1:]

        if method == "__init__":
            # __init__ → ClassName.new(args)
            params = [a.arg for a in args[1:]] if len(args) > 1 else []
            if node.args.vararg:
                params.append("...")
            self.e.line(f"function {class_name}.new({', '.join(params)})")
            self.e.indent()
            self.e.line(f"local self = setmetatable({{}}, {class_name})")
            self.ctx.enter_scope()
            self.ctx.declare("self")
            for a in args[1:]:
                self.ctx.declare(a.arg)
            for stmt in body:
                self.visit(stmt)
            # If no explicit return, add return self
            if not body or not isinstance(body[-1], ast.Return):
                self.e.line("return self")
            self.ctx.exit_scope()
            self.e.dedent()
            self.e.line("end")
            self.e.blank()
        else:
            # Regular method → Class:method(args)
            params = [a.arg for a in args[1:]] if len(args) > 1 else []
            if node.args.vararg:
                params.append("...")
            self.e.line(f"function {class_name}:{method}({', '.join(params)})")
            self.e.indent()
            self.ctx.enter_scope()
            self.ctx.declare("self")
            for a in args[1:]:
                self.ctx.declare(a.arg)
            for stmt in body:
                self.visit(stmt)
            self.ctx.exit_scope()
            self.e.dedent()
            self.e.line("end")
            self.e.blank()

    # -----------------------------------------------------------------------
    # Try / Except / Raise (Phase 6) — pcall wrapper
    # -----------------------------------------------------------------------

    def visit_Try(self, node: ast.Try) -> None:
        """
        try:
            risky()
        except ValueError as e:
            handle(e)
        finally:
            cleanup()
        →
        local _ok, _err = pcall(function()
            risky()
        end)
        if not _ok then
            local e = _err
            handle(e)
        end
        cleanup()
        """
        # Wrap the try body in pcall
        self.e.line("local _ok, _err = pcall(function()")
        self.e.indent()
        for stmt in node.body:
            self.visit(stmt)
        self.e.dedent()
        self.e.line("end)")

        # Except handlers
        if node.handlers:
            for i, handler in enumerate(node.handlers):
                keyword = "if" if i == 0 else "elseif"
                if handler.type is None:
                    # bare except:
                    self.e.line(f"{keyword} not _ok then")
                else:
                    # except SomeError as e: → if not _ok then
                    # (In Phase 6 we don't do type-based dispatch; all
                    #  exceptions are strings.  We catch everything.)
                    self.e.line(f"{keyword} not _ok then")

                self.e.indent()
                if handler.name:
                    self.ctx.declare(handler.name)
                    self.e.line(f"local {handler.name} = _err")
                for stmt in handler.body:
                    self.visit(stmt)
                self.e.dedent()
            self.e.line("end")

        # Else clause (runs when no exception)
        if node.orelse:
            self.e.line("if _ok then")
            self.e.indent()
            for stmt in node.orelse:
                self.visit(stmt)
            self.e.dedent()
            self.e.line("end")

        # Finally clause (always runs)
        if node.finalbody:
            for stmt in node.finalbody:
                self.visit(stmt)

    def visit_Raise(self, node: ast.Raise) -> None:
        """
        raise ValueError("bad")  →  error("bad")
        raise                    →  error(_err)
        """
        if node.exc is None:
            # bare raise — re-raise the current exception
            self.e.line("error(_err)")
        elif isinstance(node.exc, ast.Call):
            # raise SomeError("msg") → error("msg")
            args = [self.expr(a) for a in node.exc.args]
            if args:
                self.e.line(f"error({', '.join(args)})")
            else:
                exc_name = self.expr(node.exc.func)
                self.e.line(f'error("{exc_name}")')
        else:
            val = self.expr(node.exc)
            self.e.line(f"error({val})")

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Handled by visit_Try; this should not be called directly
        pass

    # -----------------------------------------------------------------------
    # With statement (Phase 6) — body-only, no __enter__/__exit__ protocol
    # -----------------------------------------------------------------------

    def visit_With(self, node: ast.With) -> None:
        """
        with open(f) as h:
            use(h)
        →
        do
            local h = open(f)
            use(h)
        end
        """
        self.e.line("do")
        self.e.indent()
        for item in node.items:
            ctx_expr = self.expr(item.context_expr)
            if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                var = item.optional_vars.id
                self.ctx.declare(var)
                self.e.line(f"local {var} = {ctx_expr}")
            else:
                self.e.line(ctx_expr)
        for stmt in node.body:
            self.visit(stmt)
        self.e.dedent()
        self.e.line("end")

    # -----------------------------------------------------------------------
    # Unsupported stubs (raise cleanly)
    # -----------------------------------------------------------------------

    def visit_Global(self, node: ast.Global) -> None:
        raise UnsupportedFeatureError("global", line=get_line(node))

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise UnsupportedFeatureError("nonlocal", line=get_line(node))

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        raise UnsupportedFeatureError("async for", line=get_line(node))

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        raise UnsupportedFeatureError("async with", line=get_line(node))

    # -----------------------------------------------------------------------
    # Fallback
    # -----------------------------------------------------------------------

    def generic_visit(self, node: ast.AST) -> None:
        raise UnsupportedFeatureError(node_name(node), line=get_line(node))


# ---------------------------------------------------------------------------
# Runtime header builder
# ---------------------------------------------------------------------------

_RUNTIME_REQUIRE_LINE = 'local _RT = require(script.Parent.python_runtime)'

def _build_header(flags: CompilerFlags, runtime_used: set[str]) -> list[str]:
    lines = ["-- Generated by RPy — do not edit manually"]
    if not flags.no_runtime and runtime_used:
        if flags.shared_runtime:
            lines.append(_RUNTIME_REQUIRE_LINE)
            # Localise each used helper for performance
            for name in sorted(runtime_used):
                lines.append(f"local {name} = _RT.{name}")
        else:
            # Tree-shaking: Inject used snippets directly
            snippets = get_used_snippets(runtime_used)
            if snippets:
                lines.append(snippets)
                
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(result: TransformResult, flags: CompilerFlags | None = None) -> GenerateResult:
    """
    Generate Luau source code from a TransformResult.

    Args:
        result: output of transpiler.transformer.transform()
        flags:  compiler flags (defaults to all-false/default)

    Returns:
        GenerateResult with .code (str) and .runtime_helpers (set[str])
    """
    if flags is None:
        flags = CompilerFlags()

    # Run type inference if --typed mode
    type_map = TypeMap()
    if flags.typed:
        type_map = infer_types(result.tree)

    emitter = CodeEmitter()
    ctx = GeneratorContext(
        emitter=emitter,
        flags=flags,
        scope_map=result.scope_map,
        import_info=result.import_info,
        filename=result.filename,
        type_map=type_map,
    )
    gen = LuauGenerator(ctx)
    gen.visit(result.tree)

    body = emitter.getvalue()
    header_lines = _build_header(flags, ctx.runtime_used)
    full_code = "\n".join(header_lines) + body

    return GenerateResult(code=full_code, runtime_helpers=ctx.runtime_used)
