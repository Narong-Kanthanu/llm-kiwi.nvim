local M = {}

local config = require("llm-kiwi.config")

local function report()
  local h = vim.health or require("health")
  h.start("llm-kiwi")

  local cfg = config.get()

  if vim.fn.executable(cfg.python) == 1 then
    local version = vim.fn.system({ cfg.python, "--version" }):gsub("%s+$", "")
    h.ok(cfg.python .. " on PATH (" .. version .. ")")
  else
    h.error("`" .. cfg.python .. "` not found on PATH", { "Install Python 3.10+ or set `python` in setup()" })
  end

  if cfg.script and vim.fn.filereadable(cfg.script) == 1 then
    h.ok("script found: " .. cfg.script)
  else
    h.error("script not readable: " .. tostring(cfg.script))
  end

  if #cfg.workspaces == 0 then
    h.warn("no workspaces configured", { "Add { name = ..., path = ... } entries to opts.workspaces" })
  else
    for _, ws in ipairs(cfg.workspaces) do
      local name = ws.name or "<unnamed>"
      if not ws.path then
        h.error("workspace '" .. name .. "' missing `path`")
      else
        local expanded = vim.fn.expand(ws.path)
        if vim.fn.isdirectory(expanded) == 1 then
          h.ok("workspace '" .. name .. "' → " .. expanded)
        else
          h.error("workspace '" .. name .. "' path does not exist: " .. expanded)
        end
      end
    end
  end
end

M.check = report

return M
