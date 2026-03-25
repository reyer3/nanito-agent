#!/bin/bash
# Hook: block-no-verify
# Blocks --no-verify flag on git commands to protect code quality
# Exit code 2 = hard block (prevents tool execution)

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE '\-\-no\-verify'; then
  echo "BLOCKED: --no-verify is not allowed. Fix the hook issue instead." >&2
  exit 2
fi

exit 0
