# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Community files: `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`.
- Plenary smoke tests and cross-platform CI (Ubuntu + macOS).
- Neovim version matrix in CI: stable + nightly (nightly non-blocking).
- Pinned lint tool versions (stylua, luacheck, ruff) for reproducible CI.
- Tag-triggered GitHub release workflow.

[Unreleased]: https://github.com/Narong-Kanthanu/llm-kiwi.nvim/compare/HEAD...HEAD
