"""
transpiler/project_context.py — Global state for multi-file projects.
"""

from __future__ import annotations
import threading
from typing import Dict, Any, Optional
from transpiler.ir import IRModule

class ModuleExport:
    def __init__(self, name: str):
        self.name = name
        self.symbols: Dict[str, str] = {} # name -> type_name
        self.functions: Dict[str, Any] = {} # name -> metadata

class ProjectContext:
    def __init__(self):
        self.modules: Dict[str, ModuleExport] = {}
        self._lock = threading.Lock()

    def get_module(self, module_name: str) -> ModuleExport:
        with self._lock:
            if module_name not in self.modules:
                self.modules[module_name] = ModuleExport(module_name)
            return self.modules[module_name]

    def define_export(self, module_name: str, symbol: str, type_name: str):
        module = self.get_module(module_name)
        with self._lock:
            module.symbols[symbol] = type_name
