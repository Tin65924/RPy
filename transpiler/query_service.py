"""
transpiler/query_service.py — High-level semantic queries for LSP and IDEs.
"""

from __future__ import annotations
import ast
from typing import List, Optional, Any, Dict
from pathlib import Path

from transpiler import ir
from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.analyzer import SemanticAnalyzer
from transpiler.diagnostics import manager, DiagnosticManager, Severity

class NodeFinder:
    """Finds the most specific IR node at a given line and column."""
    def __init__(self, line: int, col: int):
        self.line = line
        self.col = col
        self.found_node: Optional[ir.IRNode] = None

    def _get_node_end(self, node: ir.IRNode) -> int:
        if isinstance(node, ir.IRVariable):
            return node.col_offset + len(node.name)
        if isinstance(node, ir.IRPropertyAccess):
            return self._get_node_end(node.receiver) + 1 + len(node.property)
        if isinstance(node, ir.IRLiteral):
            return node.col_offset + len(str(node.value))
        return node.col_offset + 1 # Default

    def find(self, node: ir.IRNode):
        if hasattr(node, "lineno"):
            if node.lineno == self.line:
                start = node.col_offset
                end = self._get_node_end(node)
                
                # Check if cursor is within bounds
                if start <= self.col < end:
                    # We prefer the smallest (narrowest) node that contains the cursor
                    if self.found_node is None:
                        self.found_node = node
                    else:
                        old_width = self._get_node_end(self.found_node) - self.found_node.col_offset
                        new_width = end - start
                        if new_width <= old_width:
                            self.found_node = node

        # Recurse into children
        if hasattr(node, "__dict__"):
            for attr, value in node.__dict__.items():
                if isinstance(value, ir.IRNode):
                    self.find(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ir.IRNode):
                            self.find(item)

class QueryService:
    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        self.diagnostics = DiagnosticManager(silent=True)
        self.analyzer = SemanticAnalyzer(self.diagnostics)
        if metadata:
            self.analyzer.metadata = metadata

    def get_diagnostics(self, source: str, filename: str = "<string>") -> List[Dict[str, Any]]:
        self.diagnostics.clear()
        try:
            tree = ast.parse(source)
            ir_module = transform(tree, filename=filename)
            self.analyzer.analyze(ir_module)
        except Exception as e:
            # Handle parse errors if possible
            pass
            
        return [
            {
                "line": d.line,
                "col": d.col,
                "severity": d.severity.name,
                "message": d.message,
                "hint": d.hint
            }
            for d in self.diagnostics.diagnostics
        ]

    def get_hover(self, source: str, line: int, col: int, filename: str = "<string>") -> Optional[str]:
        try:
            tree = ast.parse(source)
            res = transform(tree, filename=filename)
            # Re-running analyze is necessary to populate type info on the fly
            self.analyzer.analyze(res.ir_module)
            
            finder = NodeFinder(line, col)
            finder.find(res.ir_module)
            
            if finder.found_node:
                node = finder.found_node
                if isinstance(node, ir.IRPropertyAccess):
                    return f"(property) {node.property}: {node.inferred_type or 'any'}"
                if isinstance(node, ir.IRMethodCall):
                    return f"(method) {node.method}: {node.inferred_type or 'any'}"
                if isinstance(node, ir.IRVariable):
                    return f"(variable) {node.name}: {node.inferred_type or 'any'}"
                if isinstance(node, ir.IRExpression) and node.inferred_type:
                    return f"(type) {node.inferred_type}"
                return f"({type(node).__name__})"
            return None
        except Exception as e:
            return f"Hover Error: {e}"

    def get_completions(self, source: str, line: int, col: int, filename: str = "<string>") -> List[Dict[str, str]]:
        # Heuristic for dot completion (e.g. "game.")
        source_lines = source.splitlines()
        if line - 1 >= len(source_lines): return []
        
        curr_line = source_lines[line-1]
        prefix = curr_line[:col]
        
        if prefix.endswith("."):
            receiver_expr = prefix[:-1]
            # We want to know the type of 'receiver_expr'
            # To do this safely, we can try to parse a modified source that is a valid expression
            try:
                # Find the last word/expression before the dot
                import re
                match = re.search(r"([a-zA-Z_0-9\.]+)$", receiver_expr)
                if not match: return []
                
                expr = match.group(0)
                # We need context. Analyze the whole source up to the previous line 
                # + the expression we found.
                context_source = "\n".join(source_lines[:line-1]) + f"\n_tmp = {expr}"
                tree = ast.parse(context_source)
                res = transform(tree, filename=filename)
                self.analyzer.analyze(res.ir_module)
                
                # The last statement is our assignment
                last_stmt = res.ir_module.body[-1]
                if isinstance(last_stmt, ir.IRAssignment):
                    rtype = self.analyzer._infer_type(last_stmt.value)
                    if rtype:
                        info = self.analyzer._get_class_info(rtype)
                        if info:
                            comps = []
                            # Properties
                            for p in info.get("properties", {}):
                                comps.append({"label": p, "kind": "Property", "detail": f"Property of {rtype}"})
                            # Methods
                            for m in info.get("methods", {}):
                                comps.append({"label": m, "kind": "Method", "detail": f"Method of {rtype}"})
                            return comps
            except Exception:
                pass
        
        return []

query_service = QueryService()
