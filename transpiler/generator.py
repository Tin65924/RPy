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

    def generate(self, module: ir.IRModule, module_name: str = "unknown_module") -> last.Block:
        self.module_name = module_name
        return self.visit(module)

    def visit(self, node: ir.IRNode) -> Any:
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def _visit_block(self, nodes: List[ir.IRStatement]) -> List[last.Statement]:
        results = []
        for n in nodes:
            res = self.visit(n)
            if res is not None:
                results.append(res)
        return results

    def visit_IRModule(self, node: ir.IRModule) -> last.Block:
        return last.Block(body=self._visit_block(node.body))

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
            "NotEq": "~=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=", "And": "and", "Or": "or",
            "Concat": ".."
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
            type_ann = node.value.inferred_type if self.flags.typed else None
            return last.LocalAssign(name=target.name, value=value, type_annotation=type_ann)
        
        return last.Assignment(target=target, value=value)

    def visit_IRPersistentAssign(self, node: ir.IRPersistentAssign) -> last.Statement:
        target = self.visit(node.target)
        value = self.visit(node.value)
        
        # Ensure it's a simple variable assignment
        if not isinstance(target, last.Variable):
            return last.Assignment(target=target, value=value)
            
        var_name = target.name
        self._declared_vars.add(var_name)
        
        # We need a unique stable key for this variable: module_name:var_name
        import hashlib
        module_name = getattr(self, "module_name", "unknown_module")
        state_key = f"{module_name}:{var_name}"
        hash_key = hashlib.md5(state_key.encode()).hexdigest()[:8]
        full_key = f"{var_name}_{hash_key}"
        
        results = []
        # _G.__rpy_state = _G.__rpy_state or {}
        results.append(last.Assignment(
            target=last.Variable("_G.__rpy_state"),
            value=last.BinaryOperation(left=last.Variable("_G.__rpy_state"), operator="or", right=last.TableLiteral())
        ))
        
        # local var = _G.__rpy_state["key"] or value
        state_acc = last.IndexOperation(receiver=last.Variable("_G.__rpy_state"), index=last.Literal(full_key))
        init_val = last.BinaryOperation(left=state_acc, operator="or", right=value)
        results.append(last.LocalAssign(name=var_name, value=init_val))
        
        # _G.__rpy_state["key"] = var
        results.append(last.Assignment(target=state_acc, value=target))
        
        return last.Block(results)

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef) -> last.Node:
        return last.FunctionDef(
            name=node.name,
            args=node.args,
            body=self._visit_block(node.body),
            is_local=node.is_local,
            is_method=node.is_method,
            arg_types=node.arg_types if self.flags.typed else [],
            return_type=node.return_type if self.flags.typed else None
        )

    def visit_IRLambda(self, node: ir.IRLambda) -> last.Lambda:
        return last.Lambda(
            args=node.args,
            body=self._visit_block(node.body),
            arg_types=node.arg_types if self.flags.typed else [],
            return_type=node.return_type if self.flags.typed else None
        )

    def visit_IRIfStatement(self, node: ir.IRIfStatement) -> last.IfStatement:
        return last.IfStatement(
            condition=self.visit(node.condition),
            then_block=self._visit_block(node.then_block),
            else_block=self._visit_block(node.else_block) if node.else_block else None
        )

    def visit_IRWhileStatement(self, node: ir.IRWhileStatement) -> last.WhileStatement:
        return last.WhileStatement(
            condition=self.visit(node.condition),
            body=self._visit_block(node.body)
        )

    def visit_IRGenericForStatement(self, node: ir.IRGenericForStatement) -> last.GenericForStatement:
        return last.GenericForStatement(
            vars=node.vars,
            iterator=self.visit(node.iterator),
            body=self._visit_block(node.body),
            var_types=node.var_types if self.flags.typed else []
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
            body=self._visit_block(node.body)
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

    def visit_IRClassDef(self, node: ir.IRClassDef) -> last.Node:
        # Emit: type ClassName = { prop: Type ... }
        # local ClassName = {}; function ClassName.new() ... end
        class_name = node.name
        
        results = []
        
        if self.flags.typed and node.properties:
            props_str = ", ".join([f"{k}: {v}" for k, v in node.properties.items()])
            results.append(last.Comment(f"type {class_name} = {{ {props_str} }}"))
            # Note: last.Comment is a bit of a hack here, we should ideally have last.TypeAlias
            # but for v0.7.0 this is a safe visual separator/documentation
        
        header = last.LocalAssign(name=class_name, value=last.TableLiteral())
        results.append(header)
        
        methods = [m for m in node.body if isinstance(m, ir.IRFunctionDef)]
        for m in methods:
            m_copy = last.FunctionDef(
                name=f"{class_name}.{m.name}",
                # ... 
                args=m.args,
                body=self._visit_block(m.body),
                is_local=False,
                arg_types=m.arg_types if self.flags.typed else [],
                return_type=m.return_type if self.flags.typed else None
            )
            results.append(m_copy)
            
        return last.Block(results)

    def visit_IRComment(self, node: ir.IRComment) -> last.Comment:
        return last.Comment(text=node.text)

    def visit_IRImport(self, node: ir.IRImport) -> last.Statement:
        # Example: import module_foo as foo
        # Luau: local foo = _G.__rpy_require("workspace/module_foo")
        
        # We need absolute string path relative to project root
        # In Python: import serverscriptservice.main -> "serverscriptservice/main"
        module_path = node.module.replace(".", "/")
        alias_name = node.alias or node.module.split(".")[-1]
        
        # Build requirement call
        req_call = last.FunctionCall(
            func=last.Variable("_G.__rpy_require" if not self.flags.shared_runtime else "require"),
            args=[last.Literal(module_path)]
        )
        return last.LocalAssign(name=alias_name, value=req_call)

    def visit_IRImportFrom(self, node: ir.IRImportFrom) -> last.Statement:
        # Example: from x.y import z as w
        # Luau: local _mod = _G.__rpy_require("x/y"); local w = _mod.z
        
        # Resolve to a normalized string path. The dependency graph handles
        # relative imports mapping to disk, but `generator.py` needs to emit
        # the absolute string path relative to the active Roblox roots.
        
        # If the emitter is currently in `workspace/scripts/test.py`
        # and has `from .. import config`, `node.module` comes directly
        # from the IR. The parser should already have normalized it, but we
        # ensure it's a flat absolute '/' path for `__rpy_require`. 
        module_path = node.module.replace(".", "/")
        
        results = []
        mod_var = f"_module_{node.module.replace('.', '_')}"
        
        # Require the module once
        req_call = last.FunctionCall(
            func=last.Variable("_G.__rpy_require" if not self.flags.shared_runtime else "require"),
            args=[last.Literal(module_path)]
        )
        results.append(last.LocalAssign(name=mod_var, value=req_call))
        
        # Extract imported names
        for i, name in enumerate(node.names):
            alias = node.aliases[i] or name
            prop_acc = last.IndexOperation(
                receiver=last.Variable(mod_var),
                index=last.Literal(name)
            )
            results.append(last.LocalAssign(name=alias, value=prop_acc))
            
        return last.Block(results)

    def generic_visit(self, node: ir.IRNode) -> Any:
        raise UnsupportedFeatureError(f"Node {type(node).__name__} unsupported in Luau generation")

    def _print_node(self, node: last.Node) -> str:
        printer = LuauPrinter()
        return printer.print_node(node)

def generate(result: TransformResult, flags: CompilerFlags, module_name: str = "unknown_module") -> GenerateResult:
    gen = IRToLuauGenerator(flags)
    luau_ast = gen.generate(result.ir_module, module_name)
    printer = LuauPrinter()
    code = printer.print_node(luau_ast)
    
    if not flags.no_runtime:
        snippets = get_used_snippets(gen.runtime_used)
        header = "-- Generated by RPy — do not edit manually\n"
        code = header + (snippets + "\n\n" if snippets else "") + code
        
    return GenerateResult(code=code, runtime_helpers=gen.runtime_used)
