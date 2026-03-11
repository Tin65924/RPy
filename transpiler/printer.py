"""
transpiler/printer.py — Serializes the Luau AST into source code.
"""

from __future__ import annotations
from typing import Any
from transpiler import luau_ast as last

class LuauPrinter:
    def __init__(self, indent_size: int = 4) -> None:
        self.indent_size = indent_size
        self.indent_level = 0

    def indent(self, text: str) -> str:
        prefix = " " * (self.indent_size * self.indent_level)
        return "\n".join(prefix + line if line.strip() else line for line in text.splitlines())

    def visit(self, node: Any) -> str:
        if node is None: return "nil"
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: Any) -> str:
        raise NotImplementedError(f"No visitor for {node.__class__.__name__}")

    def print_node(self, node: last.Node) -> str:
        return self.visit(node)

    # --- Expressions ---

    def visit_Variable(self, node: last.Variable) -> str:
        return node.name

    def visit_Literal(self, node: last.Literal) -> str:
        v = node.value
        if v is None: return "nil"
        if v is True: return "true"
        if v is False: return "false"
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            return f'"{escaped}"'
        return str(v)

    def visit_BinaryOperation(self, node: last.BinaryOperation) -> str:
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} {node.operator} {right})"

    def visit_UnaryOperation(self, node: last.UnaryOperation) -> str:
        operand = self.visit(node.operand)
        return f"({node.operator}{operand})"

    def visit_FunctionCall(self, node: last.FunctionCall) -> str:
        func = self.visit(node.func)
        args = [self.visit(a) for a in node.args]
        return f"{func}({', '.join(args)})"

    def visit_MethodCall(self, node: last.MethodCall) -> str:
        receiver = self.visit(node.receiver)
        args = [self.visit(a) for a in node.args]
        return f"{receiver}:{node.method}({', '.join(args)})"

    def visit_IndexOperation(self, node: last.IndexOperation) -> str:
        receiver = self.visit(node.receiver)
        index = self.visit(node.index)
        return f"{receiver}[{index}]"

    def visit_TableLiteral(self, node: last.TableLiteral) -> str:
        parts = [self.visit(e) for e in node.elements]
        for name, val in node.fields:
            parts.append(f"{name} = {self.visit(val)}")
        return "{" + ", ".join(parts) + "}"

    def visit_Lambda(self, node: last.Lambda) -> str:
        # Handle argument types
        args_with_types = []
        for i, arg in enumerate(node.args):
            type_ann = node.arg_types[i] if i < len(node.arg_types) else None
            if type_ann:
                args_with_types.append(f"{arg}: {type_ann}")
            else:
                args_with_types.append(arg)
        
        args_str = ", ".join(args_with_types)
        ret_ann = f": {node.return_type}" if node.return_type else ""
        
        header = f"function({args_str}){ret_ann}"
        self.indent_level += 1
        body_lines = [self.indent(self.visit(stmt)) for stmt in node.body]
        self.indent_level -= 1
        return header + "\n" + "\n".join(body_lines) + f"\n{self.indent('end')}"

    # --- Statements ---

    def visit_LocalAssign(self, node: last.LocalAssign) -> str:
        val_str = f" = {self.visit(node.value)}" if node.value else ""
        type_str = f": {node.type_annotation}" if node.type_annotation else ""
        return f"local {node.name}{type_str}{val_str}"

    def visit_Assignment(self, node: last.Assignment) -> str:
        target = self.visit(node.target)
        value = self.visit(node.value)
        return f"{target} = {value}"

    def visit_IfStatement(self, node: last.IfStatement) -> str:
        cond = self.visit(node.condition)
        lines = [f"if {cond} then"]
        self.indent_level += 1
        lines.extend([self.indent(self.visit(s)) for s in node.then_block])
        self.indent_level -= 1
        
        for e_cond, e_body in node.elif_blocks:
            lines.append(self.indent(f"elseif {self.visit(e_cond)} then"))
            self.indent_level += 1
            lines.extend([self.indent(self.visit(s)) for s in e_body])
            self.indent_level -= 1
            
        if node.else_block:
            lines.append(self.indent("else"))
            self.indent_level += 1
            lines.extend([self.indent(self.visit(s)) for s in node.else_block])
            self.indent_level -= 1
            
        lines.append(self.indent("end"))
        return "\n".join(lines)

    def visit_WhileStatement(self, node: last.WhileStatement) -> str:
        cond = self.visit(node.condition)
        self.indent_level += 1
        body_lines = [self.indent(self.visit(s)) for s in node.body]
        self.indent_level -= 1
        return f"while {cond} do\n" + "\n".join(body_lines) + f"\n{self.indent('end')}"

    def visit_ForStatement(self, node: last.ForStatement) -> str:
        start, end = self.visit(node.start), self.visit(node.end)
        step_str = f", {self.visit(node.step)}" if node.step else ""
        self.indent_level += 1
        body_lines = [self.indent(self.visit(s)) for s in node.body]
        self.indent_level -= 1
        return f"for {node.var} = {start}, {end}{step_str} do\n" + "\n".join(body_lines) + f"\n{self.indent('end')}"

    def visit_GenericForStatement(self, node: last.GenericForStatement) -> str:
        vars_with_types = []
        for i, v in enumerate(node.vars):
            type_ann = node.var_types[i] if i < len(node.var_types) else None
            if type_ann:
                vars_with_types.append(f"{v}: {type_ann}")
            else:
                vars_with_types.append(v)
        
        vars_str = ", ".join(vars_with_types)
        iterator = self.visit(node.iterator)
        self.indent_level += 1
        body_lines = [self.indent(self.visit(s)) for s in node.body]
        self.indent_level -= 1
        return f"for {vars_str} in {iterator} do\n" + "\n".join(body_lines) + f"\n{self.indent('end')}"

    def visit_FunctionDef(self, node: last.FunctionDef) -> str:
        prefix = "local " if node.is_local else ""
        name = node.name
        
        # Handle argument types
        args_with_types = []
        for i, arg in enumerate(node.args):
            type_ann = node.arg_types[i] if i < len(node.arg_types) else None
            if type_ann:
                args_with_types.append(f"{arg}: {type_ann}")
            else:
                args_with_types.append(arg)
        
        args_str = ", ".join(args_with_types)
        ret_ann = f": {node.return_type}" if node.return_type else ""
        
        self.indent_level += 1
        body_lines = [self.indent(self.visit(s)) for s in node.body]
        self.indent_level -= 1
        return f"{prefix}function {name}({args_str}){ret_ann}\n" + "\n".join(body_lines) + f"\n{self.indent('end')}"

    def visit_ReturnStatement(self, node: last.ReturnStatement) -> str:
        return f"return {self.visit(node.value)}" if node.value else "return"

    def visit_BreakStatement(self, node: last.BreakStatement) -> str:
        return "break"

    def visit_ContinueStatement(self, node: last.ContinueStatement) -> str:
        return "continue"

    def visit_PassStatement(self, node: last.PassStatement) -> str:
        return "-- pass"

    def visit_Comment(self, node: last.Comment) -> str:
        return f"-- {node.text}"

    def _classify_stmt(self, stmt: Any) -> str:
        """Classifies a statement for visual grouping in the output."""
        if isinstance(stmt, (last.LocalAssign, last.Assignment)):
            return "DECL"
        if isinstance(stmt, last.FunctionDef):
            return "FUNC"
        if isinstance(stmt, (last.IfStatement, last.WhileStatement, last.ForStatement, last.GenericForStatement)):
            return "LOGIC"
        if isinstance(stmt, (last.FunctionCall, last.MethodCall, last.ReturnStatement, last.BreakStatement, last.ContinueStatement)):
            return "EXEC"
        if isinstance(stmt, last.Comment):
            # Try to keep comments with the code they describe
            return "COMMENT"
        return "MISC"

    def visit_Block(self, node: last.Block) -> str:
        lines = []
        prev_kind = None
        for stmt in node.body:
            kind = self._classify_stmt(stmt)
            # Add a blank line when switching kinds, except for certain cases
            if prev_kind and kind != prev_kind:
                # Don't add blank lines before comments if they follow declarations
                if not (kind == "COMMENT" and prev_kind == "DECL"):
                    lines.append("")
            
            lines.append(self.visit(stmt))
            prev_kind = kind
            
        return "\n".join(lines)
