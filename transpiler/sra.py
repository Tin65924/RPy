"""
transpiler/sra.py — Scalar Replacement of Aggregates optimization pass.
"""

from __future__ import annotations
from typing import Dict, List, Set, Any, Optional
from transpiler import ir
from transpiler.escape_analysis import EscapeAnalyzer, EscapeState

class SRAPass:
    def __init__(self, analyzer: EscapeAnalyzer):
        self.analyzer = analyzer
        self.replaced_tables: Dict[str, Dict[str, str]] = {} # original_table_name -> {field_name -> new_scalar_name}
        self.new_statements: List[ir.IRStatement] = []

    def optimize_block(self, block: List[ir.IRStatement]) -> List[ir.IRStatement]:
        old_replaced = self.replaced_tables.copy()
        new_block = []
        
        for stmt in block:
            self.new_statements = []
            
            if isinstance(stmt, ir.IRAssignment):
                if isinstance(stmt.target, ir.IRVariable) and isinstance(stmt.value, ir.IRTableLiteral):
                    var_name = stmt.target.name
                    node = self.analyzer.nodes.get(var_name)
                    
                    if node and node.state == EscapeState.LOCAL:
                        # SAFE TO SRA!
                        field_map = {}
                        
                        # Process dict fields
                        for key, val in stmt.value.fields:
                            scalar_name = f"{var_name}_{key}"
                            field_map[key] = scalar_name
                            
                            new_assign = ir.IRAssignment(
                                target=ir.IRVariable(name=scalar_name),
                                value=self._rewrite_expr(val),
                                is_local=True
                            )
                            self.new_statements.append(new_assign)
                            
                        # Process array elements (we can name them arr_0, arr_1)
                        for i, el in enumerate(stmt.value.elements):
                            scalar_name = f"{var_name}_{i}"
                            field_map[str(i)] = scalar_name
                            
                            new_assign = ir.IRAssignment(
                                target=ir.IRVariable(name=scalar_name),
                                value=self._rewrite_expr(el),
                                is_local=True
                            )
                            self.new_statements.append(new_assign)
                            
                        self.replaced_tables[var_name] = field_map
                        new_block.extend(self.new_statements)
                        continue # Skip appending the original table assignment
                        
                # If not a table allocation, or not local, we still need to rewrite its value
                stmt.value = self._rewrite_expr(stmt.value)
                
                # Check if we're assigning TO a field of a replaced table (p.x = 5)
                # Actually, if the table is LOCAL, it shouldn't escape. But it could be mutated!
                # If it's mutated, we need to handle it.
                if isinstance(stmt.target, ir.IRPropertyAccess):
                    if isinstance(stmt.target.receiver, ir.IRVariable):
                        rc_name = stmt.target.receiver.name
                        if rc_name in self.replaced_tables:
                            field = stmt.target.property
                            if field in self.replaced_tables[rc_name]:
                                stmt.target = ir.IRVariable(name=self.replaced_tables[rc_name][field])
                            else:
                                # Dynamic addition of a field? Create a new scalar!
                                scalar_name = f"{rc_name}_{field}"
                                self.replaced_tables[rc_name][field] = scalar_name
                                stmt.target = ir.IRVariable(name=scalar_name)

            elif isinstance(stmt, (ir.IRIfStatement, ir.IRWhileStatement, ir.IRForStatement, ir.IRFunctionDef)):
                self._visit_stmt(stmt) # This will recursively call optimize_block on inner blocks
                
            elif isinstance(stmt, ir.IRReturnStatement) and stmt.value:
                stmt.value = self._rewrite_expr(stmt.value)
                
            elif isinstance(stmt, (ir.IRFunctionCall, ir.IRMethodCall)):
                 # Standalone calls
                 self._rewrite_expr(stmt)

            new_block.extend(self.new_statements)
            new_block.append(stmt)
            
        self.replaced_tables = old_replaced
        return new_block

    def _visit_stmt(self, node: ir.IRStatement):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, None)
        if visitor:
            visitor(node)

    def _rewrite_expr(self, expr: ir.IRExpression) -> ir.IRExpression:
        if isinstance(expr, ir.IRPropertyAccess):
            if isinstance(expr.receiver, ir.IRVariable):
                rc_name = expr.receiver.name
                if rc_name in self.replaced_tables:
                    field = expr.property
                    if field in self.replaced_tables[rc_name]:
                        return ir.IRVariable(name=self.replaced_tables[rc_name][field])
            # Otherwise just recurse
            expr.receiver = self._rewrite_expr(expr.receiver)
            
        elif isinstance(expr, ir.IRBinaryOperation):
            expr.left = self._rewrite_expr(expr.left)
            expr.right = self._rewrite_expr(expr.right)
        elif isinstance(expr, ir.IRUnaryOperation):
            expr.operand = self._rewrite_expr(expr.operand)
        elif isinstance(expr, ir.IRFunctionCall):
            expr.func = self._rewrite_expr(expr.func)
            expr.args = [self._rewrite_expr(arg) for arg in expr.args]
        elif isinstance(expr, ir.IRMethodCall):
            expr.receiver = self._rewrite_expr(expr.receiver)
            expr.args = [self._rewrite_expr(arg) for arg in expr.args]
        elif isinstance(expr, ir.IRTableLiteral):
            expr.elements = [self._rewrite_expr(e) for e in expr.elements]
            expr.fields = [(k, self._rewrite_expr(v)) for k, v in expr.fields]
            
        return expr

    def visit_IRIfStatement(self, node: ir.IRIfStatement):
        node.condition = self._rewrite_expr(node.condition)
        node.then_block = self.optimize_block(node.then_block)
        if node.else_block:
            node.else_block = self.optimize_block(node.else_block)
        new_elifs = []
        for cond, body in node.elif_blocks:
            new_elifs.append((self._rewrite_expr(cond), self.optimize_block(body)))
        node.elif_blocks = new_elifs

    def visit_IRWhileStatement(self, node: ir.IRWhileStatement):
        node.condition = self._rewrite_expr(node.condition)
        node.body = self.optimize_block(node.body)

    def visit_IRForStatement(self, node: ir.IRForStatement):
        node.start = self._rewrite_expr(node.start)
        node.end = self._rewrite_expr(node.end)
        if node.step: node.step = self._rewrite_expr(node.step)
        node.body = self.optimize_block(node.body)

    def visit_IRGenericForStatement(self, node: ir.IRGenericForStatement):
        node.iterators = [self._rewrite_expr(it) for it in node.iterators]
        node.body = self.optimize_block(node.body)

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef):
        # Functions introduce a new scope, but SRA map should inherit
        node.body = self.optimize_block(node.body)
