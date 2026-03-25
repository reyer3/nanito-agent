#!/bin/bash
# Hook: git-push-guard
# Warns before git push operations (especially to main/master)

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git\s+push'; then
  if echo "$COMMAND" | grep -qE '(--force|-f)\b'; then
    echo "BLOCKED: Force push detected. This is destructive and not allowed." >&2
    exit 2
  fi
  if echo "$COMMAND" | grep -qE '\b(main|master)\b'; then
    echo "WARNING: Pushing directly to main/master. Confirm this is intentional." >&2
  fi
fi

exit 0
