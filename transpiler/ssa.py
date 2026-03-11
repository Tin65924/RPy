"""
transpiler/ssa.py — SSA Construction and Dominance Analysis.
"""

from __future__ import annotations
from typing import Dict, Set, List, Optional
from transpiler import cfg, ir

class DominatorAnalysis:
    def __init__(self, target_cfg: cfg.CFG):
        self.cfg = target_cfg
        self.idoms: Dict[int, Optional[int]] = {} # block_id -> idom_id
        self.dominators: Dict[int, Set[int]] = {} # block_id -> set of dominator_ids
        self.frontiers: Dict[int, Set[int]] = {} # block_id -> set of block_ids

    def run(self):
        self._compute_dominators()
        self._compute_idoms()
        self._compute_frontiers()

    def _compute_dominators(self):
        # Entry node
        entry_id = self.cfg.entry_block.id
        all_blocks = set(self.cfg.blocks.keys())
        
        self.dominators = {bid: all_blocks.copy() for bid in all_blocks}
        self.dominators[entry_id] = {entry_id}
        
        changed = True
        while changed:
            changed = False
            for bid in all_blocks:
                if bid == entry_id: continue
                
                block = self.cfg.blocks[bid]
                if not block.predecessors:
                    preds_doms = set()
                else:
                    it = iter(block.predecessors)
                    preds_doms = self.dominators[next(it).id].copy()
                    for p in it:
                        preds_doms.intersection_update(self.dominators[p.id])
                
                new_doms = {bid} | preds_doms
                if new_doms != self.dominators[bid]:
                    self.dominators[bid] = new_doms
                    changed = True

    def _compute_idoms(self):
        for bid, doms in self.dominators.items():
            if bid == self.cfg.entry_block.id:
                self.idoms[bid] = None
                continue
            
            # idom(n) is the dominator d such that d != n and d is dominated by all other dominators of n
            # i.e., it's the "closest" strict dominator.
            strict_doms = doms - {bid}
            for d in strict_doms:
                # Is d dominated by all other nodes in strict_doms?
                is_idom = True
                for other in strict_doms:
                    if d != other and other not in self.dominators[d]:
                        # other does not dominate d, so d cannot be the "closest" if other is closer
                        # Wait, d is idom if NO other strict dom of n is dominated by d.
                        pass # Thinking... 
                
            # Simpler idom check: d in strict_doms is idom if no other d' in strict_doms is dominated by d and d' dominates bid
            # Or just: idom(n) is the strict dominator with the largest Dominic number or depth.
            # Since our blocks are IDed, we can use the dom size as a heuristic if entry is small.
            # Best way: d is idom(n) if d dominates n, d != n, and for any d' that dominates n, d' != n, d' dominates d.
            
            idom = None
            max_dom_count = -1
            for d in strict_doms:
                if len(self.dominators[d]) > max_dom_count:
                    max_dom_count = len(self.dominators[d])
                    idom = d
            self.idoms[bid] = idom

    def _compute_frontiers(self):
        # DF(n) is the set of all nodes w such that n dominates a predecessor of w, but n does not strictly dominate w.
        for bid in self.cfg.blocks:
            self.frontiers[bid] = set()
            
        for bid, block in self.cfg.blocks.items():
            if len(block.predecessors) >= 2:
                for p in block.predecessors:
                    runner = p.id
                    while runner != self.idoms[bid] and runner is not None:
                        self.frontiers[runner].add(bid)
                        runner = self.idoms[runner]

class SSAConstructor:
    def __init__(self, target_cfg: cfg.CFG, analysis: DominatorAnalysis):
        self.cfg = target_cfg
        self.analysis = analysis
        self.var_versions: Dict[str, int] = {} # var_name -> latest_version
        self.var_stacks: Dict[str, List[str]] = {} # var_name -> stack of versioned_names
        self.phi_placed: Dict[str, Set[int]] = {} # var_name -> set of block_ids

    def construct(self):
        self._place_phis()
        
        # Build dominator tree children map for traversal
        self.dom_children: Dict[int, List[int]] = {}
        for bid, idom in self.analysis.idoms.items():
            if idom is not None:
                self.dom_children.setdefault(idom, []).append(bid)
                
        self._rename_vars(self.cfg.entry_block.id)

    def _place_phis(self):
        # 1. Collect all variable assignments
        defs: Dict[str, Set[int]] = {}
        for bid, block in self.cfg.blocks.items():
            for stmt in block.statements:
                if isinstance(stmt, ir.IRAssignment) and isinstance(stmt.target, ir.IRVariable):
                    defs.setdefault(stmt.target.name, set()).add(bid)
                    stmt.target.original_name = stmt.target.name # Tag original

        # 2. Iteratively place Phis
        for var_name, def_blocks in defs.items():
            w = list(def_blocks)
            while w:
                x = w.pop()
                for y in self.analysis.frontiers[x]:
                    if y not in self.phi_placed.get(var_name, set()):
                        # Place Phi in block Y for var_name
                        phi = ir.IRPhi(options={})
                        phi_stmt = ir.IRAssignment(
                            target=ir.IRVariable(name=var_name, original_name=var_name), 
                            value=phi
                        )
                        self.cfg.blocks[y].statements.insert(0, phi_stmt)
                        
                        self.phi_placed.setdefault(var_name, set()).add(y)
                        if y not in def_blocks:
                            w.append(y)

    def _rename_vars(self, bid: int):
        block = self.cfg.blocks[bid]
        pushed = []

        # 1. Process Phis and regular assignments in this block
        for stmt in block.statements:
            if isinstance(stmt, ir.IRAssignment):
                # Only rename right-hand side if it's NOT a Phi (Phi is renamed by pred)
                if not isinstance(stmt.value, ir.IRPhi):
                    self._rename_in_expr(stmt.value)
                
                if isinstance(stmt.target, ir.IRVariable):
                    old_name = stmt.target.original_name or stmt.target.name
                    new_name = self._gen_new_name(old_name)
                    # Create a new variable object for the target to avoid side effects
                    stmt.target = ir.IRVariable(
                        name=new_name, 
                        original_name=old_name,
                        inferred_type=stmt.target.inferred_type,
                        lineno=stmt.target.lineno,
                        col_offset=stmt.target.col_offset
                    )
                    self.var_stacks.setdefault(old_name, []).append(new_name)
                    pushed.append(old_name)
            elif isinstance(stmt, ir.IRReturnStatement) and stmt.value:
                self._rename_in_expr(stmt.value)
            elif isinstance(stmt, ir.IRBranch):
                self._rename_in_expr(stmt.condition)

        # 2. Fill in Phi parameters for successors
        for succ in block.successors:
            for stmt in succ.statements:
                if isinstance(stmt, ir.IRAssignment) and isinstance(stmt.value, ir.IRPhi):
                    orig_name = stmt.target.original_name
                    if orig_name in self.var_stacks and self.var_stacks[orig_name]:
                        stmt.value.options[bid] = ir.IRVariable(name=self.var_stacks[orig_name][-1])
                    else:
                        # Undefined: use nil or a special Uninitialized node
                        stmt.value.options[bid] = ir.IRLiteral(value=None)

        # 3. Recursively visit children in Dominator Tree
        for child_id in self.dom_children.get(bid, []):
            self._rename_vars(child_id)
        
        # 4. Pop stacks
        for name in pushed:
            self.var_stacks[name].pop()

    def _gen_new_name(self, name: str) -> str:
        version = self.var_versions.get(name, 0) + 1
        self.var_versions[name] = version
        return f"{name}_{version}"

    def _rename_in_expr(self, expr: ir.IRExpression):
        # We handle this by mutating the original node IF it's an IRVariable,
        # but the linearizer ensures they aren't shared across different statements/uses.
        if isinstance(expr, ir.IRVariable):
            orig = expr.original_name or expr.name
            stack = self.var_stacks.get(orig)
            if stack:
                expr.name = stack[-1]
                expr.original_name = orig
        elif hasattr(expr, "__dict__"):
            for attr, v in expr.__dict__.items():
                if isinstance(v, ir.IRExpression):
                    self._rename_in_expr(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, ir.IRExpression):
                            self._rename_in_expr(item)

class SSADCE:
    """Performs Dead Code Elimination on SSA IR."""
    def __init__(self, target_cfg: cfg.CFG):
        self.cfg = target_cfg
        self.use_counts: Dict[str, int] = {}

    def run(self):
        changed = True
        while changed:
            changed = False
            self.use_counts = {}
            # 1. Count uses
            for bid, block in self.cfg.blocks.items():
                for stmt in block.statements:
                    self._count_uses(stmt)
            
            # 2. Remove statements that define unused variables and have no side effects
            for bid, block in self.cfg.blocks.items():
                new_stmts = []
                for stmt in block.statements:
                    if isinstance(stmt, ir.IRAssignment) and isinstance(stmt.target, ir.IRVariable):
                        if self.use_counts.get(stmt.target.name, 0) == 0:
                            # Is it safe to remove? (Assignments to locals with no side effects in value)
                            if not self._has_side_effects(stmt.value):
                                changed = True
                                continue
                    new_stmts.append(stmt)
                block.statements = new_stmts
        
    def _count_uses(self, stmt: ir.IRStatement):
        # We only really care about variable uses in expressions
        if isinstance(stmt, ir.IRAssignment):
            self._find_uses(stmt.value)
        elif isinstance(stmt, ir.IRReturnStatement) and stmt.value:
            self._find_uses(stmt.value)
        elif isinstance(stmt, ir.IRBranch):
            self._find_uses(stmt.condition)
        elif isinstance(stmt, (ir.IRFunctionCall, ir.IRMethodCall)):
            self._find_uses(stmt)

    def _find_uses(self, expr: ir.IRExpression):
        if isinstance(expr, ir.IRVariable):
            self.use_counts[expr.name] = self.use_counts.get(expr.name, 0) + 1
        elif isinstance(expr, ir.IRPhi):
            for opt in expr.options.values():
                self._find_uses(opt)
        elif hasattr(expr, "__dict__"):
            for v in expr.__dict__.values():
                if isinstance(v, ir.IRExpression):
                    self._find_uses(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, ir.IRExpression):
                            self._find_uses(item)

    def _has_side_effects(self, expr: ir.IRExpression) -> bool:
        if isinstance(expr, (ir.IRFunctionCall, ir.IRMethodCall)):
            return True
        if hasattr(expr, "__dict__"):
            for v in expr.__dict__.values():
                if isinstance(v, ir.IRExpression):
                    if self._has_side_effects(v): return True
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, ir.IRExpression):
                            if self._has_side_effects(item): return True
        return False

class SSAConstantPropagation:
    """Performs Constant Propagation and Folding on SSA IR."""
    def __init__(self, target_cfg: cfg.CFG):
        self.cfg = target_cfg
        self.constants: Dict[str, Any] = {} # name -> literal value

    def run(self):
        changed = True
        while changed:
            changed = False
            self.constants = {}
            
            # 1. Collect constants
            for bid, block in self.cfg.blocks.items():
                for stmt in block.statements:
                    if isinstance(stmt, ir.IRAssignment) and isinstance(stmt.target, ir.IRVariable):
                        if isinstance(stmt.value, ir.IRLiteral):
                            self.constants[stmt.target.name] = stmt.value.value
                        elif isinstance(stmt.value, ir.IRPhi):
                            values = list(stmt.value.options.values())
                            if values:
                                first = values[0]
                                if isinstance(first, ir.IRLiteral) and all(isinstance(v, ir.IRLiteral) and v.value == first.value for v in values):
                                    self.constants[stmt.target.name] = first.value
                        elif isinstance(stmt.value, ir.IRBinaryOperation):
                            l = self.constants.get(stmt.value.left.name) if isinstance(stmt.value.left, ir.IRVariable) else (stmt.value.left.value if isinstance(stmt.value.left, ir.IRLiteral) else None)
                            r = self.constants.get(stmt.value.right.name) if isinstance(stmt.value.right, ir.IRVariable) else (stmt.value.right.value if isinstance(stmt.value.right, ir.IRLiteral) else None)
                            if l is not None and r is not None:
                                try:
                                    res = self._fold(l, stmt.value.operator, r)
                                    if res is not None:
                                        stmt.value = ir.IRLiteral(value=res)
                                        self.constants[stmt.target.name] = res
                                        changed = True
                                except: pass
            
            # 2. Propagate constants
            for bid, block in self.cfg.blocks.items():
                for stmt in block.statements:
                    if self._propagate_in_stmt(stmt):
                        changed = True

    def _propagate_in_stmt(self, stmt: ir.IRStatement) -> bool:
        changed = False
        if isinstance(stmt, ir.IRAssignment):
            new_val = self._propagate_in_expr(stmt.value)
            if new_val is not stmt.value:
                stmt.value = new_val
                changed = True
        elif isinstance(stmt, ir.IRReturnStatement) and stmt.value:
            new_val = self._propagate_in_expr(stmt.value)
            if new_val is not stmt.value:
                stmt.value = new_val
                changed = True
        elif isinstance(stmt, ir.IRBranch):
            new_val = self._propagate_in_expr(stmt.condition)
            if new_val is not stmt.condition:
                stmt.condition = new_val
                changed = True
        elif isinstance(stmt, (ir.IRFunctionCall, ir.IRMethodCall)):
            # Here we expect a mutation or we handle the result
            # But IRFunctionCall is also an IRExpression.
            # Usually standalone calls are just statements.
            pass
        return changed

    def _propagate_in_expr(self, expr: ir.IRExpression) -> ir.IRExpression:
        if isinstance(expr, ir.IRVariable):
            if expr.name in self.constants:
                return ir.IRLiteral(value=self.constants[expr.name])
            return expr

        if isinstance(expr, ir.IRBinaryOperation):
            expr.left = self._propagate_in_expr(expr.left)
            expr.right = self._propagate_in_expr(expr.right)
        elif isinstance(expr, ir.IRUnaryOperation):
            expr.operand = self._propagate_in_expr(expr.operand)
        elif isinstance(expr, ir.IRPhi):
            for bid, opt in expr.options.items():
                expr.options[bid] = self._propagate_in_expr(opt)
        elif isinstance(expr, (ir.IRFunctionCall, ir.IRMethodCall)):
            if isinstance(expr, ir.IRFunctionCall):
                expr.func = self._propagate_in_expr(expr.func)
            else:
                expr.receiver = self._propagate_in_expr(expr.receiver)
            expr.args = [self._propagate_in_expr(arg) for arg in expr.args]
        elif hasattr(expr, "__dict__"):
             for k, v in expr.__dict__.items():
                 if isinstance(v, ir.IRExpression):
                     setattr(expr, k, self._propagate_in_expr(v))
                 elif isinstance(v, list):
                     new_list = []
                     for item in v:
                         if isinstance(item, ir.IRExpression):
                             new_list.append(self._propagate_in_expr(item))
                         else:
                             new_list.append(item)
                     setattr(expr, k, new_list)
        return expr

    def _fold(self, l: Any, op: str, r: Any) -> Optional[Any]:
        if op == "Add": return l + r
        if op == "Sub": return l - r
        if op == "Mult": return l * r
        if op == "Div": return l / r if r != 0 else None
        if op == "Gt": return l > r
        if op == "Lt": return l < r
        if op == "Eq": return l == r
        # ... add more as needed
        return None

class DeSSA:
    """Converts SSA IR back to normal form (eliminates Phi nodes)."""
    def __init__(self, target_cfg: cfg.CFG):
        self.cfg = target_cfg

    def run(self):
        for bid, block in self.cfg.blocks.items():
            new_statements = []
            for stmt in block.statements:
                if isinstance(stmt, ir.IRAssignment) and isinstance(stmt.value, ir.IRPhi):
                    # For a Phi: x = Phi(B1: val1, B2: val2)
                    # Insert 'x = val1' at the end of B1, etc.
                    phi = stmt.value
                    target_var = stmt.target
                    for pred_id, source_expr in phi.options.items():
                        pred_block = self.cfg.blocks[pred_id]
                        # Insert assignment before the terminator
                        assignment = ir.IRAssignment(target=target_var, value=source_expr)
                        if pred_block.statements and isinstance(pred_block.statements[-1], (ir.IRJump, ir.IRBranch)):
                            pred_block.statements.insert(-1, assignment)
                        else:
                            pred_block.statements.append(assignment)
                    # Remove the Phi statement
                    continue
                new_statements.append(stmt)
            block.statements = new_statements
