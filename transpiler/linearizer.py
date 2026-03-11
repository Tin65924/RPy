"""
transpiler/linearizer.py — Flattens IR expression trees into instructions.
"""

from __future__ import annotations
from typing import List, Optional, Any
from transpiler import ir

class IRLinearizer:
    def __init__(self):
        self._temp_count = 0
        self._instructions: List[ir.IRStatement] = []

    def _gen_temp(self, inferred_type: Optional[str] = None) -> ir.IRVariable:
        self._temp_count += 1
        return ir.IRVariable(name=f"_t{self._temp_count}", inferred_type=inferred_type)

    def linearize_module(self, module: ir.IRModule) -> ir.IRModule:
        new_body = []
        for stmt in module.body:
            new_body.extend(self.linearize_statement(stmt))
        return ir.IRModule(body=new_body)

    def linearize_statement(self, stmt: ir.IRStatement) -> List[ir.IRStatement]:
        prev_instructions = getattr(self, '_instructions', [])
        self._instructions = []
        
        if isinstance(stmt, ir.IRAssignment):
            flat_val = self.linearize_expression(stmt.value)
            # If target is property access, it also needs linearization of receiver
            if isinstance(stmt.target, ir.IRPropertyAccess):
                stmt.target.receiver = self.linearize_expression(stmt.target.receiver)
            
            stmt.value = flat_val
            self._instructions.append(stmt)
        elif isinstance(stmt, ir.IRReturnStatement):
            if stmt.value:
                stmt.value = self.linearize_expression(stmt.value)
            self._instructions.append(stmt)
        elif isinstance(stmt, ir.IRIfStatement):
            stmt.condition = self.linearize_expression(stmt.condition)
            stmt.then_block = [instr for s in stmt.then_block for instr in self.linearize_statement(s)]
            if stmt.else_block:
                stmt.else_block = [instr for s in stmt.else_block for instr in self.linearize_statement(s)]
            self._instructions.append(stmt)
        elif isinstance(stmt, ir.IRWhileStatement):
            stmt.condition = self.linearize_expression(stmt.condition)
            stmt.body = [instr for s in stmt.body for instr in self.linearize_statement(s)]
            self._instructions.append(stmt)
        elif isinstance(stmt, (ir.IRFunctionCall, ir.IRMethodCall)):
            # Standalone calls
            self.linearize_expression(stmt)
        else:
            self._instructions.append(stmt)
            
        res = self._instructions
        self._instructions = prev_instructions
        return res

    def linearize_expression(self, expr: ir.IRExpression) -> ir.IRExpression:
        if isinstance(expr, ir.IRLiteral):
            return expr
        if isinstance(expr, ir.IRVariable):
            # Create a new object to avoid sharing during SSA renaming
            return ir.IRVariable(name=expr.name, original_name=expr.original_name, inferred_type=expr.inferred_type, lineno=expr.lineno, col_offset=expr.col_offset)
        
        if isinstance(expr, ir.IRBinaryOperation):
            expr.left = self.linearize_expression(expr.left)
            expr.right = self.linearize_expression(expr.right)
            temp = self._gen_temp(expr.inferred_type)
            self._instructions.append(ir.IRAssignment(target=temp, value=expr, is_local=True))
            return temp
            
        if isinstance(expr, ir.IRUnaryOperation):
            expr.operand = self.linearize_expression(expr.operand)
            temp = self._gen_temp(expr.inferred_type)
            self._instructions.append(ir.IRAssignment(target=temp, value=expr, is_local=True))
            return temp

        if isinstance(expr, ir.IRFunctionCall):
            expr.func = self.linearize_expression(expr.func)
            expr.args = [self.linearize_expression(arg) for arg in expr.args]
            temp = self._gen_temp(expr.inferred_type)
            self._instructions.append(ir.IRAssignment(target=temp, value=expr, is_local=True))
            return temp

        if isinstance(expr, ir.IRMethodCall):
            expr.receiver = self.linearize_expression(expr.receiver)
            expr.args = [self.linearize_expression(arg) for arg in expr.args]
            temp = self._gen_temp(expr.inferred_type)
            self._instructions.append(ir.IRAssignment(target=temp, value=expr, is_local=True))
            return temp
            
        if isinstance(expr, ir.IRPropertyAccess):
            expr.receiver = self.linearize_expression(expr.receiver)
            temp = self._gen_temp(expr.inferred_type)
            self._instructions.append(ir.IRAssignment(target=temp, value=expr, is_local=True))
            return temp

        return expr
