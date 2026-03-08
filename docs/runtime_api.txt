RPy Runtime API Reference
==========================

The RPy runtime library (python_runtime.lua) provides helper functions
that emulate Python semantics in Luau. Only helpers that are actually
used get imported via `require(script.Parent.python_runtime)`.


Core Helpers
------------

py_bool(value) → boolean
    Python truthiness: 0, "", nil, false, empty list/dict → false.
    Everything else → true.

py_range(start, stop, step) → table
    Returns a list of numbers [start, start+step, ...] up to (but not
    including) stop.

py_len(obj) → number
    Returns #obj (table length).

py_str(value) → string
    Converts value to string via tostring().

py_int(value) → number
    Converts value to integer via tonumber() + math.floor().

py_float(value) → number
    Converts value to number via tonumber().

py_contains(container, value) → boolean
    Checks if value is in container (list or dict key).

py_print(...) → nil
    Multi-argument print with space separator.


List Helpers
------------

py_append(list, value) → nil
    Appends value to end of list.

py_pop(list, index?) → any
    Removes and returns item at index (default: last).

py_insert(list, index, value) → nil
    Inserts value at index.

py_remove(list, value) → nil
    Removes first occurrence of value.

py_index_of(list, value) → number
    Returns 0-based index of first occurrence.

py_sort(list) → nil
    Sorts list in place.

py_reverse(list) → nil
    Reverses list in place.

py_extend(list, other) → nil
    Appends all elements of other to list.

py_copy(list) → table
    Returns a shallow copy.

py_count(list, value) → number
    Counts occurrences of value.

py_index(list, i) → any
    Handles negative indexing: list[py_index(list, -1)] → last item.

py_slice(list, start, stop, step) → table
    Returns a sliced copy.


Dict Helpers
------------

py_keys(dict) → table
    Returns list of keys.

py_values(dict) → table
    Returns list of values.

py_items(dict) → table
    Returns list of {key, value} pairs.

py_get(dict, key, default?) → any
    Returns dict[key] or default (nil if omitted).

py_update(dict, other) → nil
    Merges other into dict.

py_setdefault(dict, key, default?) → any
    Returns dict[key], setting it to default if missing.


String Helpers
--------------

py_split(str, sep?) → table
    Splits string by separator (default: whitespace).

py_join(sep, list) → string
    Joins list elements with separator.

py_strip(str) → string
    Removes leading/trailing whitespace.

py_lstrip(str) → string
    Removes leading whitespace.

py_rstrip(str) → string
    Removes trailing whitespace.

py_upper(str) → string
    Returns uppercase version.

py_lower(str) → string
    Returns lowercase version.

py_replace(str, old, new) → string
    Replaces all occurrences of old with new.

py_find(str, sub) → number
    Returns 0-based index of substring, or -1.

py_startswith(str, prefix) → boolean
    Tests if string starts with prefix.

py_endswith(str, suffix) → boolean
    Tests if string ends with suffix.


Utility Helpers
---------------

py_sorted(list) → table
    Returns a new sorted list (does not modify original).

py_enumerate(list, start?) → table
    Returns list of {index, value} pairs (start defaults to 0).

py_zip(a, b, ...) → table
    Returns list of tuples from parallel iterables.

py_reversed(list) → table
    Returns a new reversed list.

py_format(value, spec) → string
    Formats value according to Python-style format spec.
    e.g. py_format(3.14159, ".2f") → "3.14"
