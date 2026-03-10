"""
transpiler/cfg.py — Control Flow Graph (CFG) structures for RPy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from transpiler import ir

@dataclass
class BasicBlock:
    id: int
    statements: List[ir.IRStatement] = field(default_factory=list)
    successors: List[BasicBlock] = field(default_factory=list)
    predecessors: List[BasicBlock] = field(default_factory=list)
    
    @property
    def terminator(self) -> Optional[ir.IRStatement]:
        if not self.statements:
            return None
        last = self.statements[-1]
        if isinstance(last, (ir.IRJump, ir.IRBranch, ir.IRReturnStatement)):
            return last
        return None

    def add_successor(self, other: BasicBlock):
        if other not in self.successors:
            self.successors.append(other)
            other.predecessors.append(self)

@dataclass
class CFG:
    entry_block: BasicBlock
    exit_blocks: Set[BasicBlock] = field(default_factory=set)
    blocks: Dict[int, BasicBlock] = field(default_factory=dict)

    def reconstruct_module(self) -> ir.IRModule:
        """Converts the CFG back into a linear IRModule."""
        # Simple implementation: sort blocks by ID and collect statements
        # This works because our builder generates blocks in source order
        full_body = []
        # Sort by block ID to maintain original structure as much as possible
        for bid in sorted(self.blocks.keys()):
            block = self.blocks[bid]
            for stmt in block.statements:
                # Filter out CFG-specific terminators if we want to go back to 
                # a high-level tree IR, or keep them for a low-level IR.
                # For RPy 0.6.0, we want to allow the generator to see them or strip them.
                if isinstance(stmt, (ir.IRJump, ir.IRBranch)):
                    continue # Stripping CFG nodes for reconstruction
                full_body.append(stmt)
        return ir.IRModule(body=full_body)
