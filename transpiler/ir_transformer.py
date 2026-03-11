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

    def _get_type_str(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None: return None
        if isinstance(node, ast.Name): return node.id
        if isinstance(node, ast.Constant) and node.value is None: return "nil"
        if isinstance(node, ast.Attribute):
            return f"{self._get_type_str(node.value)}.{node.attr}"
        return "any"

    def _visit_body(self, nodes: List[ast.stmt]) -> List[ir.IRStatement]:
        results = []
        for n in nodes:
            res = self.visit(n)
            if res is None: continue
            if isinstance(res, list):
                results.extend(res)
            else:
                results.append(res)
        return results

    def generic_visit(self, node: ast.AST) -> Any:
        raise UnsupportedFeatureError(
            node_name(node),
            line=getattr(node, "lineno", None),
            col=getattr(node, "col_offset", None)
        )

    def visit_Module(self, node: ast.Module) -> ir.IRModule:
        return ir.IRModule(lineno=1, body=self._visit_body(node.body))

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
        return ir.IRBinaryOperation(
            lineno=node.lineno,
            col_offset=node.col_offset,
            left=self.visit(node.left),
            operator=type(node.op).__name__,
            right=self.visit(node.right)
        )

    def visit_Compare(self, node: ast.Compare) -> ir.IRBinaryOperation:
        # Simple implementation for single comparison
        return ir.IRBinaryOperation(
            lineno=node.lineno,
            col_offset=node.col_offset,
            left=self.visit(node.left),
            operator=type(node.ops[0]).__name__,
            right=self.visit(node.comparators[0])
        )

    def visit_BoolOp(self, node: ast.BoolOp) -> ir.IRBinaryOperation:
        # x and y and z -> (x and (y and z))
        res = self.visit(node.values[-1])
        op_name = type(node.op).__name__
        for i in range(len(node.values) - 2, -1, -1):
            res = ir.IRBinaryOperation(
                lineno=node.lineno,
                left=self.visit(node.values[i]),
                operator=op_name,
                right=res
            )
        return res # type: ignore

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

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ir.IRExpression:
        if not node.values:
            return ir.IRLiteral(value="", lineno=node.lineno, col_offset=node.col_offset)
        
        # Build a concatenation chain: (val1 .. (val2 .. val3))
        res = self.visit(node.values[-1])
        if isinstance(node.values[-1], ast.FormattedValue):
            res = ir.IRFunctionCall(
                func=ir.IRVariable(name="str"),
                args=[res],
                lineno=node.lineno,
                col_offset=node.col_offset
            )

        for i in range(len(node.values) - 2, -1, -1):
            val = self.visit(node.values[i])
            if isinstance(node.values[i], ast.FormattedValue):
                val = ir.IRFunctionCall(
                    func=ir.IRVariable(name="str"),
                    args=[val],
                    lineno=node.lineno,
                    col_offset=node.col_offset
                )
            
            res = ir.IRBinaryOperation(
                lineno=node.lineno,
                left=val,
                operator="Concat",
                right=res
            )
        return res

    def visit_FormattedValue(self, node: ast.FormattedValue) -> ir.IRExpression:
        return self.visit(node.value)

    # --- Statements ---

    def visit_Assign(self, node: ast.Assign) -> ir.IRStatement:
        # Capture all targets
        ir_targets = [self.visit(t) for t in node.targets]
        ir_value = self.visit(node.value)
        
        # Check if the assignment is wrapped in a persistent call: x = persistent(0)
        is_persistent = False
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "persistent":
            is_persistent = True
            if node.value.args:
                ir_value = self.visit(node.value.args[0])
            else:
                ir_value = ir.IRLiteral(value=None)
                
        if is_persistent:
            return ir.IRPersistentAssign(
                lineno=node.lineno,
                col_offset=node.col_offset,
                target=ir_targets[0],
                value=ir_value
            )
        
        # Simple implementation for now, assuming single target (multiple assignments can be split)
        return ir.IRAssignment(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=ir_targets[0],
            value=ir_value,
            is_local=True # The analyzer will refine this if needed, but default to local
        )
        
    def visit_AnnAssign(self, node: ast.AnnAssign) -> ir.IRStatement:
        target = self.visit(node.target)
        value = self.visit(node.value) if node.value else ir.IRLiteral(value=None)
        
        ann_str = self._get_type_str(node.annotation)
        # We can detect x: persistent = 0
        if ann_str == "persistent":
            return ir.IRPersistentAssign(
                lineno=node.lineno,
                col_offset=node.col_offset,
                target=target,
                value=value
            )
            
        return ir.IRAssignment(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=target,
            value=value,
            is_local=True
        )

    def visit_AugAssign(self, node: ast.AugAssign) -> ir.IRStatement:
        # x += 1 -> x = x + 1
        target = self.visit(node.target)
        value = self.visit(node.value)
        op_name = type(node.op).__name__
        
        return ir.IRAssignment(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=target,
            value=ir.IRBinaryOperation(
                lineno=node.lineno,
                left=target,
                operator=op_name,
                right=value
            ),
            is_local=False # Usually already declared
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
            arg_types=[self._get_type_str(a.annotation) for a in node.args.args],
            return_type=self._get_type_str(node.returns),
            body=self._visit_body(node.body),
            is_local=True
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
            then_block=self._visit_body(node.body),
            else_block=self._visit_body(node.orelse) if node.orelse else None
        )

    def visit_While(self, node: ast.While) -> ir.IRWhileStatement:
        return ir.IRWhileStatement(
            lineno=node.lineno,
            col_offset=node.col_offset,
            condition=self.visit(node.test),
            body=self._visit_body(node.body)
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
                body=self._visit_body(node.body)
            )
        
        # Generic for
        loop_vars = []
        if isinstance(node.target, ast.Name):
            loop_vars = [node.target.id]
        elif isinstance(node.target, (ast.Tuple, ast.List)):
            loop_vars = [elt.id for elt in node.target.elts if isinstance(elt, ast.Name)]

        return ir.IRGenericForStatement(
            lineno=node.lineno,
            col_offset=node.col_offset,
            vars=loop_vars,
            iterator=self.visit(node.iter),
            body=self._visit_body(node.body)
        )

    def visit_Pass(self, node: ast.Pass) -> ir.IRPassStatement:
        return ir.IRPassStatement(lineno=node.lineno)

    def visit_Break(self, node: ast.Break) -> ir.IRBreakStatement:
        return ir.IRBreakStatement(lineno=node.lineno)

    def visit_Continue(self, node: ast.Continue) -> ir.IRContinueStatement:
        return ir.IRContinueStatement(lineno=node.lineno)

    def visit_Lambda(self, node: ast.Lambda) -> ir.IRLambda:
        return ir.IRLambda(
            lineno=node.lineno,
            col_offset=node.col_offset,
            args=[a.arg for a in node.args.args],
            arg_types=[self._get_type_str(a.annotation) for a in node.args.args],
            body=[ir.IRReturnStatement(value=self.visit(node.body))],
            return_type=None # Lambda return type is harder to extract from AST easily
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> ir.IRClassDef:
        return ir.IRClassDef(
            lineno=node.lineno,
            col_offset=node.col_offset,
            name=node.name,
            bases=[self.visit(b) for b in node.bases if isinstance(b, (ast.Name, ast.Attribute))],
            body=self._visit_body(node.body)
        )

    def visit_Import(self, node: ast.Import) -> List[ir.IRImport]:
        return [
            ir.IRImport(
                lineno=node.lineno,
                col_offset=node.col_offset,
                module=alias.name,
                alias=alias.asname
            )
            for alias in node.names
        ]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ir.IRImportFrom:
        return ir.IRImportFrom(
            lineno=node.lineno,
            col_offset=node.col_offset,
            module=node.module or "",
            names=[alias.name for alias in node.names],
            aliases=[alias.asname for alias in node.names],
            level=node.level
        )
