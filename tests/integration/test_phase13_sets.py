import pytest
from cli.main import main

@pytest.fixture
def workspace(tmp_path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()
    return src, out

def test_set_literal_transpilation(workspace):
    src, out = workspace
    (src / "test.py").write_text("s = {1, 2, 3}\nprint(len(s))\n", encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    assert "py_set_new({1, 2, 3})" in lua
    assert "py_len(s)" in lua

def test_set_methods_transpilation(workspace):
    src, out = workspace
    (src / "test.py").write_text("s = {1}\ns.add(2)\ns.discard(1)\ns.clear()\n", encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    assert "py_set_add(s, 2)" in lua
    assert "py_set_discard(s, 1)" in lua
    assert "py_set_clear(s)" in lua

def test_set_iteration_transpilation(workspace):
    src, out = workspace
    (src / "test.py").write_text("s = {1, 2}\nfor x in s:\n    print(x)\n", encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    # Should use py_iter for set/generic iteration
    assert "for _, x in py_iter(s) do" in lua

def test_set_contains_transpilation(workspace):
    src, out = workspace
    (src / "test.py").write_text("s = {1}\nprint(2 in s)\n", encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    assert "py_contains(s, 2)" in lua

def test_set_comprehension_source_transpilation(workspace):
    src, out = workspace
    (src / "test.py").write_text("s = {1}\nl = [x*2 for x in s]\n", encoding="utf-8")
    ret = main(["build", str(src), str(out)])
    assert ret == 0
    lua = (out / "test.lua").read_text(encoding="utf-8")
    # Comprehension should also use py_iter
    assert "for _, x in py_iter(s) do" in lua
