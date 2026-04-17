-- Headless test bootstrap. Invoke with:
--
--   nvim --headless --noplugin -u tests/minimal_init.lua \
--     -c "PlenaryBustedDirectory tests/ { minimal_init = 'tests/minimal_init.lua' }"
--
-- Expects plenary.nvim to be cloned at ./deps/plenary.nvim.

local repo_root = vim.fn.getcwd()
local plenary_path = repo_root .. "/deps/plenary.nvim"

vim.opt.runtimepath:prepend(repo_root)
vim.opt.runtimepath:prepend(plenary_path)

vim.cmd("runtime plugin/plenary.vim")
vim.cmd("runtime plugin/llm-kiwi.lua")

require("plenary.busted")
