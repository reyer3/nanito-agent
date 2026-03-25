"""Playbook executor — generates Claude Code agent dispatch commands."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from nanito_agent.agents import AgentDef
from nanito_agent.runner import ExecutionPlan, Phase, ResolvedStep


@dataclass
class AgentCommand:
    """A concrete command to spawn a Claude Code agent."""

    agent_name: str
    prompt: str
    model: str = "sonnet"
    worktree: bool = False
    output_file: str | None = None

    def to_claude_args(self) -> list[str]:
        """Generate claude CLI arguments for this agent."""
        args = [
            "claude",
            "--print",
            "--model", self.model,
            "--output-format", "stream-json",
        ]
        if self.worktree:
            args.append("--worktree")
        args.append("--prompt")
        args.append(self.prompt)
        return args

    def to_agent_tool_call(self) -> dict:
        """Generate an Agent tool call spec for in-session dispatch."""
        return {
            "description": f"[{self.agent_name}] agent",
            "prompt": self.prompt,
            "model": self.model,
            "subagent_type": "general-purpose",
            "isolation": "worktree" if self.worktree else None,
        }


@dataclass
class PhaseCommands:
    """Commands for a single execution phase."""

    phase_number: int
    parallel: bool
    commands: list[AgentCommand]


@dataclass
class ExecutionScript:
    """Complete execution script for a playbook."""

    playbook_name: str
    phases: list[PhaseCommands]
    work_dir: Path = field(default_factory=Path.cwd)

    @property
    def total_agents(self) -> int:
        return sum(len(p.commands) for p in self.phases)

    def to_summary(self) -> str:
        """Human-readable execution summary."""
        lines = [f"Execution: {self.playbook_name}", ""]
        for phase in self.phases:
            mode = "PARALLEL" if phase.parallel else "SEQUENTIAL"
            lines.append(f"Phase {phase.phase_number} [{mode}]:")
            for cmd in phase.commands:
                wt = " (worktree)" if cmd.worktree else ""
                out = f" -> {cmd.output_file}" if cmd.output_file else ""
                lines.append(
                    f"  {cmd.agent_name} [{cmd.model}]{wt}{out}"
                )
            lines.append("")
        lines.append(f"Total agents to spawn: {self.total_agents}")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize as JSON for programmatic consumption."""
        return json.dumps(
            {
                "playbook": self.playbook_name,
                "work_dir": str(self.work_dir),
                "phases": [
                    {
                        "phase": p.phase_number,
                        "parallel": p.parallel,
                        "commands": [
                            {
                                "agent": c.agent_name,
                                "model": c.model,
                                "worktree": c.worktree,
                                "output": c.output_file,
                                "prompt_length": len(c.prompt),
                            }
                            for c in p.commands
                        ],
                    }
                    for p in self.phases
                ],
                "total_agents": self.total_agents,
            },
            indent=2,
        )


def build_agent_prompt(
    step: ResolvedStep,
    agent_def: AgentDef,
    work_dir: Path,
    prior_outputs: dict[str, str] | None = None,
    engram_context: str | None = None,
    mcp_section: str | None = None,
) -> str:
    """Build the full prompt for an agent combining its definition and task."""
    parts = [
        f"# Agent: {agent_def.name}",
        f"## Role\n{agent_def.prompt}",
        f"## Task\n{step.task}",
        f"## Working Directory\n{work_dir}",
    ]
    if step.output:
        parts.append(f"## Expected Output\nWrite results to: {step.output}")
    if prior_outputs:
        ctx_lines = ["## Context from Prior Phases"]
        for filename, desc in prior_outputs.items():
            ctx_lines.append(f"- **{filename}**: {desc}")
        ctx_lines.append(
            "\nRead these files for context before starting your task."
        )
        parts.append("\n".join(ctx_lines))
    if engram_context:
        parts.append(
            "## Memory (from prior sessions)\n"
            "The following learnings were recalled from persistent memory. "
            "Use them to avoid repeating past mistakes and to build on "
            "what worked before.\n\n"
            f"{engram_context}"
        )
    if mcp_section:
        parts.append(mcp_section)
    return "\n\n".join(parts)


def compile_execution(
    plan: ExecutionPlan,
    agents: dict[str, AgentDef],
    work_dir: Path | None = None,
    engram_context: str | None = None,
    mcp_section: str | None = None,
) -> ExecutionScript:
    """Compile an execution plan into concrete agent commands."""
    wdir = work_dir or Path.cwd()
    phase_commands: list[PhaseCommands] = []

    # Track outputs from completed phases for context chaining
    accumulated_outputs: dict[str, str] = {}

    for phase in plan.phases:
        commands: list[AgentCommand] = []
        for step in phase.steps:
            agent_def = agents[step.agent]
            prompt = build_agent_prompt(
                step, agent_def, wdir,
                prior_outputs=accumulated_outputs or None,
                engram_context=engram_context,
                mcp_section=mcp_section,
            )
            cmd = AgentCommand(
                agent_name=step.agent,
                prompt=prompt,
                model=agent_def.model,
                worktree=step.worktree or agent_def.worktree,
                output_file=step.output,
            )
            commands.append(cmd)

        # Register outputs from this phase for next phases
        for step in phase.steps:
            if step.output:
                accumulated_outputs[step.output] = (
                    f"Produced by {step.agent}"
                )

        phase_commands.append(PhaseCommands(
            phase_number=phase.phase_number,
            parallel=phase.parallel,
            commands=commands,
        ))

    return ExecutionScript(
        playbook_name=plan.playbook_name,
        phases=phase_commands,
        work_dir=wdir,
    )
