"""
transpiler/dependency_graph.py — Project-wide dependency tracking.
"""

from __future__ import annotations
import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Optional

class DependencyGraph:
    def __init__(self, root_dir: str, valid_roots: Optional[List[str]] = None):
        self.root_dir = Path(root_dir).resolve()
        self.graph: Dict[Path, Set[Path]] = {} # file -> [dependencies]
        self.reverse_graph: Dict[Path, Set[Path]] = {} # file -> [files that depend on it]
        # Restrict module discovery to these specific top-level directories
        self.valid_roots = valid_roots or [
            "workspace", "replicatedstorage", "serverscriptservice", 
            "starterplayerscripts", "lighting", "startergui"
        ]

    def scan_project(self):
        """Scans the project directory and builds the dependency graph."""
        self.graph = {}
        self.reverse_graph = {}
        
        py_files = list(self.root_dir.rglob("*.py"))
        for py_file in py_files:
            # Skip files outside the valid Roblox service roots
            rel_parts = py_file.relative_to(self.root_dir).parts
            if not rel_parts or rel_parts[0] not in self.valid_roots:
                continue
            self._process_file(py_file)

    def _process_file(self, file_path: Path):
        file_path = file_path.resolve()
        if file_path not in self.graph:
            self.graph[file_path] = set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dep_path = self._resolve_module(alias.name, file_path)
                        if dep_path:
                            self._add_dependency(file_path, dep_path)
                elif isinstance(node, ast.ImportFrom):
                    dep_path = self._resolve_module(node.module, file_path, level=node.level)
                    if dep_path:
                        self._add_dependency(file_path, dep_path)
        except Exception as e:
            # Skip files that can't be parsed for dependency analysis
            pass

    def _resolve_module(self, module_name: Optional[str], current_file: Path, level: int = 0) -> Optional[Path]:
        """Resolves a module name to a file path within the project, ensuring it stays within valid roots."""
        if not module_name and level == 0:
            return None
            
        def _is_valid_path(p: Path) -> bool:
            try:
                rel = p.resolve().relative_to(self.root_dir)
                return rel.parts[0] in self.valid_roots
            except ValueError:
                return False

        # Handle relative imports
        if level > 0:
            target_dir = current_file.parent
            for _ in range(level - 1):
                target_dir = target_dir.parent
            
            if module_name:
                # from .sub import func
                parts = module_name.split(".")
                potential_path = target_dir.joinpath(*parts).with_suffix(".py")
                if potential_path.exists():
                    return potential_path.resolve()
                potential_init = target_dir.joinpath(*parts, "__init__.py")
                if potential_init.exists():
                    return potential_init.resolve()
            else:
                # from . import func
                potential_init = target_dir.joinpath("__init__.py")
                if potential_init.exists() and _is_valid_path(potential_init):
                    return potential_init.resolve()
        
        # Handle absolute imports relative to root
        if module_name:
            parts = module_name.split(".")
            # First part must be a valid root
            if parts[0] in self.valid_roots:
                potential_path = self.root_dir.joinpath(*parts).with_suffix(".py")
                if potential_path.exists() and _is_valid_path(potential_path):
                    return potential_path.resolve()
                potential_init = self.root_dir.joinpath(*parts, "__init__.py")
                if potential_init.exists() and _is_valid_path(potential_init):
                    return potential_init.resolve()
                
        return None

    def _add_dependency(self, file_path: Path, dep_path: Path):
        if dep_path == file_path:
            return
            
        self.graph[file_path].add(dep_path)
        
        if dep_path not in self.reverse_graph:
            self.reverse_graph[dep_path] = set()
        self.reverse_graph[dep_path].add(file_path)

    def get_build_order(self) -> List[Path]:
        """Returns a topologically sorted list of files. Raises CyclicDependencyError if graph is not a DAG."""
        visited = set()
        temp_stack = set()
        order = []
        
        from transpiler.errors import CyclicDependencyError

        def visit(node: Path, current_path: List[Path]):
            if node in temp_stack:
                # Found a cycle! Extract the path from the node where it looped.
                cycle_idx = current_path.index(node)
                cycle_files = [n.name for n in current_path[cycle_idx:]] + [node.name]
                raise CyclicDependencyError(cycle_files)
                
            if node not in visited:
                temp_stack.add(node)
                current_path.append(node)
                
                for neighbor in self.graph.get(node, []):
                    visit(neighbor, current_path)
                    
                current_path.pop()
                temp_stack.remove(node)
                visited.add(node)
                order.append(node)

        for node in self.graph:
            visit(node, [])
            
        return order

    def get_dependents(self, file_path: Path) -> Set[Path]:
        """Returns all modules that depend on the given module (recursive)."""
        file_path = file_path.resolve()
        all_dependents = set()
        stack = [file_path]
        
        while stack:
            curr = stack.pop()
            for dep in self.reverse_graph.get(curr, []):
                if dep not in all_dependents:
                    all_dependents.add(dep)
                    stack.append(dep)
                    
        return all_dependents
