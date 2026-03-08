--[[
  python_runtime.lua — RPy Runtime v1
  Luau helper functions that emulate Python builtins and semantics.

  This file is require()-d at the top of every RPy-generated script
  (unless --no-runtime is passed). Each helper is exposed as a field on
  the returned module table.

  Naming convention: py_<name> mirrors the Python function it emulates.

  Runtime v1 — minimal builtins needed for Phase 4 (Minimal Transpiler):
    py_bool    : Python truthiness rules (0, "", {}, nil, false → false)
    py_range   : numeric iterator compatible with ipairs / numeric for
    py_len     : len() — works on tables and strings
    py_str     : str() → tostring()
    py_int     : int() → math.floor(tonumber())
    py_float   : float() → tonumber()
    py_contains: x in collection — linear search for lists
--]]

local M = {}

-- ---------------------------------------------------------------------------
-- py_bool — Python truthiness semantics
--
-- Python falsy values: None/nil, False/false, 0, 0.0, "", [], {}
-- Lua falsy values:    nil, false
-- CRITICAL difference: Lua treats 0 and "" as TRUTHY. This shim fixes that.
-- ---------------------------------------------------------------------------
function M.py_bool(value)
    if value == nil then return false end
    if value == false then return false end
    if value == 0 then return false end
    if value == 0.0 then return false end
    if value == "" then return false end
    if type(value) == "table" and next(value) == nil then return false end
    return true
end

-- ---------------------------------------------------------------------------
-- py_range — Python range() as a Luau iterator value
--
-- Usage in generated code (after transformer detects range()):
--   The generator emits a numeric `for` directly — py_range is provided
--   as a fallback for cases where range() appears in non-for contexts.
--
-- Returns a table with __index so ipairs() works on it.
-- ---------------------------------------------------------------------------
function M.py_range(a, b, c)
    -- range(stop)         → [0, stop)
    -- range(start, stop)  → [start, stop)
    -- range(start, stop, step)
    local start, stop, step
    if b == nil then
        start, stop, step = 0, a, 1
    elseif c == nil then
        start, stop, step = a, b, 1
    else
        start, stop, step = a, b, c
    end

    local result = {}
    local i = 1
    local current = start
    if step > 0 then
        while current < stop do
            result[i] = current
            i = i + 1
            current = current + step
        end
    elseif step < 0 then
        while current > stop do
            result[i] = current
            i = i + 1
            current = current + step
        end
    end
    return result
end

-- ---------------------------------------------------------------------------
-- py_len — len(x)
-- ---------------------------------------------------------------------------
function M.py_len(x)
    local t = type(x)
    if t == "string" then
        return string.len(x)
    elseif t == "table" then
        -- #x counts consecutive integer keys from 1 (Lua convention).
        -- For py_list tables with 0-indexed metamethods this matches length.
        return #x
    end
    error("py_len: unsupported type '" .. t .. "'", 2)
end

-- ---------------------------------------------------------------------------
-- py_str — str(x)
-- ---------------------------------------------------------------------------
function M.py_str(x)
    if x == nil then return "None" end
    if x == true then return "True" end
    if x == false then return "False" end
    return tostring(x)
end

-- ---------------------------------------------------------------------------
-- py_int — int(x)
-- Truncates towards zero like Python int(), not math.floor.
-- ---------------------------------------------------------------------------
function M.py_int(x)
    local n = tonumber(x)
    if n == nil then
        error("py_int: invalid literal for int: '" .. tostring(x) .. "'", 2)
    end
    return math.modf(n)  -- truncates toward zero
end

-- ---------------------------------------------------------------------------
-- py_float — float(x)
-- ---------------------------------------------------------------------------
function M.py_float(x)
    local n = tonumber(x)
    if n == nil then
        error("py_float: could not convert to float: '" .. tostring(x) .. "'", 2)
    end
    return n
end

-- ---------------------------------------------------------------------------
-- py_contains — x in collection
-- Works on Lua tables (sequential list) and strings.
-- ---------------------------------------------------------------------------
function M.py_contains(collection, value)
    local t = type(collection)
    if t == "string" then
        -- substring check
        return string.find(collection, value, 1, true) ~= nil
    elseif t == "table" then
        for _, v in ipairs(collection) do
            if v == value then return true end
        end
        -- Also check dictionary keys
        if collection[value] ~= nil then return true end
        return false
    end
    return false
end

-- ---------------------------------------------------------------------------
-- py_print — print(*args) — Roblox already has print(), but we expose
-- a wrapper that handles Python's default separator and end="\n".
-- In Roblox Studio, print() already adds a newline; this is a pass-through.
-- ---------------------------------------------------------------------------
function M.py_print(...)
    local args = {...}
    local parts = {}
    for _, v in ipairs(args) do
        table.insert(parts, M.py_str(v))
    end
    print(table.concat(parts, "\t"))
end

-- ===========================================================================
-- RUNTIME v2 — Data structure helpers (Phase 5)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Indexing helpers
-- ---------------------------------------------------------------------------
function M.py_index(tbl, idx)
    -- Handles negative indexing: arr[-1] → arr[#arr], arr[-2] → arr[#arr-1]
    if idx < 0 then
        return tbl[#tbl + 1 + idx]
    end
    return tbl[idx + 1]
end

-- ---------------------------------------------------------------------------
-- List helpers
-- ---------------------------------------------------------------------------
function M.py_append(list, value)
    table.insert(list, value)
end

function M.py_pop(list, idx)
    if idx == nil then
        return table.remove(list)
    end
    -- Convert 0-indexed to 1-indexed
    if idx < 0 then
        idx = #list + 1 + idx
    else
        idx = idx + 1
    end
    return table.remove(list, idx)
end

function M.py_insert(list, idx, value)
    -- Convert 0-indexed to 1-indexed
    if idx < 0 then
        idx = math.max(1, #list + 1 + idx)
    else
        idx = idx + 1
    end
    table.insert(list, idx, value)
end

function M.py_remove(list, value)
    for i, v in ipairs(list) do
        if v == value then
            table.remove(list, i)
            return
        end
    end
    error("py_remove: value not in list", 2)
end

function M.py_index_of(list, value)
    for i, v in ipairs(list) do
        if v == value then
            return i - 1  -- Return 0-indexed
        end
    end
    error("py_index_of: value not in list", 2)
end

function M.py_sort(list, key, reverse)
    if reverse then
        table.sort(list, function(a, b) return a > b end)
    else
        table.sort(list)
    end
end

function M.py_reverse(list)
    local n = #list
    for i = 1, math.floor(n / 2) do
        list[i], list[n - i + 1] = list[n - i + 1], list[i]
    end
end

function M.py_extend(list, other)
    for _, v in ipairs(other) do
        table.insert(list, v)
    end
end

function M.py_copy(list)
    local new = {}
    for i, v in ipairs(list) do
        new[i] = v
    end
    return new
end

function M.py_count(list, value)
    local c = 0
    for _, v in ipairs(list) do
        if v == value then c = c + 1 end
    end
    return c
end

function M.py_slice(tbl, start, stop, step)
    -- Emulates Python list slicing: tbl[start:stop:step]
    local n = #tbl
    step = step or 1

    if start == nil then
        start = step > 0 and 0 or (n - 1)
    elseif start < 0 then
        start = math.max(0, n + start)
    end

    if stop == nil then
        stop = step > 0 and n or -1
    elseif stop < 0 then
        stop = math.max(0, n + stop)
    end

    local result = {}
    if step > 0 then
        local i = start
        while i < stop do
            table.insert(result, tbl[i + 1])
            i = i + step
        end
    elseif step < 0 then
        local i = start
        while i > stop do
            table.insert(result, tbl[i + 1])
            i = i + step
        end
    end
    return result
end

-- ---------------------------------------------------------------------------
-- Dict helpers
-- ---------------------------------------------------------------------------
function M.py_keys(dict)
    local result = {}
    for k, _ in pairs(dict) do
        table.insert(result, k)
    end
    return result
end

function M.py_values(dict)
    local result = {}
    for _, v in pairs(dict) do
        table.insert(result, v)
    end
    return result
end

function M.py_items(dict)
    local result = {}
    for k, v in pairs(dict) do
        table.insert(result, {k, v})
    end
    return result
end

function M.py_get(dict, key, default)
    local val = dict[key]
    if val == nil then
        return default
    end
    return val
end

function M.py_update(dict, other)
    for k, v in pairs(other) do
        dict[k] = v
    end
end

function M.py_setdefault(dict, key, default)
    if dict[key] == nil then
        dict[key] = default or nil
    end
    return dict[key]
end

-- ---------------------------------------------------------------------------
-- String helpers
-- ---------------------------------------------------------------------------
function M.py_split(str, sep)
    if sep == nil then
        -- Split on whitespace by default
        local result = {}
        for word in string.gmatch(str, "%S+") do
            table.insert(result, word)
        end
        return result
    end
    local result = {}
    local pattern = "(.-)" .. string.gsub(sep, "([^%w])", "%%%1")
    local last_end = 1
    for part, pos in string.gmatch(str, pattern .. "()") do
        table.insert(result, part)
        last_end = pos
    end
    table.insert(result, string.sub(str, last_end))
    return result
end

function M.py_join(sep, list)
    -- Python: sep.join(list) → py_join(sep, list)
    local parts = {}
    for _, v in ipairs(list) do
        table.insert(parts, tostring(v))
    end
    return table.concat(parts, sep)
end

function M.py_strip(str, chars)
    if chars == nil then
        return (string.match(str, "^%s*(.-)%s*$"))
    end
    local pattern = "^[" .. string.gsub(chars, "([^%w])", "%%%1") .. "]*(.-)["
        .. string.gsub(chars, "([^%w])", "%%%1") .. "]*$"
    return (string.match(str, pattern))
end

function M.py_lstrip(str, chars)
    if chars == nil then
        return (string.match(str, "^%s*(.*)"))
    end
    local pattern = "^[" .. string.gsub(chars, "([^%w])", "%%%1") .. "]*(.*)"
    return (string.match(str, pattern))
end

function M.py_rstrip(str, chars)
    if chars == nil then
        return (string.match(str, "(.-)%s*$"))
    end
    local pattern = "(.-)[" .. string.gsub(chars, "([^%w])", "%%%1") .. "]*$"
    return (string.match(str, pattern))
end

function M.py_upper(str)
    return string.upper(str)
end

function M.py_lower(str)
    return string.lower(str)
end

function M.py_replace(str, old, new, count)
    if count == nil then
        return (string.gsub(str, string.gsub(old, "([^%w])", "%%%1"), new))
    end
    local result = str
    for _ = 1, count do
        local pos = string.find(result, old, 1, true)
        if pos == nil then break end
        result = string.sub(result, 1, pos - 1) .. new .. string.sub(result, pos + #old)
    end
    return result
end

function M.py_find(str, sub, start)
    start = (start or 0) + 1  -- convert 0-indexed to 1-indexed
    local pos = string.find(str, sub, start, true)
    if pos then
        return pos - 1  -- return 0-indexed
    end
    return -1
end

function M.py_startswith(str, prefix)
    return string.sub(str, 1, #prefix) == prefix
end

function M.py_endswith(str, suffix)
    return string.sub(str, -#suffix) == suffix
end

-- ---------------------------------------------------------------------------
-- Utility builtins
-- ---------------------------------------------------------------------------
function M.py_sorted(list, key, reverse)
    local copy = M.py_copy(list)
    M.py_sort(copy, key, reverse)
    return copy
end

function M.py_enumerate(list, start)
    start = start or 0
    local result = {}
    for i, v in ipairs(list) do
        table.insert(result, {start + (i - 1), v})
    end
    return result
end

function M.py_zip(...)
    local lists = {...}
    local result = {}
    if #lists == 0 then return result end
    local min_len = #lists[1]
    for i = 2, #lists do
        if #lists[i] < min_len then min_len = #lists[i] end
    end
    for i = 1, min_len do
        local tuple = {}
        for _, list in ipairs(lists) do
            table.insert(tuple, list[i])
        end
        table.insert(result, tuple)
    end
    return result
end

function M.py_reversed(list)
    local result = {}
    for i = #list, 1, -1 do
        table.insert(result, list[i])
    end
    return result
end

-- ===========================================================================
-- RUNTIME v3 — Advanced language helpers (Phase 6)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- py_format — f-string format spec support
-- Converts Python format specs to Lua string.format patterns.
-- e.g.  py_format(3.14159, ".2f") → "3.14"
-- ---------------------------------------------------------------------------
function M.py_format(value, spec)
    if spec == nil or spec == "" then
        return M.py_str(value)
    end
    -- Try to convert Python spec to Lua format string
    -- Common patterns: .2f, d, s, .3g, etc.
    local lua_fmt = "%" .. spec
    local ok, result = pcall(string.format, lua_fmt, value)
    if ok then
        return result
    end
    return M.py_str(value)
end

return M
