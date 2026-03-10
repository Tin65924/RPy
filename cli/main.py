"""
cli/main.py — RPy command-line interface.

Usage:
    rpy transpile <src> <out> [--typed] [--fast] [--no-runtime] [--verbose]
    rpy validate <src>                — validate only, no output
    rpy setup [dir]                   — scaffold a new RPy project
    rpy live <src> <out> [flags]      — live file monitoring & Roblox sync
    
    (Aliases: build=transpile, check=validate, init=setup, watch=live)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

from transpiler.parser import parse_source, parse_file
from transpiler.transformer import transform
from transpiler.flags import CompilerFlags
from transpiler.generator import generate, GenerateResult
from transpiler.errors import TranspileError


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "0.2.0"



# ---------------------------------------------------------------------------
# rpy.json helpers
# ---------------------------------------------------------------------------

def _load_rpy_config(project_dir: Path) -> dict:
    """Load rpy.json from *project_dir*, returning an empty dict if not found."""
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
    # Only override if the CLI flag is at its default (False/None) 
    # and the config has a value. For simplicity, we just check each known key.
    if cfg_flags.get("typed") and not flags.typed:
        flags.typed = True
    if cfg_flags.get("fast") and not flags.fast:
        flags.fast = True
    if cfg_flags.get("no_runtime") and not flags.no_runtime:
        flags.no_runtime = True
    if cfg_flags.get("shared_runtime") and not flags.shared_runtime:
        flags.shared_runtime = True
    if cfg_flags.get("source_refs") and not flags.source_refs:
        flags.source_refs = True
    if cfg_flags.get("compile_time") and not flags.compile_time:
        flags.compile_time = True
        
    return flags


def _get_project_folders(config: dict) -> dict[str, str]:
    """Return folder mapping from config, falling back to defaults."""
    # We maintain the concept of folders but they are no longer Rojo-specific.
    # Standard Roblox script types mapping:
    #   server -> server scripts
    #   client -> client scripts
    #   shared -> module scripts
    raw = config.get("folders", {})
    mapping = {
        "server": "server",
        "client": "client",
        "shared": "shared",
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
) -> GenerateResult:
    """Parse → transform → generate a single .py file into Luau."""
    # Create a fresh copy of flags to avoid mutating shared state (Phase 14 fix)
    file_flags = flags
    if flags.script_type == "module":
        detected_type = _get_script_type(src_path)
        if detected_type != "module":
            from dataclasses import replace
            file_flags = replace(flags, script_type=detected_type)

    tree = parse_file(src_path)
    result = transform(tree, filename=str(src_path.absolute()), flags=file_flags)

    gen_result = generate(result, file_flags)
    return gen_result


def transpile_and_write(
    src_path: Path,
    out_path: Path,
    flags: CompilerFlags,
    verbose: bool = False,
) -> None:
    """Transpile a single file and write the result."""
    gen_result = transpile_file(src_path, flags, verbose)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(gen_result.code, encoding="utf-8")
    if verbose:
        helpers = ", ".join(sorted(gen_result.runtime_helpers)) or "(none)"
        print(f"  ✓ {src_path} → {out_path}  [runtime: {helpers}]")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> int:
    """Build command: transpile .py files to .lua."""
    src = Path(args.src)
    out = Path(args.out)
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
        shared_runtime=args.shared_runtime,
        source_refs=args.source_refs,
        compile_time=args.compile_time,
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
        print(f"Built 1 file → {out}")
        return 0

    if src.is_dir():
        py_files = [
            f for f in src.rglob("*.py")
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]
        if not py_files:
            print(f"No .py files found in {src}")
            return 1

        errors = 0
        for py_file in py_files:
            rel = py_file.relative_to(src)
            
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
            try:
                transpile_and_write(py_file, lua_file, flags, verbose=args.verbose)
            except TranspileError as e:
                source = py_file.read_text(encoding="utf-8") if py_file.exists() else None
                print(f"  ✗ {py_file}:\n{e.format_with_context(source)}", file=sys.stderr)
                errors += 1
            except Exception as e:
                print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)
                errors += 1

        total = len(py_files)
        ok = total - errors
        print(f"\nBuilt {ok}/{total} files → {out}")
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
        return 1
    print(f"\nCheck: all {total} files OK ✓")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """
    Init command: scaffold a new RPy project.

    Creates:
        src/
            server/
            client/
            shared/
        out/
            server/ client/ shared/
            python_runtime.lua
        rpy.json          — project configuration
    """
    project_dir = Path(args.dir or ".")
    project_name = project_dir.resolve().name or "RPyProject"

    # Determine folder mapping from existing rpy.json (if any)
    config = _load_rpy_config(project_dir)
    folders = _get_project_folders(config)

    # Create src subfolder structure
    src_dir = project_dir / "src"
    out_dir = project_dir / "out"
    for folder in folders:
        (src_dir / folder).mkdir(parents=True, exist_ok=True)
        (out_dir / folder).mkdir(parents=True, exist_ok=True)

    print(f"  Created src/ (server/, client/, shared/)")
    print(f"  Created out/ (server/, client/, shared/)")

    # rpy.json
    default_config = {
        "version": "2.0",
        "src": "src",
        "out": "out",
        "flags": {
            "typed": False,
            "fast": False,
            "no_runtime": False,
            "source_refs": False,
            "compile_time": False,
        },
        "exclude": ["__pycache__", "*.pyc"],
        "folders": {
            "workspace": "src/workspace",
            "server": "src/server",
            "client": "src/client",
            "shared": "src/shared"
        },
    }
    config_path = project_dir / "rpy.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(default_config, indent=2) + "\n", encoding="utf-8")
        print(f"  Created {config_path}")
    else:
        print(f"  {config_path} already exists — skipping.")

    # (Project file generation)

    # Example scripts in each folder
    _write_example_scripts(src_dir, folders)

    # Copy runtime into each out subfolder
    runtime_src = Path(__file__).parent.parent / "runtime" / "python_runtime.lua"
    if runtime_src.exists():
        for folder in folders:
            runtime_dst = out_dir / folder / "python_runtime.lua"
            if not runtime_dst.exists():
                shutil.copy2(runtime_src, runtime_dst)
        print(f"  Copied python_runtime.lua into out/ subfolders")

    print(f"\n✓ RPy project '{project_name}' initialized in {project_dir.resolve()}")
    print("  Folder structure:")
    print("    src/server/  → ServerScriptService    (server scripts)")
    print("    src/client/  → StarterPlayerScripts   (client scripts)")
    print("    src/shared/  → ReplicatedStorage      (shared modules)")
    print()
    print("  Next steps:")
    print("    rpy build src/ out/            — transpile all scripts")
    print("    rpy watch src/ out/            — live-reload scripts")
    return 0


def _write_example_scripts(src_dir: Path, mapping: dict[str, str]) -> None:
    """Write starter scripts into each src subfolder."""
    examples = {
        "server": (
            '"""Server-side RPy script."""\n'
            "from roblox import game\n\n\n"
            "def on_player_added(player):\n"
            '    print(f"Player joined: {player.Name}")\n\n\n'
            'players = game.GetService("Players")\n'
            "players.PlayerAdded.connect(on_player_added)\n"
        ),
        "client": (
            '"""Client-side RPy script."""\n'
            "from roblox import game\n\n\n"
            'players = game.GetService("Players")\n'
            "local_player = players.LocalPlayer\n"
            'print(f"Hello, {local_player.Name}!")\n'
        ),
        "shared": (
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
    for folder in mapping:
        script = examples.get(folder)
        if script is None:
            continue
        out_file = src_dir / folder / "main.py"
        if not out_file.exists():
            out_file.write_text(script, encoding="utf-8")
            print(f"  Created {out_file}")


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch command: rebuild on file changes, with optional --sync hook."""
    src = Path(args.src)
    out = Path(args.out)
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
        shared_runtime=args.shared_runtime,
        source_refs=args.source_refs,
        compile_time=args.compile_time,
    )
    interval = args.interval
    # Load config once
    project_dir = src if src.is_dir() else src.parent
    config = _load_rpy_config(project_dir)
    flags = _merge_flags(flags, config)

    if not src.exists():
        print(f"Error: {src} does not exist.", file=sys.stderr)
        return 1

    print(f"Watching {src} → {out} (interval: {interval}s)")
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

    try:
        while True:
            build_changed()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")
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

    # ---- transpile (build) ----
    transpile_p = subparsers.add_parser("transpile", aliases=["build"], help="Transpile .py files to .lua")
    transpile_p.add_argument("src", help="Source file or directory")
    transpile_p.add_argument("out", help="Output file or directory")
    transpile_p.add_argument("--typed", action="store_true", help="Emit Luau type annotations")
    transpile_p.add_argument("--fast", action="store_true", help="Skip py_bool() truthiness shims")
    transpile_p.add_argument("--no-runtime", action="store_true", dest="no_runtime",
                         help="Don't prepend runtime at all")
    transpile_p.add_argument("--shared-runtime", action="store_true",
                         help="Use a central require() instead of injecting snippets")
    transpile_p.add_argument("--source-refs", action="store_true",
                         help="Emit source line references as comments in Luau")
    transpile_p.add_argument("--compile-time", action="store_true",
                         help="Enable build-time Python execution (requires @compile_time)")
    transpile_p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # ---- validate (check) ----
    validate_p = subparsers.add_parser("validate", aliases=["check"], help="Validate .py files without output")
    validate_p.add_argument("src", help="Source file or directory")
    validate_p.add_argument("--typed", action="store_true", help="Enable typed mode for checking")
    validate_p.add_argument("--fast", action="store_true")
    validate_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    validate_p.add_argument("--shared-runtime", action="store_true")
    validate_p.add_argument("--source-refs", action="store_true")
    validate_p.add_argument("--compile-time", action="store_true")
    validate_p.add_argument("--verbose", "-v", action="store_true")

    # ---- setup (init) ----
    setup_p = subparsers.add_parser("setup", aliases=["init"], help="Scaffold a new RPy project")
    setup_p.add_argument("dir", nargs="?", default=".", help="Project directory (default: .)")

    # ---- live (watch) ----
    live_p = subparsers.add_parser("live", aliases=["watch"], help="Live monitoring and Roblox sync")
    live_p.add_argument("src", help="Source file or directory")
    live_p.add_argument("out", help="Output file or directory")
    live_p.add_argument("--typed", action="store_true")
    live_p.add_argument("--fast", action="store_true")
    live_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    live_p.add_argument("--shared-runtime", action="store_true")
    live_p.add_argument("--source-refs", action="store_true")
    live_p.add_argument("--compile-time", action="store_true")
    live_p.add_argument("--interval", type=float, default=1.0,
                         help="Poll interval in seconds (default: 1.0)")
    live_p.add_argument("--show-out", action="store_true", help="Write transpiled files to disk even in live mode")
    live_p.add_argument("--backup-studio", action="store_true", help="Backup existing Studio scripts before overwriting")
    live_p.add_argument("--verbose", "-v", action="store_true")

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
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except TranspileError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Internal error: {e}", file=sys.stderr)
        if os.environ.get("RPY_DEBUG"):
            raise
        return 2


if __name__ == "__main__":
    sys.exit(main())
