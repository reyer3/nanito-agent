#!/bin/bash
# Hook: session-end (Stop)
# Auto-saves session summary to Engram when Claude stops.
# Runs async so it doesn't block exit.

PROJECT=$(basename "$(pwd)" 2>/dev/null || echo "unknown")

# Save a lightweight session marker
engram save \
  "session:$PROJECT:$(date +%Y%m%d-%H%M)" \
  "Session ended in $PROJECT at $(date '+%Y-%m-%d %H:%M'). Check git log for details of work done." \
  --project "$PROJECT" \
  --type "session" 2>/dev/null

exit 0
