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

### Optional: install the pre-push hook

`.githooks/pre-push` runs the lint/compile checks above and rejects the push
if any fail — catching drift locally before CI does. Enable it once per clone:

```sh
git config core.hooksPath .githooks
```

The hook is opt-in because `git config` is not versioned. It mirrors CI's
lint gates but uses whatever tool versions you have on `$PATH` — CI pins its
own (see `.github/workflows/ci.yml`), so a very new stylua locally can still
diverge. Bypass with `git push --no-verify` in emergencies.

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

Releases are CHANGELOG-driven. To cut `vX.Y.Z`:

1. Move the `## [Unreleased]` entries into a new dated section at the
   top of [`CHANGELOG.md`](./CHANGELOG.md):

   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   ### Added
   - …
   ```

   Update the link anchors at the bottom of the file as well.
2. Open a PR with that change and merge it to `main`.

That's it — [`release.yml`](./.github/workflows/release.yml) fires on
the merged PR (filtered to `paths: CHANGELOG.md`) and:

- parses the topmost dated `## [X.Y.Z] - YYYY-MM-DD` heading,
- skips if the tag and the GitHub release both already exist
  (idempotent — partial failures can be re-run safely),
- runs the lint/compile gate (stylua, luacheck, ruff, py_compile),
- creates the annotated tag `vX.Y.Z` and publishes the GitHub release
  using the matching CHANGELOG block as the release body.

Pre-releases work automatically — use a suffix like `0.2.0-rc.1` in the
heading (`## [0.2.0-rc.1] - YYYY-MM-DD`) and the workflow marks the
GitHub release as a pre-release.

### Manual fallback

The workflow also accepts `workflow_dispatch`. Trigger it from the
Actions tab if a release run fails partway (e.g. tag pushed but release
publish failed) — the idempotent state checks ensure only the missing
side gets re-created.

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
