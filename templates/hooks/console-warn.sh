#!/bin/bash
# Hook: console-warn (PostToolUse)
# Warns about debug statements left in edited code

INPUT=$(cat)
DIFF=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty')

if echo "$DIFF" | grep -qE '(console\.log|console\.debug|print\(|debugger|breakpoint\(\))'; then
  echo "NOTE: Debug statement detected in edit. Remove before committing." >&2
fi

exit 0
