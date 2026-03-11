"""
transpiler/escape_analysis.py — Tracks value flow to determine variable lifetimes.
"""

from __future__ import annotations
from typing import Dict, Set, List, Optional
from transpiler import ir
from enum import Enum, auto

class EscapeState(Enum):
    LOCAL = auto()       # Never escapes the function. Safe for optimization (SRA, closure elimination).
    ARG_ESC = auto()     # Passed as an argument to a function. Might be mutated, unsafe for SRA.
    GLOBAL_ESC = auto()  # Returned from the function, assigned to a global, or captured by escaping closure.

class ValueNode:
    def __init__(self, name: str):
        self.name = name
        self.state: EscapeState = EscapeState.LOCAL
        self.escapes_to: Set[str] = set() # What other names hold a reference to this?
        
    def __repr__(self):
        return f"<ValueNode {self.name} : {self.state.name}>"

class EscapeAnalyzer:
    def __init__(self):
        self.nodes: Dict[str, ValueNode] = {}
        
    def get_or_create_node(self, name: str) -> ValueNode:
        if name not in self.nodes:
            self.nodes[name] = ValueNode(name)
        return self.nodes[name]

    def mark_escape(self, name: str, state: EscapeState):
        node = self.get_or_create_node(name)
        # State transitions: LOCAL -> ARG_ESC -> GLOBAL_ESC
        # We only escalate the state.
        if state == EscapeState.GLOBAL_ESC:
            node.state = EscapeState.GLOBAL_ESC
        elif state == EscapeState.ARG_ESC and node.state == EscapeState.LOCAL:
            node.state = EscapeState.ARG_ESC
            
    def add_flow(self, source: str, destination: str):
        """source flows into destination: dest = source"""
        src_node = self.get_or_create_node(source)
        src_node.escapes_to.add(destination)

    def analyze_module(self, module: ir.IRModule):
        self._analyze_block(module.body)
        self._propagate_escapes()

    def _analyze_block(self, block: List[ir.IRStatement]):
        for stmt in block:
            if isinstance(stmt, ir.IRAssignment):
                if isinstance(stmt.target, ir.IRVariable):
                    self.get_or_create_node(stmt.target.name) # Ensure node exists
                    if isinstance(stmt.value, ir.IRTableLiteral):
                        # The table itself doesn't "flow" from an expression, 
                        # but elements inside it flow into the target.
                        self._analyze_expr(stmt.value, stmt.target.name)
                    else:
                        self._analyze_expr(stmt.value, stmt.target.name)
                elif isinstance(stmt.target, ir.IRPropertyAccess):
                    # Assigning a value to a property of an object means it flows into that object.
                    # e.g. obj.prop = val -> val flows into obj
                    if isinstance(stmt.target.receiver, ir.IRVariable):
                        self._analyze_expr(stmt.value, stmt.target.receiver.name)
            elif isinstance(stmt, ir.IRReturnStatement):
                if stmt.value:
                    if isinstance(stmt.value, ir.IRVariable):
                        self.mark_escape(stmt.value.name, EscapeState.GLOBAL_ESC)
                    else:
                        # Dummy destination for literal/complex returns that we still want to track
                        self._analyze_expr(stmt.value, "__return__")
                        self.mark_escape("__return__", EscapeState.GLOBAL_ESC)
            elif isinstance(stmt, ir.IRFunctionDef):
                # Analyze function body. If the function itself escapes, its captured variables escape.
                # For now, simplistic approach: just mark all closed-over vars as GLOBAL_ESC if function escapes.
                # A full closure analysis would build a sub-graph.
                self._analyze_block(stmt.body)
            elif isinstance(stmt, (ir.IRIfStatement, ir.IRWhileStatement, ir.IRForStatement)):
                # Control flow nodes don't inherently cause escapes, but their bodies might.
                if hasattr(stmt, 'then_block'):
                    self._analyze_block(stmt.then_block)
                    if stmt.else_block: self._analyze_block(stmt.else_block)
                if hasattr(stmt, 'body'):
                    self._analyze_block(stmt.body)
            elif isinstance(stmt, (ir.IRFunctionCall, ir.IRMethodCall)):
                 self._analyze_expr(stmt, None)

    def _analyze_expr(self, expr: ir.IRExpression, dest_name: Optional[str]):
        if isinstance(expr, ir.IRVariable):
            if dest_name and dest_name != expr.name:
                self.add_flow(expr.name, dest_name)
        elif isinstance(expr, (ir.IRFunctionCall, ir.IRMethodCall)):
            # All arguments passed to an unknown function might escape globally or as args.
            for arg in expr.args:
                if isinstance(arg, ir.IRVariable):
                    if isinstance(expr, ir.IRMethodCall) and expr.method in ("append", "insert"):
                        # If calling b.append(c), c flows into b
                        if isinstance(expr.receiver, ir.IRVariable):
                            self.add_flow(arg.name, expr.receiver.name)
                        else:
                            self.mark_escape(arg.name, EscapeState.ARG_ESC)
                    else:
                        self.mark_escape(arg.name, EscapeState.ARG_ESC)
                else:
                    self._analyze_expr(arg, None)
                    
            if isinstance(expr, ir.IRMethodCall):
                if isinstance(expr.receiver, ir.IRVariable):
                    # We don't mark the receiver as escaping just because we called a method on it.
                    # e.g., b.append(c) doesn't mean b escapes.
                    # But b.to_string() doesn't escape b either.
                    pass
                else:
                    self._analyze_expr(expr.receiver, None)
                    
        elif isinstance(expr, ir.IRTableLiteral):
            if dest_name:
                # The table is created and assigned to dest_name.
                # Elements placed inside the table flow into dest_name.
                for el in expr.elements:
                    if isinstance(el, ir.IRVariable):
                        self.add_flow(el.name, dest_name)
                    else:
                        # For constants or nested expressions inside the table
                        self._analyze_expr(el, dest_name)
                        
                for k, v in expr.fields:
                    if isinstance(v, ir.IRVariable):
                        self.add_flow(v.name, dest_name)
                    else:
                        self._analyze_expr(v, dest_name)
                        
        elif isinstance(expr, ir.IRPropertyAccess):
            # Getting a property `p.x` and assigning it to `a`.
            # We don't say `p` flows into `a`. We just say `p`'s field flows into `a`.
            # Since fields are often scalars, we treat property accesses as safe 
            # (they don't cause the receiver itself to escape).
            pass
            
        elif isinstance(expr, ir.IRBinaryOperation):
            self._analyze_expr(expr.left, dest_name)
            self._analyze_expr(expr.right, dest_name)
        elif isinstance(expr, ir.IRUnaryOperation):
            self._analyze_expr(expr.operand, dest_name)
        elif isinstance(expr, ir.IRPhi):
            for opt in expr.options.values():
                self._analyze_expr(opt, dest_name)
        elif hasattr(expr, "__dict__"):
             for v in expr.__dict__.values():
                 if isinstance(v, ir.IRExpression):
                     self._analyze_expr(v, dest_name)
                 elif isinstance(v, list):
                     for item in v:
                         if isinstance(item, ir.IRExpression):
                             self._analyze_expr(item, dest_name)

    def _propagate_escapes(self):
        """Propagates escape states through the value flow graph."""
        changed = True
        while changed:
            changed = False
            for src_name, src_node in self.nodes.items():
                if src_node.state == EscapeState.LOCAL: continue # Nothing to propagate
                
                for dest_name in src_node.escapes_to:
                    dest_node = self.nodes.get(dest_name)
                    if dest_node:
                        # Special case: If src is GLOBAL_ESC, then dest must also be GLOBAL_ESC?
                        # No, if src flows INTO dest (dest holds a ref TO src).
                        # Actually, if SRC flows into DEST, and DEST escapes, then SRC must escape!
                        # Our graph is: src.escapes_to.add(dest) -- "src flows into dest"
                        # So if DEST is GLOBAL_ESC, SRC must become GLOBAL_ESC.
                        if dest_node.state == EscapeState.GLOBAL_ESC and src_node.state != EscapeState.GLOBAL_ESC:
                            # Wait, we need to propagate BACKWARDS along the flow edges!
                            # If A -> B, and B escapes, A escapes.
                            pass
                            
        # Correct Propagation Logic (Backwards Propagation):
        # A flows into B means B holds a reference to A.
        # So if B escapes, A must also escape.
        changed = True
        while changed:
             changed = False
             for src_name, src_node in self.nodes.items():
                 for dest_name in src_node.escapes_to:
                     dest_node = self.nodes.get(dest_name)
                     if not dest_node: continue
                     
                     # If the container (dest) escapes, what it contains (src) also escapes.
                     if dest_node.state == EscapeState.GLOBAL_ESC and src_node.state != EscapeState.GLOBAL_ESC:
                         src_node.state = EscapeState.GLOBAL_ESC
                         changed = True
                     elif dest_node.state == EscapeState.ARG_ESC and src_node.state == EscapeState.LOCAL:
                         src_node.state = EscapeState.ARG_ESC
                         changed = True
