"""
transpiler/cfg_optimizer.py — Optimization passes for the CFG.
"""

from __future__ import annotations
from typing import Set
from transpiler import cfg

class CFGOptimizer:
    def __init__(self, graph: cfg.CFG):
        self.graph = graph

    def run_dce(self):
        """
        Simple Dead Code Elimination: Remove blocks that are not reachable from the entry.
        """
        reachable = self._find_reachable(self.graph.entry_block)
        
        # Collect block IDs to remove
        to_remove = set(self.graph.blocks.keys()) - reachable
        
        for block_id in to_remove:
            # Note: We need to clean up predecessors/successors if we were doing more complex graph surgery
            # but for simple unreachable removal, we just drop from the blocks dict
            del self.graph.blocks[block_id]
            
    def _find_reachable(self, start_block: cfg.BasicBlock) -> Set[int]:
        visited = set()
        stack = [start_block]
        while stack:
            block = stack.pop()
            if block.id not in visited:
                visited.add(block.id)
                for succ in block.successors:
                    stack.append(succ)
        return visited

def optimize_cfg(graph: cfg.CFG):
    opt = CFGOptimizer(graph)
    opt.run_dce()
