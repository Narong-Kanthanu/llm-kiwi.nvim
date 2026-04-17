---@diagnostic disable: undefined-field
-- luassert fields (is_true, equals, is_function, etc.) are not seen by lua-language-server.

describe("llm-kiwi", function()
  it("loads without error", function()
    local ok, mod = pcall(require, "llm-kiwi")
    assert.is_true(ok, "require('llm-kiwi') failed: " .. tostring(mod))
    assert.is_function(mod.setup)
    assert.is_function(mod.open)
    assert.is_function(mod.close)
    assert.is_function(mod.list)
  end)

  it("accepts setup with defaults and merges options", function()
    require("llm-kiwi").setup({
      workspaces = {
        { name = "test", path = "/tmp/vault" },
      },
    })
    local cfg = require("llm-kiwi.config").get()
    assert.equals("python3", cfg.python)
    assert.equals(18765, cfg.port)
    assert.is_true(cfg.open_browser)
    assert.is_true(cfg.nvim_server)
    assert.is_string(cfg.script)
    assert.equals(1, #cfg.workspaces)
    assert.equals("test", cfg.workspaces[1].name)
  end)

  it("auto-resolves the script path", function()
    require("llm-kiwi").setup({})
    local cfg = require("llm-kiwi.config").get()
    assert.is_truthy(cfg.script:match("scripts/vault%-graph%.py$"))
  end)

  it("registers user commands", function()
    local commands = vim.api.nvim_get_commands({})
    assert.is_not_nil(commands.LlmKiwiOpen)
    assert.is_not_nil(commands.LlmKiwiClose)
    assert.is_not_nil(commands.LlmKiwiList)
  end)

  it("warns when listing with no workspaces configured", function()
    require("llm-kiwi").setup({ workspaces = {} })
    local captured = nil
    local original = vim.notify
    vim.notify = function(msg, _)
      captured = msg
    end
    require("llm-kiwi").list()
    vim.notify = original
    assert.is_truthy(captured and captured:match("no workspaces configured"))
  end)
end)
