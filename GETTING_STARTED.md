# Getting Started with RPy

RPy is a high-fidelity Python-to-Luau compiler. It allows you to write Roblox game logic using Python's clean syntax and advanced features while targeting Roblox's native Luau engine.

## Installation

```bash
# Clone the repository
git clone https://github.com/YourUsername/RPy.git
cd RPy

# Install in editable mode
pip install -e .
```

## Your First Project

1. **Initialize**: Create a new project structure.
   ```bash
   rpy setup my_roblox_game
   cd my_roblox_game
   ```

2. **Install Dependencies**: Fetch required Luau modules (optional).
   ```bash
   rpy install
   ```
   This synchronizes your `rpy.json` dependencies with Wally.

3. **Write Python**: Open `src/server/main.py` and add some logic:
   ```python
   from roblox import game
   
   print("Hello from RPy!")
   
   def on_player(player):
       print(f"Welcome, {player.Name}!")
   
   game.Players.PlayerAdded.Connect(on_player)
   ```

3. **Build**: Compile your Python code to Luau.
   ```bash
   rpy build src out
   ```
   This generates `out/server/main.server.lua`.

4. **Sync**: Use the live-sync feature to push changes directly to Roblox Studio.
   ```bash
   rpy live src out
   ```

## Advanced Features

### 💎 Typed Emission
Use `--typed` to generate Luau type annotations, enabling Studio's type checker for your compiled code.
```bash
rpy build src out --typed
```

### 🔮 Compile-Time Macros
Execute Python at build-time to generate static Luau performance optimizations using the `@compile_time` decorator.
```bash
rpy build src out --compile-time
```

### 🧠 Semantic Intelligence
RPy understands the entire Roblox API. It will warn you if you access non-existent properties or methods, and even suggests the correct one (e.g., "Did you mean 'Anchored'?" if you typed 'Ancored').

## CLI Reference

- `rpy build <src> <out>`: Transpile files or directories.
- `rpy check <src>`: Validate code without writing output.
- `rpy watch <src> <out>`: Rebuild on every save.
- `rpy live <src> <out>`: Watch and sync to a Roblox Studio session.
- `rpy init [dir]`: Scaffolding a new project.

---

For more details, see the [Reference Documentation](docs/).
