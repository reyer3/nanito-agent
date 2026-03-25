#!/bin/bash
# Hook: test-nudge (PostToolUse on Edit/Write)
# After editing source files, check if corresponding test file exists.
# Gentle reminder, not a blocker.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check source files (not tests, configs, docs, etc.)
if echo "$FILE_PATH" | grep -qE '(^|/)src/.*\.py$'; then
  # Derive expected test path
  TEST_FILE=$(echo "$FILE_PATH" | sed 's|/src/|/tests/test_|' | sed 's|/\([^/]*\)\.py$|/test_\1.py|')
  # Simpler fallback: just check tests/test_<filename>.py
  BASENAME=$(basename "$FILE_PATH" .py)
  DIRNAME=$(dirname "$FILE_PATH")
  PROJECT_ROOT=$(echo "$DIRNAME" | sed 's|/src.*||')

  if [ ! -f "$TEST_FILE" ]; then
    SIMPLE_TEST="$PROJECT_ROOT/tests/test_${BASENAME}.py"
    if [ ! -f "$SIMPLE_TEST" ]; then
      echo "NOTE: No test file found for $FILE_PATH. Consider writing tests." >&2
    fi
  fi
fi

exit 0
