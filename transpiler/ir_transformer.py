"""
transpiler/ir_transformer.py — Stage 2: Python AST to IR conversion.
"""

from __future__ import annotations
import ast
from typing import Any, List, Optional
from transpiler import ir
from transpiler.errors import UnsupportedFeatureError
from transpiler.ast_utils import get_line, node_name

class PythonToIRTransformer(ast.NodeVisitor):
    def __init__(self):
        self._temp_count = 0

    def transform(self, node: ast.AST) -> ir.IRNode:
        return self.visit(node)

    def visit_Module(self, node: ast.Module) -> ir.IRModule:
        return ir.IRModule(
            lineno=1,
            body=[self.visit(s) for s in node.body if self.visit(s) is not None]
        )

    # --- Expressions ---

    def visit_Constant(self, node: ast.Constant) -> ir.IRLiteral:
        return ir.IRLiteral(
            lineno=getattr(node, "lineno", 0),
            col_offset=getattr(node, "col_offset", 0),
            value=node.value
        )

    def visit_Name(self, node: ast.Name) -> ir.IRVariable:
        return ir.IRVariable(
            lineno=getattr(node, "lineno", 0),
            col_offset=getattr(node, "col_offset", 0),
            name=node.id
        )

    def visit_BinOp(self, node: ast.BinOp) -> ir.IRBinaryOperation:
        # Note: Operators are mapped later or preserved as strings/ast types
        # For IR we can use a more abstract representation if needed
        return ir.IRBinaryOperation(
            lineno=node.lineno,
            col_offset=node.col_offset,
            left=self.visit(node.left),
            operator=type(node.op).__name__,
            right=self.visit(node.right)
        )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ir.IRUnaryOperation:
        return ir.IRUnaryOperation(
            lineno=node.lineno,
            col_offset=node.col_offset,
            operator=type(node.op).__name__,
            operand=self.visit(node.operand)
        )

    def visit_Call(self, node: ast.Call) -> ir.IRExpression:
        if isinstance(node.func, ast.Attribute):
            return ir.IRMethodCall(
                lineno=node.lineno,
                col_offset=node.col_offset,
                receiver=self.visit(node.func.value),
                method=node.func.attr,
                args=[self.visit(arg) for arg in node.args]
            )
        return ir.IRFunctionCall(
            lineno=node.lineno,
            col_offset=node.col_offset,
            func=self.visit(node.func),
            args=[self.visit(arg) for arg in node.args]
        )

    def visit_Attribute(self, node: ast.Attribute) -> ir.IRPropertyAccess:
        return ir.IRPropertyAccess(
            lineno=node.lineno,
            col_offset=node.col_offset,
            receiver=self.visit(node.value),
            property=node.attr
        )

    def visit_Subscript(self, node: ast.Subscript) -> ir.IRIndexOperation:
        return ir.IRIndexOperation(
            lineno=node.lineno,
            col_offset=node.col_offset,
            receiver=self.visit(node.value),
            index=self.visit(node.slice)
        )

    def visit_List(self, node: ast.List) -> ir.IRTableLiteral:
        return ir.IRTableLiteral(
            lineno=node.lineno,
            col_offset=node.col_offset,
            elements=[self.visit(e) for e in node.elts]
        )

    def visit_Dict(self, node: ast.Dict) -> ir.IRTableLiteral:
        fields = []
        for k, v in zip(node.keys, node.values):
            if k is None: continue
            kn = self.visit(k).value if isinstance(k, ast.Constant) else str(self.visit(k))
            fields.append((str(kn), self.visit(v)))
        return ir.IRTableLiteral(lineno=node.lineno, col_offset=node.col_offset, fields=fields)

    # --- Statements ---

    def visit_Assign(self, node: ast.Assign) -> ir.IRStatement:
        # Capture all targets
        ir_targets = [self.visit(t) for t in node.targets]
        ir_value = self.visit(node.value)
        
        # Simple implementation for now, assuming single target (multiple assignments can be split)
        return ir.IRAssignment(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=ir_targets[0],
            value=ir_value,
            is_local=True # The analyzer will refine this if needed, but default to local
        )

    def visit_Expr(self, node: ast.Expr) -> ir.IRStatement:
        # In IR, standalone expressions are often just calls
        val = self.visit(node.value)
        if isinstance(val, (ir.IRMethodCall, ir.IRFunctionCall)):
            return val # type: ignore
        # Otherwise wrap in an assignment to _ or discard
        return ir.IRAssignment(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=ir.IRVariable(name="_"),
            value=val
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ir.IRFunctionDef:
        return ir.IRFunctionDef(
            lineno=node.lineno,
            col_offset=node.col_offset,
            name=node.name,
            args=[a.arg for a in node.args.args],
            body=[self.visit(s) for s in node.body],
            is_local=True # Default to local, analyzer will adjust
        )

    def visit_Return(self, node: ast.Return) -> ir.IRReturnStatement:
        return ir.IRReturnStatement(
            lineno=node.lineno,
            col_offset=node.col_offset,
            value=self.visit(node.value) if node.value else None
        )

    def visit_If(self, node: ast.If) -> ir.IRIfStatement:
        return ir.IRIfStatement(
            lineno=node.lineno,
            col_offset=node.col_offset,
            condition=self.visit(node.test),
            then_block=[self.visit(s) for s in node.body],
            else_block=[self.visit(s) for s in node.orelse] if node.orelse else None
        )

    def visit_While(self, node: ast.While) -> ir.IRWhileStatement:
        return ir.IRWhileStatement(
            lineno=node.lineno,
            col_offset=node.col_offset,
            condition=self.visit(node.test),
            body=[self.visit(s) for s in node.body]
        )

    def visit_For(self, node: ast.For) -> ir.IRStatement:
        from transpiler.ast_utils import is_range_call, unpack_range_args
        if is_range_call(node.iter):
            start, stop, step = unpack_range_args(node.iter)
            return ir.IRForStatement(
                lineno=node.lineno,
                col_offset=node.col_offset,
                var=node.target.id if isinstance(node.target, ast.Name) else "_",
                start=self.visit(start),
                end=self.visit(stop),
                step=self.visit(step) if step else None,
                body=[self.visit(s) for s in node.body if self.visit(s) is not None]
            )
        
        # Generic for
        return ir.IRGenericForStatement(
            lineno=node.lineno,
            col_offset=node.col_offset,
            vars=[node.target.id] if isinstance(node.target, ast.Name) else [],
            iterator=self.visit(node.iter),
            body=[self.visit(s) for s in node.body if self.visit(s) is not None]
        )

    def visit_Pass(self, node: ast.Pass) -> ir.IRPassStatement:
        return ir.IRPassStatement(lineno=node.lineno)

    def visit_Break(self, node: ast.Break) -> ir.IRBreakStatement:
        return ir.IRBreakStatement(lineno=node.lineno)

    def visit_Continue(self, node: ast.Continue) -> ir.IRContinueStatement:
        return ir.IRContinueStatement(lineno=node.lineno)

    def visit_Lambda(self, node: ast.Lambda) -> ir.IRTableLiteral:
        # In Luau, lambdas can be represented as functions.
        # For IR, we'll keep them as a functional node if we had one, 
        # but for now let's just use a simplified FunctionDef-like structure or similar.
        # Actually, let's add IRFunctionDef support for lambdas.
        return ir.IRFunctionDef(
            lineno=node.lineno,
            col_offset=node.col_offset,
            name="", # Anonymous
            args=[a.arg for a in node.args.args],
            body=[ir.IRReturnStatement(value=self.visit(node.body))],
            is_local=True
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # We don't really need a dedicated IR node for imports if they just setup the symbol table,
        # but the analyzer might want to know about them.
        # For now, we'll just skip them or return None.
        return None

    def visit_Import(self, node: ast.Import) -> None:
        return None
