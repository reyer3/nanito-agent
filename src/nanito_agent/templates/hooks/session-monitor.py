#!/usr/bin/env python3
"""Session monitor hook — logs Claude Code events to SQLite.

Standalone script using only stdlib. No external dependencies.
Registered for: PreToolUse, SessionStart, Stop, PreCompact.
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "nanito-sessions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT,
    agent_id TEXT,
    project TEXT,
    cwd TEXT,
    model TEXT,
    timestamp TEXT NOT NULL,
    payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
"""


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, KeyboardInterrupt):
        return

    session_id = data.get("session_id", "unknown")
    event_type = data.get("hook_event_name", "unknown")
    tool_name = data.get("tool_name")
    agent_id = data.get("agent_id")
    cwd = data.get("cwd", "")
    model = data.get("model")
    project = Path(cwd).name if cwd else None
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Minimal payload — keep DB lean
    if event_type == "PreToolUse":
        tool_input = data.get("tool_input", {})
        payload = json.dumps({
            "tool_name": tool_name,
            "input_keys": list(tool_input.keys()) if isinstance(tool_input, dict) else [],
        })
    else:
        payload = json.dumps({
            k: data.get(k)
            for k in ("source", "model", "permission_mode", "stop_hook_active")
            if data.get(k) is not None
        })

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO events (session_id, event_type, tool_name, agent_id, project, cwd, model, timestamp, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, event_type, tool_name, agent_id, project, cwd, model, timestamp, payload),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
