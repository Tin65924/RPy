"""
transpiler/transformer.py — Pre-codegen normalization passes over the AST.

Passes (run in order by transform()):
  0. MatchLowerer    — transforms Python 3.10 `match` statements into `if/elseif`
                        chains before other passes (Basic literal/OR/wildcard).
  1. ScopeAnalyzer  — builds a ScopeMap: Name → first-write depth, so the
                        generator knows when to emit `local`.
  2. ImportResolver — resolves import statements; marks SDK imports as
                        passthroughs, relative imports as require(), rejects
                        all others.
  3. AnnotationStripper — removes AnnAssign annotation fields (Luau handles
                            types separately; --typed mode re-derives them).

None of these passes modify the AST in place — they attach metadata or return
a modified tree.  The generator reads that metadata when emitting code.
"""

from __future__ import annotations

import ast
import os
import sys
import subprocess
import json
from dataclasses import dataclass, field
from typing import Optional, Any

from transpiler.errors import UnsupportedFeatureError
from transpiler.flags import CompilerFlags
from transpiler.ast_utils import get_line

# ---------------------------------------------------------------------------
# SDK names recognised as Luau globals (no require() emitted)
# ---------------------------------------------------------------------------

_SDK_GLOBALS: frozenset[str] = frozenset({
    "Instance", "game", "workspace",
    "Vector3", "CFrame",
    "Players", "RunService", "TweenService",
    "Color3", "UDim2", "Enum",
})


# ---------------------------------------------------------------------------
# ScopeMap — output of the scope analysis pass
# ---------------------------------------------------------------------------

@dataclass
class ScopeMap:
    """
    Records which names are *first assigned* at each function-depth level.

    depth=0 → module scope (top of file)
    depth=1 → inside a function or class
    depth=2 → nested function, etc.

    The generator uses this to decide:
      - First time a name is written at a given depth → emit `local x = …`
      - Subsequent writes at same depth              → emit `x = …`
    """
    # {depth: {name}} — names declared (first-assigned) at that depth
    declarations: dict[int, set[str]] = field(default_factory=dict)

    def declare(self, name: str, depth: int) -> None:
        self.declarations.setdefault(depth, set()).add(name)

    def is_declared(self, name: str, depth: int) -> bool:
        return name in self.declarations.get(depth, set())


# ---------------------------------------------------------------------------
# ImportInfo — output of the import resolution pass
# ---------------------------------------------------------------------------

@dataclass
class ImportInfo:
    """
    Metadata about each import statement encountered.

    sdk_names:      Names imported from `roblox` (Luau globals, no require).
    relative_reqs:  {alias: luau_require_path} for `from . import X` imports.
    """
    sdk_names: set[str] = field(default_factory=set)
    relative_reqs: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TransformResult — what transform() returns
# ---------------------------------------------------------------------------

@dataclass
class TransformResult:
    """Aggregated output of all transformer passes."""
    tree: ast.Module
    scope_map: ScopeMap
    import_info: ImportInfo
    filename: str | None = None


# ---------------------------------------------------------------------------
# Pass 0.1: Compile-Time Evaluator
# ---------------------------------------------------------------------------

class _CompileTimeEvaluator(ast.NodeTransformer):
    """
    Evaluates function calls decorated with @compile_time in a subprocess.
    Replaces the call site with the literal result (JSON-serializable).
    """
    def __init__(self, filename: str | None, enabled: bool):
        self.filename = filename
        self.enabled = enabled
        self.compile_time_funcs: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        is_compile_time = any(
            (isinstance(dec, ast.Name) and dec.id == "compile_time") or
            (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "compile_time")
            for dec in node.decorator_list
        )
        if is_compile_time:
            self.compile_time_funcs.add(node.name)
        return self.generic_visit(node) # type: ignore

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name) and node.func.id in self.compile_time_funcs:
            if not self.enabled:
                # We show a warning if @compile_time is found but --compile-time flag is missing
                # (unless it's a decorator definition itself, but we check call sites here)
                print(f"\n⚠ Warning: Compile-time directive detected for '{node.func.id}' but execution is disabled.")
                print("  Run with --compile-time to enable build-time Python execution.\n")
                return node
            
            # Execute worker
            return self._evaluate_call(node.func.id, node.args)
        return self.generic_visit(node) # type: ignore

    def _evaluate_call(self, func_name: str, args: list[ast.expr]) -> ast.AST:
        if not self.filename:
            return node # type: ignore

        # For now, only support literal args
        evaluated_args = []
        for arg in args:
            if isinstance(arg, ast.Constant):
                evaluated_args.append(arg.value)
            else:
                # Fallback to normal call if args are complex
                return ast.Call(func=ast.Name(id=func_name, ctx=ast.Load()), args=args, keywords=[])

        worker_path = os.path.join(os.path.dirname(__file__), "compile_time_worker.py")
        input_data = {
            "file_path": self.filename,
            "func_name": func_name,
            "args": evaluated_args
        }

        try:
            proc = subprocess.run(
                [sys.executable, worker_path],
                input=json.dumps(input_data).encode("utf-8"),
                capture_output=True,
                timeout=10
            )
            if proc.returncode != 0:
                err_msg = proc.stderr.decode("utf-8")
                print(f"  ✗ Error in compile-time execution: {err_msg}")
                return ast.Call(func=ast.Name(id=func_name, ctx=ast.Load()), args=args, keywords=[])
            
            output = proc.stdout.decode("utf-8").strip()
            if not output:
                 return ast.Call(func=ast.Name(id=func_name, ctx=ast.Load()), args=args, keywords=[])

            resp = json.loads(output)
            if resp.get("status") == "success":
                return self._val_to_ast(resp.get("result"))
            else:
                print(f"  ✗ Error in compile-time execution: {resp.get('message')}")
        except Exception as e:
            print(f"  ✗ Failed to run compile-time worker: {e}")

        return ast.Call(func=ast.Name(id=func_name, ctx=ast.Load()), args=args, keywords=[])

    def _val_to_ast(self, val: Any) -> ast.AST:
        if val is None or isinstance(val, (int, float, str, bool)):
            return ast.Constant(value=val)
        if isinstance(val, list):
            return ast.List(elts=[self._val_to_ast(v) for v in val], ctx=ast.Load())
        if isinstance(val, dict):
            return ast.Dict(
                keys=[self._val_to_ast(k) for k in val.keys()],
                values=[self._val_to_ast(v) for v in val.values()]
            )
        return ast.Constant(value=None)


# ---------------------------------------------------------------------------
# Pass 1: Scope Analyzer
# ---------------------------------------------------------------------------

class _ScopeAnalyzer(ast.NodeVisitor):
    """
    Single-pass scope analysis.

    Tracks function nesting depth and records the first assignment of each
    name at each depth level.  This is intentionally simple — it doesn't
    handle closures, nonlocal, or global (those raise errors elsewhere).
    """

    def __init__(self) -> None:
        self._depth = 0
        self.scope_map = ScopeMap()

    # -- depth management --

    def _enter_scope(self) -> None:
        self._depth += 1

    def _exit_scope(self) -> None:
        self._depth -= 1

    # -- visitors --

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Record the function name itself at current depth
        self.scope_map.declare(node.name, self._depth)
        self._enter_scope()
        # Record parameters as declared inside the function
        for arg in node.args.args:
            self.scope_map.declare(arg.arg, self._depth)
        if node.args.vararg:
            self.scope_map.declare(node.args.vararg.arg, self._depth)
        self.generic_visit(node)
        self._exit_scope()

    visit_AsyncFunctionDef = visit_FunctionDef   # handled (then rejected) later

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_map.declare(node.name, self._depth)
        self._enter_scope()
        self.generic_visit(node)
        self._exit_scope()

    def visit_For(self, node: ast.For) -> None:
        # Loop variable(s) are declared at current depth
        target = node.target
        if isinstance(target, ast.Name):
            self.scope_map.declare(target.id, self._depth)
        elif isinstance(target, ast.Tuple):
            for elt in target.elts:
                if isinstance(elt, ast.Name):
                    self.scope_map.declare(elt.id, self._depth)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._declare_target(target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # x += 1 — x must already be declared; don't re-declare
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and isinstance(node.target, ast.Name):
            self.scope_map.declare(node.target.id, self._depth)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                self.scope_map.declare(item.optional_vars.id, self._depth)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.scope_map.declare(node.name, self._depth)
        self.generic_visit(node)

    def _declare_target(self, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            self.scope_map.declare(target.id, self._depth)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._declare_target(elt)

    def visit_Global(self, node: ast.Global) -> None:
        raise UnsupportedFeatureError("global", line=get_line(node))

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise UnsupportedFeatureError("nonlocal", line=get_line(node))


# ---------------------------------------------------------------------------
# Pass 2: Import Resolver
# ---------------------------------------------------------------------------

class _ImportResolver(ast.NodeVisitor):
    """
    Validates and classifies all import statements.

    - `from roblox import X`    → marks X as an SDK global (no require)
    - `from . import X`         → records as require(script.Parent.X)
    - `from .sub import X`      → records as require(script.Parent.sub.X)
    - `import anything`         → UnsupportedFeatureError
    - `from other import X`     → UnsupportedFeatureError
    """

    def __init__(self) -> None:
        self.import_info = ImportInfo()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            raise UnsupportedFeatureError(
                f"import {alias.name}",
                line=get_line(node),
                hint=(
                    "RPy only supports `from roblox import ...` and "
                    "relative imports (`from . import ...`). "
                    "Standard library imports are not available in Luau."
                ),
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        level = node.level  # 0 = absolute, 1 = relative (from .), 2 = from ..

        if level == 0 and module == "roblox":
            # SDK import — passthrough, these are Luau globals
            for alias in node.names:
                name = alias.asname or alias.name
                self.import_info.sdk_names.add(name)
            return

        if level >= 1:
            # Relative import → require()
            parts = module.split(".") if module else []
            for alias in node.names:
                local_name = alias.asname or alias.name
                req_parts = ["script"] + ["Parent"] * level + parts + [alias.name]
                luau_path = ".".join(req_parts)
                self.import_info.relative_reqs[local_name] = luau_path
            return

        # Everything else is unsupported
        raise UnsupportedFeatureError(
            f"from {module} import ...",
            line=get_line(node),
            hint=(
                "RPy only supports `from roblox import ...` for Roblox APIs "
                "and `from . import ...` for local modules."
            ),
        )


# ---------------------------------------------------------------------------
# Pass 3: Annotation Stripper
# ---------------------------------------------------------------------------

class _AnnotationStripper(ast.NodeTransformer):
    """
    Removes Python type annotations from AnnAssign nodes.

    `x: int = 5`  →  treated as a plain `x = 5`
    `x: int`      →  dropped entirely (no-value annotation)

    The --typed codegen mode derives Luau types independently.
    """

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Optional[ast.Assign]:  # type: ignore[override]
        if node.value is None:
            # `x: int` with no value — drop it entirely
            return None
        # `x: int = 5` — convert to a plain Assign
        assign = ast.Assign(
            targets=[node.target],
            value=node.value,
            lineno=node.lineno,
            col_offset=node.col_offset,
        )
        self.generic_visit(assign)
        return assign


# ---------------------------------------------------------------------------
# Pass 0: Match Lowerer (Phase 13)
# ---------------------------------------------------------------------------

class _MatchLowerer(ast.NodeTransformer):
    """
    Transforms `match/case` into nested `if/elseif` blocks.
    
    Supports:
      - MatchValue (literals)
      - MatchOr (p1 | p2)
      - MatchAs (case x, case _, case pattern as x)
      - MatchSingleton (True, False, None)
    """

    def __init__(self) -> None:
        self._temp_count = 0

    def _get_temp(self) -> str:
        self._temp_count += 1
        return f"_match_tmp_{self._temp_count}"

    def visit_Match(self, node: ast.Match) -> list[ast.stmt]:
        subject = node.subject
        # Use a temp var to avoid multiple evaluation of the subject
        # (unless it's a simple, immutable Name)
        if isinstance(subject, ast.Name):
            match_var = subject.id
            pre_stmts: list[ast.stmt] = []
        else:
            match_var = self._get_temp()
            # Assign subject to temp: local _match_tmp_1 = <subject>
            pre_stmts = [ast.Assign(
                targets=[ast.Name(id=match_var, ctx=ast.Store())],
                value=subject,
                lineno=node.lineno,
                col_offset=node.col_offset
            )]

        root_if: Optional[ast.If] = None
        current_if: Optional[ast.If] = None

        for case in node.cases:
            bind_stmts: list[ast.stmt] = []
            cond = self._lower_pattern(case.pattern, ast.Name(id=match_var, ctx=ast.Load()), bind_stmts)

            if case.guard:
                # Add guard clause: if (pattern check) and (guard) then
                cond = ast.BoolOp(
                    op=ast.And(),
                    values=[cond, case.guard]
                )

            # Prepend bindings to the case body
            full_body = bind_stmts + case.body
            
            # Lower children recursively within the case body
            full_body = [self.visit(s) for s in full_body]  # type: ignore[misc]

            new_if = ast.If(test=cond, body=full_body, orelse=[], lineno=case.pattern.lineno, col_offset=case.pattern.col_offset)

            # If it's a catch-all (MatchAs with no pattern or wildcard), 
            # we could theoretically stop here and put it in orelse, but 
            # for-loop simplicity we'll just keep building the chain.

            if root_if is None:
                root_if = new_if
                current_if = new_if
            else:
                assert current_if is not None
                current_if.orelse = [new_if]
                current_if = new_if

        if root_if is None:
            return pre_stmts
        
        return pre_stmts + [root_if]

    def _lower_pattern(self, pattern: ast.AST, match_expr: ast.expr, bind_stmts: list[ast.stmt]) -> ast.expr:
        """Recursively transform a MatchPattern into a boolean Expression."""
        
        # case 1:
        if isinstance(pattern, ast.MatchValue):
            return ast.Compare(
                left=match_expr,
                ops=[ast.Eq()],
                comparators=[pattern.value]
            )

        # case 1 | 2:
        if isinstance(pattern, ast.MatchOr):
            return ast.BoolOp(
                op=ast.Or(),
                values=[self._lower_pattern(p, match_expr, bind_stmts) for p in pattern.patterns]
            )

        # case (True | False | None):
        if isinstance(pattern, ast.MatchSingleton):
            return ast.Compare(
                left=match_expr,
                ops=[ast.Eq()],  # Luau uses == for bool/nil
                comparators=[ast.Constant(value=pattern.value)]
            )

        # case [1, x]:
        if isinstance(pattern, ast.MatchSequence):
            # len(subject) == len(pattern)
            conds: list[ast.expr] = [
                ast.Compare(
                    left=ast.Call(
                        func=ast.Name(id="len", ctx=ast.Load()),
                        args=[match_expr],
                        keywords=[]
                    ),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=len(pattern.patterns))]
                )
            ]
            
            for i, subpat in enumerate(pattern.patterns):
                sub_expr = ast.Subscript(
                    value=match_expr,
                    slice=ast.Constant(value=i),  # Generates match_expr[i] (later generated as [i+1])
                    ctx=ast.Load()
                )
                conds.append(self._lower_pattern(subpat, sub_expr, bind_stmts))
                
            return ast.BoolOp(op=ast.And(), values=conds)

        # case x: / case _: / case pattern as x:
        if isinstance(pattern, ast.MatchAs):
            if pattern.name:
                # Bind the name: case x -> x = match_expr
                bind_stmts.append(ast.Assign(
                    targets=[ast.Name(id=pattern.name, ctx=ast.Store())],
                    value=match_expr,
                    lineno=pattern.lineno,
                    col_offset=pattern.col_offset
                ))
            if pattern.pattern:
                return self._lower_pattern(pattern.pattern, match_expr, bind_stmts)
            # Wildcard or bare name always matches
            return ast.Constant(value=True)

        raise UnsupportedFeatureError(
            f"Pattern matching type {type(pattern).__name__} is not yet supported in RPy.",
            line=get_line(pattern)
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform(tree: ast.Module, filename: str | None = None, flags: CompilerFlags | None = None) -> TransformResult:
    """
    Run all transformer passes over *tree* (in order) and return a
    TransformResult containing the (possibly modified) tree plus all
    metadata collected.

    Raises:
        UnsupportedFeatureError — for global/nonlocal/unsupported imports
    """
    # Pass 0 — Match lowering (mutates tree)
    lowerer = _MatchLowerer()
    tree = lowerer.visit(tree)  # type: ignore[assignment]
    ast.fix_missing_locations(tree)

    # Pass 0.1 — Compile-time evaluation
    ct_eval = _CompileTimeEvaluator(filename, flags.compile_time if flags else False)
    tree = ct_eval.visit(tree)  # type: ignore[assignment]
    ast.fix_missing_locations(tree)

    # Pass 1 — scope analysis (read-only)
    scope_analyzer = _ScopeAnalyzer()
    scope_analyzer.visit(tree)

    # Pass 2 — import resolution (read-only, raises on bad imports)
    import_resolver = _ImportResolver()
    import_resolver.visit(tree)

    # Pass 3 — annotation stripping (mutates tree, returns modified copy)
    stripper = _AnnotationStripper()
    tree = stripper.visit(tree)  # type: ignore[assignment]
    ast.fix_missing_locations(tree)

    return TransformResult(
        tree=tree,
        scope_map=scope_analyzer.scope_map,
        import_info=import_resolver.import_info,
        filename=filename,
    )
