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

local function chrome_close_script(url)
  return string.format(
    [[
tell application "System Events"
    if not (exists process "Google Chrome") then return "missing"
end tell
tell application "Google Chrome"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t starts with "%s" then
                close t
                return "closed"
            end if
        end repeat
    end repeat
end tell
return "notfound"
]],
    url
  )
end

local function safari_close_script(url)
  return string.format(
    [[
tell application "System Events"
    if not (exists process "Safari") then return "missing"
end tell
tell application "Safari"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t starts with "%s" then
                tell t to close
                return "closed"
            end if
        end repeat
    end repeat
end tell
return "notfound"
]],
    url
  )
end

function M.stop()
  local cfg = config.get()
  local base = "http://127.0.0.1:" .. cfg.port

  if vim.fn.has("mac") == 1 and vim.fn.executable("osascript") == 1 then
    vim.fn.jobstart({ "osascript", "-e", chrome_close_script(base) }, { detach = true })
    vim.fn.jobstart({ "osascript", "-e", safari_close_script(base) }, { detach = true })
  end

  vim.fn.jobstart({ "curl", "-s", "-X", "POST", "--max-time", "2", base .. "/api/shutdown" }, { detach = true })
end

return M
