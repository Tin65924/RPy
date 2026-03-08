# RPy Supported Python Subset (v0.1)

This document defines the **subset of Python syntax supported by the RPy transpiler** and how those constructs map to **Luau**.

Only features listed here are guaranteed to compile. Unsupported features will raise `UnsupportedFeatureError`.

---

# Supported Constructs

## Variables & Literals

Supported literal types:

* `int`
* `float`
* `str`
* `bool`
* `None`

### Syntax Mapping

| Python        | Luau                              |
| ------------- | --------------------------------- |
| `x = 5`       | `local x = 5`                     |
| `x = 10`      | `x = 10`                          |
| `x += 1`      | `x = x + 1`                       |
| `a, b = expr` | `local a, b = table.unpack(expr)` |
| `del x`       | `x = nil`                         |

Supported augmented assignments:

```
+=  -=  *=  /=  //=  %=  **=
```

---

# Arithmetic & Logic

### Operators

| Python            | Luau              |
| ----------------- | ----------------- |
| `+ - * / // % **` | `+ - * / // % ^`  |
| `== != < > <= >=` | `== ~= < > <= >=` |
| `and or not`      | `and or not`      |

---

### Identity

| Python   | Luau |
| -------- | ---- |
| `is`     | `==` |
| `is not` | `~=` |

---

### Membership

| Python               | Luau                            |
| -------------------- | ------------------------------- |
| `x in container`     | `py_contains(container, x)`     |
| `x not in container` | `not py_contains(container, x)` |

---

### Ternary Expressions

Python:

```python
x if cond else y
```

Luau equivalent:

```lua
(cond and x or y)
```

---

# Control Flow

## Conditional Statements

| Python           | Luau               |
| ---------------- | ------------------ |
| `if cond:`       | `if cond then`     |
| `elif cond:`     | `elseif cond then` |
| `else:`          | `else`             |
| *(end of block)* | `end`              |

---

## Loops

### Range Loops

| Python                    | Luau                         |
| ------------------------- | ---------------------------- |
| `for i in range(n)`       | `for i = 0, n-1 do`          |
| `for i in range(a, b)`    | `for i = a, b-1 do`          |
| `for i in range(a, b, s)` | `for i = a, b-step, step do` |

---

### Iterable Loops

| Python              | Luau                              |
| ------------------- | --------------------------------- |
| `for x in iterable` | `for _, x in ipairs(iterable) do` |

---

### Other Flow Control

| Python       | Luau                    |
| ------------ | ----------------------- |
| `while cond` | `while cond do ... end` |
| `break`      | `break`                 |
| `continue`   | `continue`              |
| `pass`       | `-- pass`               |

---

# Functions

Supported features:

* Positional arguments
* Varargs (`*args`)
* Return values
* Lambda expressions

---

### Syntax Mapping

| Python            | Luau                       |
| ----------------- | -------------------------- |
| `def foo(a, b):`  | `local function foo(a, b)` |
| `def foo(*args):` | `local function foo(...)`  |
| `return value`    | `return value`             |

---

### Lambda

Python:

```python
lambda x: x + 1
```

Luau:

```lua
(function(x) return (x + 1) end)
```

---

# Classes

RPy supports **Python-style classes compiled to Luau metatables**.

---

## Basic Class

Python:

```python
class Foo:
```

Luau:

```lua
local Foo = {}
Foo.__index = Foo
```

---

## Inheritance

Only **single inheritance** is supported.

Python:

```python
class Foo(Base):
```

Luau:

```lua
local Foo = setmetatable({}, {__index = Base})
Foo.__index = Foo
```

---

## Constructor

Python:

```python
def __init__(self, ...):
```

Luau:

```lua
function Foo.new(...)
```

---

## Methods

Python:

```python
def method(self, ...):
```

Luau:

```lua
function Foo:method(...)
```

---

## Class Attributes

Python:

```python
class Foo:
    value = 5
```

Luau:

```lua
Foo.value = 5
```

---

# Data Structures

| Python    | Luau      |
| --------- | --------- |
| `[1,2,3]` | `{1,2,3}` |
| `{"a":1}` | `{a = 1}` |
| `(1,2)`   | `{1,2}`   |

---

### Indexing

Python uses **0-based indexing**, while Luau uses **1-based indexing**.

| Python     | Luau           |
| ---------- | -------------- |
| `items[0]` | `items[1]`     |
| `items[i]` | `items[i + 1]` |

---

### Negative Indexing

Python:

```python
items[-1]
```

Luau:

```lua
py_index(items, -1)
```

---

### Slicing

| Python       | Luau                    |
| ------------ | ----------------------- |
| `items[1:3]` | `py_slice(items, 1, 3)` |

---

# Comprehensions

### List Comprehension

Python:

```python
[expr for x in iterable]
```

Compiled to:

* an **IIFE**
* `table.insert()` calls

---

### Filtered List Comprehension

Python:

```python
[expr for x in iterable if cond]
```

Compiled to:

* loop
* conditional guard
* insertion

---

### Dictionary Comprehension

Python:

```python
{k: v for k, v in iterable}
```

Compiled to:

* loop
* key assignment

---

# Exception Handling

### Try / Except / Finally

Python:

```python
try:
    risky()
except E:
    handle()
finally:
    cleanup()
```

Luau:

```lua
local ok, err = pcall(function()
    risky()
end)

if not ok then
    handle(err)
end

cleanup()
```

---

### Raising Exceptions

| Python                   | Luau           |
| ------------------------ | -------------- |
| `raise Exception("msg")` | `error("msg")` |
| `raise`                  | `error(_err)`  |

---

# Strings

### f-Strings

Python:

```python
f"hello {name}"
```

Luau:

```lua
("hello " .. py_str(name))
```

---

### Format Specifiers

Python:

```python
f"{x:.2f}"
```

Luau:

```lua
py_format(x, ".2f")
```

---

# Imports

| Python                 | Luau                            |
| ---------------------- | ------------------------------- |
| `from roblox import X` | removed (X assumed global)      |
| `from . import module` | `require(script.Parent.module)` |
| `import anything_else` | `UnsupportedFeatureError`       |

---

# With Statement

Python:

```python
with expr as x:
    use(x)
```

Luau:

```lua
do
    local x = expr
    use(x)
end
```

---

# Unsupported Constructs

The following features are **recognized but not implemented** and will raise `UnsupportedFeatureError`.

* `match / case`
* Multiple inheritance
* Decorators (`@decorator`)
* `async / await`
* `global` / `nonlocal`
* `eval()` / `exec()`
* Standard library imports (`os`, `json`, etc.)
* Generators (`yield`)
* Walrus operator (`:=`)

---

# Compiler Flags

| Flag           | Description                                          |
| -------------- | ---------------------------------------------------- |
| `--typed`      | Emit Luau type annotations (`local x: number = 5`)   |
| `--fast`       | Skip `py_bool()` truthiness shim (use Lua semantics) |
| `--no-runtime` | Do not prepend runtime `require()` header            |
| `--verbose`    | Print detailed build output                          |