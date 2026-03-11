"""
transpiler/analyzer.py — Semantic Analysis Pass for IR (v0.5.0).
"""

from __future__ import annotations
import json
import os
from typing import Dict, Optional, Set, Any
from transpiler import ir
from transpiler.diagnostics import manager, DiagnosticManager
from transpiler.project_context import ProjectContext, ModuleExport

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

SDK_MODULES = {"roblox", "math", "table", "string", "task", "coroutine", "debug"}

class SemanticAnalyzer:
    def __init__(self, diagnostics: Optional[DiagnosticManager] = None, project: Optional[ProjectContext] = None, module_name: str = "main"):
        self.diagnostics = diagnostics or manager
        self.project = project
        self.module_name = module_name
        self.metadata = self._load_metadata()
        self.symbol_table = SymbolTable()
        self._init_globals()
        self._exports = ModuleExport(module_name)

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
        
        # After analysis, if we are in a project, update the global project context
        if self.project:
            self.project.modules[self.module_name] = self._exports

    def visit_IRAssignment(self, node: ir.IRAssignment):
        self.analyze(node.value)
        inferred = self._infer_type(node.value)
        if inferred and not node.value.inferred_type:
            node.value.inferred_type = inferred
        
        if isinstance(node.target, ir.IRVariable):
            if inferred:
                self.symbol_table.define(node.target.name, inferred)
                if not node.target.inferred_type:
                    node.target.inferred_type = inferred
                
                # Export if we are at module level
                if self.symbol_table.parent is None: # Toplevel
                    self._exports.symbols[node.target.name] = inferred
        elif isinstance(node.target, ir.IRPropertyAccess):
            # Check for 'self.prop = value'
            if isinstance(node.target.receiver, ir.IRVariable) and node.target.receiver.name == "self":
                curr_class = getattr(self, "_current_class", None)
                if curr_class:
                    curr_class.properties[node.target.property] = inferred or "any"
                    node.target.inferred_type = inferred

        self.analyze(node.target)

    def visit_IRVariable(self, node: ir.IRVariable):
        if not node.inferred_type:
            t = self.symbol_table.lookup(node.name)
            if t:
                node.inferred_type = t
                if t.startswith("SDK_MEMBER:"):
                    # Rewrite the variable name to be qualified for the generator
                    # Actually, the generator expects a simple name for Name nodes.
                    # We might need to transform this node into an Attribute access if we want to be clean.
                    # But for now, if we just set inferred_type, we can handle it in visit_IRFunctionCall.
                    pass

    def visit_IRFunctionCall(self, node: ir.IRFunctionCall):
        self.analyze(node.func)
        for arg in node.args:
            self.analyze(arg)
        
        # Handle SDK member calls (e.g., from string import upper -> upper("..."))
        if isinstance(node.func, ir.IRVariable) and node.func.inferred_type:
            if node.func.inferred_type.startswith("SDK_MEMBER:"):
                qualified = node.func.inferred_type[11:]
                if "." in qualified:
                    mod, member = qualified.split(".", 1)
                    # Transform this function call into a method call (qualified library call)
                    # We can't easily replace 'node' itself in a visitor, but we can 
                    # change its 'func' to an Attribute if we had that in IR.
                    # In RPy IR, we have IRPropertyAccess.
                    # Let's change node.func to an IRPropertyAccess.
                    node.func = ir.IRPropertyAccess(
                        receiver=ir.IRVariable(name=mod, lineno=node.lineno, col_offset=node.col_offset),
                        property=member,
                        lineno=node.lineno,
                        col_offset=node.col_offset
                    )

        if not node.inferred_type:
            node.inferred_type = self._infer_type(node)

    def visit_IRMethodCall(self, node: ir.IRMethodCall):
        self.analyze(node.receiver)
        for arg in node.args:
            self.analyze(arg)

        receiver_type = self._infer_type(node.receiver)
        node.call_style = ir.CallStyle.COLON # Default

        if receiver_type:
            if receiver_type.startswith("Module:"):
                node.call_style = ir.CallStyle.DOT # Modules use dots
                # Infer return type from module exports
                mod_name = receiver_type[7:]
                if self.project:
                    mod_export = self.project.modules.get(mod_name)
                    if mod_export:
                        t = mod_export.symbols.get(node.method)
                        if t and t.startswith("Function:"):
                            node.inferred_type = t[9:]
                return

            class_info = self._get_class_info(receiver_type)
            if class_info:
                method_info = class_info.get("methods", {}).get(node.method)
                if method_info:
                    style_str = method_info.get("style", "colon")
                    node.call_style = ir.CallStyle.DOT if style_str == "dot" else ir.CallStyle.COLON
                    # Update inferred type of the call node itself
                    node.inferred_type = method_info.get("returns")
                    return

    def visit_IRImport(self, node: ir.IRImport):
        if node.module in SDK_MODULES:
            # e.g., import math -> math is a module
            self.symbol_table.define(node.alias or node.module, f"Module:{node.module}")
            return

        if self.project:
            # We don't perform deep analysis here, just define the module name in symbol table
            self.symbol_table.define(node.alias or node.module, f"Module:{node.module}")

    def visit_IRImportFrom(self, node: ir.IRImportFrom):
        if node.module == "roblox":
            for i, name in enumerate(node.names):
                alias = node.aliases[i] or name
                # e.g., from roblox import task -> task is a module/global
                if name in SDK_MODULES:
                    self.symbol_table.define(alias, f"Module:{name}")
                else:
                    self.symbol_table.define(alias, "any")
            return

        if node.module in SDK_MODULES:
            for i, name in enumerate(node.names):
                alias = node.aliases[i] or name
                # e.g., from math import floor -> floor is a member of math
                self.symbol_table.define(alias, f"SDK_MEMBER:{node.module}.{name}")
            return

        if self.project:
            mod_export = self.project.modules.get(node.module)
            if mod_export:
                for i, name in enumerate(node.names):
                    alias = node.aliases[i] or name
                    t = mod_export.symbols.get(name, "any")
                    self.symbol_table.define(alias, t)
            else:
                self.diagnostics.warning(
                    f"Module '{node.module}' not found in project or not yet analyzed.",
                    line=node.lineno, col=node.col_offset
                )

    def visit_IRPropertyAccess(self, node: ir.IRPropertyAccess):
        self.analyze(node.receiver)
        receiver_type = self._infer_type(node.receiver)
        
        if not receiver_type or receiver_type == "any":
            return

        # --- Module Access Fallback ---
        if receiver_type.startswith("Module:"):
            mod_name = receiver_type[7:]
            if self.project:
                mod_export = self.project.modules.get(mod_name)
                if mod_export:
                    t = mod_export.symbols.get(node.property)
                    if t:
                        node.inferred_type = t
                        return
            
            if mod_name in SDK_MODULES:
                # For SDK modules, we assume the property exists for now
                node.inferred_type = "any"
                return

            self.diagnostics.error(
                f"Module '{mod_name}' has no attribute '{node.property}'.",
                line=node.lineno, col=node.col_offset
            )
            return

        is_optional = receiver_type.endswith("?")
        base_type = receiver_type[:-1] if is_optional else receiver_type
        
        if is_optional:
            self.diagnostics.warning(
                f"Property access '{node.property}' on optional type '{receiver_type}'.",
                line=node.lineno, col=node.col_offset,
                hint=f"Consider checking 'if {getattr(node.receiver, 'name', 'object')} then' first."
            )

        class_info = self._get_class_info(base_type)
        if class_info:
            props = class_info.get("properties", {})
            prop_type = props.get(node.property)
            if prop_type:
                node.inferred_type = prop_type
                return
            
            # --- Service Fallback for DataModel ---
            if base_type == "DataModel":
                if node.property in self.metadata.get("classes", {}):
                    node.inferred_type = node.property
                    return

            # Check signals
            signals = class_info.get("signals", {})
            signal_type = signals.get(node.property)
            if signal_type:
                node.inferred_type = signal_type
                return
            
            # Not found: Fuzzy match
            from transpiler.ast_utils import get_closest_match
            all_possibilities = list(props.keys()) + list(signals.keys()) + list(class_info.get("methods", {}).keys())
            closest = get_closest_match(node.property, all_possibilities)
            
            self.diagnostics.error(
                f"Property '{node.property}' does not exist on type '{base_type}'.",
                line=node.lineno, col=node.col_offset,
                hint=f"Did you mean '{closest}'?" if closest else f"Verify the member exists on {base_type}."
            )

    def visit_IRFunctionDef(self, node: ir.IRFunctionDef):
        # Define the function itself in the parent symbol table first
        if node.name:
            # We use a special prefix for function return types in symbols or just store the type
            # For simplicity let's store it as "ReturnType(className)" or similar
            # Actually, let's just use the function name to store its return type for now.
            pass

        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        
        # Define arguments with types if available
        for i, arg in enumerate(node.args):
            t_ann = node.arg_types[i] if i < len(node.arg_types) else None
            self.symbol_table.define(arg, t_ann or "any")
        
        for stmt in node.body:
            self.analyze(stmt)
            
        # Optional: Attempt to infer return type if not explicitly set
        if not node.return_type:
            # Simple heuristic: find all return statements
            returns = []
            def find_returns(n):
                if isinstance(n, ir.IRReturnStatement):
                    returns.append(n)
                elif hasattr(n, "__dict__"):
                    for attr, v in n.__dict__.items():
                        if isinstance(v, list):
                            for item in v: find_returns(item)
                        elif isinstance(v, ir.IRNode): find_returns(v)
            
            find_returns(node)
            if returns:
                # Just take the first one for now
                ret_type = self._infer_type(returns[0].value) if returns[0].value else "nil"
                node.return_type = ret_type
            else:
                node.return_type = "any"

        self.symbol_table = old_table
        if node.name:
            self.symbol_table.define(node.name, f"Function:{node.return_type}")
            # Export if we are at module level
            if self.symbol_table.parent is None:
                self._exports.symbols[node.name] = f"Function:{node.return_type}"

    def visit_IRGenericForStatement(self, node: ir.IRGenericForStatement):
        self.analyze(node.iterator)
        
        # Heuristic for iterator types
        if not node.var_types:
            if isinstance(node.iterator, ir.IRFunctionCall) and isinstance(node.iterator.func, ir.IRVariable):
                it_name = node.iterator.func.name
                if it_name == "ipairs":
                    node.var_types = ["number", "any"]
                elif it_name == "pairs":
                    node.var_types = ["any", "any"]
        
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        for i, v in enumerate(node.vars):
            v_type = node.var_types[i] if i < len(node.var_types) else "any"
            self.symbol_table.define(v, v_type)
        
        for stmt in node.body:
            self.analyze(stmt)
        self.symbol_table = old_table

    def visit_IRIfStatement(self, node: ir.IRIfStatement):
        self.analyze(node.condition)
        
        # Flow-sensitive refinement
        refined_var = None
        old_type = None
        if isinstance(node.condition, ir.IRVariable):
            refined_var = node.condition.name
            old_type = self.symbol_table.lookup(refined_var)
            if old_type and old_type.endswith("?"):
                self.symbol_table.define(refined_var, old_type[:-1]) # Strip ?
        
        for stmt in node.then_block:
            self.analyze(stmt)
            
        # Restore type after then_block
        if refined_var and old_type:
            self.symbol_table.define(refined_var, old_type)

        if node.else_block:
            for stmt in node.else_block:
                self.analyze(stmt)

    def visit_IRClassDef(self, node: ir.IRClassDef):
        # We'll store class property info in class_properties map or similar
        # For simplicity, let's just use the symbol table to track 'self' in methods
        old_class = getattr(self, "_current_class", None)
        self._current_class = node
        
        # We might want a dedicated metadata entry for user classes
        # ... (removed redundancy)
        
        for stmt in node.body:
            self.analyze(stmt)
            
        self._current_class = old_class

    def _infer_type(self, node: ir.IRExpression) -> Optional[str]:
        if node.inferred_type:
            return node.inferred_type

        if isinstance(node, ir.IRVariable):
            return self.symbol_table.lookup(node.name)
        
        if isinstance(node, ir.IRFunctionCall):
            if isinstance(node.func, ir.IRVariable):
                sym = self.symbol_table.lookup(node.func.name)
                if sym and sym.startswith("Function:"):
                    return sym[9:]

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

def analyze(module: ir.IRModule, diagnostics: Optional[DiagnosticManager] = None, project: Optional[ProjectContext] = None, module_name: str = "main"):
    analyzer = SemanticAnalyzer(diagnostics, project, module_name)
    analyzer.analyze(module)
