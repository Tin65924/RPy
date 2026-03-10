"""
transpiler/ir.py — Intermediate Representation (IR) for RPy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any
from enum import Enum, auto

class CallStyle(Enum):
    DOT = auto()
    COLON = auto()
    UNKNOWN = auto()

@dataclass
class IRNode:
    """Base class for all IR nodes."""
    lineno: int = 0
    col_offset: int = 0

# --- Expressions ---

@dataclass
class IRExpression(IRNode):
    inferred_type: Optional[str] = None

@dataclass
class IRLiteral(IRExpression):
    value: Any = None

@dataclass
class IRVariable(IRExpression):
    name: str = ""

@dataclass
class IRBinaryOperation(IRExpression):
    left: IRExpression = field(default_factory=lambda: IRLiteral())
    operator: str = "+"
    right: IRExpression = field(default_factory=lambda: IRLiteral())

@dataclass
class IRUnaryOperation(IRExpression):
    operator: str = "-"
    operand: IRExpression = field(default_factory=lambda: IRLiteral())

@dataclass
class IRFunctionCall(IRExpression):
    func: IRExpression = field(default_factory=lambda: IRVariable())
    args: List[IRExpression] = field(default_factory=list)

@dataclass
class IRMethodCall(IRExpression):
    receiver: IRExpression = field(default_factory=lambda: IRVariable())
    method: str = ""
    args: List[IRExpression] = field(default_factory=list)
    call_style: CallStyle = CallStyle.UNKNOWN

@dataclass
class IRPropertyAccess(IRExpression):
    receiver: IRExpression = field(default_factory=lambda: IRVariable())
    property: str = ""

@dataclass
class IRTableLiteral(IRExpression):
    elements: List[IRExpression] = field(default_factory=list)
    fields: List[tuple[str, IRExpression]] = field(default_factory=list)

@dataclass
class IRIndexOperation(IRExpression):
    receiver: IRExpression = field(default_factory=lambda: IRVariable())
    index: IRExpression = field(default_factory=lambda: IRLiteral())

# --- Statements ---

@dataclass
class IRStatement(IRNode):
    pass

@dataclass
class IRModule(IRStatement):
    body: List[IRStatement] = field(default_factory=list)

@dataclass
class IRAssignment(IRStatement):
    target: IRExpression = field(default_factory=lambda: IRVariable())
    value: IRExpression = field(default_factory=lambda: IRLiteral())
    is_local: bool = False

@dataclass
class IRFunctionDef(IRStatement):
    name: str = ""
    args: List[str] = field(default_factory=list)
    body: List[IRStatement] = field(default_factory=list)
    is_local: bool = True
    is_method: bool = False

@dataclass
class IRIfStatement(IRStatement):
    condition: IRExpression = field(default_factory=lambda: IRLiteral(True))
    then_block: List[IRStatement] = field(default_factory=list)
    elif_blocks: List[tuple[IRExpression, List[IRStatement]]] = field(default_factory=list)
    else_block: Optional[List[IRStatement]] = None

@dataclass
class IRWhileStatement(IRStatement):
    condition: IRExpression = field(default_factory=lambda: IRLiteral(True))
    body: List[IRStatement] = field(default_factory=list)

@dataclass
class IRForStatement(IRStatement):
    var: str = ""
    start: IRExpression = field(default_factory=lambda: IRLiteral(0))
    end: IRExpression = field(default_factory=lambda: IRLiteral(10))
    body: List[IRStatement] = field(default_factory=list)
    step: Optional[IRExpression] = None

@dataclass
class IRGenericForStatement(IRStatement):
    vars: List[str] = field(default_factory=list)
    iterator: IRExpression = field(default_factory=lambda: IRVariable())
    body: List[IRStatement] = field(default_factory=list)

@dataclass
class IRReturnStatement(IRStatement):
    value: Optional[IRExpression] = None

@dataclass
class IRBreakStatement(IRStatement):
    pass

@dataclass
class IRContinueStatement(IRStatement):
    pass

@dataclass
class IRPassStatement(IRStatement):
    pass

@dataclass
class IRComment(IRStatement):
    text: str = ""

@dataclass
class IRClassDef(IRStatement):
    name: str = ""
    bases: List[IRExpression] = field(default_factory=list)
    body: List[IRStatement] = field(default_factory=list)

# --- CFG Terminators ---

@dataclass
class IRJump(IRStatement):
    target_block_id: int = 0

@dataclass
class IRBranch(IRStatement):
    condition: IRExpression = field(default_factory=lambda: IRLiteral(True))
    true_block_id: int = 0
    false_block_id: int = 0
