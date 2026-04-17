local M = {}

local defaults = {
  workspaces = {},
  python = "python3",
  script = nil,
  port = 18765,
  open_browser = true,
  output = nil,
  nvim_server = true,
}

local function plugin_root()
  local src = debug.getinfo(1, "S").source:sub(2)
  return vim.fn.fnamemodify(src, ":h:h:h")
end

local state = vim.deepcopy(defaults)

function M.setup(opts)
  state = vim.tbl_deep_extend("force", vim.deepcopy(defaults), opts or {})
  if not state.script then
    state.script = plugin_root() .. "/scripts/vault-graph.py"
  end
end

function M.get()
  if not state.script then
    state.script = plugin_root() .. "/scripts/vault-graph.py"
  end
  return state
end

return M
