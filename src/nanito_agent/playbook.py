"""Playbook schema and parser — YAML-driven agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class VerifySignal:
    """A single verification signal in a composite metric."""

    name: str
    command: str
    weight: float = 1.0
    direction: str = "higher"  # "higher" or "lower"


@dataclass
class Step:
    """A single agent step in a playbook."""

    agent: str
    task: str
    output: str | None = None
    worktree: bool = False
    inputs: dict[str, str] = field(default_factory=dict)


@dataclass
class ParallelGroup:
    """A group of steps that run concurrently."""

    steps: list[Step]


@dataclass
class Playbook:
    """A complete playbook definition."""

    name: str
    description: str
    inputs: list[dict[str, str]] = field(default_factory=list)
    steps: list[Step | ParallelGroup] = field(default_factory=list)
    verify: list[VerifySignal] = field(default_factory=list)

    @property
    def agent_names(self) -> set[str]:
        """Return all unique agent names used in this playbook."""
        names: set[str] = set()
        for step in self.steps:
            if isinstance(step, ParallelGroup):
                for s in step.steps:
                    names.add(s.agent)
            else:
                names.add(step.agent)
        return names

    @property
    def total_steps(self) -> int:
        """Total number of individual steps (flattened)."""
        count = 0
        for step in self.steps:
            if isinstance(step, ParallelGroup):
                count += len(step.steps)
            else:
                count += 1
        return count


def _parse_step(data: dict[str, Any]) -> Step:
    """Parse a single step from YAML dict."""
    if "agent" not in data or "task" not in data:
        msg = f"Step must have 'agent' and 'task' fields, got: {list(data.keys())}"
        raise ValueError(msg)
    return Step(
        agent=data["agent"],
        task=data["task"],
        output=data.get("output"),
        worktree=data.get("worktree", False),
        inputs=data.get("inputs", {}),
    )


def parse_playbook(source: str | Path) -> Playbook:
    """Parse a playbook from a YAML file path or YAML string."""
    is_yaml_string = (
        isinstance(source, str)
        and ("\n" in source.strip() or source.strip().startswith("name:"))
    )
    if isinstance(source, Path) or (isinstance(source, str) and not is_yaml_string):
        path = Path(source)
        if not path.exists():
            msg = f"Playbook file not found: {path}"
            raise FileNotFoundError(msg)
        raw = path.read_text()
    else:
        raw = source

    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = "Playbook must be a YAML mapping"
        raise ValueError(msg)

    if "name" not in data:
        msg = "Playbook must have a 'name' field"
        raise ValueError(msg)

    steps: list[Step | ParallelGroup] = []
    for raw_step in data.get("steps", []):
        if "parallel" in raw_step:
            parallel_steps = [_parse_step(s) for s in raw_step["parallel"]]
            steps.append(ParallelGroup(steps=parallel_steps))
        else:
            steps.append(_parse_step(raw_step))

    verify: list[VerifySignal] = []
    for raw_signal in data.get("verify", []):
        verify.append(VerifySignal(
            name=raw_signal["name"],
            command=raw_signal["command"],
            weight=raw_signal.get("weight", 1.0),
            direction=raw_signal.get("direction", "higher"),
        ))

    return Playbook(
        name=data["name"],
        description=data.get("description", ""),
        inputs=data.get("inputs", []),
        steps=steps,
        verify=verify,
    )
