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
    elif args[0] == "wish":
        _wish(args[1:])
    elif args[0] == "wishes":
        _wishes()
    elif args[0] == "approve":
        _approve(args[1:])
    elif args[0] == "reject":
        _reject(args[1:])
    elif args[0] == "web":
        _web(args[1:])
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
    from nanito_agent.mcp import MCPContext
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

    # Detect available MCP servers
    mcp_ctx = MCPContext.detect()
    if not json_mode and mcp_ctx.available:
        names = ", ".join(mcp_ctx.available.keys())
        console.print(f"[dim]MCP: {names}[/dim]")

    # Compile execution with Engram + MCP context
    plan = plan_execution(playbook, variables)
    script = compile_execution(
        plan, agents,
        engram_context=memory.prior_learnings,
        mcp_section=mcp_ctx.to_prompt_section(),
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

    # Check builtin playbooks (dev mode: repo root, installed: package)
    candidates = [
        Path(__file__).parent.parent.parent / "playbooks" / name,
        Path(__file__).parent / "playbooks" / name,
    ]
    for builtin in candidates:
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


def _wish(args: list[str]) -> None:
    from nanito_agent.inbox import create_wish

    if not args:
        console.print("[red]Usage: nanito-agent wish \"quiero X\"[/red]")
        sys.exit(1)

    raw = " ".join(args)
    project = None
    # Extract --project if provided
    for i, arg in enumerate(args):
        if arg == "--project" and i + 1 < len(args):
            project = args[i + 1]
            raw = " ".join(args[:i] + args[i + 2:])
            break

    wish = create_wish(source="terminal", raw=raw, project=project)
    console.print(f"[green]Wish created:[/green] {wish.id[:8]}")
    console.print(f"[dim]{wish.raw}[/dim]")


def _wishes() -> None:
    from rich.table import Table

    from nanito_agent.inbox import list_wishes

    wishes = list_wishes()
    if not wishes:
        console.print("[yellow]No wishes yet.[/yellow] Use: nanito-agent wish \"quiero X\"")
        return

    table = Table(title="Wishes", show_header=True)
    table.add_column("ID", style="cyan", max_width=8)
    table.add_column("Status", style="bold")
    table.add_column("Source", style="dim")
    table.add_column("Playbook", style="dim")
    table.add_column("Wish", max_width=50)

    status_colors = {
        "pending": "yellow",
        "analyzing": "blue",
        "ready": "cyan",
        "approved": "green",
        "executing": "magenta",
        "done": "green",
        "failed": "red",
    }

    for w in wishes:
        color = status_colors.get(w.status, "")
        status = f"[{color}]{w.status}[/]" if color else w.status
        table.add_row(
            w.id[:8],
            status,
            w.source,
            w.playbook or "",
            w.raw[:50],
        )

    console.print(table)


def _approve(args: list[str]) -> None:
    from nanito_agent.inbox import approve_wish, get_wish, list_wishes

    if not args:
        console.print("[red]Usage: nanito-agent approve <wish-id>[/red]")
        sys.exit(1)

    wish_id = _resolve_wish_id(args[0])
    if not wish_id:
        console.print(f"[red]Wish not found: {args[0]}[/red]")
        sys.exit(1)

    wish = get_wish(wish_id)
    if wish:
        approve_wish(wish_id)
        console.print(f"[green]Approved:[/green] {wish.raw[:60]}")
    else:
        console.print(f"[red]Wish not found: {args[0]}[/red]")
        sys.exit(1)


def _reject(args: list[str]) -> None:
    from nanito_agent.inbox import get_wish, list_wishes, reject_wish

    if not args:
        console.print("[red]Usage: nanito-agent reject <wish-id>[/red]")
        sys.exit(1)

    wish_id = _resolve_wish_id(args[0])
    if not wish_id:
        console.print(f"[red]Wish not found: {args[0]}[/red]")
        sys.exit(1)

    wish = get_wish(wish_id)
    if wish:
        reject_wish(wish_id)
        console.print(f"[red]Rejected:[/red] {wish.raw[:60]}")
    else:
        console.print(f"[red]Wish not found: {args[0]}[/red]")
        sys.exit(1)


def _resolve_wish_id(partial: str) -> str | None:
    """Resolve a partial wish ID (prefix match) to a full ID."""
    from nanito_agent.inbox import list_wishes

    wishes = list_wishes(limit=100)
    for w in wishes:
        if w.id.startswith(partial):
            return w.id
    return None


def _web(args: list[str]) -> None:
    import uvicorn

    host = "127.0.0.1"
    port = 8000

    for i, arg in enumerate(args):
        if arg == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    console.print(f"\n[bold]nanito-agent[/bold] web UI at http://{host}:{port}\n")
    uvicorn.run("nanito_agent.web:app", host=host, port=port, reload=False)


def _help() -> None:
    console.print(
        "\n[bold]Usage:[/bold]"
        "\n  nanito-agent setup [--dry-run]   Configure Claude Code"
        "\n  nanito-agent status              Show current config status"
        "\n  nanito-agent sessions [id]       Session history (--stats for aggregate)"
        "\n  nanito-agent run <playbook>      Run a playbook (--var key=val)"
        "\n  nanito-agent agents              List available agents"
        "\n  nanito-agent wish \"quiero X\"     Create a new wish (--project name)"
        "\n  nanito-agent wishes              List all wishes with status"
        "\n  nanito-agent approve <id>        Approve a wish for execution"
        "\n  nanito-agent reject <id>         Reject a wish"
        "\n  nanito-agent web                 Start the web UI (--host, --port)"
        "\n  nanito-agent --help              This message\n"
    )
