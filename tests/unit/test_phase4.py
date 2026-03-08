"""
tests/unit/test_phase4.py

Unit tests for Phase 4 — Minimal Transpiler + Runtime v1.
Tests cover: parser, transformer, and generator (golden output tests).

Each generator test follows the pattern:
  1. Parse Python source
  2. Transform it
  3. Generate Luau
  4. Assert the generated code contains expected Luau fragments
"""

from __future__ import annotations

import ast
import pytest

from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def transpile(src: str, **flag_kwargs) -> str:
    """Parse → transform → generate; return the Luau body (after header)."""
    tree = parse_source(src.strip())
    result = transform(tree)
    flags = CompilerFlags(**flag_kwargs)
    out = generate(result, flags)
    # Strip the header comment lines for cleaner assertions
    lines = out.code.splitlines()
    body_lines = [l for l in lines if not l.startswith("-- Generated") and not l.startswith("local _RT")]
    return "\n".join(body_lines).strip()


def contains(code: str, *fragments: str) -> bool:
    """Return True if all fragments appear in code."""
    return all(f in code for f in fragments)


# ===========================================================================
# Parser tests
# ===========================================================================

class TestParser:
    def test_simple_parse(self):
        tree = parse_source("x = 1")
        assert isinstance(tree, ast.Module)

    def test_syntax_error_raises_parse_error(self):
        from transpiler.errors import ParseError
        with pytest.raises(ParseError):
            parse_source("def (:")

    def test_parse_file(self, tmp_path):
        from transpiler.parser import parse_file
        p = tmp_path / "test.py"
        p.write_text("x = 42\n", encoding="utf-8")
        tree = parse_file(p)
        assert isinstance(tree, ast.Module)

    def test_unsupported_import_raises(self):
        from transpiler.errors import UnsupportedFeatureError
        with pytest.raises(UnsupportedFeatureError):
            src = parse_source("import os")
            transform(src)


# ===========================================================================
# Transformer tests
# ===========================================================================

class TestTransformer:
    def test_scope_map_module_level(self):
        tree = parse_source("x = 1\ny = 2")
        result = transform(tree)
        sm = result.scope_map
        assert sm.is_declared("x", 0)
        assert sm.is_declared("y", 0)

    def test_scope_map_function_params(self):
        tree = parse_source("def foo(a, b):\n    return a + b")
        result = transform(tree)
        sm = result.scope_map
        assert sm.is_declared("foo", 0)
        assert sm.is_declared("a", 1)
        assert sm.is_declared("b", 1)

    def test_annotation_stripping(self):
        tree = parse_source("x: int = 5")
        result = transform(tree)
        # After stripping, should be a plain Assign, no AnnAssign
        stmts = result.tree.body
        assert len(stmts) == 1
        assert isinstance(stmts[0], ast.Assign)

    def test_annotation_only_dropped(self):
        tree = parse_source("x: int")
        result = transform(tree)
        # Annotation-only (no value) should be dropped entirely
        assert len(result.tree.body) == 0

    def test_sdk_import_recorded(self):
        tree = parse_source("from roblox import Instance")
        result = transform(tree)
        assert "Instance" in result.import_info.sdk_names

    def test_unsupported_import_raises(self):
        from transpiler.errors import UnsupportedFeatureError
        with pytest.raises(UnsupportedFeatureError):
            tree = parse_source("import json")
            transform(tree)

    def test_global_raises(self):
        from transpiler.errors import UnsupportedFeatureError
        with pytest.raises(UnsupportedFeatureError):
            tree = parse_source("def f():\n    global x")
            transform(tree)


# ===========================================================================
# Generator golden tests — Literals & Assignments
# ===========================================================================

class TestLiterals:
    def test_integer(self):
        code = transpile("x = 42")
        assert "local x = 42" in code

    def test_float(self):
        code = transpile("x = 3.14")
        assert "local x = 3.14" in code

    def test_string(self):
        code = transpile('x = "hello"')
        assert 'local x = "hello"' in code

    def test_string_escaping(self):
        code = transpile('x = "say \\"hi\\""')
        assert '\\"hi\\"' in code

    def test_true(self):
        code = transpile("x = True")
        assert "local x = true" in code

    def test_false(self):
        code = transpile("x = False")
        assert "local x = false" in code

    def test_none(self):
        code = transpile("x = None")
        assert "local x = nil" in code

    def test_reassignment_no_local(self):
        code = transpile("x = 1\nx = 2")
        assert "local x = 1" in code
        assert "x = 2" in code
        # Second assignment must NOT have 'local'
        lines = [l.strip() for l in code.splitlines()]
        assert "x = 2" in lines
        assert "local x = 2" not in lines


# ===========================================================================
# Generator golden tests — Arithmetic
# ===========================================================================

class TestArithmetic:
    def test_addition(self):
        # Constant folding: 1 + 2 is pre-computed at compile time
        code = transpile("x = 1 + 2")
        assert "local x = 3" in code

    def test_subtraction(self):
        # Constant folding: 5 - 3 is pre-computed at compile time
        code = transpile("x = 5 - 3")
        assert "local x = 2" in code

    def test_multiplication(self):
        # Constant folding: 4 * 5 is pre-computed at compile time
        code = transpile("x = 4 * 5")
        assert "local x = 20" in code

    def test_division(self):
        code = transpile("x = 7 / 2")
        assert "(7 / 2)" in code

    def test_floor_division(self):
        code = transpile("x = 7 // 2")
        assert "math.floor(7 / 2)" in code

    def test_modulo(self):
        code = transpile("x = 7 % 3")
        assert "(7 % 3)" in code

    def test_power(self):
        # Constant folding: 2 ** 8 is pre-computed at compile time
        code = transpile("x = 2 ** 8")
        assert "local x = 256" in code

    def test_unary_neg(self):
        code = transpile("x = -5")
        assert "(-5)" in code

    def test_aug_assign_add(self):
        code = transpile("x = 0\nx += 1")
        assert "x = x + 1" in code

    def test_aug_assign_floor_div(self):
        code = transpile("x = 10\nx //= 3")
        assert "math.floor(x / 3)" in code

    def test_string_concat(self):
        code = transpile('x = "hello" + " world"')
        assert ".." in code


# ===========================================================================
# Generator golden tests — Comparisons & Bool
# ===========================================================================

class TestComparisons:
    def test_eq(self):
        code = transpile("x = a == b")
        assert "(a == b)" in code

    def test_neq(self):
        code = transpile("x = a != b")
        assert "(a ~= b)" in code

    def test_lt(self):
        code = transpile("x = a < b")
        assert "(a < b)" in code

    def test_bool_and(self):
        code = transpile("x = a and b")
        assert "a and b" in code

    def test_bool_or(self):
        code = transpile("x = a or b")
        assert "a or b" in code

    def test_bool_not(self):
        code = transpile("x = not a")
        assert "(not a)" in code


# ===========================================================================
# Generator golden tests — If / elif / else
# ===========================================================================

class TestIfElif:
    def test_simple_if(self):
        code = transpile("if x:\n    y = 1")
        assert "if " in code
        assert " then" in code
        assert "end" in code

    def test_if_else(self):
        code = transpile("if x:\n    y = 1\nelse:\n    y = 2")
        assert "else" in code
        assert "end" in code

    def test_if_elif_else(self):
        code = transpile("if x:\n    y = 1\nelif z:\n    y = 2\nelse:\n    y = 3")
        assert "elseif" in code
        assert "else" in code

    def test_bool_shim_applied(self):
        # Variables need py_bool (not --fast mode)
        code = transpile("if x:\n    pass", fast=False)
        assert "py_bool(x)" in code

    def test_bool_shim_skipped_fast(self):
        code = transpile("if x:\n    pass", fast=True)
        assert "py_bool" not in code
        assert "if x then" in code

    def test_compare_no_shim(self):
        # Comparisons are already boolean — no shim needed
        code = transpile("if x > 0:\n    pass", fast=False)
        assert "py_bool" not in code


# ===========================================================================
# Generator golden tests — While
# ===========================================================================

class TestWhile:
    def test_simple_while(self):
        code = transpile("while x:\n    x -= 1")
        assert "while " in code
        assert " do" in code
        assert "end" in code

    def test_while_false(self):
        code = transpile("while False:\n    pass", fast=True)
        assert "while false do" in code


# ===========================================================================
# Generator golden tests — For (range)
# ===========================================================================

class TestForRange:
    def test_range_one_arg(self):
        code = transpile("for i in range(5):\n    pass")
        assert "for i = 0, 4 do" in code

    def test_range_two_args(self):
        code = transpile("for i in range(2, 7):\n    pass")
        assert "for i = 2, 6 do" in code

    def test_range_three_args(self):
        code = transpile("for i in range(0, 10, 2):\n    pass")
        assert "for i = 0, 9, 2 do" in code

    def test_break(self):
        code = transpile("for i in range(5):\n    break")
        assert "break" in code

    def test_continue(self):
        code = transpile("for i in range(5):\n    continue")
        assert "continue" in code


# ===========================================================================
# Generator golden tests — Functions
# ===========================================================================

class TestFunctions:
    def test_simple_function(self):
        code = transpile("def greet():\n    return 1")
        assert "local function greet()" in code
        assert "return 1" in code
        assert "end" in code

    def test_function_with_params(self):
        code = transpile("def add(a, b):\n    return a + b")
        assert "local function add(a, b)" in code

    def test_return_none(self):
        code = transpile("def f():\n    return")
        assert "return" in code

    def test_vararg(self):
        code = transpile("def f(*args):\n    pass")
        assert "..." in code

    def test_lambda(self):
        code = transpile("f = lambda x: x + 1")
        assert "function(" in code
        assert "return" in code

    def test_call_builtin_print(self):
        code = transpile('print("hi")')
        assert 'print("hi")' in code

    def test_call_builtin_len(self):
        code = transpile("y = len(x)")
        assert "py_len(x)" in code

    def test_nested_function(self):
        code = transpile("def outer():\n    def inner():\n        pass\n    return inner")
        assert "function outer()" in code
        assert "function inner()" in code


# ===========================================================================
# Generator golden tests — Pass / Break / Continue / Delete / Assert
# ===========================================================================

class TestMiscStatements:
    def test_pass(self):
        code = transpile("pass")
        assert "-- pass" in code

    def test_delete(self):
        code = transpile("x = 1\ndel x")
        assert "x = nil" in code

    def test_assert_simple(self):
        code = transpile("assert x", fast=True)
        assert "assert(x)" in code

    def test_assert_with_message(self):
        code = transpile('assert x, "fail"', fast=True)
        assert 'assert(x, "fail")' in code


# ===========================================================================
# Generator flags
# ===========================================================================

class TestFlags:
    def test_no_runtime_header(self):
        flags = CompilerFlags(no_runtime=True)
        tree = parse_source("x = len(items)")
        result = transform(tree)
        out = generate(result, flags)
        assert "_RT" not in out.code

    def test_runtime_header_present_when_using_helpers(self):
        flags = CompilerFlags(no_runtime=False)
        tree = parse_source("x = len(items)")
        result = transform(tree)
        out = generate(result, flags)
        assert "py_len" in out.runtime_helpers
