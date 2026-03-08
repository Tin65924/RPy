"""
tests/unit/test_phase7.py

Unit tests for Phase 7 — --typed Mode (Type Inference + Typed Output).
Tests cover: type inference, typed variable declarations, typed function sigs.
"""

from __future__ import annotations

import ast
import pytest

from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags
from transpiler.type_inferrer import infer_types, TypeMap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def transpile(src: str, **flag_kwargs) -> str:
    tree = parse_source(src.strip())
    result = transform(tree)
    flags = CompilerFlags(**flag_kwargs)
    out = generate(result, flags)
    lines = out.code.splitlines()
    body_lines = []
    skip_header = True
    for l in lines:
        if skip_header:
            if l.startswith("-- Generated") or l.startswith("local _RT") or l.startswith("local py_") or l == "":
                continue
            skip_header = False
        body_lines.append(l)
    return "\n".join(body_lines).strip()


def infer(src: str) -> TypeMap:
    """Parse, transform, then infer types."""
    tree = parse_source(src.strip())
    result = transform(tree)
    return infer_types(result.tree)


# ===========================================================================
# Type inference (TypeMap)
# ===========================================================================

class TestTypeInference:
    def test_int_literal(self):
        tm = infer("x = 42")
        assert tm.get_var("x", 0) == "number"

    def test_float_literal(self):
        tm = infer("x = 3.14")
        assert tm.get_var("x", 0) == "number"

    def test_string_literal(self):
        tm = infer('x = "hello"')
        assert tm.get_var("x", 0) == "string"

    def test_bool_literal(self):
        tm = infer("x = True")
        assert tm.get_var("x", 0) == "boolean"

    def test_none_literal(self):
        tm = infer("x = None")
        assert tm.get_var("x", 0) == "nil"

    def test_binop_number(self):
        tm = infer("x = 1 + 2")
        assert tm.get_var("x", 0) == "number"

    def test_binop_string_concat(self):
        tm = infer('x = "a" + "b"')
        assert tm.get_var("x", 0) == "string"

    def test_comparison_is_bool(self):
        tm = infer("x = 1 > 0")
        assert tm.get_var("x", 0) == "boolean"

    def test_list_of_numbers(self):
        tm = infer("x = [1, 2, 3]")
        assert tm.get_var("x", 0) == "{number}"

    def test_list_of_strings(self):
        tm = infer('x = ["a", "b"]')
        assert tm.get_var("x", 0) == "{string}"

    def test_dict_is_table(self):
        tm = infer('x = {"a": 1}')
        assert tm.get_var("x", 0) == "{[any]: any}"

    def test_len_returns_number(self):
        tm = infer("x = len(items)")
        assert tm.get_var("x", 0) == "number"

    def test_str_returns_string(self):
        tm = infer("x = str(42)")
        assert tm.get_var("x", 0) == "string"

    def test_bool_returns_boolean(self):
        tm = infer("x = bool(0)")
        assert tm.get_var("x", 0) == "boolean"

    def test_unary_neg_preserves_number(self):
        tm = infer("x = -5")
        assert tm.get_var("x", 0) == "number"

    def test_not_is_boolean(self):
        tm = infer("x = not True")
        assert tm.get_var("x", 0) == "boolean"

    def test_fstring_is_string(self):
        tm = infer('x = f"hello {name}"')
        assert tm.get_var("x", 0) == "string"

    def test_function_return_type(self):
        tm = infer("def square(n):\n    return n * n")
        # n is 'any', so n*n is 'any'
        assert tm.get_return("square") == "any"

    def test_function_return_literal(self):
        tm = infer("def get_zero():\n    return 0")
        assert tm.get_return("get_zero") == "number"

    def test_unknown_defaults_to_any(self):
        tm = infer("x = some_function()")
        assert tm.get_var("x", 0) == "any"


# ===========================================================================
# Typed output (--typed flag)
# ===========================================================================

class TestTypedOutput:
    def test_typed_number(self):
        code = transpile("x = 42", typed=True)
        assert "local x: number = 42" in code

    def test_typed_string(self):
        code = transpile('x = "hello"', typed=True)
        assert 'local x: string = "hello"' in code

    def test_typed_boolean(self):
        code = transpile("x = True", typed=True)
        assert "local x: boolean = true" in code

    def test_typed_list_of_numbers(self):
        code = transpile("x = [1, 2, 3]", typed=True)
        assert "local x: {number}" in code

    def test_untyped_mode_no_annotations(self):
        code = transpile("x = 42", typed=False)
        assert ": number" not in code
        assert "local x = 42" in code

    def test_unknown_type_no_annotation(self):
        code = transpile("x = some_func()", typed=True)
        assert ": any" not in code  # 'any' should be suppressed
        assert "local x = some_func()" in code

    def test_typed_function_return(self):
        code = transpile("def zero():\n    return 0", typed=True)
        assert ": number" in code

    def test_typed_function_return_any_suppressed(self):
        code = transpile("def f(x):\n    return x", typed=True)
        # x is 'any', return is 'any', so no annotation
        assert "): " not in code or "): any" not in code

    def test_reassignment_no_annotation(self):
        code = transpile("x = 1\nx = 2", typed=True)
        assert "local x: number = 1" in code
        assert "x = 2" in code
        # Second line must NOT have type
        lines = [l.strip() for l in code.splitlines()]
        assert "x = 2" in lines
