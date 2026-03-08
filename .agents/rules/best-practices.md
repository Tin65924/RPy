---
trigger: always_on
---

Building a Python → Luau transpiler efficiently and safely comes down to disciplined engineering. Think of it like building a machine with interchangeable parts rather than one giant script. Each part should do one job clearly and predictably. Here are solid practices to follow.

---

### 1. Design a Clear Compiler Pipeline

Separate the compiler into well-defined stages.

1. **Parsing** – Convert Python source into an Abstract Syntax Tree (AST).
2. **Analysis** – Validate supported syntax and detect unsupported features.
3. **Transformation** – Convert Python AST structures into an internal representation.
4. **Code Generation** – Produce Luau code from that representation.

Pipeline model:

```
Python Source
   ↓
AST Parser
   ↓
Semantic Analyzer
   ↓
Intermediate Representation
   ↓
Luau Generator
```

Each stage should operate independently so changes don’t break the entire system.

---

### 2. Introduce an Intermediate Representation (IR)

Do **not translate Python directly into Luau text**.

Instead, convert Python AST nodes into a neutral structure representing program intent.

Example IR:

```
ForLoop(
  variable="i",
  start=0,
  end=4
)
```

Generated Luau:

```
for i = 0,4 do
```

Benefits:

* easier debugging
* easier optimization
* easier to extend language features later

---

### 3. Never Generate Code With Raw String Concatenation

Avoid fragile patterns like:

```
output += "local " + name
```

Use a structured code generator that tracks formatting.

Example concept:

```
emit("local", name)
emit_newline()
enter_block()
...
exit_block()
```

Benefits:

* consistent indentation
* fewer syntax errors
* cleaner generated code

---

### 4. Whitelist Supported Python Features

Treat the compiler like a **strict translator**, not a full Python interpreter.

Allow only safe constructs such as:

* variables
* arithmetic
* `if` statements
* `for` loops using `range`
* functions
* lists
* simple classes

Explicitly reject features like:

* `eval()`
* `exec()`
* file operations
* networking
* threading

This keeps the transpiler secure and predictable.

---

### 5. Never Execute User Python Code

Only **parse Python code**, never run it.

Safe:

```
ast.parse(source)
```

Unsafe:

```
eval()
exec()
importlib
```

Running arbitrary code would create major security risks.

---

### 6. Implement Clear Compiler Error Messages

Compiler errors should help developers understand what failed.

Bad:

```
KeyError: node.value.id
```

Good:

```
Unsupported feature detected:
List comprehension at line 12
```

Always include:

* error type
* source line number
* explanation of the unsupported feature

---

### 7. Walk the AST Efficiently

Avoid repeated traversals of the syntax tree.

Typical process:

```
tree = ast.parse(source)

analyze(tree)
transform(tree)
generate(tree)
```

Rules:

* parse once
* transform once per stage
* avoid unnecessary recursion

---

### 8. Build a Runtime Helper Library

Some Python behaviors should be implemented as **Luau runtime helpers**.

Example Python:

```
nums.append(5)
```

Generated Luau:

```
py_append(nums,5)
```

Runtime implementation:

```
function py_append(list,value)
    table.insert(list,value)
end
```

Benefits:

* reduces compiler complexity
* simplifies translation logic

---

### 9. Include Runtime Functions Only When Needed

Avoid shipping the entire runtime library with every script.

Example logic:

```
if append_used:
    include_runtime("py_append")
```

Benefits:

* smaller output scripts
* faster runtime execution

---

### 10. Use Modular Transformation Functions

Each Python construct should have its own handler.

Example structure:

```
transform_assign()
transform_for_loop()
transform_function_def()
transform_class_def()
```

Benefits:

* easier debugging
* simpler feature additions
* cleaner code organization

---

### 11. Create a Node Mapping System

Map Python AST nodes to transformation functions.

Example:

```
PYTHON_NODE_MAP = {
    ast.Assign: transform_assign,
    ast.For: transform_for,
    ast.If: transform_if
}
```

Advantages:

* predictable behavior
* easier compiler maintenance

---

### 12. Add Basic Compiler Optimizations

Implement small but useful optimizations.

Example: **constant folding**

Python input:

```
x = 2 + 3
```

Generated Luau:

```
local x = 5
```

Benefits:

* faster runtime execution
* cleaner output code

---

### 13. Use Automated Golden Tests

Maintain input/output test pairs.

Project structure:

```
tests/
   input/
      loop.py
   expected/
      loop.lua
```

Test process:

```
transpile(loop.py)
compare_output(loop.lua)
```

Benefits:

* prevents regressions
* verifies compiler behavior

---

### 14. Keep the Language Subset Small First

Start with a **minimal Python feature set**.

Example initial scope:

* variables
* arithmetic
* `if`
* `for range`
* functions
* lists

Add complex features later:

* classes
* iterators
* decorators
* generators

Compilers grow best **incrementally**.

---

### 15. Document the Supported Python Dialect

Define exactly what your transpiler supports.

Example specification:

```
Supported Python subset:
- functions
- loops
- lists
- simple classes
- arithmetic
```

This prevents confusion for developers using the tool.

Always update the documentation folder and its content, use .txt or any file format that would make a good documentation look goods.

---

### The Core Philosophy

The goal is not to reproduce full Python. The goal is to design a **Python dialect optimized for Roblox scripting**.

The most reliable compilers begin **small, strict, and predictable**, then grow carefully over time.