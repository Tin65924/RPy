"""
transpiler/luau_ast.py — Formal Luau AST nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union

@dataclass
class Node:
    """Base class for all Luau AST nodes."""
    pass

# --- Expressions ---

@dataclass
class Expression(Node):
    pass

@dataclass
class Literal(Expression):
    value: Union[str, int, float, bool, None]

@dataclass
class Variable(Expression):
    name: str

@dataclass
class BinaryOperation(Expression):
    left: Expression
    operator: str
    right: Expression

@dataclass
class UnaryOperation(Expression):
    operator: str
    operand: Expression

@dataclass
class FunctionCall(Expression):
    func: Expression
    args: List[Expression] = field(default_factory=list)

@dataclass
class MethodCall(Expression):
    receiver: Expression
    method: str
    args: List[Expression] = field(default_factory=list)

@dataclass
class IndexOperation(Expression):
    receiver: Expression
    index: Expression

@dataclass
class TableLiteral(Expression):
    elements: List[Expression] = field(default_factory=list)
    fields: List[tuple[str, Expression]] = field(default_factory=list)

@dataclass
class Lambda(Expression):
    args: List[str]
    body: List[Statement]

# --- Statements ---

@dataclass
class Statement(Node):
    pass

@dataclass
class LocalAssign(Statement):
    name: str
    value: Optional[Expression] = None
    type_annotation: Optional[str] = None

@dataclass
class Assignment(Statement):
    target: Expression
    value: Expression

@dataclass
class IfStatement(Statement):
    condition: Expression
    then_block: List[Statement]
    elif_blocks: List[tuple[Expression, List[Statement]]] = field(default_factory=list)
    else_block: Optional[List[Statement]] = None

@dataclass
class WhileStatement(Statement):
    condition: Expression
    body: List[Statement]

@dataclass
class ForStatement(Statement):
    var: str
    start: Expression
    end: Expression
    body: List[Statement]
    step: Optional[Expression] = None

@dataclass
class GenericForStatement(Statement):
    vars: List[str]
    iterator: Expression
    body: List[Statement]

@dataclass
class FunctionDef(Statement):
    name: str
    args: List[str]
    body: List[Statement]
    is_local: bool = True
    is_method: bool = False

@dataclass
class ReturnStatement(Statement):
    value: Optional[Expression] = None

@dataclass
class BreakStatement(Statement):
    pass

@dataclass
class ContinueStatement(Statement):
    pass

@dataclass
class PassStatement(Statement):
    pass

@dataclass
class Comment(Statement):
    text: str

@dataclass
class Block(Statement):
    body: List[Statement]
