#!/usr/bin/env python3
"""Voice notification hook — announces session events via TTS and messaging.

Standalone script using only stdlib + nanito_agent.voice (if available).
Falls back to plain stderr output if voice module is not importable.
Registered for: SessionStart, Stop.
"""

import json
import sys
from pathlib import Path


def _try_voice_announce(message: str) -> bool:
    """Attempt to announce via NanitoVoice. Returns False if unavailable."""
    try:
        from nanito_agent.voice import NanitoVoice

        voice = NanitoVoice.auto_detect()
        voice.announce(message)
        return True
    except ImportError:
        return False


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, KeyboardInterrupt):
        return

    event_type = data.get("hook_event_name", "unknown")
    cwd = data.get("cwd", "")
    project = Path(cwd).name if cwd else "unknown"
    session_id = data.get("session_id", "unknown")[:8]

    if event_type == "SessionStart":
        message = f"Nanito session started in project {project}"
    elif event_type == "Stop":
        # Count tool calls from session data if available
        tool_calls = data.get("tool_call_count")
        if tool_calls is not None:
            message = f"Session ended. {tool_calls} tool calls."
        else:
            message = f"Session ended in {project}."
    else:
        return

    if not _try_voice_announce(message):
        # Fallback: plain stderr
        print(f"[nanito] {message}", file=sys.stderr)


if __name__ == "__main__":
    main()
