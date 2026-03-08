import pytest
from cli.main import main

@pytest.fixture
def workspace(tmp_path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()
    return src, out

def test_match_literal_transpilation(workspace):
    src, out = workspace
    py_code = """
x = 1
match x:
    case 1:
        print("one")
    case 2:
        print("two")
"""
    (src / "test.py").write_text(py_code, encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    assert "if (x == 1) then" in lua
    assert "elseif (x == 2) then" in lua
    assert 'print("one")' in lua

def test_match_or_pattern_transpilation(workspace):
    src, out = workspace
    py_code = """
match x:
    case 1 | 2:
        print("small")
"""
    (src / "test.py").write_text(py_code, encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    assert "(x == 1) or (x == 2)" in lua

def test_match_wildcard_transpilation(workspace):
    src, out = workspace
    py_code = """
match x:
    case 1:
        print("one")
    case _:
        print("other")
"""
    (src / "test.py").write_text(py_code, encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    # Our wildcard lowers to 'if True' or similar in the chain
    assert "elseif true then" in lua.lower()

def test_match_variable_binding_transpilation(workspace):
    src, out = workspace
    py_code = """
match get_val():
    case 1:
        print(1)
    case val:
        print(val)
"""
    (src / "test.py").write_text(py_code, encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    # Should use a temp var for non-simple subject
    assert "_match_tmp_1" in lua
    assert "local val = _match_tmp_1" in lua

def test_match_with_guard_transpilation(workspace):
    src, out = workspace
    py_code = """
match x:
    case val if val > 0:
        print("positive")
"""
    (src / "test.py").write_text(py_code, encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    assert "true and (val > 0)" in lua
    # Note: case val produces (true and guard). Constant folding might optimize this later, but for now it's fine.
