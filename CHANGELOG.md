# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/releases/tag/v0.2.0
[0.1.0]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/releases/tag/v0.1.0
