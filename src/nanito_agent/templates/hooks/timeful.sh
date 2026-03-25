#!/usr/bin/env bash
# timeful.sh — SessionStart hook that tracks session start time
# and injects elapsed time awareness into Claude's context.

SESSION_FILE="/tmp/nanito-session-start"

if [ "$HOOK_EVENT" = "SessionStart" ] || [ ! -f "$SESSION_FILE" ]; then
    date +%s > "$SESSION_FILE"
    echo "Session started at $(date '+%H:%M'). I will track elapsed time." >&2
    exit 0
fi

START=$(cat "$SESSION_FILE" 2>/dev/null || date +%s)
NOW=$(date +%s)
ELAPSED=$(( (NOW - START) / 60 ))
HOURS=$(( ELAPSED / 60 ))
MINS=$(( ELAPSED % 60 ))

if [ "$ELAPSED" -ge 180 ]; then
    echo "SESSION ALERT: ${HOURS}h${MINS}m elapsed. Consider wrapping up, saving state to Engram, and taking a break." >&2
elif [ "$ELAPSED" -ge 120 ]; then
    echo "SESSION WARNING: ${HOURS}h${MINS}m elapsed. Long session — checkpoint your progress." >&2
elif [ "$ELAPSED" -ge 60 ]; then
    echo "SESSION NOTE: ${HOURS}h${MINS}m elapsed. Current time: $(date '+%H:%M')." >&2
else
    echo "Time: $(date '+%H:%M') (${MINS}m into session)" >&2
fi
