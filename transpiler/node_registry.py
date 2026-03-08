"""
transpiler/node_registry.py — Central dispatch map from Python AST node types
to their corresponding Luau generator handler functions.

Design rationale
----------------
Keeping handler registration in one place prevents generator.py from becoming
an unmanageable monolith.  Handlers are plain functions that accept
(node, context) and return a Luau source string (or emit via CodeEmitter).

Handlers are added here as each phase is implemented.  During Phase 3 the
registry is built but intentionally mostly empty — it fills up in Phase 4.

Usage (inside generator.py)
---------------------------
    from transpiler.node_registry import get_handler

    handler = get_handler(type(node))
    handler(node, ctx)

If no handler is registered, get_handler() raises UnsupportedFeatureError
automatically, so generator.py never needs to write that boilerplate.
"""

from __future__ import annotations

import ast
from typing import Callable, Optional, TYPE_CHECKING

from transpiler.errors import UnsupportedFeatureError
from transpiler.ast_utils import get_line, node_name

if TYPE_CHECKING:
    # Avoid circular import at runtime; only used for type hints.
    from transpiler.generator import GeneratorContext

# ---------------------------------------------------------------------------
# Type alias for handler functions
# ---------------------------------------------------------------------------

# A handler takes an AST node and a generator context, and returns a Luau
# source string.  The return can be None for statement handlers that write
# directly to context.emitter.
HandlerFn = Callable[[ast.AST, "GeneratorContext"], Optional[str]]


# ---------------------------------------------------------------------------
# Registry storage
# ---------------------------------------------------------------------------

_STATEMENT_HANDLERS: dict[type, HandlerFn] = {}
_EXPRESSION_HANDLERS: dict[type, HandlerFn] = {}


# ---------------------------------------------------------------------------
# Registration decorators
# ---------------------------------------------------------------------------

def statement(*node_types: type) -> Callable[[HandlerFn], HandlerFn]:
    """
    Decorator that registers a function as the handler for one or more
    statement-level AST node types.

    Usage:
        @statement(ast.Assign, ast.AugAssign)
        def handle_assign(node, ctx):
            ...
    """
    def decorator(fn: HandlerFn) -> HandlerFn:
        for t in node_types:
            _STATEMENT_HANDLERS[t] = fn
        return fn
    return decorator


def expression(*node_types: type) -> Callable[[HandlerFn], HandlerFn]:
    """
    Decorator that registers a function as the handler for one or more
    expression-level AST node types.

    Usage:
        @expression(ast.BinOp)
        def handle_binop(node, ctx):
            return "..."
    """
    def decorator(fn: HandlerFn) -> HandlerFn:
        for t in node_types:
            _EXPRESSION_HANDLERS[t] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def get_statement_handler(node: ast.AST) -> HandlerFn:
    """
    Return the registered statement handler for *node*'s type.

    Raises UnsupportedFeatureError if no handler is registered.
    """
    t = type(node)
    handler = _STATEMENT_HANDLERS.get(t)
    if handler is None:
        raise UnsupportedFeatureError(
            feature=node_name(node),
            line=get_line(node),
            hint=f"The Python construct '{node_name(node)}' has no Luau equivalent yet.",
        )
    return handler


def get_expression_handler(node: ast.AST) -> HandlerFn:
    """
    Return the registered expression handler for *node*'s type.

    Raises UnsupportedFeatureError if no handler is registered.
    """
    t = type(node)
    handler = _EXPRESSION_HANDLERS.get(t)
    if handler is None:
        raise UnsupportedFeatureError(
            feature=node_name(node),
            line=get_line(node),
            hint=f"The Python expression '{node_name(node)}' has no Luau equivalent yet.",
        )
    return handler


def list_registered() -> dict[str, list[str]]:
    """
    Return a dict with 'statements' and 'expressions' keys, each containing
    a sorted list of registered node type names.  Useful for --verbose output.
    """
    return {
        "statements": sorted(t.__name__ for t in _STATEMENT_HANDLERS),
        "expressions": sorted(t.__name__ for t in _EXPRESSION_HANDLERS),
    }


# ---------------------------------------------------------------------------
# Phase 4+ handlers will be imported and registered here via:
#   from transpiler import handlers   (which uses @statement / @expression)
# ---------------------------------------------------------------------------
# This import is conditional so the registry is usable before handlers exist.
try:
    import transpiler.handlers  # noqa: F401  # registers via decorators
except ModuleNotFoundError:
    pass  # handlers module is created in Phase 4
