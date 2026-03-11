from transpiler import ir
from transpiler.cfg_builder import build_cfg
from transpiler.cfg_optimizer import optimize_cfg
from typing import List, Dict, Set, Optional, Any, Union

def get_canonical(node: ir.IRExpression) -> Optional[str]:
    """Returns a canonical string representation of an expression if it is pure."""
    if isinstance(node, ir.IRLiteral):
        return f"Lit({repr(node.value)})"
    if isinstance(node, ir.IRVariable):
        return f"Var({node.name})"
    if isinstance(node, ir.IRBinaryOperation):
        l = get_canonical(node.left)
        r = get_canonical(node.right)
        if l and r: return f"Bin({l},{node.operator},{r})"
    if isinstance(node, ir.IRUnaryOperation):
        o = get_canonical(node.operand)
        if o: return f"Un({node.operator},{o})"
    if isinstance(node, ir.IRPropertyAccess):
        r = get_canonical(node.receiver)
        if r: return f"Prop({r},{node.property})"
    return None

def get_used_vars(node: ir.IRExpression) -> Set[str]:
    """Returns the set of variable names used in an expression."""
    vars = set()
    if isinstance(node, ir.IRVariable):
        vars.add(node.name)
    elif hasattr(node, "__dict__"):
        for v in node.__dict__.values():
            if isinstance(v, ir.IRExpression):
                vars.update(get_used_vars(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, ir.IRExpression):
                        vars.update(get_used_vars(item))
    return vars

class CSEPass:
    def __init__(self):
        self.expr_to_var: Dict[str, str] = {}
        self.var_to_exprs: Dict[str, Set[str]] = {} # var_name -> set of canonical strings
        self.temp_count = 0

    def _gen_temp(self) -> str:
        self.temp_count += 1
        return f"_cse_{self.temp_count}"

    def optimize_block(self, body: List[ir.IRStatement]) -> List[ir.IRStatement]:
        new_body = []
        self.expr_to_var = {}
        self.var_to_exprs = {}
        
        for stmt in body:
            if isinstance(stmt, ir.IRAssignment) and not isinstance(stmt.target, ir.IRPropertyAccess):
                # Optimize the value expression
                stmt.value = self._optimize_expr(stmt.value, new_body)
                
                # If target is a simple variable, invalidate expressions that use it
                if isinstance(stmt.target, ir.IRVariable):
                    self._invalidate(stmt.target.name)
                    
                    # Also, record this assignment as a potential CSE source if pure
                    canon = get_canonical(stmt.value)
                    if canon and not isinstance(stmt.value, (ir.IRVariable, ir.IRLiteral)):
                        self.expr_to_var[canon] = stmt.target.name
                        for v in get_used_vars(stmt.value):
                            self.var_to_exprs.setdefault(v, set()).add(canon)
                
                new_body.append(stmt)
            else:
                # For other statements (If, While, etc.), we don't do CSE across them here
                # but we can optimize their sub-expressions
                self.generic_optimize_stmt(stmt, new_body)
                new_body.append(stmt)
                
                # Side effect safety: assume any non-assignment statement might modify globals/state
                # but since we only track local variables in var_to_exprs, it's mostly fine
                # unless it's a call.
                if self._has_side_effects(stmt):
                    self._invalidate_all()

        return new_body

    def _optimize_expr(self, expr: ir.IRExpression, body: List[ir.IRStatement]) -> ir.IRExpression:
        # Recursively optimize children
        if isinstance(expr, ir.IRBinaryOperation):
            expr.left = self._optimize_expr(expr.left, body)
            expr.right = self._optimize_expr(expr.right, body)
        elif isinstance(expr, ir.IRUnaryOperation):
            expr.operand = self._optimize_expr(expr.operand, body)
        elif isinstance(expr, ir.IRPropertyAccess):
            expr.receiver = self._optimize_expr(expr.receiver, body)
        
        canon = get_canonical(expr)
        if canon and not isinstance(expr, (ir.IRVariable, ir.IRLiteral)):
            if canon in self.expr_to_var:
                return ir.IRVariable(lineno=expr.lineno, name=self.expr_to_var[canon], inferred_type=expr.inferred_type)
            else:
                # We could inject a temp here, but for now we only reuse existing assignments
                pass
        return expr

    def _invalidate(self, var_name: str):
        if var_name in self.var_to_exprs:
            for canon in self.var_to_exprs[var_name]:
                if canon in self.expr_to_var:
                    del self.expr_to_var[canon]
            del self.var_to_exprs[var_name]

    def _invalidate_all(self):
        self.expr_to_var = {}
        self.var_to_exprs = {}

    def _has_side_effects(self, stmt: ir.IRStatement) -> bool:
        if isinstance(stmt, (ir.IRFunctionCall, ir.IRMethodCall)): return True
        # Check recursively
        if hasattr(stmt, "body"):
            for s in stmt.body:
                if self._has_side_effects(s): return True
        if isinstance(stmt, ir.IRIfStatement):
            for s in stmt.then_block:
                if self._has_side_effects(s): return True
            if stmt.else_block:
                for s in stmt.else_block:
                    if self._has_side_effects(s): return True
        return False

    def generic_optimize_stmt(self, stmt: ir.IRStatement, body: List[ir.IRStatement]):
        # This would optimize expressions inside If, While etc.
        # For simplicity, we'll just handle basic expressions here if needed.
        pass

class LICMPass:
    def __init__(self):
        self.temp_count = 0

    def _gen_temp(self) -> str:
        self.temp_count += 1
        return f"_licm_{self.temp_count}"

    def optimize_loop(self, loop_node: ir.IRStatement) -> List[ir.IRStatement]:
        if not hasattr(loop_node, "body"): return [loop_node]
        
        # 1. Find all variables modified in loop body
        modified = self._get_modified_vars(loop_node.body)
        if isinstance(loop_node, ir.IRForStatement):
            modified.add(loop_node.var)
        elif isinstance(loop_node, ir.IRGenericForStatement):
            for v in loop_node.vars: modified.add(v)
            
        # 2. Find invariant expressions in assignments
        pre_loop = []
        new_body = []
        
        for stmt in loop_node.body:
            if isinstance(stmt, ir.IRAssignment) and isinstance(stmt.target, ir.IRVariable):
                # Is it invariant? (Heuristic: no side effects, no modified vars used)
                used = get_used_vars(stmt.value)
                canon = get_canonical(stmt.value)
                # Ensure the expression itself is invariant and has no side effects
                if canon and not (used & modified) and not isinstance(stmt.value, (ir.IRVariable, ir.IRLiteral)):
                    # Check if value has side effects (redundant but safe)
                    if not self._expr_has_side_effects(stmt.value):
                        temp = self._gen_temp()
                        pre_loop.append(ir.IRAssignment(
                            target=ir.IRVariable(name=temp),
                            value=stmt.value,
                            is_local=True
                        ))
                        stmt.value = ir.IRVariable(name=temp)
            new_body.append(stmt)
        
        loop_node.body = new_body
        return pre_loop + [loop_node]

    def _get_modified_vars(self, body: List[ir.IRStatement]) -> Set[str]:
        modified = set()
        for stmt in body:
            if isinstance(stmt, ir.IRAssignment):
                if isinstance(stmt.target, ir.IRVariable):
                    modified.add(stmt.target.name)
                elif isinstance(stmt.target, ir.IRPropertyAccess):
                    # Property access might alias or modify state, but we track vars
                    pass
            elif isinstance(stmt, ir.IRIfStatement):
                modified.update(self._get_modified_vars(stmt.then_block))
                if stmt.else_block:
                    modified.update(self._get_modified_vars(stmt.else_block))
                for _, elif_body in stmt.elif_blocks:
                    modified.update(self._get_modified_vars(elif_body))
            elif hasattr(stmt, "body"):
                # Nested loops/defs
                modified.update(self._get_modified_vars(stmt.body))
        return modified

    def _expr_has_side_effects(self, expr: ir.IRExpression) -> bool:
        if isinstance(expr, (ir.IRFunctionCall, ir.IRMethodCall)): return True
        if hasattr(expr, "__dict__"):
            for v in expr.__dict__.values():
                if isinstance(v, ir.IRExpression):
                    if self._expr_has_side_effects(v): return True
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, ir.IRExpression):
                            if self._expr_has_side_effects(item): return True
        return False

class RecursiveIROptimizer:
    def optimize(self, node: ir.IRNode) -> Union[ir.IRNode, List[ir.IRNode]]:
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ir.IRNode) -> ir.IRNode:
        if hasattr(node, "__dict__"):
            for attr, value in node.__dict__.items():
                if isinstance(value, ir.IRNode):
                    res = self.optimize(value)
                    if isinstance(res, list):
                        # This shouldn't really happen for non-block contexts,
                        # but if it does, we take the last one or error.
                        # For IR nodes in fields, we usually expect 1-to-1.
                        setattr(node, attr, res[-1] if res else None)
                    else:
                        setattr(node, attr, res)
                elif isinstance(value, list):
                    new_list = []
                    for item in value:
                        if isinstance(item, ir.IRNode):
                            res = self.optimize(item)
                            if isinstance(res, list):
                                new_list.extend(res)
                            else:
                                new_list.append(res)
                        else:
                            new_list.append(item)
                    setattr(node, attr, new_list)
        return node

    def _optimize_block(self, body: List[ir.IRStatement]) -> List[ir.IRStatement]:
        if not body:
            return []
            
        # 1. Recursively optimize children first
        optimized_body = []
        for s in body:
            res = self.optimize(s)
            if isinstance(res, list):
                optimized_body.extend(res)
            elif res is not None:
                optimized_body.append(res)
        
        # 2. Apply CSE (Stage 16)
        cse = CSEPass()
        optimized_body = cse.optimize_block(optimized_body)
        
        # Note: We skip the destructive CFG optimization for now to preserve
        # the high-level tree IR required by the generator.
        
        return optimized_body

    def visit_IRModule(self, node: ir.IRModule) -> ir.IRModule:
        node.body = self._optimize_block(node.body)
        return node

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef) -> ir.IRFunctionDef:
        node.body = self._optimize_block(node.body)
        return node

    def visit_IRIfStatement(self, node: ir.IRIfStatement) -> ir.IRIfStatement:
        node.then_block = self._optimize_block(node.then_block)
        
        # Optimize elif blocks
        new_elifs = []
        for cond, body in node.elif_blocks:
            # We don't optimize the condition itself for now (simple CSE happens later)
            new_elifs.append((cond, self._optimize_block(body)))
        node.elif_blocks = new_elifs
            
        if node.else_block:
            node.else_block = self._optimize_block(node.else_block)
        return node

    def visit_IRWhileStatement(self, node: ir.IRWhileStatement) -> List[ir.IRStatement]:
        node.body = self._optimize_block(node.body)
        licm = LICMPass()
        return licm.optimize_loop(node)

    def visit_IRForStatement(self, node: ir.IRForStatement) -> List[ir.IRStatement]:
        node.body = self._optimize_block(node.body)
        licm = LICMPass()
        return licm.optimize_loop(node)

    def visit_IRGenericForStatement(self, node: ir.IRGenericForStatement) -> List[ir.IRStatement]:
        node.body = self._optimize_block(node.body)
        licm = LICMPass()
        return licm.optimize_loop(node)

def optimize_ir(module: ir.IRModule):
    optimizer = RecursiveIROptimizer()
    optimizer.optimize(module)
