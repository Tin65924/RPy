"""
transpiler/restructurer.py — Reconstructs high-level IR from CFG.
"""

from __future__ import annotations
from typing import List, Set, Dict, Optional
from transpiler import cfg, ir

class CFGRestructurer:
    def __init__(self, target_cfg: cfg.CFG):
        self.cfg = target_cfg
        self.visited: Set[int] = set()

    def reconstruct(self) -> ir.IRModule:
        body = self._reconstruct_block(self.cfg.entry_block.id)
        return ir.IRModule(body=body)

    def _reconstruct_block(self, bid: int, stop_at: Optional[int] = None) -> List[ir.IRStatement]:
        if bid in self.visited or (stop_at is not None and bid == stop_at):
            return []
            
        block = self.cfg.blocks[bid]
        self.visited.add(bid)
        
        result = []
        # Add non-terminator statements
        for stmt in block.statements:
            if not isinstance(stmt, (ir.IRJump, ir.IRBranch)):
                result.append(stmt)
                
        terminator = block.terminator
        if isinstance(terminator, ir.IRJump):
            # If it's a simple jump, just continue with successor
            result.extend(self._reconstruct_block(terminator.target_block_id, stop_at))
        elif isinstance(terminator, ir.IRBranch):
            # Detect Diamond Pattern (If-Else-Merge)
            # Find the merge block (common successor of then/else branch or deeper)
            # For simplicity, we use the Dominator Tree or post-dominators.
            # RPy's CFG builder creates diamonds with a clear merge block.
            
            # Simple heuristic: look for the first block dominated by both successors?
            # Or just follow our builder's pattern: then and else both jump to a merge block.
            then_id = terminator.true_block_id
            else_id = terminator.false_block_id
            
            # Heuristic for merge block: 
            # The merge block is usually the one that follows then/else in source order
            # and is reached by both.
            merge_id = self._find_merge_block(then_id, else_id)
            
            then_body = self._reconstruct_block(then_id, stop_at=merge_id)
            else_body = self._reconstruct_block(else_id, stop_at=merge_id)
            
            result.append(ir.IRIfStatement(
                condition=terminator.condition,
                then_block=then_body,
                else_block=else_body
            ))
            
            if merge_id is not None:
                result.extend(self._reconstruct_block(merge_id, stop_at))
                
        return result

    def _find_merge_block(self, b1_id: int, b2_id: int) -> Optional[int]:
        # Very simple version: find a common successor
        s1 = self._get_all_successors(b1_id)
        s2 = self._get_all_successors(b2_id)
        common = s1.intersection(s2)
        if common:
            # Pick the "earliest" one by ID (heuristic)
            return min(common)
        return None

    def _get_all_successors(self, bid: int, depth=5) -> Set[int]:
        if depth == 0: return set()
        res = set()
        block = self.cfg.blocks.get(bid)
        if block:
            for s in block.successors:
                res.add(s.id)
                res.update(self._get_all_successors(s.id, depth - 1))
        return res
