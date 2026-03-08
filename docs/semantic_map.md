RPy Semantic Map — Python → Luau
=================================

This document maps every supported Python construct to its Luau equivalent.


Literals
--------
  Python            Luau
  ------            ----
  42                42
  3.14              3.14
  "hello"           "hello"
  True              true
  False             false
  None              nil
  [1, 2, 3]         {1, 2, 3}
  {"a": 1}          {a = 1}
  (1, 2)            {1, 2}
  []                {}
  {}                {}


Operators
---------
  Python            Luau
  ------            ----
  +                 +
  -                 -
  *                 *
  /                 /
  //                //
  %                 %
  **                ^
  ==                ==
  !=                ~=
  <  >  <=  >=      <  >  <=  >=
  and               and
  or                or
  not               not
  is                ==
  is not            ~=
  in                py_contains(container, value)
  not in            not py_contains(container, value)


Variables
---------
  Python            Luau
  ------            ----
  x = 5             local x = 5        (first assignment)
  x = 10            x = 10             (reassignment)
  x += 1            x = x + 1
  del x             x = nil
  a, b = expr       local a, b = table.unpack(expr)


Control Flow
------------
  Python                          Luau
  ------                          ----
  if cond:                        if cond then
  elif cond:                      elseif cond then
  else:                           else
                                  end

  for i in range(n):              for i = 0, n-1 do ... end
  for i in range(a, b):           for i = a, b-1 do ... end
  for i in range(a, b, s):        for i = a, b-s, s do ... end
  for x in items:                 for _, x in ipairs(items) do ... end

  while cond:                     while cond do ... end
  break                           break
  continue                        continue
  pass                            -- pass


Functions
---------
  Python                          Luau
  ------                          ----
  def foo(a, b):                  local function foo(a, b)
  def foo(*args):                 local function foo(...)
  return val                      return val
  lambda x: x + 1                (function(x) return (x + 1) end)


Classes
-------
  Python                          Luau
  ------                          ----
  class Foo:                      local Foo = {}
                                  Foo.__index = Foo

  class Foo(Base):                local Foo = setmetatable({}, {__index = Base})
                                  Foo.__index = Foo

  def __init__(self, x):          function Foo.new(x)
      self.x = x                      local self = setmetatable({}, Foo)
                                      self.x = x
                                      return self
                                  end

  def method(self, arg):          function Foo:method(arg)
      ...                             ...
                                  end

  obj = Foo(x)                    local obj = Foo.new(x)


Indexing
--------
  Python            Luau
  ------            ----
  items[0]          items[1]              (0→1 correction)
  items[3]          items[4]
  items[i]          items[i + 1]
  items[-1]         py_index(items, -1)
  items[1:3]        py_slice(items, 1, 3)
  items[::2]        py_slice(items, nil, nil, 2)


Exceptions
----------
  Python                          Luau
  ------                          ----
  try:                            local _ok, _err = pcall(function()
      risky()                         risky()
  except E as e:                  end)
      handle(e)                   if not _ok then
  finally:                            local e = _err
      cleanup()                       handle(e)
                                  end
                                  cleanup()

  raise Err("msg")                error("msg")
  raise                           error(_err)


Strings
-------
  Python                          Luau
  ------                          ----
  f"hi {name}"                    ("hi " .. py_str(name))
  f"{x:.2f}"                      ("" .. py_format(x, ".2f"))


Imports
-------
  Python                          Luau
  ------                          ----
  from roblox import X            (stripped — X is a global)
  from . import mod               local mod = require(script.Parent.mod)
  import json                     ERROR: unsupported


Builtins
--------
  Python            Luau
  ------            ----
  print(x)          print(x)
  len(x)            py_len(x)
  str(x)            py_str(x)
  int(x)            py_int(x)
  float(x)          py_float(x)
  abs(x)            math.abs(x)
  type(x)           typeof(x)
  isinstance(x, T)  typeof(x) == T
  sorted(x)         py_sorted(x)
  reversed(x)       py_reversed(x)
  enumerate(x)      py_enumerate(x)
  zip(a, b)         py_zip(a, b)


With Statement
--------------
  Python                          Luau
  ------                          ----
  with expr as x:                 do
      use(x)                          local x = expr
                                      use(x)
                                  end
