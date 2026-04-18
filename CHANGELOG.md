# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Graph viewer layout split into two real columns: a fixed 232px sidebar
  on the left (workspace picker, search, Explorer tree, reset, stats)
  and a flex-filled graph column on the right. Floating overlays
  (Folders legend, keymap help, hint) now live inside the graph column
  instead of overlapping the sidebar, so node labels never slide behind
  sidebar content.

### Fixed

- Exiting the sidebar Explorer (Esc) now restores the graph to a clean
  state — clears the red-bordered node highlight and hides the tooltip,
  matching the exit symmetry of search and focus modes.
- Explorer entry (`e`) pans the graph to the picked node so it's always
  on-screen, and tree navigation (`j`/`k`) pans smoothly using the same
  400ms easeInOutCubic animation as normal-mode `hjkl`. vis.js cancels
  the prior animation on each call, so rapid keystrokes retarget
  instead of queueing — no lag, no teleporting highlight.

## [0.4.0] - 2026-04-18

### Added

- Sidebar file Explorer in the graph UI. The left control strip now
  includes a folder-tree view of the active vault that lives underneath
  the workspace selector and search box, with the `Reset view` button
  pinned at the bottom. Press `e` from the graph to jump into the tree,
  `j`/`k` to move, `h`/`l` to collapse/expand folders, and `o` or Enter
  to open a file in Neovim. Selecting a file row highlights the
  corresponding node in the graph; switching workspace rebuilds the
  tree.
- `Cache-Control: no-store` header on the graph server so reloads after
  an `:LlmKiwiClose` / `:LlmKiwiOpen` restart never serve stale HTML
  from the browser cache.

### Changed

- Workspace selector is always visible, including for single-vault
  setups (previously auto-hidden). Aligns with the Explorer's "always
  on" sidebar layout.
- Vim keymap hint at the bottom-right of the graph is now shown in
  standalone (`file://`) mode too, not only when served over HTTP.
- Explorer is built before vis.js initialization so the sidebar still
  renders if the network canvas fails to come up.

## [0.3.0] - 2026-04-17

### Added

- Expanded Chromium-family browser support for both the refresh-on-open
  and close-on-`:LlmKiwiClose` paths: Brave Browser, Microsoft Edge,
  Vivaldi, and Chromium now join Google Chrome (and Safari) on macOS.
  The set is driven by the `chromium_apps` config option, which is the
  single source of truth — extending it automatically covers both paths.

## [0.2.0] - 2026-04-17

### Added

- Close the matching browser tab on `:LlmKiwiClose` (macOS Chrome and
  Safari via AppleScript). Teardown is now symmetric with `:LlmKiwiOpen`,
  which already uses the same workflow. On non-macOS platforms the
  behavior is unchanged: the server stops and the browser tab is left
  for the user to close.
- CHANGELOG-driven auto-release workflow
  (`.github/workflows/auto-release.yml`): pushes to `main` that add a
  new dated version block to `CHANGELOG.md` automatically create the
  git tag and publish a GitHub release using the CHANGELOG body as
  release notes.

### Removed

- "Using with obsidian.nvim" section from the README — it just
  duplicated the main install example (a workspace is only
  `{ name, path }`, no integration layer exists).

## [0.1.0] - 2026-04-17

Initial public release.

### Added

- Force-directed graph of markdown notes and `[[wikilink]]` edges rendered
  via vis.js in the browser.
- Vim-style keyboard navigation in the graph: `hjkl`, `Enter`, `f`, `w`,
  `o`, `Esc`.
- Mouse support: drag, scroll, hover, click, and double-click to open.
- Multi-vault workspaces with an in-browser selector.
- Opens files back in the running Neovim via its RPC socket.
- Unresolved links shown as ghost nodes.
- User commands: `:LlmKiwiOpen [workspace]`, `:LlmKiwiClose`, `:LlmKiwiList`.
- `:checkhealth llm-kiwi` verifying python, script path, and vault paths.
- Vimdoc help at `:help llm-kiwi`.
- Project banner (`docs/banner.svg`) displayed at the top of the README.
- Demo GIF (`docs/demo.gif`) in the README showing graph navigation and
  open-in-nvim click-through.
- Community files: `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`.
- Plenary smoke tests and cross-platform CI (Ubuntu + macOS).
- Neovim version matrix in CI: stable + nightly (nightly non-blocking).
- Pinned lint tool versions (stylua, luacheck, ruff) for reproducible CI.
- Tag-triggered GitHub release workflow.

[Unreleased]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/releases/tag/v0.4.0
[0.3.0]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/releases/tag/v0.3.0
[0.2.0]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/releases/tag/v0.2.0
[0.1.0]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/releases/tag/v0.1.0
