if vim.g.loaded_llm_kiwi == 1 then
  return
end
vim.g.loaded_llm_kiwi = 1

local function complete_workspaces(arg_lead)
  local cfg = require("llm-kiwi.config").get()
  local out = {}
  for _, ws in ipairs(cfg.workspaces) do
    if ws.name and ws.name:find(arg_lead, 1, true) == 1 then
      table.insert(out, ws.name)
    end
  end
  return out
end

vim.api.nvim_create_user_command("LlmKiwiOpen", function(params)
  require("llm-kiwi").open({ workspace = params.args ~= "" and params.args or nil })
end, {
  nargs = "?",
  complete = complete_workspaces,
  desc = "LLM Kiwi: open knowledge graph",
})

vim.api.nvim_create_user_command("LlmKiwiClose", function()
  require("llm-kiwi").close()
end, {
  desc = "LLM Kiwi: stop the running graph server",
})

vim.api.nvim_create_user_command("LlmKiwiList", function()
  require("llm-kiwi").list()
end, {
  desc = "LLM Kiwi: list configured workspaces",
})
