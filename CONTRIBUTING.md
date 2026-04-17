# Contributing to llm-kiwi.nvim

Thanks for your interest! This project is small and pragmatic — the goal is a
reliable, minimal knowledge-graph viewer for Neovim.

By participating in this project you agree to abide by our
[Code of Conduct](./CODE_OF_CONDUCT.md). For security issues, please see
[SECURITY.md](./SECURITY.md) and **do not** file a public issue.

## Development setup

Point your lazy.nvim spec at your local clone:

```lua
{
  dir = "~/path/to/llm-kiwi.nvim",
  opts = {
    workspaces = {
      { name = "test", path = "~/notes" },
    },
  },
}
```

Then `:Lazy reload llm-kiwi.nvim` after edits, or restart Neovim.

## Running the checks locally

The same checks run in CI. Before opening a PR:

```sh
# Lua
stylua --check lua/ plugin/ tests/
luacheck lua/ plugin/ tests/

# Python
ruff check scripts/
python -W error::SyntaxWarning -m py_compile scripts/vault-graph.py

# Smoke test
mkdir -p /tmp/vault && printf '# A\nSee [[b]].\n' > /tmp/vault/a.md && printf '# B\n' > /tmp/vault/b.md
python scripts/vault-graph.py --vault test=/tmp/vault --no-open --output /tmp/graph.html
```

Install tools:

```sh
brew install stylua luacheck    # or your package manager
pip install ruff
```

## Running the unit tests

The test suite uses [plenary.nvim](https://github.com/nvim-lua/plenary.nvim)
and runs headless. Clone plenary into `./deps/` the first time:

```sh
git clone --depth 1 https://github.com/nvim-lua/plenary.nvim deps/plenary.nvim
```

Then run the suite:

```sh
nvim --headless --noplugin -u tests/minimal_init.lua \
  -c "PlenaryBustedDirectory tests/ { minimal_init = 'tests/minimal_init.lua' }"
```

Tests live under `tests/` and follow the `*_spec.lua` convention.

## Cutting a release

1. Move the `## [Unreleased]` bullets in [`CHANGELOG.md`](./CHANGELOG.md) into
   a new dated section: `## [vX.Y.Z] - YYYY-MM-DD`.
2. Commit the changelog update.
3. Tag and push:

   ```sh
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

The `.github/workflows/release.yml` workflow will run the lint/compile
checks and, on success, publish a GitHub release with auto-generated
notes. No manual artifact upload is required — users install directly
from the repo via lazy.nvim.

## Scope & style

- **Keep the surface small.** New config keys need a clear use case.
- **No silent fallbacks.** Fail loudly via `vim.notify(..., vim.log.levels.ERROR)`
  when something is misconfigured.
- **Python backend is frozen-ish.** The big HTML/JS template is battle-tested;
  prefer small, well-scoped edits over rewrites.
- Follow the existing Lua module layout: public API in `init.lua`, everything
  else behind `require("llm-kiwi.<submodule>")`.

## Filing issues

Use the issue templates. For bugs, include:

- Neovim version (`nvim --version`)
- Python version (`python3 --version`)
- Your `workspaces` config (redact paths if sensitive)
- Full error from `:messages` and `:checkhealth llm-kiwi`
