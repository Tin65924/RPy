"""
transpiler/runtime_snippets.py — Collection of Luau helper functions for injection.

Each snippet is a standalone Luau string. 
Dependencies are tracked so that if one helper is used, its dependencies are also injected.
"""

# Mapping of helper name -> (source_code, dependencies)
SNIPPETS: dict[str, tuple[str, list[str]]] = {
    "py_bool": (
        """local function py_bool(value)
    if value == nil then return false end
    if value == false then return false end
    if value == 0 or value == 0.0 then return false end
    if value == "" then return false end
    if type(value) == "table" and next(value) == nil then return false end
    return true
end""",
        []
    ),

    "py_len": (
        """local function py_len(x)
    local t = type(x)
    if t == "string" then
        return string.len(x)
    elseif t == "table" then
        if x._is_set then return x._count end
        return #x
    end
    error("py_len: unsupported type '" .. t .. "'", 2)
end""",
        []
    ),

    "py_str": (
        """local function py_str(x)
    if x == nil then return "None" end
    if x == true then return "True" end
    if x == false then return "False" end
    return tostring(x)
end""",
        []
    ),

    "py_int": (
        """local function py_int(x)
    local n = tonumber(x)
    if n == nil then error("py_int: invalid literal: '" .. tostring(x) .. "'", 2) end
    return math.modf(n)
end""",
        []
    ),

    "py_float": (
        """local function py_float(x)
    local n = tonumber(x)
    if n == nil then error("py_float: could not convert: '" .. tostring(x) .. "'", 2) end
    return n
end""",
        []
    ),

    "py_range": (
        """local function py_range(a, b, c)
    local start, stop, step
    if b == nil then start, stop, step = 0, a, 1
    elseif c == nil then start, stop, step = a, b, 1
    else start, stop, step = a, b, c end
    local result = {}
    local current = start
    if step > 0 then
        while current < stop do
            table.insert(result, current)
            current = current + step
        end
    elseif step < 0 then
        while current > stop do
            table.insert(result, current)
            current = current + step
        end
    end
    return result
end""",
        []
    ),

    "py_print": (
        """local function py_print(...)
    local args = {...}
    local parts = {}
    for _, v in ipairs(args) do
        table.insert(parts, py_str(v))
    end
    print(table.concat(parts, "\\t"))
end""",
        ["py_str"]
    ),

    "py_contains": (
        """local function py_contains(collection, value)
    local t = type(collection)
    if t == "string" then
        return string.find(collection, value, 1, true) ~= nil
    elseif t == "table" then
        if collection._is_set then return collection.items[value] == true end
        for _, v in ipairs(collection) do if v == value then return true end end
        if collection[value] ~= nil then return true end
    end
    return false
end""",
        []
    ),

    "py_index": (
        """local function py_index(tbl, idx)
    if idx < 0 then return tbl[#tbl + 1 + idx] end
    return tbl[idx + 1]
end""",
        []
    ),

    "py_append": (
        """local function py_append(list, value)
    table.insert(list, value)
end""",
        []
    ),

    "py_pop": (
        """local function py_pop(list, idx)
    if idx == nil then return table.remove(list) end
    if idx < 0 then idx = #list + 1 + idx else idx = idx + 1 end
    return table.remove(list, idx)
end""",
        []
    ),

    "py_slice": (
        """local function py_slice(tbl, start, stop, step)
    local n = #tbl
    step = step or 1
    if start == nil then start = step > 0 and 0 or (n - 1)
    elseif start < 0 then start = math.max(0, n + start) end
    if stop == nil then stop = step > 0 and n or -1
    elseif stop < 0 then stop = math.max(0, n + stop) end
    local result = {}
    local i = start
    if step > 0 then
        while i < stop do
            table.insert(result, tbl[i + 1])
            i = i + step
        end
    elseif step < 0 then
        while i > stop do
            table.insert(result, tbl[i + 1])
            i = i + step
        end
    end
    return result
end""",
        []
    ),

    "py_iter": (
        """local function py_iter(iterable)
    local t = type(iterable)
    if t == "table" then
        if iterable._is_set then
            local f, s, var = pairs(iterable.items)
            return function(_, prev)
                local k = f(s, prev)
                if k ~= nil then return 0, k end
                return nil
            end, s, var
        end
        return ipairs(iterable)
    end
    return function() end
end""",
        []
    ),

    "py_enumerate": (
        """local function py_enumerate(list, start)
    start = start or 0
    local result = {}
    for i, v in ipairs(list) do
        table.insert(result, {start + (i - 1), v})
    end
    return result
end""",
        []
    ),
    
    # Dict helpers
    "py_keys": (
        """local function py_keys(dict)
    local res = {}
    for k in pairs(dict) do table.insert(res, k) end
    return res
end""",
        []
    ),
    
    "py_values": (
        """local function py_values(dict)
    local res = {}
    for _, v in pairs(dict) do table.insert(res, v) end
    return res
end""",
        []
    ),

    "py_items": (
        """local function py_items(dict)
    local res = {}
    for k, v in pairs(dict) do table.insert(res, {k, v}) end
    return res
end""",
        []
    ),

    # String helpers
    "py_split": (
        """local function py_split(str, sep)
    if sep == nil then
        local res = {}
        for w in string.gmatch(str, "%S+") do table.insert(res, w) end
        return res
    end
    local res = {}
    local pattern = "(.-)" .. string.gsub(sep, "([^%w])", "%%%1")
    local last_end = 1
    for part, pos in string.gmatch(str, pattern .. "()") do
        table.insert(res, part)
        last_end = pos
    end
    table.insert(res, string.sub(str, last_end))
    return res
end""",
        []
    ),

    # Set helpers
    "py_set_new": (
        """local function py_set_new(iterable)
    local s = { _is_set = true, items = {}, _count = 0 }
    if iterable then
        for _, v in py_iter(iterable) do
            if not s.items[v] then
                s.items[v] = true
                s._count = s._count + 1
            end
        end
    end
    return s
end""",
        ["py_iter"]
    ),

    "py_set_add": (
        """local function py_set_add(s, item)
    if not s.items[item] then
        s.items[item] = true
        s._count = s._count + 1
    end
end""",
        []
    ),

    "py_set_discard": (
        """local function py_set_discard(s, item)
    if s.items[item] then
        s.items[item] = nil
        s._count = s._count - 1
    end
end""",
        []
    ),

    "py_set_clear": (
        """local function py_set_clear(s)
    s.items = {}
    s._count = 0
end""",
        []
    ),

    "py_set_union": (
        """local function py_set_union(s1, s2)
    local s = py_set_new()
    for k in pairs(s1.items) do py_set_add(s, k) end
    for k in pairs(s2.items) do py_set_add(s, k) end
    return s
end""",
        ["py_set_new", "py_set_add"]
    ),

    "py_set_intersection": (
        """local function py_set_intersection(s1, s2)
    local s = py_set_new()
    for k in pairs(s1.items) do
        if s2.items[k] then py_set_add(s, k) end
    end
    return s
end""",
        ["py_set_new", "py_set_add"]
    ),

    "py_set_difference": (
        """local function py_set_difference(s1, s2)
    local s = py_set_new()
    for k in pairs(s1.items) do
        if not s2.items[k] then py_set_add(s, k) end
    end
    return s
end""",
        ["py_set_new", "py_set_add"]
    ),
}

def get_used_snippets(used_names: set[str]) -> str:
    """
    Builds the final Luau header by recursively resolving dependencies
    of all used helper functions.
    """
    to_inject = set()
    stack = list(used_names)
    
    while stack:
        name = stack.pop()
        if name in SNIPPETS and name not in to_inject:
            to_inject.add(name)
            _, deps = SNIPPETS[name]
            stack.extend(deps)
            
    if not to_inject:
        return ""
        
    names = sorted(list(to_inject))
    lines = [f"local {', '.join(names)}"]
    
    for name in names:
        code, _ = SNIPPETS[name]
        # remove "local " from the start of the standard 'local function name()' snippet
        if code.startswith("local "):
            code = code[6:]
        lines.append(code)
        
    return "\n".join(lines) + "\n"
