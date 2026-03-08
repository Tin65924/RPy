# RPy — Developer Setup

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Python | 3.8+ | Compiler runtime |
| Git | any | Version control |
| Roblox Studio | latest | For manual end-to-end testing |
| Rojo | 7.x | Syncs Luau output into Studio |

## 1. Clone the repository

```powershell
git clone <https://github.com/Tin65924/RPy>
cd RPy
```

## 2. Create and activate the virtual environment

```powershell
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```powershell
pip install -r requirements.txt

# Or, install the package in editable mode with dev extras:
pip install -e ".[dev]"
```

## 4. Verify the installation

```powershell
# Run the full test suite
python -m pytest tests/ -v

# Run a quick smoke test
python -c "from transpiler.parser import parse_source; print(parse_source('x = 1'))"

# Check the CLI entry point
python -m cli.main --help
```

## 5. Run the transpiler manually

```powershell
# Transpile a single file
python -m cli.main build examples/hello_world.py output/hello_world.lua

# Validate without writing output
python -m cli.main check examples/hello_world.py

# Watch for changes and recompile
python -m cli.main watch src/ output/ --verbose
```

## 6. Project layout at a glance

```
RPy/
├── transpiler/      # Compiler stages (errors → ast_utils → node_registry → parser → transformer → generator)
├── runtime/         # python_runtime.lua — Luau stdlib shims
├── sdk/             # roblox.py — thin IDE stubs for Roblox APIs
├── cli/             # rpy build / watch / check / init
├── tests/
│   ├── unit/        # Per-AST-node unit tests
│   └── integration/ # Full .py → .lua golden tests
├── examples/        # Sample Python game scripts
└── docs/            # supported_subset.md, semantic_map.md, runtime_api.md
```

## 7. Running a specific test file

```powershell
python -m pytest tests/unit/test_literals.py -v
python -m pytest tests/unit/test_control_flow.py -v -k "test_for_range"
```

## 8. Compiler flags

| Flag | Effect |
|---|---|
| `--typed` | Emit Luau type annotations (`local x: number = 5`) |
| `--fast` | Skip `py_bool()` truthiness shims (Lua semantics, faster) |
| `--no-runtime` | Don't prepend `require(python_runtime)` header |
| `--verbose` | Print each compiled file and timing |

## 9. Coding conventions

- All Python files must be compatible with **Python 3.8+** (no `match` syntax, etc. in the transpiler source itself).
- Each new AST node handler should be registered in `transpiler/node_registry.py`.
- Every new transformation must have a corresponding golden test in `tests/unit/`.
- Runtime helpers in `python_runtime.lua` follow the naming scheme `py_<name>`.
