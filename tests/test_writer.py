"""Tests for settings.json patching logic."""

from nanito_agent.writer import _ensure_hook


def test_ensure_hook_creates_new_event():
    hooks = {}
    _ensure_hook(hooks, "PreToolUse", "Bash", ["bash /tmp/test.sh"])
    assert len(hooks["PreToolUse"]) == 1
    assert hooks["PreToolUse"][0]["matcher"] == "Bash"
    assert len(hooks["PreToolUse"][0]["hooks"]) == 1


def test_ensure_hook_appends_to_existing_matcher():
    hooks = {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash /tmp/a.sh"}]}
        ]
    }
    _ensure_hook(hooks, "PreToolUse", "Bash", ["bash /tmp/b.sh"])
    assert len(hooks["PreToolUse"]) == 1
    assert len(hooks["PreToolUse"][0]["hooks"]) == 2


def test_ensure_hook_no_duplicates():
    hooks = {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash /tmp/a.sh"}]}
        ]
    }
    _ensure_hook(hooks, "PreToolUse", "Bash", ["bash /tmp/a.sh"])
    assert len(hooks["PreToolUse"][0]["hooks"]) == 1


def test_ensure_hook_with_timeout():
    hooks = {}
    _ensure_hook(hooks, "SessionStart", "*", ["bash /tmp/start.sh"], timeout=5000)
    entry = hooks["SessionStart"][0]["hooks"][0]
    assert entry["timeout"] == 5000


def test_ensure_hook_different_matchers():
    hooks = {}
    _ensure_hook(hooks, "PreToolUse", "Bash", ["bash /tmp/a.sh"])
    _ensure_hook(hooks, "PreToolUse", "Edit|Write", ["bash /tmp/b.sh"])
    assert len(hooks["PreToolUse"]) == 2
