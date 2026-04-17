# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

Two-process plugin: a thin Lua layer in Neovim spawns a detached Python script that does all the real work.

- **Lua (`lua/llm-kiwi/`)** is glue: `init.lua` exposes `setup/open/close/list`; `config.lua` holds defaults and `tbl_deep_extend("force", ...)` merge; `runner.lua` builds the argv for `vault-graph.py` and `jobstart`s it detached. `runner.lua`'s `M.stop` is also the *browser-close* path — it dispatches `osascript` against each entry in `cfg.chromium_apps` plus Safari, then `curl`s `POST /api/shutdown`. User commands live in `plugin/llm-kiwi.lua` and call into the public API.
- **Python (`scripts/vault-graph.py`)** is the engine: scans `[[wikilinks]]`, emits a single-file HTML graph with an embedded vis.js bundle, and — when `--nvim-server` is set — runs an HTTP server on `127.0.0.1:18765` that exposes `/api/open` (clicks in the browser call back into the same Neovim via its RPC socket, invoking `:edit`) and `/api/shutdown`. On macOS it uses AppleScript to *refresh* a matching tab in an existing Chromium browser or Safari instead of spawning a new one; falls back to `webbrowser.open` otherwise.
- **`chromium_apps` list** is the single source of truth for supported macOS Chromium browsers. It's set in `config.lua`, propagated to the Python process via repeatable `--chromium-app` flags in `runner.lua:build_argv`, and consulted in both `M.stop` (close) and `open_or_refresh` (refresh). Extending it (e.g. Arc, Opera beta) automatically covers both paths.

The Python script is intentionally self-contained — it embeds a large HTML/JS template and is meant to be usable standalone (`python3 scripts/vault-graph.py --vault name=path`). That's why args like `--chromium-app` carry a fallback default list mirroring the Lua defaults.

## Commands

### Tests

```sh
# first-time setup (once)
git clone --depth 1 https://github.com/nvim-lua/plenary.nvim deps/plenary.nvim

# full suite
nvim --headless --noplugin -u tests/minimal_init.lua \
  -c "PlenaryBustedDirectory tests/ { minimal_init = 'tests/minimal_init.lua' }"

# single spec file
nvim --headless --noplugin -u tests/minimal_init.lua \
  -c "PlenaryBustedFile tests/llm-kiwi/init_spec.lua"
```

Specs follow the `*_spec.lua` convention under `tests/`.

### Lint / checks (same as CI)

```sh
stylua --check lua/ plugin/ tests/
luacheck lua/ plugin/ tests/
ruff check scripts/
python -W error::SyntaxWarning -m py_compile scripts/vault-graph.py
```

### End-to-end smoke

```sh
mkdir -p /tmp/vault && printf '# A\nSee [[b]].\n' > /tmp/vault/a.md && printf '# B\n' > /tmp/vault/b.md
python3 scripts/vault-graph.py --vault test=/tmp/vault --no-open --output /tmp/graph.html
```

## Project rules (from CONTRIBUTING.md)

- **No silent fallbacks.** Misconfiguration must surface through `vim.notify(..., vim.log.levels.ERROR)` — see the guards in `runner.lua:M.start`.
- **Keep the config surface small.** A new key in `config.lua` needs a clear use case. The existing keys are defaults merged by `tbl_deep_extend("force", ...)`; list values replace wholesale (intentional, e.g. `chromium_apps`).
- **Module layout:** public API lives in `lua/llm-kiwi/init.lua`; everything else is private behind `require("llm-kiwi.<submodule>")`.
- **Python backend is frozen-ish.** The big embedded HTML/JS template is battle-tested; prefer small, well-scoped edits over rewrites.

## Releases

CHANGELOG-driven. Move `## [Unreleased]` items into a dated `## [X.Y.Z] - YYYY-MM-DD` section and merge to `main`; `.github/workflows/auto-release.yml` runs the full lint/compile/test gate, tags `vX.Y.Z`, and publishes a GitHub release using the CHANGELOG body. Pre-release suffixes (e.g. `0.2.0-rc.1`) are detected automatically. Manual tag pushes go through `release.yml` as a fallback.
