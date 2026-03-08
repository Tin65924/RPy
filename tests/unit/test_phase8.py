"""
tests/unit/test_phase8.py

Unit tests for Phase 8 — Roblox SDK stubs.
Tests cover: SDK imports, stub completeness, transpiler passthrough behavior.
"""

from __future__ import annotations

import pytest

from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags
from transpiler.errors import UnsupportedFeatureError


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


def get_sdk_names(src: str) -> set:
    tree = parse_source(src.strip())
    result = transform(tree)
    return result.import_info.sdk_names


# ===========================================================================
# SDK import passthrough
# ===========================================================================

class TestSDKPassthrough:
    def test_instance_import(self):
        code = transpile("from roblox import Instance")
        assert "require" not in code
        assert "Instance" not in code  # no Luau assignment needed

    def test_vector3_import(self):
        code = transpile("from roblox import Vector3\npos = Vector3.new(1, 2, 3)")
        assert "require" not in code
        assert "Vector3.new(1, 2, 3)" in code

    def test_multiple_imports(self):
        code = transpile("from roblox import Instance, Vector3, CFrame")
        assert "require" not in code

    def test_sdk_names_recorded(self):
        names = get_sdk_names("from roblox import Instance, Vector3, game")
        assert "Instance" in names
        assert "Vector3" in names
        assert "game" in names

    def test_game_service(self):
        code = transpile("""\
from roblox import game
players = game.GetService("Players")
""")
        assert 'game.GetService("Players")' in code or "game:GetService" in code

    def test_workspace_access(self):
        code = transpile("""\
from roblox import workspace
parts = workspace.GetChildren()
""")
        assert "workspace" in code

    def test_color3_constructor(self):
        code = transpile("""\
from roblox import Color3
red = Color3.fromRGB(255, 0, 0)
""")
        assert "Color3.fromRGB(255, 0, 0)" in code

    def test_udim2_constructor(self):
        code = transpile("""\
from roblox import UDim2
size = UDim2.fromScale(0.5, 0.5)
""")
        assert "UDim2.fromScale(0.5, 0.5)" in code

    def test_enum_access(self):
        code = transpile("""\
from roblox import Enum
style = Enum.EasingStyle.Quad
""")
        assert "Enum.EasingStyle.Quad" in code

    def test_tween_info(self):
        code = transpile("""\
from roblox import TweenInfo
info = TweenInfo.new(1)
""")
        assert "TweenInfo.new(1)" in code


# ===========================================================================
# SDK + code interaction
# ===========================================================================

class TestSDKWithCode:
    def test_sdk_with_function(self):
        code = transpile("""\
from roblox import Instance
def create_part():
    part = Instance.new("Part")
    part.Size = Vector3.new(4, 1, 2)
    return part
""")
        assert "Instance.new" in code
        assert "part.Size" in code
        assert "function create_part()" in code

    def test_sdk_with_loop(self):
        code = transpile("""\
from roblox import workspace
for i in range(10):
    part = Instance.new("Part")
""")
        assert "for i = 0, 9 do" in code

    def test_sdk_with_class(self):
        code = transpile("""\
from roblox import Instance
class GameManager:
    def __init__(self):
        self.score = 0
    def add_score(self, points):
        self.score += points
""")
        assert "function GameManager.new()" in code
        assert "function GameManager:add_score(points)" in code


# ===========================================================================
# Stdlib imports still rejected
# ===========================================================================

class TestStdlibRejection:
    def test_stdlib_import_rejected(self):
        with pytest.raises(UnsupportedFeatureError):
            transpile("import os")

    def test_stdlib_from_rejected(self):
        with pytest.raises(UnsupportedFeatureError):
            transpile("from json import dumps")

    def test_relative_import_works(self):
        code = transpile("from . import utils")
        assert "require" in code


# ===========================================================================
# SDK stub completeness (verify the module is importable)
# ===========================================================================

class TestSDKStubCompleteness:
    """Verify the SDK stubs module structure is correct."""

    def test_roblox_module_importable(self):
        import sdk.roblox as roblox
        assert hasattr(roblox, "Instance")
        assert hasattr(roblox, "Vector3")
        assert hasattr(roblox, "CFrame")
        assert hasattr(roblox, "Color3")
        assert hasattr(roblox, "UDim2")
        assert hasattr(roblox, "game")
        assert hasattr(roblox, "workspace")

    def test_services_exist(self):
        import sdk.roblox as roblox
        assert hasattr(roblox, "Players")
        assert hasattr(roblox, "RunService")
        assert hasattr(roblox, "TweenService")
        assert hasattr(roblox, "DataStoreService")
        assert hasattr(roblox, "ReplicatedStorage")
        assert hasattr(roblox, "ServerStorage")

    def test_data_types_exist(self):
        import sdk.roblox as roblox
        assert hasattr(roblox, "Vector2")
        assert hasattr(roblox, "Vector3")
        assert hasattr(roblox, "CFrame")
        assert hasattr(roblox, "Color3")
        assert hasattr(roblox, "BrickColor")
        assert hasattr(roblox, "UDim")
        assert hasattr(roblox, "UDim2")
        assert hasattr(roblox, "TweenInfo")
        assert hasattr(roblox, "Ray")
        assert hasattr(roblox, "Region3")

    def test_global_functions_exist(self):
        import sdk.roblox as roblox
        assert hasattr(roblox, "wait")
        assert hasattr(roblox, "typeof")
        assert hasattr(roblox, "tick")
        assert hasattr(roblox, "pcall")

    def test_enum_exists(self):
        import sdk.roblox as roblox
        assert hasattr(roblox, "Enum")

    def test_task_library(self):
        import sdk.roblox as roblox
        assert hasattr(roblox, "task")

    def test_all_exports(self):
        import sdk.roblox as roblox
        assert len(roblox.__all__) > 40  # We have 74 exports
