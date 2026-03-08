"""
tests/unit/test_infrastructure.py

Unit tests for Phase 3 — AST Infrastructure:
  - transpiler/errors.py
  - transpiler/ast_utils.py
  - transpiler/node_registry.py
"""

from __future__ import annotations

import ast
import pytest

from transpiler.errors import (
    TranspileError,
    UnsupportedFeatureError,
    ParseError,
    InternalError,
)
from transpiler.ast_utils import (
    get_line,
    get_col,
    node_name,
    is_constant,
    is_name,
    is_none,
    is_range_call,
    unpack_range_args,
    get_attr_chain,
    needs_bool_shim,
)
from transpiler.node_registry import (
    statement,
    expression,
    get_statement_handler,
    get_expression_handler,
    list_registered,
)


# ===========================================================================
# errors.py
# ===========================================================================

class TestTranspileError:
    def test_basic_message(self):
        err = TranspileError("something went wrong")
        assert "something went wrong" in str(err)
        assert "TranspileError" in str(err)

    def test_with_line_and_col(self):
        err = TranspileError("bad node", line=12, col=5)
        s = str(err)
        assert "12" in s
        assert "5" in s

    def test_with_filename(self):
        err = TranspileError("bad", filename="game.py", line=3)
        assert "game.py" in str(err)

    def test_hint_appears(self):
        err = TranspileError("oops", hint="Try doing X instead.")
        assert "Try doing X instead." in str(err)

    def test_is_exception(self):
        with pytest.raises(TranspileError):
            raise TranspileError("test")


class TestUnsupportedFeatureError:
    def test_feature_in_message(self):
        err = UnsupportedFeatureError("match/case", line=7)
        s = str(err)
        assert "match/case" in s
        assert "UnsupportedFeatureError" in s

    def test_default_hint_for_known_feature(self):
        err = UnsupportedFeatureError("match/case")
        assert "if/elif" in err.hint  # default hint mentions if/elif

    def test_custom_hint_overrides_default(self):
        err = UnsupportedFeatureError("match/case", hint="Custom hint here.")
        assert "Custom hint here." in str(err)

    def test_unknown_feature_no_hint(self):
        err = UnsupportedFeatureError("time_travel")
        assert err.hint is None

    def test_is_transpile_error(self):
        err = UnsupportedFeatureError("yield")
        assert isinstance(err, TranspileError)


class TestParseError:
    def test_wraps_syntax_error(self):
        try:
            ast.parse("def (:")
        except SyntaxError as e:
            err = ParseError(e)
            assert "ParseError" in str(err)
            assert isinstance(err, TranspileError)

    def test_preserves_line(self):
        try:
            ast.parse("x = (")
        except SyntaxError as e:
            err = ParseError(e)
            assert err.line is not None


class TestInternalError:
    def test_message_and_hint(self):
        err = InternalError("unexpected node type")
        s = str(err)
        assert "InternalError" in s
        assert "unexpected node type" in s

    def test_is_transpile_error(self):
        assert isinstance(InternalError("x"), TranspileError)


# ===========================================================================
# ast_utils.py
# ===========================================================================

def _parse_expr(src: str) -> ast.expr:
    """Parse a Python expression and return its AST node."""
    tree = ast.parse(src, mode="eval")
    return tree.body


def _parse_stmt(src: str) -> ast.stmt:
    """Parse a Python statement and return its first AST node."""
    tree = ast.parse(src)
    return tree.body[0]


class TestGetLine:
    def test_constant_has_line(self):
        node = _parse_expr("42")
        assert get_line(node) == 1

    def test_missing_lineno_returns_none(self):
        node = ast.AST()  # bare AST has no lineno
        assert get_line(node) is None


class TestNodeName:
    def test_constant(self):
        assert node_name(_parse_expr("1")) == "Constant"

    def test_binop(self):
        assert node_name(_parse_expr("1 + 2")) == "BinOp"


class TestIsConstant:
    def test_number(self):
        assert is_constant(_parse_expr("42"))

    def test_string(self):
        assert is_constant(_parse_expr("'hello'"))

    def test_name_is_not_constant(self):
        assert not is_constant(_parse_expr("x"))


class TestIsName:
    def test_name_match(self):
        node = _parse_expr("foo")
        assert is_name(node, "foo")

    def test_name_mismatch(self):
        node = _parse_expr("foo")
        assert not is_name(node, "bar")

    def test_no_id_check(self):
        node = _parse_expr("foo")
        assert is_name(node)  # no id_ arg → just checks isinstance

    def test_constant_not_name(self):
        assert not is_name(_parse_expr("42"))


class TestIsNone:
    def test_none(self):
        assert is_none(_parse_expr("None"))

    def test_zero_not_none(self):
        assert not is_none(_parse_expr("0"))


class TestIsRangeCall:
    def test_range_one_arg(self):
        assert is_range_call(_parse_expr("range(5)"))

    def test_range_two_args(self):
        assert is_range_call(_parse_expr("range(0, 10)"))

    def test_range_three_args(self):
        assert is_range_call(_parse_expr("range(0, 10, 2)"))

    def test_non_range_name(self):
        assert not is_range_call(_parse_expr("xrange(5)"))

    def test_method_call_not_range(self):
        assert not is_range_call(_parse_expr("obj.range(5)"))

    def test_too_many_args(self):
        assert not is_range_call(_parse_expr("range(0, 10, 2, 3)"))


class TestUnpackRangeArgs:
    def test_one_arg(self):
        node = _parse_expr("range(5)")
        start, stop, step = unpack_range_args(node)
        assert isinstance(start, ast.Constant) and start.value == 0
        assert isinstance(stop, ast.Constant) and stop.value == 5
        assert step is None

    def test_two_args(self):
        node = _parse_expr("range(2, 8)")
        start, stop, step = unpack_range_args(node)
        assert start.value == 2   # type: ignore[attr-defined]
        assert stop.value == 8    # type: ignore[attr-defined]
        assert step is None

    def test_three_args(self):
        node = _parse_expr("range(0, 10, 2)")
        start, stop, step = unpack_range_args(node)
        assert step is not None
        assert step.value == 2    # type: ignore[attr-defined]


class TestGetAttrChain:
    def test_simple(self):
        node = _parse_expr("a.b")
        assert isinstance(node, ast.Attribute)
        assert get_attr_chain(node) == ["a", "b"]

    def test_deep_chain(self):
        node = _parse_expr("game.Workspace.Part")
        assert isinstance(node, ast.Attribute)
        assert get_attr_chain(node) == ["game", "Workspace", "Part"]


class TestNeedsBoolShim:
    def test_compare_safe(self):
        node = _parse_expr("x == 1")
        assert not needs_bool_shim(node)

    def test_boolop_safe(self):
        node = _parse_expr("a and b")
        assert not needs_bool_shim(node)

    def test_true_literal_safe(self):
        node = _parse_expr("True")
        assert not needs_bool_shim(node)

    def test_name_needs_shim(self):
        node = _parse_expr("x")
        assert needs_bool_shim(node)

    def test_number_needs_shim(self):
        node = _parse_expr("0")
        assert needs_bool_shim(node)

    def test_string_needs_shim(self):
        node = _parse_expr("''")
        assert needs_bool_shim(node)


# ===========================================================================
# node_registry.py
# ===========================================================================

class TestNodeRegistry:
    def test_register_and_retrieve_statement(self):
        @statement(ast.Pass)
        def _handle_pass(node, ctx):
            return "-- pass"

        handler = get_statement_handler(ast.Pass())
        assert handler(ast.Pass(), None) == "-- pass"  # type: ignore[arg-type]

    def test_register_and_retrieve_expression(self):
        @expression(ast.Starred)
        def _handle_starred(node, ctx):
            return "..."

        handler = get_expression_handler(ast.Starred())
        assert handler(ast.Starred(), None) == "..."  # type: ignore[arg-type]

    def test_missing_statement_raises_unsupported(self):
        # ast.Global is not registered in Phase 3
        with pytest.raises(UnsupportedFeatureError):
            get_statement_handler(ast.Global(names=[]))

    def test_missing_expression_raises_unsupported(self):
        # ast.Await is not registered in Phase 3
        with pytest.raises(UnsupportedFeatureError):
            get_expression_handler(ast.Await(value=ast.Constant(value=None)))

    def test_list_registered_returns_dict(self):
        result = list_registered()
        assert "statements" in result
        assert "expressions" in result
        assert isinstance(result["statements"], list)
