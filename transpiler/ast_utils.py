"""
transpiler/ast_utils.py — Stateless helpers for inspecting Python AST nodes.

These functions are pure utilities: they take AST nodes and return simple
Python values.  They contain no side-effects and no state.
"""

from __future__ import annotations

import ast
from typing import Iterator, Optional, Tuple


# ---------------------------------------------------------------------------
# Location helpers
# ---------------------------------------------------------------------------

def get_line(node: ast.AST) -> Optional[int]:
    """Return the 1-indexed source line number of *node*, or None."""
    return getattr(node, "lineno", None)


def get_col(node: ast.AST) -> Optional[int]:
    """Return the 1-indexed column offset of *node*, or None."""
    col = getattr(node, "col_offset", None)
    # ast col_offset is 0-indexed, convert to 1-indexed for user messages
    return col + 1 if col is not None else None


def node_name(node: ast.AST) -> str:
    """Return a human-readable name for *node* type (e.g. 'FunctionDef')."""
    return type(node).__name__


# ---------------------------------------------------------------------------
# Type-checking helpers
# ---------------------------------------------------------------------------

def is_constant(node: ast.AST) -> bool:
    """Return True if *node* is a literal constant (number, string, bool, None)."""
    return isinstance(node, ast.Constant)


def is_name(node: ast.AST, id_: str | None = None) -> bool:
    """
    Return True if *node* is an ast.Name node.
    If *id_* is given, also check that Name.id == id_.
    """
    if not isinstance(node, ast.Name):
        return False
    return id_ is None or node.id == id_


def is_none(node: ast.AST) -> bool:
    """Return True if *node* is the literal None constant."""
    return isinstance(node, ast.Constant) and node.value is None


def is_ellipsis(node: ast.AST) -> bool:
    """Return True if *node* is the Ellipsis constant (...)."""
    return isinstance(node, ast.Constant) and isinstance(node.value, type(...))


# ---------------------------------------------------------------------------
# Range-call detection (used by For-loop handler)
# ---------------------------------------------------------------------------

def is_range_call(node: ast.AST) -> bool:
    """
    Return True if *node* is a bare call to the builtin `range()`.

    Matches:
        range(n)
        range(a, b)
        range(a, b, step)

    Does NOT match:
        some_obj.range(...)
        my_range(...)
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
        and not node.keywords          # no keyword args allowed
        and 1 <= len(node.args) <= 3   # 1, 2, or 3 positional args
    )


def unpack_range_args(
    call: ast.Call,
) -> Tuple[ast.expr, ast.expr, Optional[ast.expr]]:
    """
    Given a confirmed range() Call node, return (start, stop, step).

    range(n)       → (Constant(0), n,    None)
    range(a, b)    → (a,           b,    None)
    range(a, b, c) → (a,           b,    c)
    """
    args = call.args
    zero = ast.Constant(value=0)
    if len(args) == 1:
        return zero, args[0], None
    elif len(args) == 2:
        return args[0], args[1], None
    else:
        return args[0], args[1], args[2]


# ---------------------------------------------------------------------------
# Child iteration helpers
# ---------------------------------------------------------------------------

def iter_child_stmts(node: ast.AST) -> Iterator[ast.stmt]:
    """
    Yield every direct child statement of *node*, in order.
    Works for Module, FunctionDef, ClassDef, If, For, While, With, Try, etc.
    """
    for field_name, value in ast.iter_fields(node):
        if field_name in {"body", "orelse", "finalbody", "handlers"}:
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.stmt):
                        yield item


# ---------------------------------------------------------------------------
# Attribute / method call helpers
# ---------------------------------------------------------------------------

def is_method_call(node: ast.AST, method: str) -> bool:
    """
    Return True if *node* is a method call of the form ``obj.method(...)``.

    Example:
        is_method_call(node, "append")  # True for `my_list.append(x)`
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
    )


def get_attr_chain(node: ast.Attribute) -> list[str]:
    """
    Return the dotted name chain for an Attribute node.

    Example:
        game.GetService("Players")
        → get_attr_chain(node.func) → ["game", "GetService"]
    """
    parts: list[str] = [node.attr]
    current: ast.expr = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    parts.reverse()
    return parts


# ---------------------------------------------------------------------------
# Boolean / truthiness context helpers
# ---------------------------------------------------------------------------

def _bool_trivially_safe(node: ast.AST) -> bool:
    """
    Return True if the node's runtime value will never differ between
    Python and Lua truthiness rules — i.e. wrapping it in py_bool() is
    provably unnecessary.

    Safe cases:
      - True / False / None constants  (same in both languages)
      - Comparison results             (always bool in Python, truthy bool in Lua)
      - BoolOp (and/or) results        (bool in Python, truthy in Lua)
    """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, bool) or node.value is None
    if isinstance(node, (ast.Compare, ast.BoolOp)):
        return True
    return False


def needs_bool_shim(node: ast.AST) -> bool:
    """
    Return True if a boolean context (if, while, assert) over *node* requires
    wrapping with py_bool() to preserve Python truthiness semantics.

    In --fast mode the caller should skip this check entirely.
    """
    return not _bool_trivially_safe(node)
