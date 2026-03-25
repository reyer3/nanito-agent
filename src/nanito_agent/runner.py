"""Playbook runner — orchestrates agent execution from playbook definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from nanito_agent.playbook import ParallelGroup, Playbook, Step, parse_playbook


@dataclass
class StepResult:
    """Result of executing a single agent step."""

    agent: str
    task: str
    status: str  # "pending", "running", "done", "failed", "skipped"
    output_file: str | None = None
    error: str | None = None


@dataclass
class RunContext:
    """Shared context for a playbook run — holds variables and outputs."""

    variables: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    work_dir: Path = field(default_factory=Path.cwd)
    results: list[StepResult] = field(default_factory=list)

    def resolve(self, template: str) -> str:
        """Resolve {{variable}} placeholders in a template string."""
        merged = {**self.variables, **self.outputs}

        def _replace(match: re.Match) -> str:
            key = match.group(1).strip()
            return merged.get(key, match.group(0))

        return re.sub(r"\{\{(.+?)\}\}", _replace, template)


@dataclass
class ExecutionPlan:
    """A resolved, ready-to-execute plan from a playbook."""

    playbook_name: str
    description: str
    phases: list[Phase]
    context: RunContext


@dataclass
class Phase:
    """A single execution phase — sequential or parallel."""

    phase_number: int
    parallel: bool
    steps: list[ResolvedStep]


@dataclass
class ResolvedStep:
    """A step with all templates resolved to concrete values."""

    agent: str
    task: str
    output: str | None
    worktree: bool


def plan_execution(
    playbook: Playbook | str | Path,
    variables: dict[str, str] | None = None,
) -> ExecutionPlan:
    """Create an execution plan from a playbook without running anything.

    Resolves all template variables and organizes steps into phases.
    """
    if not isinstance(playbook, Playbook):
        playbook = parse_playbook(playbook)

    ctx = RunContext(
        variables=variables or {},
        work_dir=Path.cwd(),
    )

    phases: list[Phase] = []
    phase_num = 0

    for step in playbook.steps:
        phase_num += 1
        if isinstance(step, ParallelGroup):
            resolved = [
                ResolvedStep(
                    agent=s.agent,
                    task=ctx.resolve(s.task),
                    output=s.output,
                    worktree=s.worktree,
                )
                for s in step.steps
            ]
            phases.append(Phase(
                phase_number=phase_num,
                parallel=True,
                steps=resolved,
            ))
        else:
            resolved_step = ResolvedStep(
                agent=step.agent,
                task=ctx.resolve(step.task),
                output=step.output,
                worktree=step.worktree,
            )
            phases.append(Phase(
                phase_number=phase_num,
                parallel=False,
                steps=[resolved_step],
            ))

    return ExecutionPlan(
        playbook_name=playbook.name,
        description=playbook.description,
        phases=phases,
        context=ctx,
    )


def render_plan(plan: ExecutionPlan) -> str:
    """Render an execution plan as a human-readable summary."""
    lines = [
        f"Playbook: {plan.playbook_name}",
        f"Description: {plan.description}",
        f"Phases: {len(plan.phases)}",
        "",
    ]

    total_steps = 0
    for phase in plan.phases:
        mode = "parallel" if phase.parallel else "sequential"
        lines.append(f"Phase {phase.phase_number} ({mode}):")
        for step in phase.steps:
            total_steps += 1
            worktree_flag = " [worktree]" if step.worktree else ""
            output_flag = f" -> {step.output}" if step.output else ""
            lines.append(
                f"  [{step.agent}]{worktree_flag} {step.task}{output_flag}"
            )
        lines.append("")

    lines.append(f"Total steps: {total_steps}")
    agents = {s.agent for p in plan.phases for s in p.steps}
    lines.append(f"Agents needed: {', '.join(sorted(agents))}")

    return "\n".join(lines)
