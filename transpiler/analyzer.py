"""
transpiler/analyzer.py — Semantic Analysis Pass for IR (v0.5.0).
"""

from __future__ import annotations
import json
import os
from typing import Dict, Optional, Set, Any
from transpiler import ir

class SymbolTable:
    def __init__(self, parent: Optional[SymbolTable] = None):
        self.parent = parent
        self.symbols: Dict[str, str] = {} # name -> type_name

    def lookup(self, name: str) -> Optional[str]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def define(self, name: str, type_name: str):
        self.symbols[name] = type_name

class SemanticAnalyzer:
    def __init__(self):
        self.metadata = self._load_metadata()
        self.symbol_table = SymbolTable()
        self._init_globals()

    def _load_metadata(self) -> Dict[str, Any]:
        path = os.path.join(os.path.dirname(__file__), "api_metadata.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load metadata: {e}")
            return {"classes": {}, "globals": {}}

    def _init_globals(self):
        globals_map = self.metadata.get("globals", {})
        for name, type_name in globals_map.items():
            self.symbol_table.define(name, type_name)

    def analyze(self, node: ir.IRNode):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        visitor(node)

    def generic_visit(self, node: ir.IRNode):
        if hasattr(node, "__dict__"):
            for attr, value in node.__dict__.items():
                if isinstance(value, ir.IRNode):
                    self.analyze(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ir.IRNode):
                            self.analyze(item)

    def visit_IRModule(self, node: ir.IRModule):
        for stmt in node.body:
            self.analyze(stmt)

    def visit_IRAssignment(self, node: ir.IRAssignment):
        self.analyze(node.value)
        inferred = self._infer_type(node.value)
        
        if isinstance(node.target, ir.IRVariable):
            if inferred:
                self.symbol_table.define(node.target.name, inferred)
        
        # If target already has a type but value changes it, we might want to update it
        # but for simple RPy let's just stick to first definition in scope
        self.analyze(node.target)

    def visit_IRMethodCall(self, node: ir.IRMethodCall):
        self.analyze(node.receiver)
        for arg in node.args:
            self.analyze(arg)

        receiver_type = self._infer_type(node.receiver)
        node.call_style = ir.CallStyle.COLON # Default

        if receiver_type:
            class_info = self._get_class_info(receiver_type)
            if class_info:
                method_info = class_info.get("methods", {}).get(node.method)
                if method_info:
                    style_str = method_info.get("style", "colon")
                    node.call_style = ir.CallStyle.DOT if style_str == "dot" else ir.CallStyle.COLON
                    # Update inferred type of the call node itself
                    node.inferred_type = method_info.get("returns")
                    return

    def visit_IRPropertyAccess(self, node: ir.IRPropertyAccess):
        self.analyze(node.receiver)
        receiver_type = self._infer_type(node.receiver)
        if receiver_type:
            class_info = self._get_class_info(receiver_type)
            if class_info:
                # Check properties
                prop_type = class_info.get("properties", {}).get(node.property)
                if prop_type:
                    node.inferred_type = prop_type
                    return
                # Check signals
                signal_type = class_info.get("signals", {}).get(node.property)
                if signal_type:
                    node.inferred_type = signal_type
                    return

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef):
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        for arg in node.args:
            self.symbol_table.define(arg, "any")
        for stmt in node.body:
            self.analyze(stmt)
        self.symbol_table = old_table

    def _infer_type(self, node: ir.IRExpression) -> Optional[str]:
        if node.inferred_type:
            return node.inferred_type

        if isinstance(node, ir.IRVariable):
            return self.symbol_table.lookup(node.name)
        
        if isinstance(node, ir.IRMethodCall):
            # Special case for GetService
            receiver_type = self._infer_type(node.receiver)
            if receiver_type == "DataModel" and node.method == "GetService":
                if len(node.args) > 0 and isinstance(node.args[0], ir.IRLiteral) and isinstance(node.args[0].value, str):
                    service_name = node.args[0].value
                    # Basic mapping of common service names to their types
                    # In a full impl, this would be a map or just return service_name
                    if service_name in self.metadata.get("classes", {}):
                        return service_name
                    return "Instance" # Fallback

        if isinstance(node, ir.IRLiteral):
            if isinstance(node.value, str): return "string"
            if isinstance(node.value, bool): return "bool"
            if isinstance(node.value, (int, float)): return "number"
            if node.value is None: return "nil"

        return None

    def _get_class_info(self, class_name: str) -> Optional[Dict[str, Any]]:
        classes = self.metadata.get("classes", {})
        info = classes.get(class_name)
        if not info:
            return None
        
        # Merge with base classes if 'inherits' is present
        base_name = info.get("inherits")
        if base_name:
            base_info = self._get_class_info(base_name)
            if base_info:
                # Proper deep merge for properties, methods, signals
                merged = base_info.copy()
                for key in ["properties", "methods", "signals"]:
                    merged[key] = base_info.get(key, {}).copy()
                    merged[key].update(info.get(key, {}))
                return merged
        return info

def analyze(module: ir.IRModule):
    analyzer = SemanticAnalyzer()
    analyzer.analyze(module)
