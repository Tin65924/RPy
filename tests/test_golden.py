"""
tests/test_golden.py — Golden Test Runner for RPy.

This test suite discovers all .py files in tests/golden/, transpiles them,
and compares the output against a .expected.lua file.
"""

import pytest
from pathlib import Path
from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags

GOLDEN_DIR = Path(__file__).parent / "golden"

def get_golden_files():
    """Discover all .py files in the golden directory."""
    return list(GOLDEN_DIR.glob("*.py"))

def transpile(src: str, **flag_kwargs) -> str:
    """Standard RPy pipeline for testing."""
    tree = parse_source(src.strip())
    result = transform(tree)
    flags = CompilerFlags(**flag_kwargs)
    out = generate(result, flags)
    return out.code.strip()

@pytest.mark.parametrize("py_file", get_golden_files(), ids=lambda p: p.name)
def test_golden(py_file: Path):
    """Run a single golden test case."""
    expected_file = py_file.with_suffix(".expected.lua")
    
    # Read source Python
    py_code = py_file.read_text(encoding="utf-8")
    
    # Transpile to Luau
    # Note: We use default flags for golden tests unless specified in the filename
    actual_luau = transpile(py_code)
    
    # If expected file doesn't exist, create it (bootstrap mode)
    if not expected_file.exists():
        expected_file.write_text(actual_luau, encoding="utf-8")
        pytest.skip(f"Created expected file for {py_file.name}. Please review it.")
    
    expected_luau = expected_file.read_text(encoding="utf-8").strip()
    
    # Compare
    # We strip whitespace to be resilient to minor formatting differences
    # but the goal of Phase 2 (Printer) will be to make this even more robust.
    assert actual_luau == expected_luau, f"Output mismatch for {py_file.name}. See diff above."

def test_round_trip_validation():
    """
    Placeholder for Phase 1 enhancement: 
    Verify generated Luau is syntactically valid using a Luau tool if available.
    """
    pass
