local M = {}

function M.setup(opts)
  require("llm-kiwi.config").setup(opts)
end

function M.open(opts)
  opts = opts or {}
  require("llm-kiwi.runner").start(opts.workspace)
end

function M.close()
  require("llm-kiwi.runner").stop()
end

function M.list()
  local cfg = require("llm-kiwi.config").get()
  if #cfg.workspaces == 0 then
    vim.notify("llm-kiwi: no workspaces configured", vim.log.levels.WARN)
    return
  end
  local lines = { "llm-kiwi workspaces:" }
  for _, ws in ipairs(cfg.workspaces) do
    table.insert(lines, string.format("  %s — %s", ws.name or "<unnamed>", ws.path or "<no path>"))
  end
  vim.notify(table.concat(lines, "\n"), vim.log.levels.INFO)
end

return M
