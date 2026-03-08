"""
cli/main.py — RPy command-line interface.

Usage:
    rpy build <src> <out> [--typed] [--fast] [--no-runtime] [--verbose] [--sync]
    rpy check <src>                   — validate only, no output
    rpy init [dir]                    — scaffold a new RPy project (with Rojo support)
    rpy watch <src> <out> [flags]     — rebuild on file changes, with optional auto-sync
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

from transpiler.parser import parse_source, parse_file
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags, GenerateResult
from transpiler.errors import TranspileError


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "0.2.0"


# ---------------------------------------------------------------------------
# Default Rojo folder mapping:  src-subfolder → Roblox service name
# ---------------------------------------------------------------------------
_DEFAULT_ROJO_MAPPING = {
    "server": "ServerScriptService",
    "client": "StarterPlayerScripts",
    "shared": "ReplicatedStorage",
}

# Template for the Rojo default.project.json
_ROJO_PROJECT_TEMPLATE = {
    "name": "RPyProject",
    "tree": {
        "$className": "DataModel",
    },
}


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


def _rojo_mapping(config: dict) -> dict[str, str]:
    """Return folder→service mapping from config, falling back to defaults."""
    raw = config.get("rojo_mapping", {})
    mapping = dict(_DEFAULT_ROJO_MAPPING)
    mapping.update(raw)
    return mapping


# ---------------------------------------------------------------------------
# Rojo project.json generation & safe merging
# ---------------------------------------------------------------------------

def _build_rojo_tree(project_dir: Path, out_dir: Path, mapping: dict[str, str]) -> dict:
    """
    Construct the Rojo 'tree' section mapping out subfolders to Roblox services.
    Only includes subfolders that actually exist under *out_dir*.
    Paths in JSON are saved relative to *project_dir*.
    """
    tree: dict = {"$className": "DataModel"}
    for folder, service in mapping.items():
        folder_path = out_dir / folder
        if folder_path.exists():
            # Calculate path relative to project_dir for the JSON
            try:
                rel_path = folder_path.relative_to(project_dir)
            except ValueError:
                # Fallback to absolute if not under project_dir
                rel_path = folder_path
            
            tree[service] = {
                "$className": service,
                folder: {
                    "$path": str(rel_path),
                },
            }
    return tree


def _write_rojo_config(
    project_dir: Path,
    out_dir: Path,
    mapping: dict[str, str],
    project_name: str = "RPyProject",
) -> None:
    """
    Create or safely merge a Rojo default.project.json.

    If the file already exists:
      1. Back it up to default.project.backup.json.
      2. Merge RPy's tree entries into the existing config (non-destructive).
    """
    rojo_path = project_dir / "default.project.json"
    new_tree = _build_rojo_tree(project_dir, out_dir, mapping)
    new_config = {"name": project_name, "tree": new_tree}

    if rojo_path.exists():
        # Back up the existing config
        backup_path = project_dir / "default.project.backup.json"
        shutil.copy2(rojo_path, backup_path)
        print(f"  Backed up existing Rojo config → {backup_path}")

        # Load existing and merge our keys in
        try:
            existing = json.loads(rojo_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

        existing_tree = existing.get("tree", {"$className": "DataModel"})
        # Merge: RPy entries win on conflict, existing non-RPy entries are preserved
        merged_tree = {**existing_tree, **new_tree}
        existing["tree"] = merged_tree
        rojo_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"  Merged Rojo mappings → {rojo_path}")
    else:
        rojo_path.write_text(json.dumps(new_config, indent=2) + "\n", encoding="utf-8")
        print(f"  Created {rojo_path}")


# ---------------------------------------------------------------------------
# Auto-sync hook (runs rojo serve/build after successful transpile)
# ---------------------------------------------------------------------------

def _run_sync_hook(config: dict, project_dir: Path, verbose: bool) -> None:
    """
    Run the configured sync command after a successful build.

    Configured via rpy.json:
        "sync_command": "rojo build"   (default)
    or specify a full command list:
        "sync_command": ["rojo", "serve", "--watch"]
    """
    sync_cmd = config.get("sync_command", None)
    if sync_cmd is None:
        # Default: try to run `rojo build` if rojo is available
        sync_cmd = "rojo build"

    if isinstance(sync_cmd, str):
        cmd_parts = sync_cmd.split()
    else:
        cmd_parts = list(sync_cmd)

    if verbose:
        print(f"  → Running sync: {' '.join(cmd_parts)}")

    try:
        result = subprocess.run(
            cmd_parts, cwd=str(project_dir), capture_output=not verbose, timeout=30
        )
        if result.returncode != 0 and verbose:
            print(f"  ⚠ Sync command exited with code {result.returncode}", file=sys.stderr)
        elif verbose:
            print("  ✓ Sync complete.")
    except FileNotFoundError:
        print(
            f"  ⚠ Sync command '{cmd_parts[0]}' not found. "
            f"Is Rojo installed and in PATH?",
            file=sys.stderr,
        )
    except subprocess.TimeoutExpired:
        print("  ⚠ Sync command timed out after 30s.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Unmapped file warning
# ---------------------------------------------------------------------------

def _warn_unmapped(src_dir: Path, mapping: dict[str, str], verbose: bool) -> None:
    """
    Warn about .py files under src_dir that sit outside mapped subfolders.
    These files will still be transpiled but won't be auto-synced via Rojo.
    """
    if not src_dir.is_dir():
        return
    mapped_folders = set(mapping.keys())
    unmapped: list[Path] = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(src_dir)
        top_folder = rel.parts[0] if len(rel.parts) > 1 else None
        if top_folder not in mapped_folders:
            unmapped.append(py_file)
    if unmapped:
        print(
            f"\n⚠  Warning: {len(unmapped)} file(s) are outside mapped Rojo folders "
            f"({', '.join(sorted(mapped_folders))}):",
            file=sys.stderr,
        )
        for f in unmapped[:5]:
            print(f"     {f}", file=sys.stderr)
        if len(unmapped) > 5:
            print(f"     ... and {len(unmapped)-5} more.", file=sys.stderr)
        print(
            "   These files will be transpiled but not auto-mapped in default.project.json.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Core transpile function
# ---------------------------------------------------------------------------

def transpile_file(
    src_path: Path,
    flags: CompilerFlags,
    verbose: bool = False,
) -> GenerateResult:
    """Parse → transform → generate a single .py file into Luau."""
    tree = parse_file(src_path)
    result = transform(tree)
    gen_result = generate(result, flags)
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
    )

    # Load project config for sync/mapping support
    project_dir = src.parent if src.is_file() else src.parent
    config = _load_rpy_config(project_dir)
    mapping = _rojo_mapping(config)

    if src.is_file():
        if out.suffix == "":
            out = out / src.with_suffix(".lua").name
        transpile_and_write(src, out, flags, verbose=args.verbose)
        print(f"Built 1 file → {out}")
        if getattr(args, "sync", False):
            _run_sync_hook(config, project_dir, verbose=args.verbose)
        return 0

    if src.is_dir():
        # Warn about files sitting outside mapped Rojo folders
        _warn_unmapped(src, mapping, verbose=args.verbose)

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
            lua_file = out / rel.with_suffix(".lua")
            try:
                transpile_and_write(py_file, lua_file, flags, verbose=args.verbose)
            except TranspileError as e:
                print(f"  ✗ {py_file}: {e}", file=sys.stderr)
                errors += 1
            except Exception as e:
                print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)
                errors += 1

        total = len(py_files)
        ok = total - errors
        print(f"\nBuilt {ok}/{total} files → {out}")
        if errors:
            print(f"  {errors} file(s) had errors.", file=sys.stderr)
        elif getattr(args, "sync", False):
            _run_sync_hook(config, project_dir, verbose=args.verbose)
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
    )

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
            print(f"  ✗ {py_file}: {e}", file=sys.stderr)
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
    Init command: scaffold a new RPy + Rojo project.

    Creates:
        src/
            server/      → ServerScriptService
            client/      → StarterPlayerScripts
            shared/      → ReplicatedStorage
        out/
            server/ client/ shared/
            python_runtime.lua
        rpy.json          — project configuration
        default.project.json — Rojo configuration (or merged if it exists)
    """
    project_dir = Path(args.dir or ".")
    project_name = project_dir.resolve().name or "RPyProject"

    # Determine folder mapping from existing rpy.json (if any)
    config = _load_rpy_config(project_dir)
    mapping = _rojo_mapping(config)

    # Create src subfolder structure
    src_dir = project_dir / "src"
    out_dir = project_dir / "out"
    for folder in mapping:
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
        },
        "exclude": ["__pycache__", "*.pyc"],
        "rojo_mapping": {
            "server": "ServerScriptService",
            "client": "StarterPlayerScripts",
            "shared": "ReplicatedStorage",
        },
        "sync_command": "rojo build",
    }
    config_path = project_dir / "rpy.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(default_config, indent=2) + "\n", encoding="utf-8")
        print(f"  Created {config_path}")
    else:
        print(f"  {config_path} already exists — skipping.")

    # default.project.json (create or merge)
    _write_rojo_config(project_dir, out_dir, mapping, project_name=project_name)

    # Example scripts in each folder
    _write_example_scripts(src_dir, mapping)

    # Copy runtime into each out subfolder
    runtime_src = Path(__file__).parent.parent / "runtime" / "python_runtime.lua"
    if runtime_src.exists():
        for folder in mapping:
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
    print("    rpy build src/ out/ --sync     — transpile and run rojo build")
    print("    rpy watch src/ out/ --sync     — live-reload with Rojo")
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
    )
    interval = args.interval
    do_sync = getattr(args, "sync", False)

    # Load config once for mapping + sync
    project_dir = src if src.is_dir() else src.parent
    config = _load_rpy_config(project_dir)
    mapping = _rojo_mapping(config)

    if not src.exists():
        print(f"Error: {src} does not exist.", file=sys.stderr)
        return 1

    print(f"Watching {src} → {out} (interval: {interval}s)")
    if do_sync:
        sync_cmd = config.get("sync_command", "rojo build")
        print(f"  Auto-sync enabled: '{sync_cmd}' will run after each successful rebuild.")
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
                    print(f"  ✗ {py_file}: {e}", file=sys.stderr)
                except Exception as e:
                    print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)
        return rebuilt

    try:
        while True:
            rebuilt = build_changed()
            if rebuilt > 0 and do_sync:
                _run_sync_hook(config, project_dir, verbose=args.verbose)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")
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

    # ---- build ----
    build_p = subparsers.add_parser("build", help="Transpile .py files to .lua")
    build_p.add_argument("src", help="Source file or directory")
    build_p.add_argument("out", help="Output file or directory")
    build_p.add_argument("--typed", action="store_true", help="Emit Luau type annotations")
    build_p.add_argument("--fast", action="store_true", help="Skip py_bool() truthiness shims")
    build_p.add_argument("--no-runtime", action="store_true", dest="no_runtime",
                         help="Don't prepend runtime require")
    build_p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    build_p.add_argument("--sync", action="store_true",
                         help="Run sync command (e.g. rojo build) after successful build")

    # ---- check ----
    check_p = subparsers.add_parser("check", help="Validate .py files without output")
    check_p.add_argument("src", help="Source file or directory")
    check_p.add_argument("--typed", action="store_true", help="Enable typed mode for checking")
    check_p.add_argument("--fast", action="store_true")
    check_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    check_p.add_argument("--verbose", "-v", action="store_true")

    # ---- init ----
    init_p = subparsers.add_parser("init", help="Scaffold a new RPy project with Rojo support")
    init_p.add_argument("dir", nargs="?", default=".", help="Project directory (default: .)")

    # ---- watch ----
    watch_p = subparsers.add_parser("watch", help="Watch and rebuild on changes")
    watch_p.add_argument("src", help="Source file or directory")
    watch_p.add_argument("out", help="Output file or directory")
    watch_p.add_argument("--typed", action="store_true")
    watch_p.add_argument("--fast", action="store_true")
    watch_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    watch_p.add_argument("--interval", type=float, default=1.0,
                         help="Poll interval in seconds (default: 1.0)")
    watch_p.add_argument("--sync", action="store_true",
                         help="Run sync command after each rebuild")
    watch_p.add_argument("--verbose", "-v", action="store_true")

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
        "build": cmd_build,
        "check": cmd_check,
        "init": cmd_init,
        "watch": cmd_watch,
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
