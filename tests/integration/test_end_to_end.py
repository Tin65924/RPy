"""
tests/integration/test_end_to_end.py

End-to-end integration tests — full pipeline from Python source to Luau output.
These tests verify that complete, realistic scripts transpile correctly.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from cli.main import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with src/ and out/ directories."""
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()
    return src, out


# ===========================================================================
# End-to-end: realistic scripts
# ===========================================================================

class TestEndToEnd:
    def test_hello_world(self, workspace):
        src, out = workspace
        (src / "hello.py").write_text(
            'print("Hello from RPy!")\n',
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "hello.lua").read_text(encoding="utf-8")
        assert 'print("Hello from RPy!")' in lua

    def test_variables_and_math(self, workspace):
        src, out = workspace
        (src / "math.py").write_text(
            "x = 10\ny = 20\nz = x + y * 2\nresult = z / 3\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "math.lua").read_text(encoding="utf-8")
        assert "local x = 10" in lua
        assert "local z = (x + (y * 2))" in lua

    def test_function_and_loop(self, workspace):
        src, out = workspace
        (src / "loop.py").write_text(
            "def greet(name):\n"
            '    return f"Hello {name}"\n\n'
            "for i in range(3):\n"
            "    print(greet(i))\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "loop.lua").read_text(encoding="utf-8")
        assert "local function greet(name)" in lua
        assert "for i = 0, 2 do" in lua

    def test_class_transpilation(self, workspace):
        src, out = workspace
        (src / "npc.py").write_text(
            "class NPC:\n"
            "    def __init__(self, name, health):\n"
            "        self.name = name\n"
            "        self.health = health\n"
            "    def take_damage(self, amount):\n"
            "        self.health = self.health - amount\n"
            "    def is_alive(self):\n"
            "        return self.health > 0\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "npc.lua").read_text(encoding="utf-8")
        assert "local NPC = {}" in lua
        assert "NPC.__index = NPC" in lua
        assert "function NPC.new(name, health)" in lua
        assert "local self = setmetatable({}, NPC)" in lua
        assert "function NPC:take_damage(amount)" in lua
        assert "function NPC:is_alive()" in lua

    def test_try_except(self, workspace):
        src, out = workspace
        (src / "safe.py").write_text(
            "try:\n"
            "    risky()\n"
            "except:\n"
            "    print('error')\n"
            "finally:\n"
            "    cleanup()\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "safe.lua").read_text(encoding="utf-8")
        assert "pcall" in lua
        assert "cleanup()" in lua

    def test_list_operations(self, workspace):
        src, out = workspace
        (src / "lists.py").write_text(
            "items = [1, 2, 3]\n"
            "items.append(4)\n"
            "first = items[0]\n"
            "last = items[-1]\n"
            "sliced = items[1:3]\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "lists.lua").read_text(encoding="utf-8")
        assert "py_append" in lua
        assert "items[1]" in lua  # 0→1 correction
        assert "py_index" in lua  # negative index
        assert "py_slice" in lua

    def test_roblox_sdk_script(self, workspace):
        src, out = workspace
        (src / "game.py").write_text(
            "from roblox import Instance, workspace, Vector3\n\n"
            "def spawn_part(pos):\n"
            '    part = Instance.new("Part")\n'
            "    part.Position = pos\n"
            "    part.Parent = workspace\n"
            "    return part\n\n"
            "spawn_part(Vector3.new(0, 10, 0))\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        lua = (out / "game.lua").read_text(encoding="utf-8")
        assert "Instance.new" in lua
        assert "Vector3.new(0, 10, 0)" in lua
        # SDK import should NOT produce a require
        lines = [l for l in lua.splitlines() if "require" in l]
        assert all("python_runtime" in l for l in lines)

    def test_typed_mode_e2e(self, workspace):
        src, out = workspace
        (src / "typed.py").write_text(
            "x = 42\n"
            'name = "Alice"\n'
            "active = True\n"
            "scores = [100, 200, 300]\n"
            "def double(n):\n"
            "    return n * 2\n",
            encoding="utf-8",
        )
        ret = main(["build", str(src), str(out), "--typed"])
        assert ret == 0
        lua = (out / "typed.lua").read_text(encoding="utf-8")
        assert "local x: number" in lua
        assert "local name: string" in lua
        assert "local active: boolean" in lua
        assert "{number}" in lua

    def test_fast_mode_e2e(self, workspace):
        src, out = workspace
        (src / "fast.py").write_text(
            "x = []\nif x:\n    print('truthy')\n",
            encoding="utf-8",
        )
        # With fast mode, no py_bool shim
        ret = main(["build", str(src), str(out), "--fast"])
        assert ret == 0
        lua = (out / "fast.lua").read_text(encoding="utf-8")
        assert "py_bool" not in lua

    def test_multi_file_project(self, workspace):
        src, out = workspace
        (src / "a.py").write_text("x = 1\n", encoding="utf-8")
        (src / "b.py").write_text("y = 2\n", encoding="utf-8")
        (src / "c.py").write_text("z = 3\n", encoding="utf-8")
        ret = main(["build", str(src), str(out)])
        assert ret == 0
        assert (out / "a.lua").exists()
        assert (out / "b.lua").exists()
        assert (out / "c.lua").exists()


# ===========================================================================
# Error handling
# ===========================================================================

class TestErrorHandling:
    def test_unsupported_import_reported(self, workspace):
        src, out = workspace
        (src / "bad.py").write_text("import json\n", encoding="utf-8")
        ret = main(["check", str(src)])
        assert ret == 1

    def test_syntax_error_reported(self, workspace):
        src, out = workspace
        (src / "broken.py").write_text("def (:\n", encoding="utf-8")
        ret = main(["check", str(src)])
        assert ret == 1

    def test_partial_build_continues(self, workspace):
        src, out = workspace
        (src / "good.py").write_text("x = 1\n", encoding="utf-8")
        (src / "bad.py").write_text("import os\n", encoding="utf-8")
        ret = main(["build", str(src), str(out)])
        assert ret == 1  # overall failure
        assert (out / "good.lua").exists()  # good file still built
