"""
transpiler/type_inferrer.py — Basic type inference pass for --typed mode.

This pass walks the AST (after transformer processing) and annotates
expressions with inferred Luau types. The generator then uses these
annotations to emit typed Luau (`local x: number = 5`).

Type inference strategy (intentionally simple for v1):
  1. Constant propagation: literals → their type
  2. BinOp propagation: number op number → number, string .. string → string
  3. Function return types: inferred from return statements
  4. Everything unknown → any

Supported Luau types: number, string, boolean, nil, any, {[any]: any}
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Luau type constants
# ---------------------------------------------------------------------------

NUMBER  = "number"
STRING  = "string"
BOOLEAN = "boolean"
NIL     = "nil"
ANY     = "any"
TABLE   = "{[any]: any}"
ARRAY_NUMBER  = "{number}"
ARRAY_STRING  = "{string}"
ARRAY_ANY     = "{any}"
INSTANCE      = "Instance"
PLAYER        = "Player"
VECTOR3       = "Vector3"
CFRAME        = "CFrame"
COLOR3        = "Color3"
ENUM_ITEM     = "EnumItem"


# ---------------------------------------------------------------------------
# TypeMap: stores inferred types keyed by variable name + scope depth
# ---------------------------------------------------------------------------

@dataclass
class TypeMap:
    """
    Maps (name, depth) → inferred Luau type string.
    Also maps AST node id → inferred type for expressions.
    """
    _var_types: dict[tuple[str, int], str] = field(default_factory=dict)
    _expr_types: dict[int, str] = field(default_factory=dict)
    _return_types: dict[str, str] = field(default_factory=dict)  # func_name → return type

    def set_var(self, name: str, depth: int, luau_type: str) -> None:
        self._var_types[(name, depth)] = luau_type

    def get_var(self, name: str, depth: int) -> str:
        return self._var_types.get((name, depth), ANY)

    def set_expr(self, node: ast.AST, luau_type: str) -> None:
        self._expr_types[id(node)] = luau_type

    def get_expr(self, node: ast.AST) -> str:
        return self._expr_types.get(id(node), ANY)

    def set_return(self, func_name: str, luau_type: str) -> None:
        self._return_types[func_name] = luau_type

    def get_return(self, func_name: str) -> str:
        return self._return_types.get(func_name, ANY)


# ---------------------------------------------------------------------------
# TypeInferrer — AST visitor that populates a TypeMap
# ---------------------------------------------------------------------------

class TypeInferrer(ast.NodeVisitor):
    """
    Single-pass type inference visitor.

    After visiting, `self.type_map` contains inferred types for all
    variables and expressions encountered.
    """

    def __init__(self) -> None:
        self.type_map = TypeMap()
        self._depth = 0
        self._current_func: Optional[str] = None

    # -- helpers --

    def _infer_expr(self, node: ast.expr) -> str:
        """Infer and record the type of an expression node."""
        t = self._compute_type(node)
        self.type_map.set_expr(node, t)
        return t

    def _compute_type(self, node: ast.expr) -> str:
        """Compute the Luau type for an expression."""
        if isinstance(node, ast.Constant):
            return self._type_of_constant(node.value)

        if isinstance(node, ast.Name):
            return self.type_map.get_var(node.id, self._depth)

        if isinstance(node, ast.BinOp):
            left = self._infer_expr(node.left)
            right = self._infer_expr(node.right)
            return self._binop_result(left, right, node.op)

        if isinstance(node, ast.UnaryOp):
            operand = self._infer_expr(node.operand)
            if isinstance(node.op, ast.Not):
                return BOOLEAN
            if isinstance(node.op, (ast.USub, ast.UAdd)):
                return NUMBER if operand == NUMBER else ANY
            return ANY

        if isinstance(node, ast.BoolOp):
            return BOOLEAN

        if isinstance(node, ast.Compare):
            # Comparisons always produce booleans
            for comp in node.comparators:
                self._infer_expr(comp)
            return BOOLEAN

        if isinstance(node, ast.IfExp):
            body_t = self._infer_expr(node.body)
            else_t = self._infer_expr(node.orelse)
            return body_t if body_t == else_t else ANY

        if isinstance(node, ast.List):
            if node.elts:
                first_t = self._infer_expr(node.elts[0])
                for e in node.elts[1:]:
                    self._infer_expr(e)
                if first_t == NUMBER:
                    return ARRAY_NUMBER
                if first_t == STRING:
                    return ARRAY_STRING
            return ARRAY_ANY

        if isinstance(node, ast.Tuple):
            for e in node.elts:
                self._infer_expr(e)
            return ARRAY_ANY

        if isinstance(node, ast.Dict):
            return TABLE

        if isinstance(node, ast.Call):
            # Try to infer from known builtins
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in ("int", "float", "abs"):
                    return NUMBER
                if name in ("str",):
                    return STRING
                if name in ("bool",):
                    return BOOLEAN
                if name in ("len",):
                    return NUMBER
                if name in ("sorted", "list", "reversed"):
                    return ARRAY_ANY
                # Check if we know the return type of a user function
                return self.type_map.get_return(name)

            # Handle Roblox method calls: game.GetService("Players") -> Players
            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                # GetService
                if attr == "GetService" and node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        return arg0.value  # Returns the service type name
                
                # Instance methods that return specific types
                if attr in ("FindFirstChild", "FindFirstAncestor", "WaitForChild"):
                    return f"{INSTANCE}?" # Union with nil
                
                if attr == "GetChildren" or attr == "GetDescendants":
                    return "{Instance}"
                
                # Constructors: Vector3.new(...)
                if attr == "new" and isinstance(node.func.value, ast.Name):
                    constructor_name = node.func.value.id
                    if constructor_name in ("Vector3", "Vector2", "CFrame", "UDim2", "UDim", "Color3", "Rect"):
                        return constructor_name
                    
            return ANY

        if isinstance(node, ast.Subscript):
            return ANY

        if isinstance(node, ast.Attribute):
            return ANY

        if isinstance(node, ast.Lambda):
            return ANY  # functions are opaque

        if isinstance(node, ast.JoinedStr):
            return STRING

        if isinstance(node, ast.ListComp):
            return ARRAY_ANY

        if isinstance(node, ast.DictComp):
            return TABLE

        return ANY

    @staticmethod
    def _type_of_constant(value: object) -> str:
        if value is None:
            return NIL
        if isinstance(value, bool):
            return BOOLEAN
        if isinstance(value, int):
            return NUMBER
        if isinstance(value, float):
            return NUMBER
        if isinstance(value, str):
            return STRING
        return ANY

    @staticmethod
    def _binop_result(left: str, right: str, op: ast.operator) -> str:
        if isinstance(op, ast.Add):
            if left == STRING or right == STRING:
                return STRING
            if left == NUMBER and right == NUMBER:
                return NUMBER
            return ANY
        if isinstance(op, (ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
                           ast.Mod, ast.Pow)):
            if left == NUMBER and right == NUMBER:
                return NUMBER
            return ANY
        return ANY

    # -- statement visitors --

    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_Assign(self, node: ast.Assign) -> None:
        value_type = self._infer_expr(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.type_map.set_var(target.id, self._depth, value_type)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._infer_expr(node.value)
        # Type doesn't change for augmented assignment
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev_func = self._current_func
        self._current_func = node.name
        self._depth += 1

        # Record parameter types as 'any'
        for arg in node.args.args:
            self.type_map.set_var(arg.arg, self._depth, ANY)

        for stmt in node.body:
            self.visit(stmt)

        self._depth -= 1
        self._current_func = prev_func

    def visit_Return(self, node: ast.Return) -> None:
        if node.value and self._current_func:
            ret_type = self._infer_expr(node.value)
            self.type_map.set_return(self._current_func, ret_type)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.type_map.set_var(node.name, self._depth, TABLE)
        self._depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self._depth -= 1

    def visit_For(self, node: ast.For) -> None:
        if isinstance(node.target, ast.Name):
            self.type_map.set_var(node.target.id, self._depth, ANY)
        for stmt in node.body:
            self.visit(stmt)

    def visit_If(self, node: ast.If) -> None:
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_While(self, node: ast.While) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_Try(self, node: ast.Try) -> None:
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            if handler.name:
                self.type_map.set_var(handler.name, self._depth, ANY)
            for stmt in handler.body:
                self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                self.type_map.set_var(item.optional_vars.id, self._depth, ANY)
        for stmt in node.body:
            self.visit(stmt)

    def visit_Expr(self, node: ast.Expr) -> None:
        self._infer_expr(node.value)

    def generic_visit(self, node: ast.AST) -> None:
        # Don't crash on unhandled nodes — just skip
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                self.visit(child)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_types(tree: ast.Module) -> TypeMap:
    """
    Run type inference over *tree* and return a TypeMap.

    Args:
        tree: An ast.Module (already transformed by transformer.py).

    Returns:
        TypeMap with inferred types for variables and expressions.
    """
    inferrer = TypeInferrer()
    inferrer.visit(tree)
    return inferrer.type_map
