#!/usr/bin/env bash
# PreToolUse hook: remind Claude to re-check CLAUDE.md before a git commit
# whenever architecturally-relevant files are staged.
#
# Wired from .claude/settings.json with `if: "Bash(git commit*)"`, so this
# script only runs for commit calls — but it still defensively re-checks the
# command on stdin in case the filter is ever removed or tweaked.
#
# Output contract: stdout is a Claude Code hook JSON object (non-blocking,
# exit 0). Silent exit 0 means "no reminder needed."

set -euo pipefail

input="$(cat)"

command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')
case "$command" in
    *"git commit"*) ;;
    *) exit 0 ;;
esac

staged=$(git diff --cached --name-only 2>/dev/null || true)
[ -z "$staged" ] && exit 0

relevant=0
while IFS= read -r path; do
    [ -z "$path" ] && continue
    case "$path" in
        lua/*|plugin/*|scripts/*|.github/workflows/*) relevant=1; break ;;
        stylua.toml|.luacheckrc|pyproject.toml|tests/minimal_init.lua) relevant=1; break ;;
    esac
done <<< "$staged"

[ "$relevant" -eq 0 ] && exit 0

reminder="Files under lua/, plugin/, scripts/, .github/workflows/, or lint/test config are staged for this commit. Before committing, verify CLAUDE.md still accurately reflects: (1) Architecture — the Lua↔Python two-process split and the chromium_apps propagation path; (2) Commands — lint (stylua/luacheck/ruff/py_compile) and test (plenary, single-spec vs full suite) invocations still match CI; (3) Project rules — the four invariants from CONTRIBUTING.md. If any drift exists, update CLAUDE.md and stage it into this same commit. If CLAUDE.md is still accurate, proceed with the commit."

jq -nc --arg ctx "$reminder" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx
  }
}'
