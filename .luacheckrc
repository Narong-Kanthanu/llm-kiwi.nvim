std = "luajit"
cache = true

globals = {
  "vim",
}

read_globals = {
  "jit",
}

ignore = {
  "212/_.*", -- unused argument starting with underscore
  "631",     -- line too long (stylua owns formatting)
}

exclude_files = {
  ".luarocks",
  "lua_modules",
  "deps",
}

-- plenary.busted provides these as globals in test files
files["tests/"] = {
  read_globals = {
    "describe",
    "it",
    "before_each",
    "after_each",
    "setup",
    "teardown",
    "pending",
    "assert",
  },
}
