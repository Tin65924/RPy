"""
transpiler/ir_optimizer.py — Recursive IR optimization passes.
"""

from __future__ import annotations
from transpiler import ir
from transpiler.cfg_builder import build_cfg
from transpiler.cfg_optimizer import optimize_cfg

class RecursiveIROptimizer:
    def optimize(self, node: ir.IRNode) -> ir.IRNode:
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ir.IRNode) -> ir.IRNode:
        if hasattr(node, "__dict__"):
            for attr, value in node.__dict__.items():
                if isinstance(value, ir.IRNode):
                    setattr(node, attr, self.optimize(value))
                elif isinstance(value, list):
                    new_list = []
                    for item in value:
                        if isinstance(item, ir.IRNode):
                            new_list.append(self.optimize(item))
                        else:
                            new_list.append(item)
                    setattr(node, attr, new_list)
        return node

    def _optimize_block(self, body: List[ir.IRStatement]) -> List[ir.IRStatement]:
        if not body:
            return []
            
        # 1. Recursively optimize children first (e.g. inner if/while)
        optimized_body = [self.optimize(s) for s in body]
        
        # 2. Apply CFG optimization to this block
        # We wrap it in a mock module for the builder
        mock_mod = ir.IRModule(body=optimized_body)
        graph = build_cfg(mock_mod)
        optimize_cfg(graph)
        result_mod = graph.reconstruct_module()
        
        return result_mod.body

    def visit_IRModule(self, node: ir.IRModule) -> ir.IRModule:
        node.body = self._optimize_block(node.body)
        return node

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef) -> ir.IRFunctionDef:
        node.body = self._optimize_block(node.body)
        return node

    def visit_IRIfStatement(self, node: ir.IRIfStatement) -> ir.IRIfStatement:
        node.then_block = self._optimize_block(node.then_block)
        if node.else_block:
            node.else_block = self._optimize_block(node.else_block)
        return node

    def visit_IRWhileStatement(self, node: ir.IRWhileStatement) -> ir.IRWhileStatement:
        node.body = self._optimize_block(node.body)
        return node

    def visit_IRForStatement(self, node: ir.IRForStatement) -> ir.IRForStatement:
        node.body = self._optimize_block(node.body)
        return node

def optimize_ir(module: ir.IRModule):
    optimizer = RecursiveIROptimizer()
    optimizer.optimize(module)
