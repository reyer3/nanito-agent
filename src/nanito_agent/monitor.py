"""Session monitor — query and display Claude Code session history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

DB_PATH = Path.home() / ".claude" / "nanito-sessions.db"


def _connect() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        console.print(
            "[yellow]No session data yet.[/yellow] "
            "Run Claude Code with nanito-agent hooks active."
        )
        return None
    return sqlite3.connect(str(DB_PATH))


def list_sessions(limit: int = 20) -> None:
    """Show recent sessions with summary stats."""
    conn = _connect()
    if not conn:
        return

    rows = conn.execute(
        """
        SELECT
            session_id,
            project,
            model,
            MIN(timestamp) AS started,
            MAX(timestamp) AS last_activity,
            COUNT(CASE WHEN event_type = 'PreToolUse' THEN 1 END) AS tool_calls,
            COUNT(DISTINCT tool_name) AS unique_tools,
            COUNT(DISTINCT CASE WHEN agent_id IS NOT NULL THEN agent_id END) AS agents
        FROM events
        GROUP BY session_id
        ORDER BY started DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    if not rows:
        console.print("[yellow]No sessions recorded yet.[/yellow]")
        return

    table = Table(title="Recent Sessions", show_header=True)
    table.add_column("ID", style="cyan", max_width=12)
    table.add_column("Project", style="bold")
    table.add_column("Model", style="dim")
    table.add_column("Started")
    table.add_column("Last Activity")
    table.add_column("Tools", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Agents", justify="right")

    for sid, project, model, started, last, tools, unique, agents in rows:
        short_id = (sid or "?")[:8]
        model_short = (model or "?").replace("claude-", "")[:12]
        table.add_row(
            short_id,
            project or "?",
            model_short,
            started or "?",
            last or "?",
            str(tools),
            str(unique),
            str(agents),
        )

    console.print(table)
    console.print("\n  [dim]Use: nanito-agent sessions <id> for detail[/dim]")


def show_session(session_id: str) -> None:
    """Show detailed timeline for a specific session."""
    conn = _connect()
    if not conn:
        return

    rows = conn.execute(
        """
        SELECT event_type, tool_name, agent_id, timestamp, payload
        FROM events
        WHERE session_id LIKE ?
        ORDER BY timestamp ASC
        """,
        (f"{session_id}%",),
    ).fetchall()
    conn.close()

    if not rows:
        console.print(f"[yellow]No events found for session {session_id}[/yellow]")
        return

    table = Table(title=f"Session {session_id[:8]}...", show_header=True)
    table.add_column("Time", style="dim", max_width=8)
    table.add_column("Event", style="bold")
    table.add_column("Tool", style="cyan")
    table.add_column("Agent", style="magenta", max_width=10)
    table.add_column("Detail", style="dim", max_width=40)

    event_styles = {
        "SessionStart": "green",
        "Stop": "red",
        "PreCompact": "yellow",
        "PostToolUse": "dim",
    }

    for event_type, tool_name, agent_id, timestamp, payload in rows:
        time_short = timestamp.split("T")[1] if "T" in (timestamp or "") else (timestamp or "")
        detail = _extract_detail(payload)
        style = event_styles.get(event_type, "")
        event_display = f"[{style}]{event_type}[/]" if style else event_type

        table.add_row(
            time_short,
            event_display,
            tool_name or "",
            (agent_id or "")[:8],
            detail,
        )

    console.print(table)

    # Summary
    tool_count = sum(1 for r in rows if r[0] == "PreToolUse")
    unique_tools = len({r[1] for r in rows if r[1]})
    console.print(
        f"\n  [dim]Events: {len(rows)}  |  Tool calls: {tool_count}"
        f"  |  Unique tools: {unique_tools}[/dim]"
    )


def show_stats() -> None:
    """Show aggregate session statistics."""
    conn = _connect()
    if not conn:
        return

    total_sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM events").fetchone()[0]
    total_tools = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type = 'PreToolUse'"
    ).fetchone()[0]

    top_tools = conn.execute(
        """
        SELECT tool_name, COUNT(*) as cnt
        FROM events WHERE tool_name IS NOT NULL
        GROUP BY tool_name ORDER BY cnt DESC LIMIT 10
        """
    ).fetchall()

    top_projects = conn.execute(
        """
        SELECT project, COUNT(DISTINCT session_id) as sessions, COUNT(*) as events
        FROM events WHERE project IS NOT NULL
        GROUP BY project ORDER BY sessions DESC LIMIT 10
        """
    ).fetchall()

    daily = conn.execute(
        """
        SELECT DATE(timestamp) as day, COUNT(DISTINCT session_id) as sessions, COUNT(*) as events
        FROM events WHERE timestamp >= DATE('now', '-7 days')
        GROUP BY day ORDER BY day DESC
        """
    ).fetchall()

    conn.close()

    console.print("\n[bold]Session Stats[/bold]")
    console.print(f"  Sessions: {total_sessions}  |  Tool calls: {total_tools}\n")

    if top_tools:
        table = Table(title="Top Tools", show_header=True)
        table.add_column("Tool", style="cyan")
        table.add_column("Count", justify="right")
        for name, cnt in top_tools:
            table.add_row(name, str(cnt))
        console.print(table)

    if top_projects:
        table = Table(title="Top Projects", show_header=True)
        table.add_column("Project", style="bold")
        table.add_column("Sessions", justify="right")
        table.add_column("Events", justify="right")
        for proj, sessions, events in top_projects:
            table.add_row(proj, str(sessions), str(events))
        console.print(table)

    if daily:
        table = Table(title="Last 7 Days", show_header=True)
        table.add_column("Day")
        table.add_column("Sessions", justify="right")
        table.add_column("Events", justify="right")
        for day, sessions, events in daily:
            table.add_row(day, str(sessions), str(events))
        console.print(table)


def _extract_detail(payload: str | None) -> str:
    """Extract human-readable detail from event payload."""
    if not payload:
        return ""
    try:
        p = json.loads(payload)
        if "input_keys" in p:
            return ", ".join(p["input_keys"][:3])
        if "source" in p:
            return p["source"]
        if "model" in p:
            return p["model"]
    except json.JSONDecodeError:
        pass
    return ""
