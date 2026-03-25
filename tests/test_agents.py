"""Tests for agent registry — discovery, loading, and validation."""

from pathlib import Path

import pytest

from nanito_agent.agents import (
    AgentDef,
    discover_agents,
    load_agent,
    validate_playbook_agents,
)


AGENT_WITH_FRONTMATTER = """\
---
name: test-agent
description: A test agent
model: opus
tools: ["Read", "Write"]
worktree: true
---

You are a test agent. Do test things.
"""

AGENT_NO_FRONTMATTER = """\
You are a simple agent with no frontmatter.

Just do your job.
"""


def test_load_agent_with_frontmatter(tmp_path):
    """Load agent with YAML frontmatter."""
    f = tmp_path / "test-agent.md"
    f.write_text(AGENT_WITH_FRONTMATTER)
    agent = load_agent(f)
    assert agent.name == "test-agent"
    assert agent.description == "A test agent"
    assert agent.model == "opus"
    assert "Read" in agent.tools
    assert agent.worktree is True
    assert "test agent" in agent.prompt


def test_load_agent_no_frontmatter(tmp_path):
    """Load agent without frontmatter uses filename as name."""
    f = tmp_path / "simple.md"
    f.write_text(AGENT_NO_FRONTMATTER)
    agent = load_agent(f)
    assert agent.name == "simple"
    assert agent.model == "sonnet"  # default
    assert "simple agent" in agent.prompt


def test_discover_builtin_agents():
    """Discover builtin agents from package directory."""
    agents = discover_agents()
    assert len(agents) >= 6
    assert "architect" in agents
    assert "implementer" in agents
    assert "api-designer" in agents
    assert "frontend-builder" in agents
    assert "tester" in agents
    assert "reviewer" in agents


def test_discover_with_extra_dirs(tmp_path):
    """Extra directories override builtins."""
    f = tmp_path / "custom-agent.md"
    f.write_text(AGENT_WITH_FRONTMATTER.replace("test-agent", "custom-agent"))
    agents = discover_agents(extra_dirs=[tmp_path])
    assert "custom-agent" in agents


def test_discover_extra_overrides_builtin(tmp_path):
    """Project agent overrides builtin with same name."""
    f = tmp_path / "architect.md"
    f.write_text("---\nname: architect\ndescription: custom\n---\nCustom.")
    agents = discover_agents(extra_dirs=[tmp_path])
    assert agents["architect"].description == "custom"


def test_discover_project_agents_auto(tmp_path):
    """Auto-detect agents/ dir in work_dir."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    f = agents_dir / "project-agent.md"
    f.write_text("---\nname: project-agent\ndescription: local\n---\nDo stuff.")
    agents = discover_agents(work_dir=tmp_path)
    assert "project-agent" in agents


def test_project_agents_override_builtins(tmp_path):
    """Project agents/ dir overrides builtins with same name."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    f = agents_dir / "architect.md"
    f.write_text("---\nname: architect\ndescription: custom arch\n---\nCustom.")
    agents = discover_agents(work_dir=tmp_path)
    assert agents["architect"].description == "custom arch"


def test_no_project_agents_dir(tmp_path):
    """Works fine when no agents/ dir exists in work_dir."""
    agents = discover_agents(work_dir=tmp_path)
    assert "architect" in agents  # still has builtins


def test_validate_all_present():
    """No missing agents when all are available."""
    agents = discover_agents()
    missing = validate_playbook_agents(
        {"architect", "implementer"}, agents
    )
    assert missing == []


def test_validate_missing():
    """Report missing agents."""
    agents = discover_agents()
    missing = validate_playbook_agents(
        {"architect", "unicorn-agent", "magic-builder"}, agents
    )
    assert "magic-builder" in missing
    assert "unicorn-agent" in missing
    assert "architect" not in missing


def test_agent_is_worktree_capable():
    """is_worktree_capable property works."""
    agent = AgentDef(name="t", description="", worktree=True)
    assert agent.is_worktree_capable is True
    agent2 = AgentDef(name="t2", description="", worktree=False)
    assert agent2.is_worktree_capable is False
