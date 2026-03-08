"""
transpiler/transformer.py — Pre-codegen normalization passes over the AST.

Passes (run in order by transform()):
  1. ScopeAnalyzer  — builds a ScopeMap: Name → first-write depth, so the
                       generator knows when to emit `local`.
  2. ImportResolver — resolves import statements; marks SDK imports as
                       passthroughs, relative imports as require(), rejects
                       all others.
  3. AnnotationStripper — removes AnnAssign annotation fields (Luau handles
                           types separately; --typed mode re-derives them).
  4. MatchGuard     — raises UnsupportedFeatureError on any Match node
                       (belt-and-suspenders; parser also checks).

None of these passes modify the AST in place — they attach metadata or raise
errors.  The generator reads that metadata when emitting code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional

from transpiler.errors import UnsupportedFeatureError
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
# Pass 4: Match Guard (belt-and-suspenders)
# ---------------------------------------------------------------------------

class _MatchGuard(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:
        if type(node).__name__ == "Match":
            raise UnsupportedFeatureError("match/case", line=get_line(node))
        super().generic_visit(node)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform(tree: ast.Module) -> TransformResult:
    """
    Run all transformer passes over *tree* (in order) and return a
    TransformResult containing the (possibly modified) tree plus all
    metadata collected.

    Raises:
        UnsupportedFeatureError — for global/nonlocal/unsupported imports/match
    """
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

    # Pass 4 — match/case guard (read-only, belt-and-suspenders)
    _MatchGuard().visit(tree)

    return TransformResult(
        tree=tree,
        scope_map=scope_analyzer.scope_map,
        import_info=import_resolver.import_info,
    )
