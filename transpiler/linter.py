"""
transpiler/linter.py — Stage 17: Roblox-specific static analysis.
"""

from transpiler import ir
from transpiler.diagnostics import manager, Severity
from typing import Optional, Set

class LinterPass:
    def __init__(self, diagnostics=None):
        self.diagnostics = diagnostics or manager

    def lint(self, node: ir.IRNode):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        visitor(node)

    def generic_visit(self, node: ir.IRNode):
        if hasattr(node, "__dict__"):
            for attr, value in node.__dict__.items():
                if isinstance(value, ir.IRNode):
                    self.lint(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ir.IRNode):
                            self.lint(item)

    def visit_IRFunctionCall(self, node: ir.IRFunctionCall):
        if isinstance(node.func, ir.IRVariable):
            name = node.func.name
            if name == "wait":
                self.diagnostics.warning(
                    "Legacy 'wait()' detected. Use 'task.wait()' for better performance and reliability.",
                    line=node.lineno, col=node.col_offset,
                    hint="task.wait() respects the 60Hz heartbeat and prevents throttling issues."
                )
            elif name == "spawn":
                self.diagnostics.warning(
                    "Legacy 'spawn()' detected. Use 'task.spawn()' for predictable execution order.",
                    line=node.lineno, col=node.col_offset,
                    hint="task.spawn() executes the thread immediately without the 0.03s delay."
                )
            elif name == "delay":
                self.diagnostics.warning(
                    "Legacy 'delay()' detected. Use 'task.delay()'.",
                    line=node.lineno, col=node.col_offset
                )
        self.generic_visit(node)

    def visit_IRVariable(self, node: ir.IRVariable):
        if node.name == "_G":
            self.diagnostics.warning(
                "Usage of global table '_G' detected. This is generally discouraged in Roblox.",
                line=node.lineno, col=node.col_offset,
                hint="Consider using ModuleScripts for shared state management."
            )
        elif node.name == "shared":
             self.diagnostics.warning(
                "Usage of 'shared' table detected. This is generally discouraged in Roblox.",
                line=node.lineno, col=node.col_offset,
                hint="Consider using ModuleScripts for shared state management."
            )

    def visit_IRModule(self, node: ir.IRModule):
        self.generic_visit(node)

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef):
        self.generic_visit(node)

    def visit_IRIfStatement(self, node: ir.IRIfStatement):
        self.generic_visit(node)

    def visit_IRWhileStatement(self, node: ir.IRWhileStatement):
        self.generic_visit(node)

    def visit_IRForStatement(self, node: ir.IRForStatement):
        self.generic_visit(node)

    def visit_IRGenericForStatement(self, node: ir.IRGenericForStatement):
        self.generic_visit(node)

def lint_ir(module: ir.IRModule):
    linter = LinterPass()
    linter.lint(module)
