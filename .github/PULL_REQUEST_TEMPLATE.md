## Summary

<!-- What changes, and why. -->

## Test plan

- [ ] `stylua --check lua/ plugin/ tests/`
- [ ] `luacheck lua/ plugin/ tests/`
- [ ] `ruff check scripts/`
- [ ] `python -W error::SyntaxWarning -m py_compile scripts/vault-graph.py`
- [ ] `nvim --headless --noplugin -u tests/minimal_init.lua -c "PlenaryBustedDirectory tests/"`
- [ ] Manually opened the graph with a local vault and verified the change
- [ ] Updated `CHANGELOG.md` under `## [Unreleased]` if user-visible

## Notes for reviewers

<!-- Anything tricky, intentional trade-offs, screenshots, etc. -->
