# RPy Semantic Map — Python → Luau

This document defines how **Python constructs are translated into Luau** in the RPy transpiler.

Each section maps Python syntax to its **equivalent Luau representation**.

---

# Literals

| Python      | Luau        |
| ----------- | ----------- |
| `42`        | `42`        |
| `3.14`      | `3.14`      |
| `"hello"`   | `"hello"`   |
| `True`      | `true`      |
| `False`     | `false`     |
| `None`      | `nil`       |
| `[1, 2, 3]` | `{1, 2, 3}` |
| `{"a": 1}`  | `{a = 1}`   |
| `(1, 2)`    | `{1, 2}`    |
| `[]`        | `{}`        |
| `{}`        | `{}`        |

Notes:

* Python **tuples are represented as tables**.
* Python **lists map directly to Luau arrays**.

---

# Operators

| Python      | Luau                                |
| ----------- | ----------------------------------- |
| `+`         | `+`                                 |
| `-`         | `-`                                 |
| `*`         | `*`                                 |
| `/`         | `/`                                 |
| `//`        | `//`                                |
| `%`         | `%`                                 |
| `**`        | `^`                                 |
| `==`        | `==`                                |
| `!=`        | `~=`                                |
| `< > <= >=` | `< > <= >=`                         |
| `and`       | `and`                               |
| `or`        | `or`                                |
| `not`       | `not`                               |
| `is`        | `==`                                |
| `is not`    | `~=`                                |
| `in`        | `py_contains(container, value)`     |
| `not in`    | `not py_contains(container, value)` |

---

# Variables

| Python        | Luau                               |
| ------------- | ---------------------------------- |
| `x = 5`       | `local x = 5` *(first assignment)* |
| `x = 10`      | `x = 10` *(reassignment)*          |
| `x += 1`      | `x = x + 1`                        |
| `del x`       | `x = nil`                          |
| `a, b = expr` | `local a, b = table.unpack(expr)`  |

---

# Control Flow

### Conditional Statements

| Python        | Luau               |
| ------------- | ------------------ |
| `if cond:`    | `if cond then`     |
| `elif cond:`  | `elseif cond then` |
| `else:`       | `else`             |
| *(block end)* | `end`              |

---

### Loops

| Python                     | Luau                                   |
| -------------------------- | -------------------------------------- |
| `for i in range(n):`       | `for i = 0, n-1 do ... end`            |
| `for i in range(a, b):`    | `for i = a, b-1 do ... end`            |
| `for i in range(a, b, s):` | `for i = a, b-s, s do ... end`         |
| `for x in items:`          | `for _, x in ipairs(items) do ... end` |

---

### Other Control

| Python        | Luau                    |
| ------------- | ----------------------- |
| `while cond:` | `while cond do ... end` |
| `break`       | `break`                 |
| `continue`    | `continue`              |
| `pass`        | `-- pass`               |

---

# Functions

| Python            | Luau                             |
| ----------------- | -------------------------------- |
| `def foo(a, b):`  | `local function foo(a, b)`       |
| `def foo(*args):` | `local function foo(...)`        |
| `return val`      | `return val`                     |
| `lambda x: x + 1` | `(function(x) return x + 1 end)` |

---

# Classes

### Basic Class

```python
class Foo:
```

```lua
local Foo = {}
Foo.__index = Foo
```

---

### Inheritance

```python
class Foo(Base):
```

```lua
local Foo = setmetatable({}, {__index = Base})
Foo.__index = Foo
```

---

### Constructor

```python
def __init__(self, x):
    self.x = x
```

```lua
function Foo.new(x)
    local self = setmetatable({}, Foo)
    self.x = x
    return self
end
```

---

### Methods

```python
def method(self, arg):
```

```lua
function Foo:method(arg)
```

---

### Instantiation

```python
obj = Foo(x)
```

```lua
local obj = Foo.new(x)
```

---

# Indexing

| Python       | Luau                           |
| ------------ | ------------------------------ |
| `items[0]`   | `items[1]`                     |
| `items[3]`   | `items[4]`                     |
| `items[i]`   | `items[i + 1]`                 |
| `items[-1]`  | `py_index(items, -1)`          |
| `items[1:3]` | `py_slice(items, 1, 3)`        |
| `items[::2]` | `py_slice(items, nil, nil, 2)` |

Note:

* Python uses **0-based indexing**.
* Luau uses **1-based indexing**, so offsets are applied.

---

# Exceptions

### Try / Except

```python
try:
    risky()
except E as e:
    handle(e)
finally:
    cleanup()
```

```lua
local _ok, _err = pcall(function()
    risky()
end)

if not _ok then
    local e = _err
    handle(e)
end

cleanup()
```

---

### Raising Errors

| Python             | Luau           |
| ------------------ | -------------- |
| `raise Err("msg")` | `error("msg")` |
| `raise`            | `error(_err)`  |

---

# Strings

| Python         | Luau                        |
| -------------- | --------------------------- |
| `f"hi {name}"` | `"hi " .. py_str(name)`     |
| `f"{x:.2f}"`   | `"" .. py_format(x, ".2f")` |

---

# Imports

| Python                 | Luau                                     |
| ---------------------- | ---------------------------------------- |
| `from roblox import X` | *(removed — `X` is global)*              |
| `from . import mod`    | `local mod = require(script.Parent.mod)` |
| `import json`          | ❌ Unsupported                            |

---

# Builtins

| Python             | Luau              |
| ------------------ | ----------------- |
| `print(x)`         | `print(x)`        |
| `len(x)`           | `py_len(x)`       |
| `str(x)`           | `py_str(x)`       |
| `int(x)`           | `py_int(x)`       |
| `float(x)`         | `py_float(x)`     |
| `abs(x)`           | `math.abs(x)`     |
| `type(x)`          | `typeof(x)`       |
| `isinstance(x, T)` | `typeof(x) == T`  |
| `sorted(x)`        | `py_sorted(x)`    |
| `reversed(x)`      | `py_reversed(x)`  |
| `enumerate(x)`     | `py_enumerate(x)` |
| `zip(a, b)`        | `py_zip(a, b)`    |

---

# With Statement

Python's `with` statement is translated to a simple scoped block.

```python
with expr as x:
    use(x)
```

```lua
do
    local x = expr
    use(x)
end
```