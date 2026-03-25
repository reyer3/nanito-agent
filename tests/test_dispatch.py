"""Tests for agent dispatcher — execution and result handling."""

from pathlib import Path
from unittest.mock import patch

from nanito_agent.dispatch import (
    AgentResult,
    DispatchResult,
    claude_available,
    run_agent,
    run_phase,
)
from nanito_agent.executor import AgentCommand, PhaseCommands


def _cmd(name: str = "test", worktree: bool = False) -> AgentCommand:
    return AgentCommand(
        agent_name=name,
        prompt="Do something",
        model="sonnet",
        worktree=worktree,
    )


def test_agent_result_success():
    r = AgentResult("arch", 1, 0, "done", "")
    assert r.success is True


def test_agent_result_failure():
    r = AgentResult("arch", 1, 1, "", "error")
    assert r.success is False


def test_dispatch_result_summary():
    dr = DispatchResult(
        playbook_name="test",
        phase_results=[
            [AgentResult("a", 1, 0), AgentResult("b", 1, 0)],
            [AgentResult("c", 2, 1, stderr="failed")],
        ],
    )
    assert dr.total_agents == 3
    assert dr.succeeded == 2
    assert dr.failed == 1
    assert dr.all_passed is False
    summary = dr.summary()
    assert "test" in summary
    assert "FAIL" in summary


def test_dispatch_result_all_passed():
    dr = DispatchResult(
        playbook_name="test",
        phase_results=[
            [AgentResult("a", 1, 0)],
        ],
    )
    assert dr.all_passed is True


def test_run_agent_with_echo():
    """Run agent with a mocked claude that just echoes."""
    cmd = _cmd("test-echo")
    with patch(
        "nanito_agent.dispatch.subprocess.run",
    ) as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "output"
        mock_run.return_value.stderr = ""
        result = run_agent(cmd, 1, Path("/tmp"))
        assert result.success is True
        assert result.agent_name == "test-echo"


def test_run_agent_timeout():
    """Timeout produces failure result."""
    import subprocess

    cmd = _cmd("slow")
    with patch(
        "nanito_agent.dispatch.subprocess.run",
        side_effect=subprocess.TimeoutExpired("claude", 600),
    ):
        result = run_agent(cmd, 1, Path("/tmp"))
        assert result.success is False
        assert "TIMEOUT" in result.stderr


def test_run_agent_not_found():
    """Missing claude CLI produces failure result."""
    cmd = _cmd("missing")
    with patch(
        "nanito_agent.dispatch.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        result = run_agent(cmd, 1, Path("/tmp"))
        assert result.success is False
        assert "not found" in result.stderr


def test_run_phase_sequential():
    """Sequential phase runs commands in order."""
    phase = PhaseCommands(
        phase_number=1,
        parallel=False,
        commands=[_cmd("a"), _cmd("b")],
    )
    with patch("nanito_agent.dispatch.run_agent") as mock:
        mock.return_value = AgentResult("x", 1, 0)
        results = run_phase(phase, Path("/tmp"))
        assert len(results) == 2


def test_run_phase_sequential_stops_on_failure():
    """Sequential phase stops at first failure."""
    phase = PhaseCommands(
        phase_number=1,
        parallel=False,
        commands=[_cmd("a"), _cmd("b"), _cmd("c")],
    )
    with patch("nanito_agent.dispatch.run_agent") as mock:
        mock.side_effect = [
            AgentResult("a", 1, 0),
            AgentResult("b", 1, 1),  # fails
            AgentResult("c", 1, 0),  # should not run
        ]
        results = run_phase(phase, Path("/tmp"))
        assert len(results) == 2  # stopped after b


def test_run_phase_parallel():
    """Parallel phase runs all commands concurrently."""
    phase = PhaseCommands(
        phase_number=1,
        parallel=True,
        commands=[_cmd("a"), _cmd("b"), _cmd("c")],
    )
    with patch("nanito_agent.dispatch.run_agent") as mock:
        mock.return_value = AgentResult("x", 1, 0)
        results = run_phase(phase, Path("/tmp"))
        assert len(results) == 3


def test_claude_available():
    """claude_available checks for claude binary."""
    with patch("nanito_agent.dispatch.shutil.which", return_value=None):
        assert claude_available() is False
    with patch(
        "nanito_agent.dispatch.shutil.which",
        return_value="/usr/bin/claude",
    ):
        assert claude_available() is True
