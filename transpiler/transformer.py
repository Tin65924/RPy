"""
transpiler/transformer.py — Stage 1 & 2: Python AST passes and IR transformation.
"""

from __future__ import annotations
import ast
import os
import sys
import json
import subprocess
from dataclasses import dataclass
from typing import Any, Optional

from transpiler import ir
from transpiler.ir_transformer import PythonToIRTransformer
from transpiler.analyzer import analyze
from transpiler.flags import CompilerFlags
from transpiler.errors import UnsupportedFeatureError
from transpiler.ast_utils import get_line
from transpiler.ir_optimizer import optimize_ir
from transpiler.linter import lint_ir
from transpiler.cache_manager import cache

@dataclass
class TransformResult:
    """Aggregated output of all transformer passes."""
    ir_module: ir.IRModule
    filename: str | None = None

# --- Pass 0: Match Lowerer ---
class _MatchLowerer(ast.NodeTransformer):
    """Transforms match/case into nested if/elseif blocks (Syntactic Sugar)."""
    # (Implementation omitted for brevity in this architectural demonstration, 
    # but normally would be here as in previous version)
    pass

# --- Pass 0.1: Compile-Time Evaluator ---
class _CompileTimeEvaluator(ast.NodeTransformer):
    """Evaluates @compile_time decorated calls."""
    def __init__(self, filename: str | None, enabled: bool):
        self.filename = filename
        self.enabled = enabled
        self.compile_time_funcs = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        is_compile_time = any(
            (isinstance(dec, ast.Name) and dec.id == "compile_time")
            for dec in node.decorator_list
        )
        if is_compile_time:
            self.compile_time_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name) and node.func.id in self.compile_time_funcs:
            if not self.enabled: return node
            
            # Execute the function call at compile-time and expect an AST node or a constant
            # For simplicity, we'll support returning values that we convert to constants,
            # or List of statements to splice (not easy with NodeTransformer.visit_Call)
            # We'll stick to constant results for now, but allow unrolling in a loop handler.
            try:
                # Basic sandbox: only builtins + current tree (not safe, but illustrative)
                # In a real impl, we'd use a separate process or more robust sandboxing
                from transpiler.compile_time_worker import execute_macro
                result = execute_macro(node, self.filename)
                if isinstance(result, ast.AST):
                    return result
                return ast.Constant(value=result)
            except Exception as e:
                print(f"Warning: Compile-time execution failed: {e}")
                return node
        return self.generic_visit(node)

# --- Pass 3: Annotation Stripper ---
class _AnnotationStripper(ast.NodeTransformer):
    """Removes type annotations from Python code before IR conversion."""
    def visit_AnnAssign(self, node: ast.AnnAssign) -> Optional[ast.AST]:
        if getattr(node.annotation, "id", None) == "persistent":
            return node
        if node.value is None: return None
        assign = ast.Assign(targets=[node.target], value=node.value, lineno=node.lineno, col_offset=node.col_offset)
        return self.generic_visit(assign)

from transpiler.project_context import ProjectContext

def transform(
    tree: ast.Module, 
    filename: str | None = None, 
    flags: CompilerFlags | None = None,
    project: Optional[ProjectContext] = None,
    module_name: str = "main"
) -> TransformResult:
    """
    Full Semantic Compilation Pipeline:
    1. Python AST Passes (Desugaring, Stripping)
    2. Python AST -> IR Transformation
    3. Semantic Analysis on IR
    """
    # ... (skipping unchanged pass logic) ...
    # Try cache (disabled for project analysis to ensure propagation)
    source_str = ast.unparse(tree)
    if not project:
        cached_ir = cache.get_cached_ir(source_str)
        if cached_ir:
            return TransformResult(ir_module=cached_ir, filename=filename)

    # Pass 3: Annotation Stripping
    stripper = _AnnotationStripper()
    tree = stripper.visit(tree)
    ast.fix_missing_locations(tree)

    # Stage 2: Python AST -> IR
    transformer = PythonToIRTransformer()
    ir_module = transformer.transform(tree)

    # Stage 3: Semantic Analysis
    analyze(ir_module, project=project, module_name=module_name)

    # Phase 6: Escape Analysis
    from transpiler.escape_analysis import EscapeAnalyzer
    esc_analyzer = EscapeAnalyzer()
    esc_analyzer.analyze_module(ir_module)
    # Store escape analyzer globally/on module for downstream passes (e.g. SRA) to use
    ir_module.escape_analyzer = esc_analyzer

    # Stage 17: Roblox Rule Engine (Linter)
    lint_ir(ir_module)

    # Stage 4: Logical Optimizations (Stage 16)
    optimize_ir(ir_module)
    
    # Phase 6: Escape Analysis Optimizations (Must happen after logical optimizations simplify the tree)
    from transpiler.sra import SRAPass
    from transpiler.closure_opt import ClosureEliminationPass
    
    sra_pass = SRAPass(esc_analyzer)
    for i, stmt in enumerate(ir_module.body):
        if isinstance(stmt, ir.IRFunctionDef):
            stmt.body = sra_pass.optimize_block(stmt.body)
            
    clo_pass = ClosureEliminationPass(esc_analyzer)
    for i, stmt in enumerate(ir_module.body):
        if isinstance(stmt, ir.IRFunctionDef):
            stmt.body = clo_pass.optimize_block(stmt.body)
    
    # Cache the result
    cache.save_ir(source_str, ir_module)

    if flags and flags.debug:
        from transpiler.diagnostics import manager
        if manager.has_errors():
            print("\nCompilation failed with errors.")
            # In a real CLI, we might exit here

    return TransformResult(
        ir_module=ir_module,
        filename=filename
    )
