"""Agent dispatcher — spawns Claude Code instances from execution scripts."""

from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from nanito_agent.executor import AgentCommand, ExecutionScript, PhaseCommands


@dataclass
class AgentResult:
    """Result of a single agent execution."""

    agent_name: str
    phase: int
    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class DispatchResult:
    """Result of executing a full playbook."""

    playbook_name: str
    phase_results: list[list[AgentResult]] = field(default_factory=list)

    @property
    def total_agents(self) -> int:
        return sum(len(pr) for pr in self.phase_results)

    @property
    def succeeded(self) -> int:
        return sum(
            1 for pr in self.phase_results
            for r in pr if r.success
        )

    @property
    def failed(self) -> int:
        return self.total_agents - self.succeeded

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        lines = [
            f"Dispatch: {self.playbook_name}",
            f"Agents: {self.succeeded}/{self.total_agents} succeeded",
        ]
        for i, phase in enumerate(self.phase_results):
            for r in phase:
                status = "OK" if r.success else f"FAIL (exit {r.exit_code})"
                lines.append(
                    f"  Phase {r.phase}: [{r.agent_name}] {status}"
                )
        return "\n".join(lines)


def claude_available() -> bool:
    """Check if claude CLI is available."""
    return shutil.which("claude") is not None


def run_agent(cmd: AgentCommand, phase_num: int, work_dir: Path) -> AgentResult:
    """Execute a single agent via Claude Code CLI."""
    args = cmd.to_claude_args()
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=str(work_dir),
            timeout=600,
        )
        return AgentResult(
            agent_name=cmd.agent_name,
            phase=phase_num,
            exit_code=result.returncode,
            stdout=result.stdout[-2000:] if result.stdout else "",
            stderr=result.stderr[-1000:] if result.stderr else "",
        )
    except subprocess.TimeoutExpired:
        return AgentResult(
            agent_name=cmd.agent_name,
            phase=phase_num,
            exit_code=-1,
            stderr="TIMEOUT: agent exceeded 10 minute limit",
        )
    except FileNotFoundError:
        return AgentResult(
            agent_name=cmd.agent_name,
            phase=phase_num,
            exit_code=-2,
            stderr="Claude CLI not found. Install: https://claude.ai/download",
        )


def run_phase(
    phase: PhaseCommands,
    work_dir: Path,
) -> list[AgentResult]:
    """Execute a single phase — sequential or parallel."""
    if phase.parallel and len(phase.commands) > 1:
        return _run_parallel(phase, work_dir)
    return _run_sequential(phase, work_dir)


def _run_sequential(phase: PhaseCommands, work_dir: Path) -> list[AgentResult]:
    results = []
    for cmd in phase.commands:
        result = run_agent(cmd, phase.phase_number, work_dir)
        results.append(result)
        if not result.success:
            break  # stop phase on first failure
    return results


def _run_parallel(phase: PhaseCommands, work_dir: Path) -> list[AgentResult]:
    results: list[AgentResult] = []
    with ThreadPoolExecutor(max_workers=len(phase.commands)) as pool:
        futures = {
            pool.submit(run_agent, cmd, phase.phase_number, work_dir): cmd
            for cmd in phase.commands
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results


def dispatch(
    script: ExecutionScript,
    stop_on_failure: bool = True,
) -> DispatchResult:
    """Execute a full playbook by dispatching agents phase by phase."""
    result = DispatchResult(playbook_name=script.playbook_name)

    for phase in script.phases:
        phase_results = run_phase(phase, script.work_dir)
        result.phase_results.append(phase_results)

        if stop_on_failure and any(not r.success for r in phase_results):
            break

    return result
