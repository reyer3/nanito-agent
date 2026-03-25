"""Tests for the session monitor module."""

import sqlite3
from unittest.mock import patch

import pytest

from nanito_agent.monitor import list_sessions, show_session, show_stats

CWD = "/home/user/myproject"
INSERT_SQL = (
    "INSERT INTO events "
    "(session_id, event_type, tool_name, agent_id,"
    " project, cwd, model, timestamp, payload) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _event(
    sid, etype, tool=None, agent=None,
    project="myproject", cwd=CWD, model=None,
    ts="2026-03-24T10:00:00", payload="{}",
):
    return (sid, etype, tool, agent, project, cwd, model, ts, payload)


SEED_EVENTS = [
    _event("s1", "SessionStart", model="claude-sonnet-4-6",
           ts="2026-03-24T10:00:00",
           payload='{"source":"startup"}'),
    _event("s1", "PreToolUse", tool="Read",
           ts="2026-03-24T10:00:05",
           payload='{"tool_name":"Read","input_keys":["file_path"]}'),
    _event("s1", "PreToolUse", tool="Edit",
           ts="2026-03-24T10:00:10",
           payload='{"tool_name":"Edit","input_keys":["file_path"]}'),
    _event("s1", "PreToolUse", tool="Bash",
           ts="2026-03-24T10:00:15",
           payload='{"tool_name":"Bash","input_keys":["command"]}'),
    _event("s1", "PreToolUse", tool="Agent", agent="agent-abc",
           ts="2026-03-24T10:00:20",
           payload='{"tool_name":"Agent","input_keys":["prompt"]}'),
    _event("s1", "Stop", ts="2026-03-24T10:05:00",
           payload='{"stop_hook_active":true}'),
    _event("s2", "SessionStart", project="other",
           cwd="/home/user/other", model="claude-opus-4-6",
           ts="2026-03-24T11:00:00",
           payload='{"source":"startup"}'),
    _event("s2", "PreToolUse", tool="Grep", project="other",
           cwd="/home/user/other", ts="2026-03-24T11:00:05",
           payload='{"tool_name":"Grep","input_keys":["pattern"]}'),
]


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database with test data."""
    db_path = tmp_path / "nanito-sessions.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            tool_name TEXT, agent_id TEXT,
            project TEXT, cwd TEXT, model TEXT,
            timestamp TEXT NOT NULL, payload TEXT
        );
        CREATE INDEX idx_events_session ON events(session_id);
        CREATE INDEX idx_events_timestamp ON events(timestamp);
        """
    )
    conn.executemany(INSERT_SQL, SEED_EVENTS)
    conn.commit()
    conn.close()

    with patch("nanito_agent.monitor.DB_PATH", db_path):
        yield db_path


def test_list_sessions(temp_db, capsys):
    """list_sessions shows session summaries."""
    list_sessions()
    output = capsys.readouterr().out
    assert "myproject" in output


def test_show_session(temp_db, capsys):
    """show_session displays timeline for a session prefix."""
    show_session("s1")
    output = capsys.readouterr().out
    assert "Read" in output
    assert "Edit" in output
    assert "Bash" in output


def test_show_session_not_found(temp_db, capsys):
    """show_session handles missing session gracefully."""
    show_session("nonexistent")
    output = capsys.readouterr().out
    assert "No events found" in output


def test_show_stats(temp_db, capsys):
    """show_stats displays aggregate statistics."""
    show_stats()
    output = capsys.readouterr().out
    assert "Session Stats" in output


def test_no_database(tmp_path, capsys):
    """Functions handle missing database gracefully."""
    fake_path = tmp_path / "does-not-exist.db"
    with patch("nanito_agent.monitor.DB_PATH", fake_path):
        list_sessions()
    output = capsys.readouterr().out
    assert "No session data" in output
