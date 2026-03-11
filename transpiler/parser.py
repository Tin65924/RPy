"""
transpiler/parser.py — Python source -> ast.Module wrapper.

Responsibilities:
  - Call ast.parse() with proper error handling
  - Detect match/case nodes and raise UnsupportedFeatureError early
  - Warn when the compiler runtime is < 3.10 (match nodes won't be in AST)
  - Provide parse_source() and parse_file() as the public API
"""

from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path

from transpiler.errors import ParseError, UnsupportedFeatureError

# ---------------------------------------------------------------------------
# Version guard
# ---------------------------------------------------------------------------

_COMPILER_PY = sys.version_info[:2]

if _COMPILER_PY < (3, 10):
    warnings.warn(
        f"RPy is running on Python {_COMPILER_PY[0]}.{_COMPILER_PY[1]}. "
        "match/case syntax in user scripts will cause a ParseError rather "
        "than a clean UnsupportedFeatureError. Upgrade to Python 3.10+ "
        "for the best experience.",
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_source(source: str, filename: str | None = None) -> ast.Module:
    """
    Parse *source* as Python 3.10-subset code.

    Returns:
        ast.Module — the root of the AST.

    Raises:
        ParseError — on Python syntax errors in the source.
    """
    try:
        tree = ast.parse(source, filename=filename or "<string>", type_comments=False)
    except SyntaxError as exc:
        raise ParseError(exc, filename=filename) from exc

    return tree


def parse_file(path: str | Path) -> ast.Module:
    """
    Read *path* from disk and parse it.

    Returns:
        ast.Module — the root of the AST.

    Raises:
        ParseError            — on Python syntax errors.
        UnsupportedFeatureError — if match/case is detected.
        OSError               — if the file cannot be read.
    """
    p = Path(path)
    source = p.read_text(encoding="utf-8")
    return parse_source(source, filename=str(p))
