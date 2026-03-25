"""Agent registry — discovers and loads agent definitions for playbook execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

BUILTIN_AGENTS_DIR = Path(__file__).parent / "agents"


@dataclass
class AgentDef:
    """An agent definition loaded from YAML frontmatter + markdown body."""

    name: str
    description: str
    model: str = "sonnet"
    tools: list[str] = field(default_factory=list)
    worktree: bool = False
    prompt: str = ""

    @property
    def is_worktree_capable(self) -> bool:
        return self.worktree


def load_agent(path: Path) -> AgentDef:
    """Load an agent definition from a markdown file with YAML frontmatter."""
    content = path.read_text()

    if not content.startswith("---"):
        return AgentDef(
            name=path.stem,
            description="",
            prompt=content.strip(),
        )

    parts = content.split("---", 2)
    if len(parts) < 3:
        msg = f"Invalid frontmatter in {path}"
        raise ValueError(msg)

    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()

    return AgentDef(
        name=meta.get("name", path.stem),
        description=meta.get("description", ""),
        model=meta.get("model", "sonnet"),
        tools=meta.get("tools", []),
        worktree=meta.get("worktree", False),
        prompt=body,
    )


def discover_agents(
    extra_dirs: list[Path] | None = None,
) -> dict[str, AgentDef]:
    """Discover all available agent definitions.

    Searches builtin agents dir + any extra directories.
    Later definitions override earlier ones (project agents override builtins).
    """
    agents: dict[str, AgentDef] = {}

    dirs = [BUILTIN_AGENTS_DIR]
    if extra_dirs:
        dirs.extend(extra_dirs)

    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            agent = load_agent(f)
            agents[agent.name] = agent

    return agents


def validate_playbook_agents(
    needed: set[str],
    available: dict[str, AgentDef],
) -> list[str]:
    """Check if all agents needed by a playbook are available.

    Returns list of missing agent names (empty = all good).
    """
    return sorted(needed - set(available.keys()))
