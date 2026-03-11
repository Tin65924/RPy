import asyncio
import time
from pathlib import Path
from typing import Optional

from cli.main import transpile_file, _get_script_type, _validate_placement, transpile_and_write
from transpiler.flags import CompilerFlags
from transpiler.errors import TranspileError
from sync.server import DevServer
from sync.watcher import start_watcher

class RPyLiveCoordinator:
    def __init__(self, src_dir: Path, out_dir: Path, flags: CompilerFlags, host="localhost", port=8000):
        self.src_dir = src_dir
        self.out_dir = out_dir
        self.flags = flags
        
        # Load config
        project_dir = src_dir if src_dir.is_dir() else src_dir.parent
        from cli.main import _load_rpy_config
        self.config = _load_rpy_config(project_dir)
        
        # Merge CLI flags into config for the plugin
        self.config["flags"] = self.config.get("flags", {})
        self.config["flags"]["backup_studio"] = flags.backup_studio
        
        self.server = DevServer(host, port, config=self.config)
        self.watcher = None

    async def run(self):
        # 1. Initial full build
        print(f"Performing initial build of {self.src_dir}...")
        self.rebuild_all()
        
        # 2. Start server
        await self.server.start()
        
        # 3. Start watcher
        self.watcher = start_watcher(self.src_dir, self.handle_file_change)
        
        print(f"Live sync is active. Press Ctrl+C to stop.")
        
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.watcher.stop()
            self.watcher.join()

    def handle_file_change(self, py_path: Path, deleted: bool = False):
        if deleted:
            rel_path = str(py_path.relative_to(self.src_dir))
            if self.server.remove_file(rel_path):
                print(f"  - {rel_path} deleted")
            return

        from transpiler.dependency_graph import DependencyGraph
        from cli.main import _get_project_folders
        valid_roots = list(_get_project_folders(self.server.config).keys())
        graph = DependencyGraph(str(self.src_dir), valid_roots=valid_roots)
        try:
            graph.scan_project()
        except TranspileError as e:
            print(f"  ⚠ DAG validation error: {e}")

        visited = set()
        to_sync = [py_path]
        
        while to_sync:
            curr_path = to_sync.pop(0)
            if curr_path in visited: continue
            visited.add(curr_path)
            
            # Add dependents
            for dep in graph.reverse_graph.get(curr_path, []):
                if dep not in visited and dep not in to_sync:
                    to_sync.append(dep)
                    
            self._sync_single_file(curr_path, is_dependency=(curr_path != py_path))

    def _sync_single_file(self, py_path: Path, is_dependency: bool = False):
        rel_path = str(py_path.relative_to(self.src_dir))
        warning = _validate_placement(py_path, self.src_dir, {})
        if warning and not is_dependency:
            print(f"  ⚠ {warning}")

        start_time = time.time()
        try:
            from cli.main import transpile_file
            # Note: transpile_file expects flags, we pass self.flags
            result = transpile_file(py_path, self.flags)
            latency = (time.time() - start_time) * 1000 # ms
            
            if self.flags.show_out:
                lua_path = self.out_dir / py_path.relative_to(self.src_dir).with_suffix(".lua")
                lua_path.parent.mkdir(parents=True, exist_ok=True)
                lua_path.write_text(result.code, encoding="utf-8")

            script_type = _get_script_type(py_path)
            self.server.update_file(rel_path, result.code, script_type, latency)
            
            prefix = "  ↻" if is_dependency else "  ✓"
            print(f"{prefix} {rel_path} synced ({latency:.1f}ms)")
            
        except TranspileError as e:
            print(f"  ✗ {py_path.name}: {e}")
        except Exception as e:
            print(f"  ✗ {py_path.name}: Internal error: {e}")

    def rebuild_all(self):
        py_files = list(self.src_dir.rglob("*.py"))
        for py_file in py_files:
            if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                continue
            self._sync_single_file(py_file)

async def start_live_sync(src: Path, out: Path, flags: CompilerFlags):
    coordinator = RPyLiveCoordinator(src, out, flags)
    await coordinator.run()
