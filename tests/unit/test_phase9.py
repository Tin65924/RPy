"""
tests/unit/test_phase9.py

Unit tests for Phase 9 — CLI Tools.
Tests cover: build, check, init commands and argument parsing.
"""

from __future__ import annotations

import os
import sys
import json
import pytest
from pathlib import Path

from cli.main import main, build_parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temp project with a source file."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text('x = 42\nprint(x)\n', encoding="utf-8")
    return tmp_path


@pytest.fixture
def tmp_roblox_project(tmp_path):
    """Create a temp project with a Roblox SDK script."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "game.py").write_text(
        'from roblox import workspace\n'
        'def setup():\n'
        '    part = workspace.GetChildren()\n'
        '    return part\n',
        encoding="utf-8",
    )
    return tmp_path


# ===========================================================================
# Parser
# ===========================================================================

class TestParser:
    def test_build_parser(self):
        parser = build_parser()
        args = parser.parse_args(["build", "src", "out"])
        assert args.command == "build"
        assert args.src == "src"
        assert args.out == "out"

    def test_build_flags(self):
        parser = build_parser()
        args = parser.parse_args(["build", "src", "out", "--typed", "--fast", "--no-runtime"])
        assert args.typed is True
        assert args.fast is True
        assert args.no_runtime is True

    def test_check_parser(self):
        parser = build_parser()
        args = parser.parse_args(["check", "src"])
        assert args.command == "check"

    def test_init_parser(self):
        parser = build_parser()
        args = parser.parse_args(["init", "myproject"])
        assert args.command == "init"
        assert args.dir == "myproject"

    def test_watch_parser(self):
        parser = build_parser()
        args = parser.parse_args(["watch", "src", "out", "--interval", "2.0"])
        assert args.command == "watch"
        assert args.interval == 2.0

    def test_version(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0


# ===========================================================================
# Build command
# ===========================================================================

class TestBuild:
    def test_build_single_file(self, tmp_project):
        out = tmp_project / "out"
        ret = main(["build", str(tmp_project / "src" / "hello.py"),
                     str(out / "hello.lua")])
        assert ret == 0
        assert (out / "hello.lua").exists()
        content = (out / "hello.lua").read_text(encoding="utf-8")
        assert "local x = 42" in content

    def test_build_directory(self, tmp_project):
        out = tmp_project / "out"
        ret = main(["build", str(tmp_project / "src"), str(out)])
        assert ret == 0
        assert (out / "hello.lua").exists()

    def test_build_typed(self, tmp_project):
        out = tmp_project / "out"
        ret = main(["build", str(tmp_project / "src" / "hello.py"),
                     str(out / "hello.lua"), "--typed"])
        assert ret == 0
        content = (out / "hello.lua").read_text(encoding="utf-8")
        assert "number" in content  # x = 42 should get `: number`

    def test_build_fast(self, tmp_project):
        out = tmp_project / "out"
        ret = main(["build", str(tmp_project / "src" / "hello.py"),
                     str(out / "hello.lua"), "--fast"])
        assert ret == 0

    def test_build_nonexistent_src(self, tmp_project):
        ret = main(["build", str(tmp_project / "nope.py"),
                     str(tmp_project / "out.lua")])
        assert ret == 1

    def test_build_no_py_files(self, tmp_project):
        empty = tmp_project / "empty"
        empty.mkdir()
        ret = main(["build", str(empty), str(tmp_project / "out")])
        assert ret == 1

    def test_build_sdk_passthrough(self, tmp_roblox_project):
        out = tmp_roblox_project / "out"
        ret = main(["build",
                     str(tmp_roblox_project / "src" / "game.py"),
                     str(out / "game.lua")])
        assert ret == 0
        content = (out / "game.lua").read_text(encoding="utf-8")
        assert "workspace" in content
        assert "require" not in content or "python_runtime" in content


# ===========================================================================
# Check command
# ===========================================================================

class TestCheck:
    def test_check_valid(self, tmp_project):
        ret = main(["check", str(tmp_project / "src" / "hello.py"), "--verbose"])
        assert ret == 0

    def test_check_directory(self, tmp_project):
        ret = main(["check", str(tmp_project / "src")])
        assert ret == 0

    def test_check_invalid_file(self, tmp_project):
        bad = tmp_project / "bad.py"
        bad.write_text("import os\n", encoding="utf-8")
        ret = main(["check", str(bad)])
        assert ret == 1

    def test_check_nonexistent(self, tmp_project):
        ret = main(["check", str(tmp_project / "nope.py")])
        assert ret == 1


# ===========================================================================
# Init command
# ===========================================================================

class TestInit:
    def test_init_creates_structure(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        ret = main(["init", str(project)])
        assert ret == 0
        assert (project / "src").is_dir()
        assert (project / "out").is_dir()
        assert (project / "rpy.json").exists()
        assert (project / "src" / "main.py").exists()

    def test_init_config_contents(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        main(["init", str(project)])
        config = json.loads((project / "rpy.json").read_text(encoding="utf-8"))
        assert config["version"] == "1.0"
        assert config["src"] == "src"
        assert config["out"] == "out"

    def test_init_example_script(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        main(["init", str(project)])
        content = (project / "src" / "main.py").read_text(encoding="utf-8")
        assert "Instance" in content
        assert "workspace" in content

    def test_init_idempotent(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        main(["init", str(project)])
        # Running again shouldn't overwrite
        ret = main(["init", str(project)])
        assert ret == 0


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_no_command(self, capsys):
        ret = main([])
        assert ret == 0  # prints help
        captured = capsys.readouterr()
        assert "rpy" in captured.out

    def test_build_with_error_in_file(self, tmp_path):
        """A file with unsupported syntax should report error but not crash."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("import json\n", encoding="utf-8")
        (src / "good.py").write_text("x = 1\n", encoding="utf-8")
        out = tmp_path / "out"
        ret = main(["build", str(src), str(out)])
        assert ret == 1  # partial failure
        assert (out / "good.lua").exists()  # good file still built
