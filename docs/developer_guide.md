# RPy Developer Guide

Welcome to the RPy transpiler! RPy allows you to write idiomatic Python code and compile it directly into highly optimized Roblox Luau. 

This guide covers the essential features, APIs, configuration, and workflows to get the most out of the RPy ecosystem.

---

## 🚀 Key Features

### 1. Zero-Cost Roblox Integration
RPy natively understands the Roblox SDK. When you write standard Python syntax, it maps directly to Luau operations without wrapping objects in slow emulation layers.
*   `math.floor(x)` compiles purely to `math.floor(x)`
*   `task.wait(1)` compiles purely to `task.wait(1)`
*   `string.upper(s)` compiles purely to `string.upper(s)`

### 2. State-Preserving Hot Reload
RPy features a real-time development server (`rpy live`) that instantly syncs Python script changes to a running Roblox Studio Play Solo session.
*   **Persistent State:** Use the `persistent` annotation or function to save data across reloads.
    ```python
    score: persistent = 0  # Will not reset to 0 when this file is hot-reloaded!
    ```

### 3. Engine-Level Optimizations
RPy acts as an advanced optimizing compiler, performing:
*   **Constant Folding & DCE:** Evaluates static arithmetic (e.g., `2 + 3` -> `5`) and removes dead code paths entirely.
*   **Scalar Replacement (SRA) & Escape Analysis:** If you initialize a temporary dictionary (`p = {"x": 1, "y": 2}`) that never leaves the function, RPy unpacks it into lightweight scalar registers (`local p_x = 1; local p_y = 2`), saving memory allocation.
*   **Parallel Compilation:** Compiles massive project dependency trees dynamically across all your CPU cores.

---

## 🛠️ CLI Workflow & Usage

RPy provides a robust command-line interface (CLI) to orchestrate your workflow.

### 1. Initialize a Project
Create the fundamental `src/`, `out/`, and `rpy.json` structure:
```bash
rpy setup path/to/project
```

### 2. Transpile Once (Build)
Compile all files safely across a CPU threadpool:
```bash
rpy build src/ out/ --workers 4
```
**Options:**
*   `--typed`: Emit native Luau type annotations (from Python type hints).
*   `--fast`: Skip truthiness shims for aggressive performance.

### 3. Live Sync (Hot Reload)
Start the local Dev Server to continuously push changes into Roblox Studio:
```bash
rpy live src/ out/
```

### 4. Install Packages
Download modular Luau packages natively via Wally:
```bash
rpy install .
```

---

## ⚙️ Configuration (`rpy.json`)
The `rpy.json` file sits at your project root and configures compiler behaviors.

```json
{
  "version": "2.0",
  "src": "src",
  "out": "out",
  "flags": {
    "typed": true,
    "fast": false,
    "no_runtime": false
  },
  "folders": {
    "workspace": "src/workspace",
    "server": "src/server",
    "client": "src/client",
    "shared": "src/shared"
  }
}
```

---

## 📜 Writing Scripts (Usage Examples)

### Basic Server Script
Files placed in `src/server/` compile to `Script` objects in `ServerScriptService`.

```python
# src/server/init.server.py
from roblox import game

players = game.GetService("Players")

def on_player_added(player):
    print(f"[{player.UserId}] Joined the game: {player.Name}")

players.PlayerAdded.connect(on_player_added)
```

### Shared Utility Module
Files placed in `src/shared/` compile to `ModuleScript` objects in `ReplicatedStorage`.

```python
# src/shared/math_utils.py
import math

def get_distance(p1, p2):
    return (p1 - p2).Magnitude
```

### Client UI Logic
Files placed in `src/client/` compile to `LocalScript` objects in `StarterPlayerScripts`.

```python
# src/client/ui.client.py
from roblox import game
from shared.math_utils import get_distance

local_player = game.GetService("Players").LocalPlayer
print(f"Client initializing for {local_player.Name}")
```

---

## 🛑 What NOT to do (Language Boundaries)

RPy transpiles to Luau, therefore some dynamic Python features are unsupported due to the target environment's strict structural constraints:

1. **No `eval()` or `exec()`**: RPy is statically analyzed and compiled ahead-of-time.
2. **No dynamic classes with runtime meta-mutations (`type()`)**. Use standard static class declarations.
3. **No file reading operations (`open()`) at runtime**: Roblox runs in a sandboxed, networked environment.

RPy is designed to feel like Python while performing flawlessly as Luau. Keep your logic structural, explicitly typed, and deterministic!
