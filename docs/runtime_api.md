# RPy Runtime API Reference

The **RPy runtime library** (`python_runtime.lua`) provides helper functions that emulate **Python semantics in Luau**.

Only helpers that are actually required by the transpiled code are imported:

```lua
local py = require(script.Parent.python_runtime)
```

The runtime exposes a set of `py_*` helper functions used to replicate Python behavior.

---

# Core Helpers

### `py_bool(value) → boolean`

Implements **Python truthiness rules**.

Returns `false` for:

* `0`
* `""`
* `nil`
* `false`
* empty lists `{}`

Returns `true` for everything else.

---

### `py_range(start, stop, step) → table`

Returns a numeric sequence similar to Python's `range()`.

Example:

```python
range(0, 5, 1)
```

Produces:

```lua
{0, 1, 2, 3, 4}
```

The `stop` value is **exclusive**.

---

### `py_len(obj) → number`

Returns the length of a table.

```lua
py_len(obj) -- equivalent to #obj
```

---

### `py_str(value) → string`

Converts a value to a string.

```lua
py_str(value) -- internally uses tostring()
```

---

### `py_int(value) → number`

Converts a value to an integer.

```lua
math.floor(tonumber(value))
```

---

### `py_float(value) → number`

Converts a value to a number.

```lua
tonumber(value)
```

---

### `py_contains(container, value) → boolean`

Checks if a value exists in a container.

Supported containers:

* lists
* dictionary keys

Equivalent to Python's:

```python
value in container
```

---

### `py_print(...) → nil`

Python-style multi-argument printing.

Arguments are joined with spaces.

Example:

```python
print("hello", 5)
```

Produces:

```
hello 5
```

---

# List Helpers

### `py_append(list, value)`

Appends a value to the end of a list.

```python
list.append(value)
```

---

### `py_pop(list, index?) → any`

Removes and returns an element.

* Default: last element

Example:

```python
list.pop()
list.pop(2)
```

---

### `py_insert(list, index, value)`

Inserts a value at a given index.

---

### `py_remove(list, value)`

Removes the **first occurrence** of a value.

---

### `py_index_of(list, value) → number`

Returns the **0-based index** of the first occurrence.

---

### `py_sort(list)`

Sorts the list **in place**.

---

### `py_reverse(list)`

Reverses the list **in place**.

---

### `py_extend(list, other)`

Appends all elements from `other`.

Equivalent to:

```python
list.extend(other)
```

---

### `py_copy(list) → table`

Returns a **shallow copy** of the list.

---

### `py_count(list, value) → number`

Counts occurrences of a value.

---

### `py_index(list, i) → any`

Handles **negative indexing**.

Example:

```python
list[-1]
```

Equivalent Luau usage:

```lua
list[py_index(list, -1)]
```

---

### `py_slice(list, start, stop, step) → table`

Returns a **sliced copy** of a list.

Example:

```python
list[1:5:2]
```

---

# Dictionary Helpers

### `py_keys(dict) → table`

Returns a list of dictionary keys.

Equivalent to:

```python
dict.keys()
```

---

### `py_values(dict) → table`

Returns a list of dictionary values.

Equivalent to:

```python
dict.values()
```

---

### `py_items(dict) → table`

Returns `{key, value}` pairs.

Equivalent to:

```python
dict.items()
```

---

### `py_get(dict, key, default?) → any`

Returns a value or a default.

Example:

```python
dict.get("a", 0)
```

---

### `py_update(dict, other)`

Merges `other` into `dict`.

Equivalent to:

```python
dict.update(other)
```

---

### `py_setdefault(dict, key, default?) → any`

Returns the value for a key.

If the key does not exist, it is inserted with `default`.

Equivalent to:

```python
dict.setdefault(key, default)
```

---

# String Helpers

### `py_split(str, sep?) → table`

Splits a string into a list.

Default separator: **whitespace**

Example:

```python
"hello world".split()
```

---

### `py_join(sep, list) → string`

Joins list elements using a separator.

Example:

```python
",".join(list)
```

---

### `py_strip(str) → string`

Removes leading and trailing whitespace.

---

### `py_lstrip(str) → string`

Removes leading whitespace.

---

### `py_rstrip(str) → string`

Removes trailing whitespace.

---

### `py_upper(str) → string`

Returns an uppercase version.

---

### `py_lower(str) → string`

Returns a lowercase version.

---

### `py_replace(str, old, new) → string`

Replaces all occurrences of a substring.

---

### `py_find(str, sub) → number`

Returns the **0-based index** of a substring.

Returns `-1` if not found.

---

### `py_startswith(str, prefix) → boolean`

Checks if the string begins with `prefix`.

---

### `py_endswith(str, suffix) → boolean`

Checks if the string ends with `suffix`.

---

# Utility Helpers

### `py_sorted(list) → table`

Returns a **new sorted list**.

Does **not modify the original list**.

Equivalent to:

```python
sorted(list)
```

---

### `py_enumerate(list, start?) → table`

Returns `{index, value}` pairs.

Default start index: `0`.

Example:

```python
enumerate(list)
```

---

### `py_zip(a, b, ...) → table`

Combines multiple iterables into tuples.

Example:

```python
zip(a, b)
```

Produces:

```lua
{
    {a1, b1},
    {a2, b2},
}
```

---

### `py_reversed(list) → table`

Returns a **new reversed list**.

Equivalent to:

```python
reversed(list)
```

---

### `py_format(value, spec) → string`

Formats values using Python-style format specifiers.

Example:

```lua
py_format(3.14159, ".2f")
```

Result:

```
"3.14"
```