"""CLI entry point for nanito-agent."""

import sys

from rich.console import Console

from nanito_agent.questions import run_questionnaire
from nanito_agent.writer import install_config

console = Console()


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] == "setup":
        _setup(dry_run="--dry-run" in args)
    elif args[0] == "status":
        _status()
    elif args[0] == "sessions":
        _sessions(args[1:])
    elif args[0] == "run":
        _run(args[1:])
    elif args[0] == "agents":
        _agents()
    elif args[0] == "--help":
        _help()
    else:
        console.print(f"[red]Unknown command: {args[0]}[/red]")
        _help()
        sys.exit(1)


def _setup(dry_run: bool = False) -> None:
    console.print("\n[bold]nanito-agent[/bold] — Claude Code configurator\n")

    profile = run_questionnaire()

    if dry_run:
        console.print("\n[yellow]Dry run — nothing written.[/yellow]")
        console.print(profile)
        return

    install_config(profile)
    console.print("\n[bold green]Done.[/bold green] Restart Claude Code to activate.\n")


def _status() -> None:
    from nanito_agent.status import show_status

    show_status()


def _sessions(args: list[str]) -> None:
    from nanito_agent.monitor import list_sessions, show_session, show_stats

    if not args:
        list_sessions()
    elif args[0] == "--stats":
        show_stats()
    else:
        show_session(args[0])


def _run(args: list[str]) -> None:
    from pathlib import Path

    from nanito_agent.agents import discover_agents, validate_playbook_agents
    from nanito_agent.executor import compile_execution
    from nanito_agent.memory import PlaybookMemory
    from nanito_agent.playbook import parse_playbook
    from nanito_agent.runner import plan_execution, render_plan

    if not args:
        console.print(
            "[red]Usage: nanito-agent run <playbook.yaml>"
            " [--var key=val ...] [--dry-run] [--json][/red]"
        )
        sys.exit(1)

    dry_run = "--dry-run" in args
    json_mode = "--json" in args
    playbook_path = _resolve_playbook(args[0])
    variables = _parse_vars(args[1:])

    playbook = parse_playbook(playbook_path)
    if not json_mode:
        console.print(f"\n[bold]Playbook:[/bold] {playbook.name}")
        console.print(f"[dim]{playbook.description}[/dim]\n")

    # Validate agents
    agents = discover_agents()
    missing = validate_playbook_agents(playbook.agent_names, agents)
    if missing:
        console.print(
            f"[red]Missing agents: {', '.join(missing)}[/red]"
        )
        console.print(
            "[dim]Create them in src/nanito_agent/agents/"
            " or a project agents/ dir[/dim]"
        )
        sys.exit(1)

    # Load memory from Engram (prior learnings for this playbook)
    memory = PlaybookMemory.load(playbook.name)
    if memory.prior_learnings and not json_mode:
        console.print("[dim]Engram: loaded prior learnings[/dim]")

    # Compile execution with Engram context
    plan = plan_execution(playbook, variables)
    script = compile_execution(
        plan, agents, engram_context=memory.prior_learnings,
    )

    if json_mode:
        print(script.to_json())  # noqa: T201 — raw print for clean JSON
    else:
        console.print(render_plan(plan))
        console.print("")
        console.print(script.to_summary())

    if dry_run:
        console.print(
            "\n[yellow]Dry run — validated plan, "
            "no agents dispatched.[/yellow]"
        )


def _resolve_playbook(name: str) -> "Path":
    from pathlib import Path

    # Direct path
    path = Path(name)
    if path.exists():
        return path

    # Check builtin playbooks
    builtin = Path(__file__).parent.parent.parent / "playbooks" / name
    if builtin.exists():
        return builtin
    if not name.endswith(".yaml"):
        builtin_yaml = builtin.with_suffix(".yaml")
        if builtin_yaml.exists():
            return builtin_yaml

    console.print(f"[red]Playbook not found: {name}[/red]")
    sys.exit(1)


def _parse_vars(args: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    i = 0
    while i < len(args):
        if args[i] == "--var" and i + 1 < len(args):
            key, _, val = args[i + 1].partition("=")
            variables[key] = val
            i += 2
        else:
            i += 1
    return variables


def _agents() -> None:
    from rich.table import Table

    from nanito_agent.agents import discover_agents

    agents = discover_agents()

    table = Table(title="Available Agents", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Worktree")
    table.add_column("Description")

    for name, agent in sorted(agents.items()):
        wt = "[green]yes[/green]" if agent.worktree else ""
        table.add_row(name, agent.model, wt, agent.description)

    console.print(table)


def _help() -> None:
    console.print(
        "\n[bold]Usage:[/bold]"
        "\n  nanito-agent setup [--dry-run]   Configure Claude Code"
        "\n  nanito-agent status              Show current config status"
        "\n  nanito-agent sessions [id]       Session history (--stats for aggregate)"
        "\n  nanito-agent run <playbook>      Run a playbook (--var key=val)"
        "\n  nanito-agent agents              List available agents"
        "\n  nanito-agent --help              This message\n"
    )
