"""
transpiler/ast_utils.py — Stateless helpers for inspecting Python AST nodes.

These functions are pure utilities: they take AST nodes and return simple
Python values.  They contain no side-effects and no state.
"""

from __future__ import annotations

import ast
from typing import Iterator, Optional, Tuple, List
import difflib


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

def get_closest_match(word: str, possibilities: List[str]) -> Optional[str]:
    """Return the closest match for *word* in *possibilities* using difflib."""
    matches = difflib.get_close_matches(word, possibilities, n=1, cutoff=0.6)
    return matches[0] if matches else None


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

    range(n)       -> (Constant(0), n,    None)
    range(a, b)    -> (a,           b,    None)
    range(a, b, c) -> (a,           b,    c)
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
      - bool / None constants         (same in both languages)
      - int/float non-zero literals   (both languages agree these are truthy)
        * 0 and 0.0 differ: Python -> False, Lua -> true, so they still need shim
      - Comparison results            (always produce a boolean)
      - BoolOp (and/or) results       (result is one of the operands)
      - UnaryOp(Not)                  (result is always a Lua boolean)
    """
    if isinstance(node, ast.Constant):
        # bool and None: identical semantics in Python and Lua
        if isinstance(node.value, bool) or node.value is None:
            return True
        # Non-zero integers and floats are truthy in both — safe to skip shim
        if isinstance(node.value, (int, float)) and node.value != 0:
            return True
        # Non-empty strings are truthy in Python but ALSO truthy in Lua
        # (Lua only considers nil/false as falsy — empty string is truthy in Lua)
        # So we only need the shim for empty string ""
        if isinstance(node.value, str) and node.value != "":
            return True
        return False
    if isinstance(node, (ast.Compare, ast.BoolOp)):
        return True
    # `not expr` always produces a Lua boolean — no shim needed
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return True
    return False


def needs_bool_shim(node: ast.AST) -> bool:
    """
    Return True if a boolean context (if, while, assert) over *node* requires
    wrapping with py_bool() to preserve Python truthiness semantics.

    In --fast mode the caller should skip this check entirely.
    """
    return not _bool_trivially_safe(node)


# ---------------------------------------------------------------------------
# Constant folding helpers
# ---------------------------------------------------------------------------

_FOLD_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Pow: lambda a, b: a ** b,
}


def fold_constant_binop(node: ast.AST) -> Optional[int | float]:
    """
    If *node* is a BinOp where both operands are numeric constants and the
    operator is foldable, return the pre-computed result.

    Returns None if folding is not safe or not applicable.

    Deliberately excludes division (/ // %) to avoid ZeroDivisionError and
    floating-point precision surprises at compile time.
    """
    if not isinstance(node, ast.BinOp):
        return None
    op_type = type(node.op)
    folder = _FOLD_OPS.get(op_type)
    if folder is None:
        return None
    left, right = node.left, node.right
    if not (isinstance(left, ast.Constant) and isinstance(right, ast.Constant)):
        return None
    if not (isinstance(left.value, (int, float)) and isinstance(right.value, (int, float))):
        return None
    # Avoid folding integer exponentiation that could produce huge literals
    if op_type is ast.Pow and isinstance(right.value, int) and right.value > 32:
        return None
    try:
        result = folder(left.value, right.value)
    except (OverflowError, ZeroDivisionError):
        return None
    return result
