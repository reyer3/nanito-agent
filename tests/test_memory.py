"""Tests for memory integration with Engram."""

from pathlib import Path
from unittest.mock import patch

from nanito_agent.memory import (
    PlaybookMemory,
    engram_available,
    engram_save,
    engram_search,
)


def test_engram_available_when_missing():
    """Returns False when engram is not installed."""
    with patch("nanito_agent.memory.shutil.which", return_value=None):
        assert engram_available() is False


def test_engram_available_when_present():
    """Returns True when engram is installed."""
    with patch("nanito_agent.memory.shutil.which", return_value="/usr/bin/engram"):
        assert engram_available() is True


def test_engram_search_returns_none_when_unavailable():
    """Search returns None when engram not installed."""
    with patch("nanito_agent.memory.engram_available", return_value=False):
        assert engram_search("test") is None


def test_engram_save_returns_false_when_unavailable():
    """Save returns False when engram not installed."""
    with patch("nanito_agent.memory.engram_available", return_value=False):
        assert engram_save("topic", "content") is False


def test_playbook_memory_load_no_engram():
    """PlaybookMemory.load works without engram (no learnings)."""
    with patch("nanito_agent.memory.engram_available", return_value=False):
        mem = PlaybookMemory.load("build-saas", Path("/tmp/project"))
        assert mem.playbook_name == "build-saas"
        assert mem.project == "project"
        assert mem.prior_learnings is None


def test_playbook_memory_load_with_engram(tmp_path):
    """PlaybookMemory.load retrieves prior learnings."""
    with (
        patch("nanito_agent.memory.engram_available", return_value=True),
        patch(
            "nanito_agent.memory.engram_search",
            side_effect=lambda q, **kw: "Found: auth was a bottleneck"
            if "playbook" in q else None,
        ),
    ):
        mem = PlaybookMemory.load("build-api", tmp_path)
        assert mem.prior_learnings is not None
        assert "auth was a bottleneck" in mem.prior_learnings


def test_playbook_memory_save_phase_result():
    """save_phase_result only saves failures."""
    with patch("nanito_agent.memory.engram_save") as mock_save:
        mem = PlaybookMemory(
            playbook_name="test", project="proj",
        )
        # Success — should NOT call engram_save
        mem.save_phase_result(1, "architect", "done", "ok")
        mock_save.assert_not_called()

        # Failure — SHOULD call engram_save
        mem.save_phase_result(2, "tester", "failed", "3 tests broke")
        mock_save.assert_called_once()


def test_playbook_memory_save_completion():
    """save_completion records to engram."""
    with patch("nanito_agent.memory.engram_save") as mock_save:
        mem = PlaybookMemory(
            playbook_name="build-saas", project="crm",
        )
        mem.save_completion(5, 5, 0, "All phases passed")
        mock_save.assert_called_once()
        call_content = mock_save.call_args.kwargs.get("content", "")
        assert "completed" in call_content
