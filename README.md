<p align="center">
  <img src="./docs/banner.svg" alt="llm-kiwi.nvim — knowledge graphs for your markdown vaults" width="720">
</p>

<p align="center">
  <a href="https://github.com/Narong-Kanthanu/llm-kiwi.nvim/actions/workflows/ci.yml"><img src="https://github.com/Narong-Kanthanu/llm-kiwi.nvim/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://neovim.io"><img src="https://img.shields.io/badge/Neovim-0.9+-57A143?logo=neovim&logoColor=white" alt="Neovim 0.9+"></a>
  <a href="./CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg" alt="Contributor Covenant 2.1"></a>
</p>

# llm-kiwi.nvim

An interactive knowledge-graph viewer for Neovim — scans `[[wikilinks]]`
across one or more markdown vaults and opens a force-directed graph in your
browser. Click (or `hjkl`-navigate) a node to jump straight into that `.md`
file inside the running Neovim instance.

<p align="center">
  <img src="./docs/demo.gif" alt="llm-kiwi.nvim demo — graph on the left, markdown note on the right" width="900">
</p>

Built for browsing **AI-generated wikis** in the style of Andrej Karpathy's
[llm-wiki concept](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
— incrementally-maintained markdown networks synthesized by an LLM — but
works with any Obsidian-flavoured vault or plain `[[wikilink]]` notes.

## Features

- Force-directed graph of notes and wikilink edges (vis.js, rendered in your
  browser)
- Sidebar file Explorer that mirrors the vault's folder tree, synced
  bidirectionally with the graph — `j`/`k` to move, `h`/`l` to
  collapse/expand folders, `o`/Enter to open. Picking a file highlights
  its node in the graph; conversely, `hjkl`-navigating the graph moves
  the Explorer cursor to the matching file row and auto-expands any
  collapsed ancestor folders along the way
- Vim-style keyboard navigation: `hjkl` to move, `Enter` to focus,
  `e` to jump to the file Explorer, `f` to search, `w` to switch workspace,
  `o` to open in Neovim, `Esc` to back
- Mouse support: drag to pan, scroll to zoom, hover to highlight, click to
  focus, double-click / label-click to open the note
- Multi-vault support with an in-browser workspace selector — switching
  vaults rebuilds the Explorer tree automatically
- Opens files back in your running Neovim via its RPC socket
- Unresolved `[[links]]` shown as ghost nodes (excluded from the Explorer)

## Requirements

- Neovim 0.9+
- Python 3.10+ on `PATH`
- macOS for in-place browser tab refresh and close (AppleScript). Chrome,
  Brave, Edge, Vivaldi, Chromium, and Safari are supported out of the box;
  extend `chromium_apps` in `setup()` to add others (e.g. Arc, Opera). On
  other platforms, each invocation opens a new browser tab via
  `webbrowser.open`.

## Install

With [lazy.nvim](https://github.com/folke/lazy.nvim):

```lua
{
  "Narong-Kanthanu/llm-kiwi.nvim",
  cmd = { "LlmKiwiOpen", "LlmKiwiClose", "LlmKiwiList" },
  opts = {
    workspaces = {
      { name = "personal", path = "~/notes" },
      { name = "llm-wiki", path = "~/llm-wiki" },
    },
  },
  keys = {
    { "<leader>kg", "<cmd>LlmKiwiOpen<cr>", desc = "LLM Kiwi: open graph" },
  },
}
```

No keymaps are registered by default — bind what you want.

## Commands

| Command                      | Description                               |
| ---------------------------- | ----------------------------------------- |
| `:LlmKiwiOpen [workspace]`   | Open graph; optionally activate workspace |
| `:LlmKiwiClose`              | Stop the running graph server             |
| `:LlmKiwiList`               | List configured workspaces                |
| `:checkhealth llm-kiwi`      | Verify python, script, and vault paths    |

## Configuration

All options with their defaults:

```lua
require("llm-kiwi").setup({
  workspaces = {},          -- { { name = "...", path = "..." }, ... }
  python = "python3",       -- python executable
  script = nil,             -- path to vault-graph.py (auto-resolved)
  port = 18765,             -- local HTTP port for the graph server
  open_browser = true,      -- set false to just generate HTML
  output = nil,             -- if set, write static HTML here instead of running server
  nvim_server = true,       -- pass vim.v.servername so clicks open in this nvim
  chromium_apps = {         -- macOS Chromium apps to refresh/close via AppleScript
    "Google Chrome",
    "Google Chrome Canary",
    "Brave Browser",
    "Microsoft Edge",
    "Vivaldi",
    "Chromium",
  },
})
```

## Credits

- Graph concept inspired by Andrej Karpathy's
  [llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
- Graph rendering by [vis.js](https://visjs.org/) (loaded from jsDelivr CDN).

## Contributing

Contributions are welcome — please read
[CONTRIBUTING.md](./CONTRIBUTING.md) first. By participating, you agree to
abide by the [Code of Conduct](./CODE_OF_CONDUCT.md). For security
reports, see [SECURITY.md](./SECURITY.md). A summary of user-facing
changes lives in the [Changelog](./CHANGELOG.md).

## License

[MIT](./LICENSE)
