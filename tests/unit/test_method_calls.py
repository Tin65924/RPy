"""
tests/unit/test_method_calls.py

Unit tests for method call syntax (dot vs colon) heuristic.
"""

from __future__ import annotations
import pytest
from transpiler.parser import parse_source
from transpiler.transformer import transform
from transpiler.generator import generate, CompilerFlags

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

class TestMethodCallSyntax:
    def test_static_library_dot(self):
        # math.abs should use dot
        code = transpile("y = math.abs(-5)")
        # Generator wraps negative numbers in parens: (-5)
        assert "math.abs((-5))" in code

    def test_constructor_dot(self):
        # Instance.new should use dot
        code = transpile('p = Instance.new("Part")')
        assert 'Instance.new("Part")' in code

    def test_vector_constructor_dot(self):
        # Vector3.new should use dot
        code = transpile('v = Vector3.new(1, 2, 3)')
        assert 'Vector3.new(1, 2, 3)' in code

    def test_instance_method_colon(self):
        # part.Destroy should use colon
        code = transpile('part.Destroy()')
        assert 'part:Destroy()' in code

    def test_signal_connect_colon(self):
        # part.Touched.Connect should use colon for Connect
        code = transpile('part.Touched.Connect(lambda: print("hi"))')
        assert 'part.Touched:Connect(' in code

    def test_game_getservice_colon(self):
        # game.GetService should use colon
        code = transpile('plrs = game.GetService("Players")')
        assert 'game:GetService("Players")' in code

    def test_workspace_call_colon(self):
        # workspace.Raycast should use colon
        code = transpile('workspace.Raycast(v1, v2)')
        assert 'workspace:Raycast(v1, v2)' in code

    def test_nested_property_call_colon(self):
        # player.Character.Humanoid.TakeDamage should use colon
        code = transpile('player.Character.Humanoid.TakeDamage(10)')
        assert 'player.Character.Humanoid:TakeDamage(10)' in code

    def test_enum_access_dot(self):
        # Enum.PartType.Block (not a call, but good to check)
        code = transpile('x = Enum.PartType.Block')
        assert 'Enum.PartType.Block' in code

    def test_enum_static_call_dot(self):
        # Enum.GetEnums should use dot
        code = transpile('x = Enum.GetEnums()')
        assert 'Enum.GetEnums()' in code

    def test_variable_assignment_instance_colon(self):
        # Variables assigned from Instance.new should use colon
        code = transpile("""
p = Instance.new("Part")
p.Destroy()
""")
        assert "p:Destroy()" in code

    def test_variable_assignment_getservice_colon(self):
        # Variables assigned from GetService should use colon
        code = transpile("""
plrs = game.GetService("Players")
plrs.GetPlayers()
""")
        assert "plrs:GetPlayers()" in code
