"""Memory integration — bridges playbook execution with Engram persistent memory.

Provides hooks for the playbook lifecycle:
- Before execution: recall relevant history
- After each phase: save notable findings
- After completion: save execution summary
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def engram_available() -> bool:
    """Check if engram CLI is installed."""
    return shutil.which("engram") is not None


def engram_search(query: str, project: str | None = None) -> str | None:
    """Search Engram for relevant memories."""
    if not engram_available():
        return None
    cmd = ["engram", "search", query]
    if project:
        cmd.extend(["--project", project])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def engram_save(
    topic: str,
    content: str,
    project: str | None = None,
    memory_type: str = "project",
) -> bool:
    """Save a memory to Engram."""
    if not engram_available():
        return False
    cmd = ["engram", "save", topic, content]
    if project:
        cmd.extend(["--project", project])
    if memory_type:
        cmd.extend(["--type", memory_type])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


@dataclass
class PlaybookMemory:
    """Memory context for a playbook execution."""

    playbook_name: str
    project: str
    prior_learnings: str | None = None

    @classmethod
    def load(cls, playbook_name: str, work_dir: Path | None = None) -> PlaybookMemory:
        """Load relevant memories before playbook execution."""
        project = (work_dir or Path.cwd()).name

        # Search for prior executions of this playbook
        prior = engram_search(
            f"playbook:{playbook_name}", project=project,
        )

        # Search for known issues in this project
        issues = engram_search(
            f"issue:{project}", project=project,
        )

        learnings = None
        parts = []
        if prior:
            parts.append(f"Prior runs of {playbook_name}:\n{prior}")
        if issues:
            parts.append(f"Known issues:\n{issues}")
        if parts:
            learnings = "\n\n".join(parts)

        return cls(
            playbook_name=playbook_name,
            project=project,
            prior_learnings=learnings,
        )

    def save_phase_result(
        self,
        phase: int,
        agent: str,
        status: str,
        summary: str,
    ) -> None:
        """Save a phase result to Engram (only notable ones)."""
        if status in ("failed", "blocked"):
            engram_save(
                topic=f"playbook:{self.playbook_name}:phase{phase}",
                content=(
                    f"Agent {agent} {status} in {self.playbook_name} "
                    f"({self.project}): {summary}"
                ),
                project=self.project,
            )

    def save_completion(
        self,
        total_phases: int,
        succeeded: int,
        failed: int,
        summary: str,
    ) -> None:
        """Save playbook completion summary to Engram."""
        status = "completed" if failed == 0 else "partial"
        engram_save(
            topic=f"playbook:{self.playbook_name}:execution",
            content=(
                f"Playbook {self.playbook_name} {status} in {self.project}. "
                f"Phases: {succeeded}/{total_phases} succeeded, {failed} failed. "
                f"{summary}"
            ),
            project=self.project,
        )

    def save_learning(self, lesson: str) -> None:
        """Save a learning/insight discovered during execution."""
        engram_save(
            topic=f"learning:{self.playbook_name}:{self.project}",
            content=lesson,
            project=self.project,
        )
