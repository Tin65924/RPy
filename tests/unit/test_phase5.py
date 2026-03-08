"""
tests/unit/test_phase5.py

Unit tests for Phase 5 — Data Structures + Runtime v2.
Tests cover: list/dict/tuple literals, subscripts (0→1), slicing,
comprehensions, and method-call interception.
"""

from __future__ import annotations

import pytest

from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def transpile(src: str, **flag_kwargs) -> str:
    tree = parse_source(src.strip())
    result = transform(tree)
    flags = CompilerFlags(**flag_kwargs)
    out = generate(result, flags)
    lines = out.code.splitlines()
    # Strip header lines for cleaner assertions
    body_lines = []
    skip_header = True
    for l in lines:
        if skip_header:
            if l.startswith("-- Generated") or l.startswith("local _RT") or l.startswith("local py_") or l == "":
                continue
            skip_header = False
        body_lines.append(l)
    return "\n".join(body_lines).strip()


def used_helpers(src: str) -> set:
    tree = parse_source(src.strip())
    result = transform(tree)
    out = generate(result, CompilerFlags())
    return out.runtime_helpers


# ===========================================================================
# List literals
# ===========================================================================

class TestListLiterals:
    def test_empty_list(self):
        code = transpile("x = []")
        assert "local x = {}" in code

    def test_list_with_elements(self):
        code = transpile("x = [1, 2, 3]")
        assert "local x = {1, 2, 3}" in code

    def test_nested_list(self):
        code = transpile("x = [[1, 2], [3, 4]]")
        assert "{1, 2}" in code
        assert "{3, 4}" in code

    def test_list_of_strings(self):
        code = transpile('x = ["a", "b"]')
        assert '"a"' in code and '"b"' in code


# ===========================================================================
# Tuple literals
# ===========================================================================

class TestTupleLiterals:
    def test_tuple(self):
        code = transpile("x = (1, 2, 3)")
        assert "local x = {1, 2, 3}" in code

    def test_empty_tuple(self):
        code = transpile("x = ()")
        assert "local x = {}" in code


# ===========================================================================
# Dict literals
# ===========================================================================

class TestDictLiterals:
    def test_empty_dict(self):
        code = transpile("x = {}")
        assert "local x = {}" in code

    def test_dict_string_keys(self):
        code = transpile('x = {"name": "Alice", "age": 30}')
        assert "name" in code
        assert "age" in code

    def test_dict_identifier_keys_use_short_syntax(self):
        code = transpile('x = {"a": 1}')
        assert "a = 1" in code

    def test_dict_numeric_keys(self):
        code = transpile("x = {1: 'a', 2: 'b'}")
        assert "[1]" in code or "[2]" in code


# ===========================================================================
# Subscript (indexing) with 0→1 correction
# ===========================================================================

class TestSubscript:
    def test_literal_index_zero(self):
        code = transpile("y = items[0]")
        assert "items[1]" in code

    def test_literal_index_three(self):
        code = transpile("y = items[3]")
        assert "items[4]" in code

    def test_variable_index(self):
        code = transpile("y = items[i]")
        assert "items[i + 1]" in code

    def test_negative_index(self):
        code = transpile("y = items[-1]")
        assert "py_index(items, (-1))" in code

    def test_subscript_assignment_literal(self):
        code = transpile("items = []\nitems[0] = 5")
        assert "items[1] = 5" in code

    def test_subscript_assignment_variable(self):
        code = transpile("items = []\nitems[i] = 5")
        assert "items[i + 1] = 5" in code


# ===========================================================================
# Slicing
# ===========================================================================

class TestSlicing:
    def test_basic_slice(self):
        code = transpile("y = items[1:3]")
        assert "py_slice" in code

    def test_slice_with_step(self):
        code = transpile("y = items[::2]")
        assert "py_slice" in code

    def test_slice_open_end(self):
        code = transpile("y = items[1:]")
        assert "py_slice" in code

    def test_slice_records_runtime(self):
        helpers = used_helpers("y = items[1:3]")
        assert "py_slice" in helpers


# ===========================================================================
# List / dict method calls → runtime helpers
# ===========================================================================

class TestMethodCalls:
    def test_append(self):
        code = transpile("items.append(5)")
        assert "py_append(items, 5)" in code

    def test_pop(self):
        code = transpile("x = items.pop()")
        assert "py_pop(items)" in code

    def test_insert(self):
        code = transpile("items.insert(0, 99)")
        assert "py_insert(items, 0, 99)" in code

    def test_remove(self):
        code = transpile("items.remove(5)")
        assert "py_remove(items, 5)" in code

    def test_sort(self):
        code = transpile("items.sort()")
        assert "py_sort(items)" in code

    def test_reverse(self):
        code = transpile("items.reverse()")
        assert "py_reverse(items)" in code

    def test_extend(self):
        code = transpile("items.extend(other)")
        assert "py_extend(items, other)" in code

    def test_copy(self):
        code = transpile("y = items.copy()")
        assert "py_copy(items)" in code

    def test_dict_keys(self):
        code = transpile("k = d.keys()")
        assert "py_keys(d)" in code

    def test_dict_values(self):
        code = transpile("v = d.values()")
        assert "py_values(d)" in code

    def test_dict_items(self):
        code = transpile("i = d.items()")
        assert "py_items(d)" in code

    def test_dict_get(self):
        code = transpile('v = d.get("key", 0)')
        assert "py_get(d" in code

    def test_str_split(self):
        code = transpile('parts = s.split(",")')
        assert "py_split(s" in code

    def test_str_join(self):
        code = transpile('result = ",".join(parts)')
        assert "py_join" in code

    def test_str_upper(self):
        code = transpile("y = s.upper()")
        assert "py_upper(s)" in code

    def test_str_lower(self):
        code = transpile("y = s.lower()")
        assert "py_lower(s)" in code

    def test_str_strip(self):
        code = transpile("y = s.strip()")
        assert "py_strip(s)" in code

    def test_str_replace(self):
        code = transpile('y = s.replace("a", "b")')
        assert "py_replace(s" in code

    def test_str_find(self):
        code = transpile('y = s.find("x")')
        assert "py_find(s" in code

    def test_str_startswith(self):
        code = transpile('y = s.startswith("hello")')
        assert "py_startswith(s" in code

    def test_str_endswith(self):
        code = transpile('y = s.endswith("!")')
        assert "py_endswith(s" in code

    def test_method_records_runtime_helper(self):
        helpers = used_helpers("items.append(5)")
        assert "py_append" in helpers


# ===========================================================================
# List comprehensions
# ===========================================================================

class TestListComprehension:
    def test_simple_listcomp(self):
        code = transpile("squares = [x * x for x in range(5)]")
        assert "(function()" in code
        assert "table.insert" in code
        assert "return _r" in code
        assert "end)()" in code

    def test_listcomp_with_filter(self):
        code = transpile("evens = [x for x in range(10) if x % 2 == 0]", fast=True)
        assert "if " in code
        assert "table.insert" in code

    def test_listcomp_over_list(self):
        code = transpile("doubled = [x * 2 for x in items]")
        assert "ipairs" in code


# ===========================================================================
# Dict comprehensions
# ===========================================================================

class TestDictComprehension:
    def test_simple_dictcomp(self):
        code = transpile("sq = {x: x * x for x in range(5)}")
        assert "(function()" in code
        assert "_r[" in code
        assert "return _r" in code

    def test_dictcomp_with_filter(self):
        code = transpile("d = {k: v for k, v in pairs_data if v > 0}", fast=True)
        assert "if " in code


# ===========================================================================
# Builtin remap (sorted, enumerate, etc.)
# ===========================================================================

class TestBuiltinRemap:
    def test_sorted(self):
        code = transpile("y = sorted(items)")
        assert "py_sorted(items)" in code

    def test_abs_maps_to_math(self):
        code = transpile("y = abs(x)")
        assert "math.abs(x)" in code

    def test_type_maps_to_typeof(self):
        code = transpile("y = type(x)")
        assert "typeof(x)" in code

    def test_enumerate(self):
        code = transpile("y = enumerate(items)")
        assert "py_enumerate(items)" in code

    def test_zip(self):
        code = transpile("y = zip(a, b)")
        assert "py_zip(a, b)" in code

    def test_reversed(self):
        code = transpile("y = reversed(items)")
        assert "py_reversed(items)" in code
