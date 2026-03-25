"""Tests for CLI run and agents commands."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nanito_agent.cli import _agents, _parse_vars, _resolve_playbook, _run

PLAYBOOKS_DIR = Path(__file__).parent.parent / "playbooks"


def test_parse_vars_basic():
    """Parse --var key=val pairs."""
    result = _parse_vars(["--var", "idea=CRM", "--var", "stack=python"])
    assert result == {"idea": "CRM", "stack": "python"}


def test_parse_vars_empty():
    """No vars returns empty dict."""
    assert _parse_vars([]) == {}


def test_parse_vars_ignores_other_args():
    """Non --var args are ignored."""
    result = _parse_vars(["--other", "foo", "--var", "x=1"])
    assert result == {"x": "1"}


def test_resolve_playbook_direct_path(tmp_path):
    """Resolve a direct file path."""
    f = tmp_path / "test.yaml"
    f.write_text("name: test")
    result = _resolve_playbook(str(f))
    assert result == f


def test_resolve_playbook_not_found(capsys):
    """Exit on nonexistent playbook."""
    with pytest.raises(SystemExit):
        _resolve_playbook("/nonexistent/playbook.yaml")


def test_run_shows_plan(tmp_path, capsys):
    """run shows execution plan."""
    playbook = tmp_path / "test.yaml"
    playbook.write_text(
        "name: test\n"
        "description: Test playbook\n"
        "steps:\n"
        "  - agent: architect\n"
        "    task: Design something\n"
    )
    with patch("sys.argv", ["nanito-agent", "run", str(playbook)]):
        _run([str(playbook)])
    output = capsys.readouterr().out
    assert "test" in output
    assert "architect" in output


def test_run_with_variables(tmp_path, capsys):
    """Variables are resolved in the plan."""
    playbook = tmp_path / "test.yaml"
    playbook.write_text(
        "name: test\n"
        "description: Test\n"
        "steps:\n"
        "  - agent: architect\n"
        "    task: 'Build {{idea}}'\n"
    )
    _run([str(playbook), "--var", "idea=CRM"])
    output = capsys.readouterr().out
    assert "CRM" in output


def test_run_missing_agent(tmp_path, capsys):
    """Error when playbook references unknown agent."""
    playbook = tmp_path / "test.yaml"
    playbook.write_text(
        "name: test\n"
        "description: Test\n"
        "steps:\n"
        "  - agent: unicorn-agent\n"
        "    task: Do magic\n"
    )
    with pytest.raises(SystemExit):
        _run([str(playbook)])


def test_run_no_args(capsys):
    """Error when run called without playbook."""
    with pytest.raises(SystemExit):
        _run([])


def test_agents_list(capsys):
    """agents command lists available agents."""
    _agents()
    output = capsys.readouterr().out
    assert "architect" in output
    assert "implementer" in output


def test_run_json_output(tmp_path, capsys):
    """--json flag outputs JSON execution script."""
    playbook = tmp_path / "test.yaml"
    playbook.write_text(
        "name: test\n"
        "description: Test\n"
        "steps:\n"
        "  - agent: architect\n"
        "    task: Design it\n"
    )
    _run([str(playbook), "--json"])
    output = capsys.readouterr().out
    import json
    data = json.loads(output)
    assert data["playbook"] == "test"
    assert data["total_agents"] == 1


def test_run_shows_execution_summary(tmp_path, capsys):
    """Default output includes execution summary."""
    playbook = tmp_path / "test.yaml"
    playbook.write_text(
        "name: test\n"
        "description: Test\n"
        "steps:\n"
        "  - agent: architect\n"
        "    task: Design it\n"
    )
    _run([str(playbook)])
    output = capsys.readouterr().out
    assert "SEQUENTIAL" in output or "Total agents" in output


def test_builtin_playbooks_exist():
    """All builtin playbooks exist."""
    assert (PLAYBOOKS_DIR / "build-saas.yaml").exists()
    assert (PLAYBOOKS_DIR / "build-api.yaml").exists()
    assert (PLAYBOOKS_DIR / "build-dashboard.yaml").exists()
