"""
transpiler/analyzer.py — Semantic Analysis Pass for IR.
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
        # Initialize global symbols
        self.symbol_table.define("game", "game")
        self.symbol_table.define("workspace", "workspace")
        self.symbol_table.define("Instance", "InstanceLib")
        self.symbol_table.define("Vector3", "Vector3")
        self.symbol_table.define("CFrame", "CFrame")

    def _load_metadata(self) -> Dict[str, Any]:
        path = os.path.join(os.path.dirname(__file__), "api_metadata.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {"classes": {}, "libraries": {}}

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
        if isinstance(node.target, ir.IRVariable):
            # Try to infer type from value
            inferred = self._infer_type(node.value)
            if inferred:
                self.symbol_table.define(node.target.name, inferred)
        self.analyze(node.target)

    def visit_IRMethodCall(self, node: ir.IRMethodCall):
        self.analyze(node.receiver)
        for arg in node.args:
            self.analyze(arg)

        # Method resolution logic
        receiver_type = self._infer_type(node.receiver)
        node.call_style = ir.CallStyle.COLON # Default

        if receiver_type:
            class_info = self._get_class_info(receiver_type)
            if class_info:
                method_info = class_info.get("methods", {}).get(node.method)
                if method_info:
                    style_str = method_info.get("call_style", "colon")
                    node.call_style = ir.CallStyle.DOT if style_str == "dot" else ir.CallStyle.COLON
                    return

        # Fallback to heuristics if no metadata
        if receiver_type in self.metadata.get("libraries", {}):
            node.call_style = ir.CallStyle.DOT

    def visit_IRPropertyAccess(self, node: ir.IRPropertyAccess):
        self.analyze(node.receiver)
        # Property access is usually dot in Luau
        pass

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef):
        # Create new scope
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
            # If it's a known getter like game.GetService or Instance.new
            receiver_type = self._infer_type(node.receiver)
            if receiver_type == "game" and node.method == "GetService":
                # For now assume it returns Instance or specific service if we had service map
                return "Instance"
            if receiver_type == "InstanceLib" and node.method == "new":
                return "Instance"
            
            # Lookup method return type in metadata
            if receiver_type:
                class_info = self._get_class_info(receiver_type)
                if class_info:
                    method_info = class_info.get("methods", {}).get(node.method)
                    if method_info:
                        return method_info.get("type")

        if isinstance(node, ir.IRPropertyAccess):
            receiver_type = self._infer_type(node.receiver)
            if receiver_type:
                class_info = self._get_class_info(receiver_type)
                if class_info:
                    prop_info = class_info.get("properties", {}).get(node.property)
                    if prop_info:
                        return prop_info.get("type")
                    signal_info = class_info.get("signals", {}).get(node.property)
                    if signal_info:
                        return signal_info.get("type")

        return None

    def _get_class_info(self, class_name: str) -> Optional[Dict[str, Any]]:
        classes = self.metadata.get("classes", {})
        info = classes.get(class_name)
        if not info:
            return None
        
        # Merge with base classes
        base_name = info.get("extends")
        if base_name:
            base_info = self._get_class_info(base_name)
            if base_info:
                merged = base_info.copy()
                merged.update(info)
                # Deep merge properties/methods/signals if needed
                for category in ["properties", "methods", "signals"]:
                    merged[category] = base_info.get(category, {}).copy()
                    merged[category].update(info.get(category, {}))
                return merged
        return info

def analyze(module: ir.IRModule):
    analyzer = SemanticAnalyzer()
    analyzer.analyze(module)
