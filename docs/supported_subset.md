RPy Supported Python Subset (v0.1)
====================================

This document defines exactly which Python constructs the RPy
transpiler accepts and how they map to Luau.


Supported Constructs
--------------------

Variables & Literals
  - int, float, str, bool, None literals
  - Variable assignment and reassignment
  - Augmented assignment (+=, -=, *=, /=, //=, %=, **=)
  - Tuple unpacking: a, b = expr  →  local a, b = table.unpack(...)
  - Delete: del x  →  x = nil

Arithmetic & Logic
  - +  -  *  /  //  %  **
  - ==  !=  <  >  <=  >=
  - and  or  not
  - is / is not  →  ==  / ~=
  - in / not in  →  py_contains()
  - Ternary:  x if cond else y  →  (cond and x or y)

Control Flow
  - if / elif / else
  - for i in range(n)      →  for i = 0, n-1 do
  - for i in range(a, b)   →  for i = a, b-1 do
  - for i in range(a,b,s)  →  for i = a, b-step, step do
  - for x in iterable      →  for _, x in ipairs(iterable) do
  - while / break / continue / pass

Functions
  - def with positional args
  - *args  →  ... (vararg)
  - return values
  - Lambda:  lambda x: x+1  →  (function(x) return (x + 1) end)

Classes
  - class Foo:               →  local Foo = {}; Foo.__index = Foo
  - class Foo(Base):         →  setmetatable({}, {__index = Base})
  - def __init__(self, ...): →  function Foo.new(...)
  - def method(self, ...):   →  function Foo:method(...)
  - Class-level attributes   →  Foo.attr = value
  - Single inheritance only

Data Structures
  - List literals:    [1, 2, 3]      →  {1, 2, 3}
  - Dict literals:    {"a": 1}       →  {a = 1}
  - Tuple literals:   (1, 2)         →  {1, 2}
  - Subscript:        items[0]       →  items[1]  (0→1 index)
  - Negative index:   items[-1]      →  py_index(items, -1)
  - Slice:            items[1:3]     →  py_slice(items, 1, 3)

Comprehensions
  - [expr for x in iter]            →  IIFE with table.insert
  - [expr for x in iter if cond]    →  IIFE with if guard
  - {k: v for k, v in iter}         →  IIFE with key assignment

Exception Handling
  - try / except / finally          →  pcall() wrapper
  - raise Exception("msg")          →  error("msg")
  - raise (bare re-raise)           →  error(_err)

Strings
  - f"hello {name}"                 →  ("hello " .. py_str(name))
  - Format specs: f"{x:.2f}"        →  py_format(x, ".2f")

Imports
  - from roblox import X            →  (stripped — X is a Luau global)
  - from . import module            →  require(script.Parent.module)
  - import anything_else            →  UnsupportedFeatureError

With Statement
  - with expr as x:                 →  do local x = expr; ...; end


Unsupported Constructs
----------------------

These raise UnsupportedFeatureError with clear messages:

  - match/case (recognized but not implemented)
  - Multiple inheritance
  - Decorators (@decorator)
  - async/await
  - global / nonlocal
  - eval() / exec()
  - Standard library imports (os, json, etc.)
  - Generators (yield)
  - Walrus operator (:=)


Compiler Flags
--------------

  --typed        Emit Luau type annotations (local x: number = 5)
  --fast         Skip py_bool() truthiness shim (Lua semantics)
  --no-runtime   Don't prepend runtime require() header
  --verbose      Print detailed build output
