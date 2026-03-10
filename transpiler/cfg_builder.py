"""
transpiler/cfg_builder.py — Converts IR tree to Control Flow Graph.
"""

from __future__ import annotations
from typing import List, Optional, Dict
from transpiler import ir, cfg

class CFGBuilder:
    def __init__(self):
        self._block_count = 0
        self._blocks: Dict[int, cfg.BasicBlock] = {}
        self._current_block: Optional[cfg.BasicBlock] = None
        self._loop_stack: List[tuple[int, int]] = [] # (continue_block_id, break_block_id)

    def build(self, module: ir.IRModule) -> cfg.CFG:
        entry = self._create_block()
        self._current_block = entry
        
        for stmt in module.body:
            self._process_statement(stmt)
            
        return cfg.CFG(entry_block=entry, blocks=self._blocks)

    def _create_block(self) -> cfg.BasicBlock:
        block = cfg.BasicBlock(id=self._block_count)
        self._blocks[self._block_count] = block
        self._block_count += 1
        return block

    def _emit(self, stmt: ir.IRStatement):
        if self._current_block:
            self._current_block.statements.append(stmt)
            # If we just emitted a terminator, the block ends
            if isinstance(stmt, (ir.IRReturnStatement, ir.IRJump, ir.IRBranch, ir.IRBreakStatement, ir.IRContinueStatement)):
                self._current_block = None

    def _process_statement(self, stmt: ir.IRStatement):
        # If current block is None (e.g. after a return), we create a "dead" block 
        # for subsequent statements. DCE will remove it later if it stays unreachable.
        if self._current_block is None:
            self._current_block = self._create_block()

        if isinstance(stmt, ir.IRIfStatement):
            self._process_if(stmt)
        elif isinstance(stmt, ir.IRWhileStatement):
            self._process_while(stmt)
        elif isinstance(stmt, ir.IRReturnStatement):
            self._emit(stmt)
        elif isinstance(stmt, ir.IRBreakStatement):
            if self._loop_stack:
                _, break_id = self._loop_stack[-1]
                self._emit(ir.IRJump(target_block_id=break_id))
                self._current_block.add_successor(self._blocks[break_id])
            self._current_block = None
        elif isinstance(stmt, ir.IRContinueStatement):
            if self._loop_stack:
                cont_id, _ = self._loop_stack[-1]
                self._emit(ir.IRJump(target_block_id=cont_id))
                self._current_block.add_successor(self._blocks[cont_id])
            self._current_block = None
        else:
            self._emit(stmt)

    def _process_if(self, stmt: ir.IRIfStatement):
        then_block = self._create_block()
        else_block = self._create_block()
        merge_block = self._create_block()
        
        # Branch to then/else
        branch = ir.IRBranch(condition=stmt.condition, true_block_id=then_block.id, false_block_id=else_block.id)
        
        prev_block = self._current_block
        if prev_block:
            self._emit(branch)
            prev_block.add_successor(then_block)
            prev_block.add_successor(else_block)
            
        # Process then
        self._current_block = then_block
        for s in stmt.then_block:
            self._process_statement(s)
        if self._current_block:
            target = self._current_block
            self._emit(ir.IRJump(target_block_id=merge_block.id))
            target.add_successor(merge_block)
            
        # Process else
        self._current_block = else_block
        if stmt.else_block:
            for s in stmt.else_block:
                self._process_statement(s)
        if self._current_block:
            target = self._current_block
            self._emit(ir.IRJump(target_block_id=merge_block.id))
            target.add_successor(merge_block)
            
        self._current_block = merge_block

    def _process_while(self, stmt: ir.IRWhileStatement):
        cond_block = self._create_block()
        body_block = self._create_block()
        exit_block = self._create_block()
        
        if self._current_block:
            self._emit(ir.IRJump(target_block_id=cond_block.id))
            self._current_block.add_successor(cond_block)
            
        # Cond block
        self._current_block = cond_block
        branch = ir.IRBranch(condition=stmt.condition, true_block_id=body_block.id, false_block_id=exit_block.id)
        self._emit(branch)
        cond_block.add_successor(body_block)
        cond_block.add_successor(exit_block)
        
        # Body block
        self._loop_stack.append((cond_block.id, exit_block.id))
        self._current_block = body_block
        for s in stmt.body:
            self._process_statement(s)
        if self._current_block:
            target = self._current_block
            self._emit(ir.IRJump(target_block_id=cond_block.id))
            target.add_successor(cond_block)
        self._loop_stack.pop()
            
        self._current_block = exit_block

def build_cfg(module: ir.IRModule) -> cfg.CFG:
    builder = CFGBuilder()
    return builder.build(module)
