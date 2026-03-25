#!/bin/bash
# Hook: session-start (SessionStart)
# Auto-loads recent Engram context at session start.
# Runs async so it doesn't block startup.

# Get project name from current directory
PROJECT=$(basename "$(pwd)" 2>/dev/null || echo "unknown")

# Load recent context from Engram
CONTEXT=$(engram context "$PROJECT" 2>/dev/null)

if [ -n "$CONTEXT" ] && [ "$CONTEXT" != "No recent context found." ]; then
  echo "ENGRAM SESSION CONTEXT ($PROJECT):" >&2
  echo "$CONTEXT" | head -30 >&2
  echo "---" >&2
  echo "Use mem_search for deeper lookups. Use mem_session_start to begin tracking." >&2
fi

exit 0
