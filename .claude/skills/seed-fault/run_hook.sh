#!/usr/bin/env bash
# Usage: bash .claude/skills/seed-fault/run_hook.sh <path relative to repo root>
#
# Feeds .claude/hooks/check_leakage.sh the same PostToolUse JSON that Claude
# Code sends after an Edit, and prints the hook's exit code and stderr so they
# can be pasted into docs/SEEDED_FAULTS.md verbatim. In a live session the hook
# fires on its own; this reproduces its output on demand, including for edits
# made outside the agent.
set -uo pipefail

repo=$(git rev-parse --show-toplevel)
[ -d "$repo/.venv/bin" ] && export PATH="$repo/.venv/bin:$PATH"
err=$(mktemp)
printf '{"hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"%s"}}' \
  "$repo/${1:?usage: run_hook.sh <path>}" \
  | CLAUDE_PROJECT_DIR="$repo" "$repo/.claude/hooks/check_leakage.sh" >/dev/null 2>"$err"
code=$?
echo "hook exit code: $code"
echo "hook stderr:"
cat "$err"
rm -f "$err"
