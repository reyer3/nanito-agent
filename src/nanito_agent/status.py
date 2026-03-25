"""Status checker — shows current nanito-agent configuration state."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

CLAUDE_DIR = Path.home() / ".claude"


def show_status() -> None:
    """Display current Claude Code configuration status."""
    table = Table(title="nanito-agent status", show_header=True)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    # CLAUDE.md
    claude_md = CLAUDE_DIR / "CLAUDE.md"
    if claude_md.exists():
        lines = len(claude_md.read_text().splitlines())
        table.add_row("CLAUDE.md", "[green]OK[/green]", f"{lines} lines")
    else:
        table.add_row("CLAUDE.md", "[red]MISSING[/red]", "Run: nanito-agent setup")

    # Hooks
    hooks_dir = CLAUDE_DIR / "hooks"
    if hooks_dir.exists():
        hook_count = len(list(hooks_dir.glob("*.sh")))
        table.add_row("Hooks", "[green]OK[/green]", f"{hook_count} scripts")
    else:
        table.add_row("Hooks", "[red]MISSING[/red]", "Run: nanito-agent setup")

    # Settings hooks
    settings_file = CLAUDE_DIR / "settings.json"
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
        hook_events = len(settings.get("hooks", {}))
        has_deny = bool(settings.get("permissions", {}).get("deny"))
        table.add_row("Settings hooks", "[green]OK[/green]" if hook_events else "[yellow]NONE[/yellow]", f"{hook_events} events")
        table.add_row("Deny list", "[green]OK[/green]" if has_deny else "[yellow]NONE[/yellow]", "")
    else:
        table.add_row("Settings", "[red]MISSING[/red]", "")

    # Engram
    if shutil.which("engram"):
        table.add_row("Engram", "[green]OK[/green]", "Binary found")
    else:
        table.add_row("Engram", "[yellow]NOT FOUND[/yellow]", "Optional but recommended")

    # Engram MCP
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
        has_engram_mcp = "engram" in settings.get("mcpServers", {})
        table.add_row("Engram MCP", "[green]OK[/green]" if has_engram_mcp else "[yellow]NOT SET[/yellow]", "")

    # Plugins
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
        plugin_count = len(settings.get("enabledPlugins", {}))
        table.add_row("Plugins", "[green]OK[/green]" if plugin_count else "[yellow]NONE[/yellow]", f"{plugin_count} enabled")

    # SuperClaude
    sc_dir = CLAUDE_DIR / "commands" / "sc"
    if sc_dir.exists():
        sc_count = len(list(sc_dir.glob("*.md")))
        table.add_row("SuperClaude", "[green]OK[/green]" if sc_count > 10 else "[yellow]PARTIAL[/yellow]", f"{sc_count} commands")
    else:
        table.add_row("SuperClaude", "[dim]NOT INSTALLED[/dim]", "Optional: npx superclaude install")

    console.print(table)
