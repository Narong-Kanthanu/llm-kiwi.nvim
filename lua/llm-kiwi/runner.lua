local M = {}

local config = require("llm-kiwi.config")

local function build_argv(cfg, active)
  local argv = { cfg.python, cfg.script }

  for _, ws in ipairs(cfg.workspaces) do
    if ws.name and ws.path then
      table.insert(argv, "--vault")
      table.insert(argv, ws.name .. "=" .. vim.fn.expand(ws.path))
    end
  end

  if #cfg.workspaces > 1 then
    table.insert(argv, "--all")
  end

  if active and active ~= "" then
    table.insert(argv, "--active")
    table.insert(argv, active)
  end

  if cfg.nvim_server and vim.v.servername ~= "" then
    table.insert(argv, "--nvim-server")
    table.insert(argv, vim.v.servername)
  end

  if not cfg.open_browser then
    table.insert(argv, "--no-open")
  end

  if cfg.output then
    table.insert(argv, "--output")
    table.insert(argv, vim.fn.expand(cfg.output))
  end

  return argv
end

function M.start(active)
  local cfg = config.get()

  if #cfg.workspaces == 0 then
    vim.notify("llm-kiwi: no workspaces configured. Set `workspaces` in setup().", vim.log.levels.ERROR)
    return
  end

  if vim.fn.executable(cfg.python) == 0 then
    vim.notify("llm-kiwi: `" .. cfg.python .. "` not found on PATH.", vim.log.levels.ERROR)
    return
  end

  if vim.fn.filereadable(cfg.script) == 0 then
    vim.notify("llm-kiwi: script not found: " .. cfg.script, vim.log.levels.ERROR)
    return
  end

  local argv = build_argv(cfg, active)
  vim.fn.jobstart(argv, { detach = true })
end

function M.stop()
  local cfg = config.get()
  local url = "http://127.0.0.1:" .. cfg.port .. "/api/shutdown"
  vim.fn.jobstart({ "curl", "-s", "-X", "POST", "--max-time", "2", url }, { detach = true })
end

return M
