"""
tests/unit/test_phase6.py

Unit tests for Phase 6 — Advanced Language + Runtime v3.
Tests cover: ClassDef, Try/Except/Raise, With, f-strings (JoinedStr),
and import handling edge cases.
"""

from __future__ import annotations

import pytest

from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags
from transpiler.errors import UnsupportedFeatureError


# ---------------------------------------------------------------------------
# Helper
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


def used_helpers(src: str) -> set:
    tree = parse_source(src.strip())
    result = transform(tree)
    out = generate(result, CompilerFlags())
    return out.runtime_helpers


# ===========================================================================
# Classes
# ===========================================================================

class TestClassDef:
    def test_simple_class(self):
        code = transpile("""\
class Dog:
    def __init__(self, name):
        self.name = name
    def bark(self):
        return "woof"
""")
        assert "local Dog = {}" in code
        assert "Dog.__index = Dog" in code
        assert "function Dog.new(name)" in code
        assert "local self = setmetatable({}, Dog)" in code
        assert "self.name = name" in code
        assert "return self" in code
        assert "function Dog:bark()" in code
        assert 'return "woof"' in code

    def test_class_with_inheritance(self):
        code = transpile("""\
class Puppy(Dog):
    def __init__(self, name, tiny):
        self.name = name
        self.tiny = tiny
""")
        assert "setmetatable({}, {__index = Dog})" in code
        assert "function Puppy.new(name, tiny)" in code

    def test_multiple_inheritance_raises(self):
        with pytest.raises(UnsupportedFeatureError, match="multiple inheritance"):
            transpile("class Bad(A, B):\n    pass")

    def test_class_level_attribute(self):
        code = transpile("""\
class Config:
    version = 1
    name = "app"
""")
        assert "Config.version = 1" in code
        assert 'Config.name = "app"' in code

    def test_method_without_self_body(self):
        code = transpile("""\
class Noop:
    def nothing(self):
        pass
""")
        assert "function Noop:nothing()" in code
        assert "-- pass" in code

    def test_empty_class(self):
        code = transpile("class Empty:\n    pass")
        assert "local Empty = {}" in code
        assert "-- pass" in code

    def test_decorator_raises(self):
        with pytest.raises(UnsupportedFeatureError, match="decorator"):
            transpile("@some_deco\nclass Bad:\n    pass")

    def test_init_auto_return_self(self):
        """__init__ should add 'return self' if no explicit return."""
        code = transpile("""\
class Foo:
    def __init__(self):
        self.x = 1
""")
        assert "return self" in code

    def test_init_with_explicit_return(self):
        """If __init__ explicitly returns, don't add another."""
        code = transpile("""\
class Foo:
    def __init__(self):
        self.x = 1
        return
""")
        # Should have return, then return self is NOT added
        lines = [l.strip() for l in code.splitlines()]
        # Count "return self" — should be 0 since explicit return is present
        assert lines.count("return self") == 0


# ===========================================================================
# Try / Except / Raise
# ===========================================================================

class TestTryExcept:
    def test_basic_try_except(self):
        code = transpile("""\
try:
    risky()
except:
    handle()
""")
        assert "local _ok, _err = pcall(function()" in code
        assert "risky()" in code
        assert "if not _ok then" in code
        assert "handle()" in code
        assert "end" in code

    def test_except_as(self):
        code = transpile("""\
try:
    risky()
except Exception as e:
    print(e)
""")
        assert "local e = _err" in code

    def test_try_finally(self):
        code = transpile("""\
try:
    risky()
except:
    handle()
finally:
    cleanup()
""")
        assert "cleanup()" in code

    def test_try_else(self):
        code = transpile("""\
try:
    safe()
except:
    handle()
else:
    success()
""")
        assert "if _ok then" in code
        assert "success()" in code


class TestRaise:
    def test_raise_with_message(self):
        code = transpile('raise ValueError("bad input")')
        assert 'error("bad input")' in code

    def test_raise_bare(self):
        code = transpile("""\
try:
    risky()
except:
    raise
""")
        assert "error(_err)" in code

    def test_raise_no_args(self):
        code = transpile("raise RuntimeError()")
        assert 'error("RuntimeError")' in code

    def test_raise_variable(self):
        code = transpile("raise msg")
        assert "error(msg)" in code


# ===========================================================================
# With statement
# ===========================================================================

class TestWith:
    def test_with_as(self):
        code = transpile("""\
with get_resource() as r:
    use(r)
""")
        assert "do" in code
        assert "local r = get_resource()" in code
        assert "use(r)" in code
        assert code.strip().endswith("end")

    def test_with_no_as(self):
        code = transpile("""\
with acquire_lock():
    work()
""")
        assert "do" in code
        assert "work()" in code


# ===========================================================================
# f-strings (JoinedStr)
# ===========================================================================

class TestFStrings:
    def test_simple_fstring(self):
        code = transpile('x = f"hello {name}"')
        assert ".." in code  # concatenation
        assert '"hello "' in code
        assert "py_str" in code or "name" in code

    def test_fstring_multiple_parts(self):
        code = transpile('x = f"{a} and {b}"')
        assert ".." in code

    def test_fstring_literal_only(self):
        code = transpile('x = f"plain text"')
        assert '"plain text"' in code

    def test_fstring_records_py_str(self):
        helpers = used_helpers('x = f"val: {v}"')
        assert "py_str" in helpers

    def test_fstring_with_expression(self):
        code = transpile('x = f"sum: {a + b}"')
        assert ".." in code

    def test_empty_fstring(self):
        code = transpile('x = f""')
        assert '""' in code


# ===========================================================================
# Imports (Phase 6 verifications — already handled but tested here)
# ===========================================================================

class TestImports:
    def test_roblox_import_passthrough(self):
        code = transpile("from roblox import Instance")
        # SDK imports produce no Luau code
        assert "require" not in code
        assert "Instance" not in code  # no assignment, it's a global

    def test_relative_import(self):
        code = transpile("from . import utils")
        assert "require(" in code
        assert "utils" in code

    def test_unsupported_stdlib_import(self):
        with pytest.raises(UnsupportedFeatureError):
            transpile("import json")

    def test_unsupported_from_stdlib(self):
        with pytest.raises(UnsupportedFeatureError):
            transpile("from os import path")


# ===========================================================================
# match/case (should raise)
# ===========================================================================

class TestMatchCase:
    """match/case is detected in parser and raises UnsupportedFeatureError."""
    # Can't easily test on Python < 3.10 since ast.parse won't produce Match nodes
    pass
