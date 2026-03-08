"""
transpiler/handlers.py — Optional AST node handlers registered via decorators.

This module is imported by transpiler.node_registry to populate the central
dispatch maps.  It allows us to split the massive generator.py into smaller,
feature-specific files.

Currently, Phase 13 features (Sets, Match/Case) are still in LuauGenerator,
but core infrastructure is moving here.
"""

from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from transpiler.node_registry import statement, expression

if TYPE_CHECKING:
    from transpiler.generator import GeneratorContext

# ---------------------------------------------------------------------------
# Core Statement Handlers
# ---------------------------------------------------------------------------

@statement(ast.Pass)
def handle_pass(node: ast.Pass, ctx: GeneratorContext) -> None:
    ctx.emitter.line("-- pass")

@statement(ast.Break)
def handle_break(node: ast.Break, ctx: GeneratorContext) -> None:
    ctx.emitter.line("break")

@statement(ast.Continue)
def handle_continue(node: ast.Continue, ctx: GeneratorContext) -> None:
    ctx.emitter.line("continue")
