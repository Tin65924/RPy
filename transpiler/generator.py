"""
transpiler/generator.py — The core Luau code generator (IR-based).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set
from transpiler import ir
from transpiler import luau_ast as last
from transpiler.errors import UnsupportedFeatureError
from transpiler.printer import LuauPrinter
from transpiler.flags import CompilerFlags
from transpiler.transformer import TransformResult
from transpiler.runtime_snippets import get_used_snippets

@dataclass
class GenerateResult:
    code: str
    runtime_helpers: Set[str]

class IRToLuauGenerator:
    def __init__(self, flags: CompilerFlags):
        self._declared_vars = set()
        self.flags = flags
        self.runtime_used = set()

    def generate(self, module: ir.IRModule) -> last.Block:
        return self.visit(module)

    def visit(self, node: ir.IRNode) -> Any:
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def visit_IRModule(self, node: ir.IRModule) -> last.Block:
        return last.Block(body=[self.visit(s) for s in node.body if self.visit(s) is not None])

    # --- Expressions ---

    def visit_IRLiteral(self, node: ir.IRLiteral) -> last.Literal:
        return last.Literal(value=node.value)

    def visit_IRVariable(self, node: ir.IRVariable) -> last.Variable:
        remap = {"print": "print", "len": "py_len", "str": "py_str", "int": "py_int", "float": "py_float",
                 "abs": "math.abs", "min": "math.min", "max": "math.max", "type": "typeof"}
        name = remap.get(node.name, node.name)
        if name.startswith("py_"):
            self.runtime_used.add(name[3:])
        return last.Variable(name=name)

    def visit_IRBinaryOperation(self, node: ir.IRBinaryOperation) -> last.BinaryOperation:
        op_map = {
            "Add": "+", "Sub": "-", "Mult": "*", "Div": "/",
            "Mod": "%", "Pow": "^", "BitAnd": "&", "BitOr": "|",
            "BitXor": "~", "LShift": "<<", "RShift": ">>", "Eq": "==",
            "NotEq": "~=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=", "And": "and", "Or": "or"
        }
        luau_op = op_map.get(node.operator, node.operator)
        return last.BinaryOperation(
            left=self.visit(node.left),
            operator=luau_op,
            right=self.visit(node.right)
        )

    def visit_IRUnaryOperation(self, node: ir.IRUnaryOperation) -> last.UnaryOperation:
        op_map = {"USub": "-", "UAdd": "+", "Not": "not ", "Invert": "~"}
        return last.UnaryOperation(
            operator=op_map.get(node.operator, node.operator),
            operand=self.visit(node.operand)
        )

    def visit_IRFunctionCall(self, node: ir.IRFunctionCall) -> last.FunctionCall:
        return last.FunctionCall(
            func=self.visit(node.func),
            args=[self.visit(arg) for arg in node.args]
        )

    def visit_IRMethodCall(self, node: ir.IRMethodCall) -> last.Node:
        receiver = self.visit(node.receiver)
        args = [self.visit(arg) for arg in node.args]
        
        if node.call_style == ir.CallStyle.DOT:
            # We need to manually construct the property access for dot calls
            # because last.Variable(f"{receiver}.{method}") is fragile
            return last.FunctionCall(
                func=last.Variable(f"{self._print_node(receiver)}.{node.method}"),
                args=args
            )
        else:
            return last.MethodCall(
                receiver=receiver,
                method=node.method,
                args=args
            )

    def visit_IRPropertyAccess(self, node: ir.IRPropertyAccess) -> last.Variable:
        receiver = self.visit(node.receiver)
        return last.Variable(name=f"{self._print_node(receiver)}.{node.property}")

    def visit_IRTableLiteral(self, node: ir.IRTableLiteral) -> last.TableLiteral:
        return last.TableLiteral(
            elements=[self.visit(e) for e in node.elements],
            fields=[(k, self.visit(v)) for k, v in node.fields]
        )

    def visit_IRIndexOperation(self, node: ir.IRIndexOperation) -> last.IndexOperation:
        return last.IndexOperation(
            receiver=self.visit(node.receiver),
            index=self.visit(node.index)
        )

    # --- Statements ---

    def visit_IRAssignment(self, node: ir.IRAssignment) -> last.Statement:
        target = self.visit(node.target)
        value = self.visit(node.value)
        
        # We use node.is_local OR our own internal tracker as a safety net
        should_be_local = node.is_local
        if isinstance(target, last.Variable):
            if target.name in self._declared_vars or "." in target.name:
                should_be_local = False
            else:
                self._declared_vars.add(target.name)
        else:
            should_be_local = False

        if should_be_local:
            return last.LocalAssign(name=target.name, value=value)
        
        return last.Assignment(target=target, value=value)

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef) -> last.Node:
        if not node.name:
            # Anonymous function (Lambda)
            return last.Lambda(
                args=node.args,
                body=[self.visit(s) for s in node.body if self.visit(s) is not None]
            )
        return last.FunctionDef(
            name=node.name,
            args=node.args,
            body=[self.visit(s) for s in node.body if self.visit(s) is not None],
            is_local=node.is_local,
            is_method=node.is_method
        )

    def visit_IRIfStatement(self, node: ir.IRIfStatement) -> last.IfStatement:
        return last.IfStatement(
            condition=self.visit(node.condition),
            then_block=[self.visit(s) for s in node.then_block if self.visit(s) is not None],
            else_block=[self.visit(s) for s in node.else_block if self.visit(s) is not None] if node.else_block else None
        )

    def visit_IRWhileStatement(self, node: ir.IRWhileStatement) -> last.WhileStatement:
        return last.WhileStatement(
            condition=self.visit(node.condition),
            body=[self.visit(s) for s in node.body if self.visit(s) is not None]
        )

    def visit_IRGenericForStatement(self, node: ir.IRGenericForStatement) -> last.GenericForStatement:
        return last.GenericForStatement(
            vars=node.vars,
            iterator=self.visit(node.iterator),
            body=[self.visit(s) for s in node.body if self.visit(s) is not None]
        )

    def visit_IRForStatement(self, node: ir.IRForStatement) -> last.ForStatement:
        # Python range(stop) is exclusive, Luau for is inclusive.
        # stop -> stop - 1
        stop_val = self.visit(node.end)
        stop_expr = last.BinaryOperation(
            left=stop_val,
            operator="-",
            right=last.Literal(1)
        )
        return last.ForStatement(
            var=node.var,
            start=self.visit(node.start),
            end=stop_expr,
            step=self.visit(node.step) if node.step else None,
            body=[self.visit(s) for s in node.body if self.visit(s) is not None]
        )

    def visit_IRReturnStatement(self, node: ir.IRReturnStatement) -> last.ReturnStatement:
        return last.ReturnStatement(
            value=self.visit(node.value) if node.value else None
        )

    def visit_IRBreakStatement(self, node: ir.IRBreakStatement) -> last.BreakStatement:
        return last.BreakStatement()

    def visit_IRContinueStatement(self, node: ir.IRContinueStatement) -> last.ContinueStatement:
        return last.ContinueStatement()

    def visit_IRPassStatement(self, node: ir.IRPassStatement) -> None:
        return None

    def visit_IRComment(self, node: ir.IRComment) -> last.Comment:
        return last.Comment(text=node.text)

    def generic_visit(self, node: ir.IRNode) -> Any:
        raise UnsupportedFeatureError(f"Node {type(node).__name__} unsupported in Luau generation")

    def _print_node(self, node: last.Node) -> str:
        printer = LuauPrinter()
        return printer.print_node(node)

def generate(result: TransformResult, flags: CompilerFlags) -> GenerateResult:
    gen = IRToLuauGenerator(flags)
    luau_ast = gen.generate(result.ir_module)
    printer = LuauPrinter()
    code = printer.print_node(luau_ast)
    
    if not flags.no_runtime:
        snippets = get_used_snippets(gen.runtime_used)
        header = "-- Generated by RPy — do not edit manually\n"
        code = header + (snippets + "\n\n" if snippets else "") + code
        
    return GenerateResult(code=code, runtime_helpers=gen.runtime_used)
