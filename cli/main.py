"""
cli/main.py — RPy command-line interface.

Usage:
    rpy transpile <src> <out> [--typed] [--fast] [--no-runtime] [--verbose]
    rpy validate <src>                - validate only, no output
    rpy setup [dir]                   - scaffold a new RPy project
    rpy live <src> <out> [flags]      - live file monitoring & Roblox sync
    
    (Aliases: build=transpile, check=validate, init=setup, watch=live)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

try:
    import tomllib
except ImportError:
    tomllib = None

from transpiler.parser import parse_source, parse_file
from transpiler.transformer import transform
from transpiler.flags import CompilerFlags
from transpiler.generator import generate, GenerateResult
from transpiler.errors import TranspileError
from transpiler.dependency_graph import DependencyGraph
from transpiler.project_context import ProjectContext
from transpiler.analyzer import SemanticAnalyzer
from transpiler.package_manager import PackageManager


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "1.0.0"



# ---------------------------------------------------------------------------
# rpy.json helpers
# ---------------------------------------------------------------------------

def _load_rpy_config(project_dir: Path) -> dict:
    """Load rpy.toml or rpy.json from *project_dir*, returning an empty dict if not found."""
    toml_path = project_dir / "rpy.toml"
    if toml_path.exists():
        if tomllib is None:
            print("Warning: rpy.toml found but 'tomllib' is missing (requires Python 3.11+).", file=sys.stderr)
            return {}
        try:
            return tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: rpy.toml is malformed ({e}). Using defaults.", file=sys.stderr)
            return {}

    cfg_path = project_dir / "rpy.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"Warning: rpy.json is malformed ({e}). Using defaults.", file=sys.stderr)
    return {}


def _merge_flags(flags: CompilerFlags, config: dict) -> CompilerFlags:
    """Merge flags from rpy.json into the provided CompilerFlags object (CLI wins)."""
    cfg_flags = config.get("flags", {})
    # Map of flag name to its attribute in CompilerFlags
    flag_map = {
        "typed": "typed",
        "fast": "fast",
        "no_runtime": "no_runtime",
        "shared_runtime": "shared_runtime",
        "source_refs": "source_refs",
        "compile_time": "compile_time",
        "debug": "debug"
    }
    
    for cfg_key, attr in flag_map.items():
        if cfg_flags.get(cfg_key) and not getattr(flags, attr):
            setattr(flags, attr, True)
            
    return flags


def _get_project_folders(config: dict) -> dict[str, str]:
    """Return folder mapping from config, falling back to native Roblox services."""
    raw = config.get("folders", {})
    mapping = {
        "workspace": "workspace",
        "replicatedstorage": "replicatedstorage",
        "serverscriptservice": "serverscriptservice",
        "starterplayerscripts": "starterplayerscripts",
        "lighting": "lighting",
        "startergui": "startergui"
    }
    mapping.update(raw)
    return mapping


# ---------------------------------------------------------------------------
# Project Setup Helpers
# ---------------------------------------------------------------------------
# (Project configuration generation logic)


# ---------------------------------------------------------------------------
# Syncing logic placeholder
# ---------------------------------------------------------------------------
# (Sync hooks moved to external dev server)


# (Structure warnings removed)


# ---------------------------------------------------------------------------
# Core transpile function
def _get_script_type(path: Path) -> str:
    """Determine script type from filename suffixes."""
    name = path.name.lower()
    if name.endswith(".server.py"):
        return "server"
    if name.endswith(".client.py"):
        return "client"
    return "module"


def _validate_placement(path: Path, src_root: Path, folders: dict[str, str]) -> Optional[str]:
    """
    Validate if a script is placed in a logically correct folder.
    Returns an error message if invalid, otherwise None.
    """
    name = path.name.lower()
    rel_path = str(path.relative_to(src_root)).lower()
    
    # Example: .server.py should be in a 'server' folder (mapped or literal)
    if ".server.py" in name:
        if "client" in rel_path or "starterplayer" in rel_path:
            return f"Placement Warning: Server script '{path.name}' is located in a client-side folder."
    
    if ".client.py" in name:
        if "server" in rel_path or "serverscriptservice" in rel_path:
            return f"Placement Warning: Client script '{path.name}' is located in a server-side folder."
            
    return None


def transpile_file(
    src_path: Path,
    flags: CompilerFlags,
    verbose: bool = False,
    project: Optional[ProjectContext] = None,
    module_name: str = "main"
) -> GenerateResult:
    """Parse -> transform -> generate a single .py file into Luau."""
    # Create a fresh copy of flags to avoid mutating shared state (Phase 14 fix)
    file_flags = flags
    if flags.script_type == "module":
        detected_type = _get_script_type(src_path)
        if detected_type != "module":
            from dataclasses import replace
            file_flags = replace(flags, script_type=detected_type)

    tree = parse_file(src_path)
    result = transform(
        tree, 
        filename=str(src_path.absolute()), 
        flags=file_flags,
        project=project,
        module_name=module_name
    )

    gen_result = generate(result, file_flags)
    return gen_result


def transpile_and_write(
    src_path: Path,
    out_path: Path,
    flags: CompilerFlags,
    verbose: bool = False,
    project: Optional[ProjectContext] = None,
    module_name: str = "main"
) -> None:
    """Transpile a single file and write the result."""
    gen_result = transpile_file(src_path, flags, verbose, project, module_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(gen_result.code, encoding="utf-8")
    if verbose:
        helpers = ", ".join(sorted(gen_result.runtime_helpers)) or "(none)"
        print(f"  [OK] {src_path} -> {out_path}  [runtime: {helpers}]")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> int:
    """Build command: transpile .py files to .lua."""
    src = Path(args.src).resolve()
    out = Path(args.out).resolve()
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
        shared_runtime=args.shared_runtime,
        source_refs=args.source_refs,
        compile_time=args.compile_time,
        debug=args.debug,
    )

    # Load project config
    project_dir = src.parent if src.is_file() else src
    config = _load_rpy_config(project_dir)
    flags = _merge_flags(flags, config)

    if src.is_file():
        if out.suffix == "":
            name = src.name
            if name.endswith(".server.py"):
                new_name = name.replace(".server.py", ".server.lua")
            elif name.endswith(".client.py"):
                new_name = name.replace(".client.py", ".client.lua")
            elif name.endswith(".module.py"):
                new_name = name.replace(".module.py", ".lua")
            else:
                new_name = name.replace(".py", ".lua")
            out = out / new_name
        try:
            transpile_and_write(src, out, flags, verbose=args.verbose)
        except TranspileError as e:
            source = src.read_text(encoding="utf-8") if src.exists() else None
            print(f"Error: {e.format_with_context(source)}", file=sys.stderr)
            return 1
        print(f"Built 1 file -> {out}")
        return 0

    if src.is_dir():
        project = ProjectContext()
        graph = DependencyGraph(str(src))
        graph.scan_project()
        import concurrent.futures
        import threading
        import multiprocessing

        # We still call get_build_order() to let it validate the DAG cycle detection.
        try:
            build_order = graph.get_build_order()
        except TranspileError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if not build_order:
            print(f"No .py files found in {src}")
            return 1

        in_degree = {n: len(deps) for n, deps in graph.graph.items()}
        ready_queue = [n for n in graph.graph if in_degree[n] == 0]
        
        completed_nodes = 0
        total_nodes = len(graph.graph)
        errors = 0

        # Output formatting lock for deterministic logs
        print_lock = threading.Lock()

        def compile_file(py_file: Path) -> bool:
            try:
                # Calculate module name for the project context
                rel = py_file.relative_to(src)
                module_name = ".".join(rel.with_suffix("").parts)
                if module_name.endswith(".__init__"): 
                    module_name = module_name[:-9]
                
                # Use same naming convention for output files
                name = py_file.name
                if name.endswith(".server.py"):
                    new_name = name.replace(".server.py", ".server.lua")
                elif name.endswith(".client.py"):
                    new_name = name.replace(".client.py", ".client.lua")
                elif name.endswith(".module.py"):
                    new_name = name.replace(".module.py", ".lua")
                else:
                    new_name = name.replace(".py", ".lua")
                
                lua_file = out / rel.parent / new_name

                # The print output inside transpile_and_write is captured/suppressed optionally,
                # but for simplicity we rely on transpile_file and handle writes manually here,
                # OR we wrap transpile_and_write with the lock if verbose.
                
                # For Phase 1 parallelism, we compile then write.
                from transpiler.parser import parse_file
                from transpiler.transformer import transform
                from transpiler.generator import generate
                
                file_flags = flags
                if flags.script_type == "module":
                    detected_type = _get_script_type(py_file)
                    if detected_type != "module":
                        from dataclasses import replace
                        file_flags = replace(flags, script_type=detected_type)

                tree = parse_file(py_file)
                result = transform(
                    tree, 
                    filename=str(py_file.absolute()), 
                    flags=file_flags,
                    project=project,
                    module_name=module_name
                )
                gen_result = generate(result, file_flags, module_name=module_name)
                
                lua_file.parent.mkdir(parents=True, exist_ok=True)
                lua_file.write_text(gen_result.code, encoding="utf-8")
                
                if args.verbose:
                    helpers = ", ".join(sorted(gen_result.runtime_helpers)) or "(none)"
                    with print_lock:
                        print(f"  [OK] {py_file} -> {lua_file}  [runtime: {helpers}]")
                return True
            except TranspileError as e:
                source = py_file.read_text(encoding="utf-8") if py_file.exists() else None
                with print_lock:
                    print(f"  ✗ {py_file}:\n{e.format_with_context(source)}\n", file=sys.stderr)
                return False
            except Exception as e:
                with print_lock:
                    print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)
                    if flags.debug:
                        import traceback
                        traceback.print_exc()
                return False

        num_workers = args.workers if getattr(args, "workers", 0) > 0 else (multiprocessing.cpu_count() or 4)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_node = {}
            for node in ready_queue:
                future_to_node[executor.submit(compile_file, node)] = node
            ready_queue.clear()
            
            while future_to_node:
                done, _ = concurrent.futures.wait(
                    future_to_node.keys(), 
                    return_when=concurrent.futures.FIRST_COMPLETED
                )
                
                for fut in done:
                    node = future_to_node.pop(fut)
                    completed_nodes += 1
                    try:
                        success = fut.result()
                        if not success:
                            errors += 1
                        else:
                            # Update dependents
                            for dependent in graph.reverse_graph.get(node, []):
                                in_degree[dependent] -= 1
                                if in_degree[dependent] == 0:
                                    future_to_node[executor.submit(compile_file, dependent)] = dependent
                    except Exception:
                        errors += 1

        ok = total_nodes - errors
        print(f"\nBuilt {ok}/{total_nodes} files -> {out} (workers: {num_workers})")
        if getattr(args, "expose_out", False):
            print(f"Output directory available at: {out.resolve()}")
        if errors:
            print(f"  {errors} file(s) had errors.", file=sys.stderr)
        return 1 if errors else 0

    print(f"Error: {src} does not exist.", file=sys.stderr)
    return 1


def cmd_check(args: argparse.Namespace) -> int:
    """Check command: validate .py files without writing output."""
    src = Path(args.src)
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
        shared_runtime=args.shared_runtime,
        source_refs=args.source_refs,
        compile_time=args.compile_time,
        debug=args.debug,
    )

    # Load project config to merge flags
    project_dir = src.parent if src.is_file() else src
    config = _load_rpy_config(project_dir)
    flags = _merge_flags(flags, config)

    files: list[Path] = []
    if src.is_file():
        files = [src]
    elif src.is_dir():
        files = [
            f for f in src.rglob("*.py")
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]
    else:
        print(f"Error: {src} does not exist.", file=sys.stderr)
        return 1

    errors = 0
    for py_file in files:
        try:
            transpile_file(py_file, flags, verbose=args.verbose)
            if args.verbose:
                print(f"  ✓ {py_file}")
        except TranspileError as e:
            source = py_file.read_text(encoding="utf-8") if py_file.exists() else None
            print(f"  ✗ {py_file}:\n{e.format_with_context(source)}", file=sys.stderr)
            errors += 1
        except Exception as e:
            print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)
            errors += 1

    total = len(files)
    ok = total - errors
    if errors:
        print(f"\nCheck: {ok}/{total} files OK, {errors} error(s).")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """
    Init command: scaffold a new RPy project.

    Creates:
        workspace/
        replicatedstorage/
        serverscriptservice/
        starterplayerscripts/
        .rpy/out/
        rpy.toml          — project configuration
    """
    project_dir = Path(args.dir or ".")
    project_name = project_dir.resolve().name or "RPyProject"

    # Determine folder mapping from existing config (if any)
    config = _load_rpy_config(project_dir)
    folders = _get_project_folders(config)

    # Create root service structure
    out_dir = project_dir / ".rpy" / "out"
    for folder_key, folder_name in folders.items():
        if folder_key not in ("lighting", "startergui"): # Skip these by default to reduce clutter
            (project_dir / folder_name).mkdir(parents=True, exist_ok=True)
            (out_dir / folder_name).mkdir(parents=True, exist_ok=True)

    print(f"  Created native service folders")
    print(f"  Created hidden .rpy/out/ artifacts directory")

    # rpy.toml
    default_config = f"""version = "2.0"
src = "."
out = ".rpy/out"
exclude = ["__pycache__", "*.pyc", "tools", ".rpy"]

[flags]
typed = false
fast = false
no_runtime = false
source_refs = false
compile_time = false

[folders]
workspace = "workspace"
replicatedstorage = "replicatedstorage"
serverscriptservice = "serverscriptservice"
starterplayerscripts = "starterplayerscripts"
lighting = "lighting"
startergui = "startergui"
"""
    config_path = project_dir / "rpy.toml"
    if not config_path.exists():
        config_path.write_text(default_config, encoding="utf-8")
        print(f"  Created {config_path}")
    else:
        print(f"  {config_path} already exists — skipping.")

    # Example scripts in each folder
    _write_example_scripts(project_dir, folders)

    # Copy runtime into each out subfolder
    runtime_src = Path(__file__).parent.parent / "runtime" / "python_runtime.lua"
    if runtime_src.exists():
        for folder_key, folder_name in folders.items():
            if folder_key not in ("lighting", "startergui"):
                runtime_dst = out_dir / folder_name / "python_runtime.lua"
                if not runtime_dst.exists():
                    shutil.copy2(runtime_src, runtime_dst)
        print(f"  Copied python_runtime.lua into .rpy/out/ subfolders")

    print(f"\n[OK] RPy project '{project_name}' initialized in {project_dir.resolve()}")
    print("  Folder structure:")
    print("    serverscriptservice/  (server scripts)")
    print("    starterplayerscripts/ (client scripts)")
    print("    replicatedstorage/    (shared modules)")
    print("    workspace/            (world logic)")
    print()
    print("  Next steps:")
    print("    rpy transpile . .rpy/out/        - transpile all scripts")
    print("    rpy live . .rpy/out/             - start dev server & sync to Studio")
    return 0


def _write_example_scripts(project_dir: Path, mapping: dict[str, str]) -> None:
    """Write starter scripts into each root subfolder."""
    examples = {
        "serverscriptservice": (
            '"""Server-side RPy script."""\n'
            "from roblox import game\n\n\n"
            "def on_player_added(player):\n"
            '    print(f"Player joined: {player.Name}")\n\n\n'
            'players = game.GetService("Players")\n'
            "players.PlayerAdded.connect(on_player_added)\n"
        ),
        "starterplayerscripts": (
            '"""Client-side RPy script."""\n'
            "from roblox import game\n\n\n"
            'players = game.GetService("Players")\n'
            "local_player = players.LocalPlayer\n"
            'print(f"Hello, {local_player.Name}!")\n'
        ),
        "replicatedstorage": (
            '"""Shared utility module."""\n\n\n'
            "def clamp(value, min_val, max_val):\n"
            '    """Clamp value between min and max."""\n'
            "    if value < min_val:\n"
            "        return min_val\n"
            "    if value > max_val:\n"
            "        return max_val\n"
            "    return value\n"
        ),
    }
    for folder_key, folder_name in mapping.items():
        script = examples.get(folder_key)
        if script is None:
            continue
        out_file = project_dir / folder_name / ("init.server.py" if folder_key == "serverscriptservice" else "init.client.py" if folder_key == "starterplayerscripts" else "utils.py")
        if not out_file.exists():
            out_file.write_text(script, encoding="utf-8")
            print(f"  Created {out_file}")


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch command: rebuild on file changes, with optional --sync hook."""
    out = Path(args.out)
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
        shared_runtime=args.shared_runtime,
        source_refs=args.source_refs,
        compile_time=args.compile_time,
        debug=args.debug,
    )
    interval = args.interval
    # Load config once
    project_dir = src if src.is_dir() else src.parent
    config = _load_rpy_config(project_dir)
    flags = _merge_flags(flags, config)

    if not src.exists():
        print(f"Error: {src} does not exist.", file=sys.stderr)
        return 1

    print(f"Watching {src} -> {out} (interval: {interval}s)")
    print("Press Ctrl+C to stop.\n")

    last_mtimes: dict[Path, float] = {}

    def get_files() -> list[Path]:
        if src.is_file():
            return [src]
        return [
            f for f in src.rglob("*.py")
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]

    def build_changed() -> int:
        """Rebuild all changed files. Returns count of newly transpiled files."""
        nonlocal last_mtimes
        files = get_files()
        rebuilt = 0
        for py_file in files:
            try:
                mtime = py_file.stat().st_mtime
            except OSError:
                continue

            if py_file not in last_mtimes or last_mtimes[py_file] < mtime:
                last_mtimes[py_file] = mtime
                # Resolve output path (respects mapped subfolders)
                if src.is_file():
                    lua_path = out if out.suffix == ".lua" else out / py_file.with_suffix(".lua").name
                else:
                    rel = py_file.relative_to(src)
                    lua_path = out / rel.with_suffix(".lua")
                try:
                    transpile_and_write(py_file, lua_path, flags, verbose=True)
                    rebuilt += 1
                except TranspileError as e:
                    source = py_file.read_text(encoding="utf-8") if py_file.exists() else None
                    print(f"  ✗ {py_file}:\n{e.format_with_context(source)}", file=sys.stderr)
                except Exception as e:
                    print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)
        return rebuilt

    """Alias for live syncing."""
    return cmd_live(args)


def cmd_lsp(args: argparse.Namespace) -> int:
    """Starts the RPy Language Server."""
    # Ensure the project root is in sys.path so 'server' and 'transpiler' are findable
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    try:
        from server.lsp_server import start_lsp_server
        start_lsp_server(host=args.host, port=args.port)
    except ImportError as e:
        print(f"\033[91mError:\033[0m Could not find LSP server module: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    """Live command: monitor files and sync to Dev Server."""
    src = Path(args.src)
    out = Path(args.out)
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
        shared_runtime=args.shared_runtime,
        source_refs=args.source_refs,
        compile_time=args.compile_time,
        debug=args.debug,
    )
    
    # Load config
    project_dir = src if src.is_dir() else src.parent
    config = _load_rpy_config(project_dir)
    flags = _merge_flags(flags, config)

    # Use asyncio to run the coordinator
    from sync.coordinator import start_live_sync
    try:
        asyncio.run(start_live_sync(src, out, flags))
    except KeyboardInterrupt:
        print("\nLive sync stopped.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install command: download and prepare dependencies."""
    project_dir = Path(args.dir).resolve()
    pm = PackageManager(str(project_dir))
    try:
        pm.install()
        return 0
    except Exception as e:
        print(f"\033[91mError during installation:\033[0m {e}", file=sys.stderr)
        return 1


def cmd_expose_out(args: argparse.Namespace) -> int:
    """Print the absolute path to the .rpy/out folder."""
    project_dir = Path(args.dir or ".").resolve()
    out_dir = project_dir / ".rpy" / "out"
    print(str(out_dir))
    return 0

def cmd_open_out(args: argparse.Namespace) -> int:
    """Open the .rpy/out folder in the system file explorer."""
    project_dir = Path(args.dir or ".").resolve()
    out_dir = project_dir / ".rpy" / "out"
    if not out_dir.exists():
        print(f"Error: {out_dir} does not exist. Run 'rpy build' first.", file=sys.stderr)
        return 1
        
    print(f"Opening {out_dir}...")
    import platform
    import subprocess
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(out_dir)
        elif system == "Darwin":
            subprocess.run(["open", str(out_dir)], check=True)
        else:
            subprocess.run(["xdg-open", str(out_dir)], check=True)
        return 0
    except Exception as e:
        print(f"Error opening folder: {e}", file=sys.stderr)
        return 1

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rpy",
        description="RPy — Python to Roblox Luau transpiler",
    )
    parser.add_argument("--version", action="version", version=f"rpy {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- build / transpile ----
    build_p = subparsers.add_parser("build", aliases=["transpile"], help="Build the project into Luau")
    build_p.add_argument("src", nargs="?", default=".", help="Source file or directory (default: .)")
    build_p.add_argument("out", nargs="?", default=".rpy/out", help="Output directory (default: .rpy/out)")
    build_p.add_argument("--typed", action="store_true", help="Emit Luau type annotations")
    build_p.add_argument("--fast", action="store_true", help="Skip truthiness shims for performance")
    build_p.add_argument("--no-runtime", action="store_true", dest="no_runtime", help="Do not emit runtime helpers")
    build_p.add_argument("--shared-runtime", action="store_true", help="Use centralized runtime instead of per-file inline")
    build_p.add_argument("--source-refs", action="store_true", help="Include --!nocheck and original file paths")
    build_p.add_argument("--compile-time", action="store_true", help="Enable build-time Python execution (requires @compile_time)")
    build_p.add_argument("--workers", type=int, default=os.cpu_count(), help="Number of concurrent workers")
    build_p.add_argument("--debug", action="store_true", help="Enable diagnostic logging")
    build_p.add_argument("--expose-out", action="store_true", help="Print the absolute path to the .rpy/out folder after building")
    build_p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # ---- validate ----
    validate_p = subparsers.add_parser("validate", aliases=["check"], help="Check syntax without outputting files")
    validate_p.add_argument("src", nargs="?", default=".", help="Source file or directory")
    validate_p.add_argument("--typed", action="store_true")
    validate_p.add_argument("--fast", action="store_true")
    validate_p.add_argument("--compile-time", action="store_true")
    validate_p.add_argument("--debug", action="store_true")
    validate_p.add_argument("--verbose", "-v", action="store_true")

    # ---- setup (init) ----
    setup_p = subparsers.add_parser("setup", aliases=["init"], help="Scaffold a new RPy project")
    setup_p.add_argument("dir", nargs="?", default=".", help="Project directory (default: .)")

    # ---- live (watch) ----
    live_p = subparsers.add_parser("live", aliases=["watch"], help="Live monitoring and Roblox sync")
    live_p.add_argument("src", nargs="?", default=".", help="Source file or directory")
    live_p.add_argument("out", nargs="?", default=".rpy/out", help="Output folder")
    live_p.add_argument("--typed", action="store_true")
    live_p.add_argument("--fast", action="store_true")
    live_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    live_p.add_argument("--shared-runtime", action="store_true")
    live_p.add_argument("--source-refs", action="store_true")
    live_p.add_argument("--compile-time", action="store_true")
    live_p.add_argument("--debug", action="store_true")
    live_p.add_argument("--interval", type=float, default=1.0,
                         help="Poll interval in seconds (default: 1.0)")
    live_p.add_argument("--show-out", action="store_true", help="Write transpiled files to disk even in live mode")
    live_p.add_argument("--backup-studio", action="store_true", help="Backup existing Studio scripts before overwriting")
    live_p.add_argument("--verbose", "-v", action="store_true")

    # ---- install ----
    install_p = subparsers.add_parser("install", help="Install dependencies from rpy.toml")
    install_p.add_argument("dir", nargs="?", default=".", help="Project directory")
    install_p.set_defaults(func=cmd_install)

    # ---- expose-out ----
    expose_p = subparsers.add_parser("expose-out", help="Print the absolute path to the .rpy/out folder")
    expose_p.add_argument("dir", nargs="?", default=".", help="Project directory")
    expose_p.set_defaults(func=cmd_expose_out)

    # ---- open-out ----
    open_p = subparsers.add_parser("open-out", help="Open the .rpy/out folder in file explorer")
    open_p.add_argument("dir", nargs="?", default=".", help="Project directory")
    open_p.set_defaults(func=cmd_open_out)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "transpile": cmd_build,
        "build": cmd_build,
        "validate": cmd_check,
        "check": cmd_check,
        "setup": cmd_init,
        "init": cmd_init,
        "live": cmd_live,
        "watch": cmd_live,
        "lsp": cmd_lsp,
        "install": cmd_install,
        "expose-out": cmd_expose_out,
        "open-out": cmd_open_out,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except TranspileError as e:
        # Most transpile errors are reported within handlers for file-specific context.
        # This catch-all handles any that escape or are global.
        print(f"\033[91mError:\033[0m {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130
    except Exception as e:
        # Use try-except to avoid encoding errors on windows when printing to stderr
        try:
            print(f"\033[91mInternal Compiler Error:\033[0m {e}", file=sys.stderr)
        except UnicodeEncodeError:
            print(f"\033[91mInternal Compiler Error:\033[0m {repr(e)}", file=sys.stderr)
        print("  This is likely a bug in RPy. Please report it with the stack trace.", file=sys.stderr)
        if os.environ.get("RPY_DEBUG") or (hasattr(args, "debug") and args.debug):
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

