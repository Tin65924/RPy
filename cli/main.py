"""
cli/main.py — RPy command-line interface.

Usage:
    rpy build <src> <out> [--typed] [--fast] [--no-runtime] [--verbose]
    rpy check <src>                   — validate only, no output
    rpy init                          — scaffold a new RPy project
    rpy watch <src> <out> [flags]     — rebuild on file changes
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import json
from pathlib import Path
from typing import Optional, Sequence

from transpiler.parser import parse_source, parse_file
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags, GenerateResult
from transpiler.errors import TranspileError


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "0.1.0"


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

    if src.is_file():
        # Single file
        if out.suffix == "":
            out = out / src.with_suffix(".lua").name
        transpile_and_write(src, out, flags, verbose=args.verbose)
        print(f"Built 1 file → {out}")
        return 0

    if src.is_dir():
        # Directory: transpile all .py files
        py_files = list(src.rglob("*.py"))
        # Exclude __init__.py and __pycache__
        py_files = [
            f for f in py_files
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
    """Init command: scaffold a new RPy project."""
    project_dir = Path(args.dir or ".")

    # Create directory structure
    dirs = [
        project_dir / "src",
        project_dir / "out",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  Created {d}/")

    # Create rpy.json config
    config = {
        "version": "1.0",
        "src": "src",
        "out": "out",
        "flags": {
            "typed": False,
            "fast": False,
            "no_runtime": False,
        },
        "exclude": ["__pycache__", "*.pyc"],
    }
    config_path = project_dir / "rpy.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"  Created {config_path}")
    else:
        print(f"  {config_path} already exists, skipping.")

    # Create example script
    example = project_dir / "src" / "main.py"
    if not example.exists():
        example.write_text(
            '"""RPy example script."""\n'
            "from roblox import Instance, workspace\n\n\n"
            "def create_part():\n"
            '    part = Instance.new("Part")\n'
            "    part.Parent = workspace\n"
            "    return part\n\n\n"
            "create_part()\n",
            encoding="utf-8",
        )
        print(f"  Created {example}")

    # Copy runtime
    runtime_src = Path(__file__).parent.parent / "runtime" / "python_runtime.lua"
    runtime_dst = project_dir / "out" / "python_runtime.lua"
    if runtime_src.exists() and not runtime_dst.exists():
        import shutil
        shutil.copy2(runtime_src, runtime_dst)
        print(f"  Copied runtime → {runtime_dst}")

    print(f"\n✓ RPy project initialized in {project_dir.resolve()}")
    print("  Next: run `rpy build src out` to transpile.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch command: rebuild on file changes (simple polling)."""
    src = Path(args.src)
    out = Path(args.out)
    flags = CompilerFlags(
        typed=args.typed,
        fast=args.fast,
        no_runtime=args.no_runtime,
    )
    interval = args.interval

    if not src.exists():
        print(f"Error: {src} does not exist.", file=sys.stderr)
        return 1

    print(f"Watching {src} → {out} (interval: {interval}s)")
    print("Press Ctrl+C to stop.\n")

    # Track mtimes
    last_mtimes: dict[Path, float] = {}

    def get_files() -> list[Path]:
        if src.is_file():
            return [src]
        return [
            f for f in src.rglob("*.py")
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]

    def build_changed() -> None:
        nonlocal last_mtimes
        files = get_files()
        for py_file in files:
            try:
                mtime = py_file.stat().st_mtime
            except OSError:
                continue

            if py_file not in last_mtimes or last_mtimes[py_file] < mtime:
                last_mtimes[py_file] = mtime
                if src.is_file():
                    lua_path = out if out.suffix == ".lua" else out / py_file.with_suffix(".lua").name
                else:
                    rel = py_file.relative_to(src)
                    lua_path = out / rel.with_suffix(".lua")
                try:
                    transpile_and_write(py_file, lua_path, flags, verbose=True)
                except TranspileError as e:
                    print(f"  ✗ {py_file}: {e}", file=sys.stderr)
                except Exception as e:
                    print(f"  ✗ {py_file}: internal error: {e}", file=sys.stderr)

    try:
        while True:
            build_changed()
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

    # build
    build_p = subparsers.add_parser("build", help="Transpile .py files to .lua")
    build_p.add_argument("src", help="Source file or directory")
    build_p.add_argument("out", help="Output file or directory")
    build_p.add_argument("--typed", action="store_true", help="Emit Luau type annotations")
    build_p.add_argument("--fast", action="store_true", help="Skip py_bool() truthiness shims")
    build_p.add_argument("--no-runtime", action="store_true", dest="no_runtime",
                         help="Don't prepend runtime require")
    build_p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # check
    check_p = subparsers.add_parser("check", help="Validate .py files without output")
    check_p.add_argument("src", help="Source file or directory")
    check_p.add_argument("--typed", action="store_true", help="Enable typed mode for checking")
    check_p.add_argument("--fast", action="store_true")
    check_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    check_p.add_argument("--verbose", "-v", action="store_true")

    # init
    init_p = subparsers.add_parser("init", help="Scaffold a new RPy project")
    init_p.add_argument("dir", nargs="?", default=".", help="Project directory (default: .)")

    # watch
    watch_p = subparsers.add_parser("watch", help="Watch and rebuild on changes")
    watch_p.add_argument("src", help="Source file or directory")
    watch_p.add_argument("out", help="Output file or directory")
    watch_p.add_argument("--typed", action="store_true")
    watch_p.add_argument("--fast", action="store_true")
    watch_p.add_argument("--no-runtime", action="store_true", dest="no_runtime")
    watch_p.add_argument("--interval", type=float, default=1.0,
                         help="Poll interval in seconds (default: 1.0)")

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
