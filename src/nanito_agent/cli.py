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


def _help() -> None:
    console.print(
        "\n[bold]Usage:[/bold]"
        "\n  nanito-agent setup [--dry-run]   Configure Claude Code"
        "\n  nanito-agent status              Show current config status"
        "\n  nanito-agent --help              This message\n"
    )
