"""Tests for plugin structure — skills, commands, agents are discoverable."""

import json
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent / "plugin"


def test_plugin_json_valid():
    """plugin.json is valid JSON with required fields."""
    pj = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    assert data["name"] == "nanito-agent"
    assert "agents" in data
    assert "commands" in data
    assert "skills" in data


def test_plugin_agents_exist():
    """All referenced agents exist."""
    pj = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    for agent_path in data["agents"]:
        assert (PLUGIN_DIR / agent_path).exists(), f"Missing: {agent_path}"


def test_plugin_skills_dirs_exist():
    """Skill directories contain SKILL.md files."""
    skills_dir = PLUGIN_DIR / "skills"
    skill_files = list(skills_dir.rglob("SKILL.md"))
    assert len(skill_files) >= 3  # nanito-core, memory-protocol, playbook-runner


def test_playbook_runner_skill_exists():
    """Playbook runner skill is present."""
    skill = PLUGIN_DIR / "skills" / "playbook-runner" / "SKILL.md"
    assert skill.exists()
    content = skill.read_text()
    assert "build-saas" in content
    assert "build-api" in content
    assert "build-dashboard" in content


def test_nanito_run_command_exists():
    """nanito-run command is present."""
    cmd = PLUGIN_DIR / "commands" / "nanito-run.md"
    assert cmd.exists()
    content = cmd.read_text()
    assert "nanito-run" in content


def test_commands_dir_has_files():
    """Commands directory has .md files."""
    cmds = list((PLUGIN_DIR / "commands").glob("*.md"))
    assert len(cmds) >= 2  # nanito-setup + nanito-run
