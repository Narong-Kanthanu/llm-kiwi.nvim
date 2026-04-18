---@diagnostic disable: undefined-field
-- Exercises scripts/vault-graph.py end-to-end: builds a fixture vault, runs
-- the generator, and asserts the emitted HTML contains the Explorer markup,
-- CSS, and JS plumbing. Runtime JS behavior is verified interactively; this
-- spec guards the shape of the generated file against regressions.

local function repo_root()
  local src = debug.getinfo(1, "S").source:sub(2)
  return vim.fn.fnamemodify(src, ":p:h:h:h")
end

local function write_file(path, contents)
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local f = assert(io.open(path, "w"))
  f:write(contents)
  f:close()
end

local function read_file(path)
  local f = assert(io.open(path, "r"))
  local data = f:read("*a")
  f:close()
  return data
end

-- Generate the HTML once and reuse it across assertions. Plenary busted
-- doesn't expose a block-scope `setup` hook, so we do this at module load.
local root = repo_root()
local script = root .. "/scripts/vault-graph.py"
local tmp = vim.fn.tempname()
local vault = tmp .. "/vault"
local out = tmp .. "/graph.html"

-- Fixture vault: root-level note + nested folders + a wikilink.
write_file(vault .. "/home.md", "# Home\nSee [[one]].\n")
write_file(vault .. "/notes/one.md", "# One\n")
write_file(vault .. "/projects/alpha/deep.md", "# Deep\n")

local cmd = string.format(
  "python3 %s --vault test=%s --no-open --output %s 2>&1",
  vim.fn.shellescape(script),
  vim.fn.shellescape(vault),
  vim.fn.shellescape(out)
)
local build_output = vim.fn.system(cmd)
local build_exit = vim.v.shell_error
local html = (build_exit == 0) and read_file(out) or ""

-- Clean up the fixture vault and generated HTML when the test session exits.
vim.api.nvim_create_autocmd("VimLeavePre", {
  callback = function() vim.fn.delete(tmp, "rf") end,
})

describe("vault-graph.py generated HTML", function()
  it("builds successfully against the fixture vault", function()
    assert.equals(0, build_exit,
      "vault-graph.py failed to build:\n" .. tostring(build_output))
    assert.is_true(#html > 1000, "generated HTML is suspiciously small")
  end)

  it("emits the Explorer DOM container", function()
    assert.is_truthy(html:find('id="explorer"', 1, true), "#explorer div missing")
    assert.is_truthy(html:find('id="explorer-header"', 1, true), "#explorer-header missing")
    assert.is_truthy(html:find('id="explorer-list"', 1, true), "#explorer-list missing")
    assert.is_truthy(html:find("Explorer", 1, true), "Explorer header text missing")
  end)

  it("emits Explorer CSS styles", function()
    assert.is_truthy(html:find("#explorer {", 1, true), "#explorer CSS block missing")
    assert.is_truthy(html:find(".explorer-row", 1, true), ".explorer-row styles missing")
    assert.is_truthy(html:find(".explorer-row.selected", 1, true), "selected-row styles missing")
  end)

  it("emits Explorer JS build + render functions", function()
    assert.is_truthy(html:find("buildExplorerTree", 1, true), "buildExplorerTree missing")
    assert.is_truthy(html:find("flattenExplorer", 1, true), "flattenExplorer missing")
    assert.is_truthy(html:find("renderExplorerList", 1, true), "renderExplorerList missing")
    assert.is_truthy(html:find("explorerSelect", 1, true), "explorerSelect missing")
    assert.is_truthy(html:find("explorerMove", 1, true), "explorerMove missing")
    assert.is_truthy(html:find("enterExplorer", 1, true), "enterExplorer missing")
    assert.is_truthy(html:find("exitExplorer", 1, true), "exitExplorer missing")
  end)

  it("wires the 'e' keybinding and lists it in the keymap help", function()
    -- Keymap help entry
    assert.is_truthy(html:find("'explorer'", 1, true), "keymap help 'explorer' entry missing")
    -- The hint text mentions the e-key
    assert.is_truthy(html:find("e explorer", 1, true), "hint 'e explorer' text missing")
  end)

  it("runs Explorer setup BEFORE vis.Network init (so graph failures don't hide it)", function()
    local explorer_pos = html:find("buildExplorerTree(data.nodes)", 1, true)
    local vis_pos = html:find("new vis.Network(", 1, true)
    assert.is_truthy(explorer_pos, "Explorer build call missing")
    assert.is_truthy(vis_pos, "vis.Network init missing")
    assert.is_true(explorer_pos < vis_pos,
      "Explorer must be built before vis.Network so graph init failures don't blank the sidebar")
  end)

  it("places Reset view button AFTER the Explorer in the controls panel", function()
    local explorer_div = html:find('<div id="explorer">', 1, true)
    local reset_btn = html:find('id="reset-btn"', 1, true)
    assert.is_truthy(explorer_div, "#explorer div missing")
    assert.is_truthy(reset_btn, "#reset-btn missing")
    assert.is_true(reset_btn > explorer_div,
      "Reset view button must be positioned after the Explorer (user-requested layout)")
  end)

  it("keeps the workspace selector always visible (no single-vault auto-hide)", function()
    -- The old hide-when-single rule was removed; ensure it doesn't sneak back.
    assert.is_nil(html:find("wsNames.length <= 1", 1, true),
      "workspace selector should no longer auto-hide for single-vault setups")
  end)

  it("unconditionally populates the keymap help (not gated on server mode)", function()
    -- The server-mode gate around keymap help was removed; the help must
    -- render in both file:// and http:// contexts.
    local gated = html:find("if (IS_SERVER_MODE) {\n%s+document.getElementById%('hint'%)")
    assert.is_nil(gated, "keymap help should not be gated on IS_SERVER_MODE")
  end)

  it("populates the vault JSON payload with all discovered notes", function()
    -- Three markdown files were created in the fixture; all three should be in the data.
    assert.is_truthy(html:find("home.md", 1, true), "home.md missing from payload")
    assert.is_truthy(html:find("notes/one.md", 1, true), "nested note missing from payload")
    assert.is_truthy(html:find("projects/alpha/deep.md", 1, true), "deeply nested note missing from payload")
  end)

  it("emits the Cache-Control header in server mode to avoid stale HTML", function()
    -- This lives in the Python source, not the HTML output; read the script directly.
    local py = read_file(script)
    assert.is_truthy(py:find("Cache-Control", 1, true),
      "server must send Cache-Control so browsers don't serve pre-Explorer HTML from cache")
    assert.is_truthy(py:find("no-store", 1, true),
      "Cache-Control should include no-store")
  end)
end)
