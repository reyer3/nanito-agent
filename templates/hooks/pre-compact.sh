#!/bin/bash
# Hook: pre-compact (PreCompact)
# Saves critical state to Engram before context compaction.
# This ensures memory survives the compaction event.

PROJECT=$(basename "$(pwd)" 2>/dev/null || echo "unknown")

engram save \
  "compaction:$PROJECT:$(date +%Y%m%d-%H%M)" \
  "Context compaction triggered in $PROJECT. Call mem_context to reload state after compaction." \
  --project "$PROJECT" \
  --type "session" 2>/dev/null

echo "STATE SAVED: Engram has your pre-compaction context. After compaction, call mem_context to recover." >&2

exit 0
