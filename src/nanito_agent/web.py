"""Web UI for nanito-agent — FastAPI + HTMX dashboard."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from nanito_agent.agents import discover_agents
from nanito_agent.mcp import MCPContext
from nanito_agent.memory import engram_available
from nanito_agent.monitor import DB_PATH
from nanito_agent.playbook import ParallelGroup, parse_playbook
from nanito_agent.runner import plan_execution, render_plan

app = FastAPI(title="nanito-agent", docs_url="/docs")

PLAYBOOKS_DIR = Path(__file__).parent.parent.parent / "playbooks"

# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

_CSS = "https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css"
_HTMX = "https://unpkg.com/htmx.org@2.0.4"


def _layout(title: str, body: str, active: str = "") -> str:
    def _nav_link(href: str, label: str) -> str:
        aria = ' aria-current="page"' if label.lower() == active.lower() else ""
        return f'<li><a href="{href}"{aria}>{label}</a></li>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - nanito-agent</title>
  <link rel="stylesheet" href="{_CSS}">
  <script src="{_HTMX}"></script>
  <style>
    .card {{ border: 1px solid var(--pico-muted-border-color); border-radius: 8px; padding: 1.5rem; }}
    .grid-3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
    .stat-value {{ font-size: 2.5rem; font-weight: bold; margin: 0; }}
    .stat-label {{ color: var(--pico-muted-color); margin: 0; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.85rem; }}
    .badge-parallel {{ background: var(--pico-primary-background); }}
    .badge-seq {{ background: var(--pico-secondary-background); }}
    pre {{ font-size: 0.85rem; }}
    nav ul {{ list-style: none; padding: 0; }}
  </style>
</head>
<body>
  <nav class="container-fluid">
    <ul><li><strong>nanito-agent</strong></li></ul>
    <ul>
      {_nav_link("/", "Dashboard")}
      {_nav_link("/playbooks", "Playbooks")}
      {_nav_link("/agents", "Agents")}
      {_nav_link("/sessions", "Sessions")}
    </ul>
  </nav>
  <main class="container">
    {body}
  </main>
  <footer class="container">
    <small>nanito-agent web UI</small>
  </footer>
</body>
</html>"""


def _table(headers: list[str], rows: list[list[str]]) -> str:
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = ""
    for row in rows:
        tds = "".join(f"<td>{c}</td>" for c in row)
        trs += f"<tr>{tds}</tr>\n"
    return f"""<figure><table>
<thead><tr>{ths}</tr></thead>
<tbody>{trs}</tbody>
</table></figure>"""


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _db_connect() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    return sqlite3.connect(str(DB_PATH))


def _db_session_count() -> int:
    conn = _db_connect()
    if not conn:
        return 0
    try:
        row = conn.execute("SELECT COUNT(DISTINCT session_id) FROM events").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def _db_recent_sessions(limit: int = 20) -> list[dict[str, Any]]:
    conn = _db_connect()
    if not conn:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                session_id,
                project,
                model,
                MIN(timestamp) AS started,
                COUNT(CASE WHEN event_type = 'PreToolUse' THEN 1 END) AS tool_calls
            FROM events
            GROUP BY session_id
            ORDER BY started DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "session_id": r[0],
                "project": r[1] or "?",
                "model": (r[2] or "?").replace("claude-", "")[:16],
                "started": r[3] or "?",
                "tool_calls": r[4],
            }
            for r in rows
        ]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _db_session_events(session_id: str) -> list[dict[str, Any]]:
    conn = _db_connect()
    if not conn:
        return []
    try:
        rows = conn.execute(
            """
            SELECT event_type, tool_name, agent_id, timestamp, payload
            FROM events
            WHERE session_id LIKE ?
            ORDER BY timestamp ASC
            """,
            (f"{session_id}%",),
        ).fetchall()
        results = []
        for r in rows:
            detail = ""
            if r[4]:
                try:
                    p = json.loads(r[4])
                    if "input_keys" in p:
                        detail = ", ".join(p["input_keys"][:3])
                    elif "source" in p:
                        detail = p["source"]
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(
                {
                    "event_type": r[0],
                    "tool_name": r[1] or "",
                    "agent_id": (r[2] or "")[:8],
                    "timestamp": r[3] or "",
                    "detail": detail,
                }
            )
        return results
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Playbook helpers
# ---------------------------------------------------------------------------


def _list_playbooks() -> list[dict[str, str]]:
    results = []
    dirs = [PLAYBOOKS_DIR]
    # Also check installed package location
    pkg_playbooks = Path(__file__).parent / "playbooks"
    if pkg_playbooks.exists() and pkg_playbooks != PLAYBOOKS_DIR:
        dirs.append(pkg_playbooks)
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.yaml")):
            try:
                pb = parse_playbook(f)
                results.append(
                    {
                        "name": pb.name,
                        "file": f.stem,
                        "description": pb.description,
                        "steps": str(pb.total_steps),
                        "agents": ", ".join(sorted(pb.agent_names)),
                    }
                )
            except Exception:
                results.append(
                    {
                        "name": f.stem,
                        "file": f.stem,
                        "description": "(parse error)",
                        "steps": "?",
                        "agents": "?",
                    }
                )
    return results


def _resolve_playbook_path(name: str) -> Path | None:
    candidates = [
        PLAYBOOKS_DIR / f"{name}.yaml",
        PLAYBOOKS_DIR / name,
        Path(__file__).parent / "playbooks" / f"{name}.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    agents = discover_agents()
    playbooks = _list_playbooks()
    session_count = _db_session_count()
    recent = _db_recent_sessions(limit=10)

    cards = f"""<div class="grid-3">
  <article class="card">
    <p class="stat-value">{len(agents)}</p>
    <p class="stat-label">Agents</p>
  </article>
  <article class="card">
    <p class="stat-value">{len(playbooks)}</p>
    <p class="stat-label">Playbooks</p>
  </article>
  <article class="card">
    <p class="stat-value">{session_count}</p>
    <p class="stat-label">Sessions</p>
  </article>
</div>"""

    if recent:
        rows = [
            [
                s["session_id"][:8],
                s["project"],
                s["started"],
                str(s["tool_calls"]),
            ]
            for s in recent
        ]
        sessions_table = "<h3>Recent Sessions</h3>" + _table(
            ["ID", "Project", "Started", "Tools"], rows
        )
    else:
        sessions_table = "<p>No sessions recorded yet.</p>"

    body = f"<h1>Dashboard</h1>{cards}{sessions_table}"
    return _layout("Dashboard", body, active="Dashboard")


@app.get("/playbooks", response_class=HTMLResponse)
async def playbooks_list() -> str:
    playbooks = _list_playbooks()

    rows = []
    for pb in playbooks:
        actions = (
            f'<a href="/playbooks/{pb["file"]}">Preview</a> | '
            f'<button hx-post="/playbooks/{pb["file"]}/run" '
            f'hx-target="#run-result" hx-swap="innerHTML">Run</button>'
        )
        rows.append([pb["name"], pb["description"], pb["steps"], pb["agents"], actions])

    body = "<h1>Playbooks</h1>"
    body += _table(["Name", "Description", "Steps", "Agents", "Actions"], rows)
    body += '<div id="run-result"></div>'
    return _layout("Playbooks", body, active="Playbooks")


@app.get("/playbooks/{name}", response_class=HTMLResponse)
async def playbook_detail(name: str) -> str:
    path = _resolve_playbook_path(name)
    if not path:
        body = f"<h1>Playbook not found: {name}</h1><p>Check the playbooks directory.</p>"
        return _layout("Not Found", body, active="Playbooks")

    pb = parse_playbook(path)
    plan = plan_execution(pb, {})
    rendered = render_plan(plan)

    # Build phases detail
    phases_html = ""
    for step_or_group in pb.steps:
        if isinstance(step_or_group, ParallelGroup):
            badge = '<span class="badge badge-parallel">parallel</span>'
            items = "".join(
                f"<li><strong>{s.agent}</strong>: {s.task}</li>"
                for s in step_or_group.steps
            )
            phases_html += f"<div>{badge}<ul>{items}</ul></div>"
        else:
            badge = '<span class="badge badge-seq">sequential</span>'
            phases_html += (
                f"<div>{badge} <strong>{step_or_group.agent}</strong>: "
                f"{step_or_group.task}</div>"
            )

    # Inputs
    inputs_html = ""
    if pb.inputs:
        input_rows = []
        for inp in pb.inputs:
            input_rows.append(
                [
                    inp.get("name", "?"),
                    inp.get("description", ""),
                    inp.get("default", ""),
                ]
            )
        inputs_html = "<h3>Inputs</h3>" + _table(
            ["Name", "Description", "Default"], input_rows
        )

    body = f"""<h1>{pb.name}</h1>
<p>{pb.description}</p>
{inputs_html}
<h3>Phases</h3>
{phases_html}
<h3>Execution Plan</h3>
<pre>{rendered}</pre>
<p><a href="/playbooks">Back to playbooks</a></p>"""
    return _layout(pb.name, body, active="Playbooks")


@app.post("/playbooks/{name}/run", response_class=HTMLResponse)
async def playbook_run(name: str, request: Request) -> str:
    path = _resolve_playbook_path(name)
    if not path:
        return f"<p><strong>Error:</strong> Playbook {name} not found.</p>"

    # Parse optional JSON vars from body
    variables: dict[str, str] = {}
    try:
        body_bytes = await request.body()
        if body_bytes:
            variables = json.loads(body_bytes)
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        pb = parse_playbook(path)
        plan = plan_execution(pb, variables)
        rendered = render_plan(plan)
        return (
            f'<article class="card"><h4>Execution plan for {pb.name}</h4>'
            f"<pre>{rendered}</pre>"
            f"<p><em>Dry-run preview. Full execution requires the CLI.</em></p>"
            f"</article>"
        )
    except Exception as exc:
        return f"<p><strong>Error:</strong> {exc}</p>"


@app.get("/agents", response_class=HTMLResponse)
async def agents_list() -> str:
    agents = discover_agents()

    rows = []
    for name, agent in sorted(agents.items()):
        wt = "yes" if agent.worktree else ""
        rows.append([name, agent.model, wt, agent.description])

    body = "<h1>Agents</h1>"
    body += _table(["Name", "Model", "Worktree", "Description"], rows)
    return _layout("Agents", body, active="Agents")


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_list() -> str:
    sessions = _db_recent_sessions(limit=50)

    if sessions:
        rows = [
            [
                f'<a href="/sessions/{s["session_id"]}">{s["session_id"][:8]}</a>',
                s["project"],
                s["model"],
                s["started"],
                str(s["tool_calls"]),
            ]
            for s in sessions
        ]
        table = _table(["ID", "Project", "Model", "Started", "Tools"], rows)
    else:
        table = "<p>No sessions recorded yet. Run Claude Code with nanito-agent hooks active.</p>"

    body = f"<h1>Sessions</h1>{table}"
    return _layout("Sessions", body, active="Sessions")


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(session_id: str) -> str:
    events = _db_session_events(session_id)

    if not events:
        body = (
            f"<h1>Session {session_id[:8]}...</h1>"
            "<p>No events found for this session.</p>"
        )
        return _layout("Session", body, active="Sessions")

    rows = [
        [
            e["timestamp"].split("T")[1] if "T" in e["timestamp"] else e["timestamp"],
            e["event_type"],
            e["tool_name"],
            e["agent_id"],
            e["detail"],
        ]
        for e in events
    ]
    table = _table(["Time", "Event", "Tool", "Agent", "Detail"], rows)

    tool_count = sum(1 for e in events if e["event_type"] == "PreToolUse")
    unique_tools = len({e["tool_name"] for e in events if e["tool_name"]})

    body = f"""<h1>Session {session_id[:8]}...</h1>
<p>Events: {len(events)} | Tool calls: {tool_count} | Unique tools: {unique_tools}</p>
{table}
<p><a href="/sessions">Back to sessions</a></p>"""
    return _layout("Session Detail", body, active="Sessions")


@app.get("/api/status", response_class=JSONResponse)
async def api_status() -> dict[str, Any]:
    agents = discover_agents()
    playbooks = _list_playbooks()
    mcp = MCPContext.detect()

    return {
        "status": "ok",
        "agents": len(agents),
        "playbooks": len(playbooks),
        "sessions": _db_session_count(),
        "mcp": {
            "available": list(mcp.available.keys()),
        },
        "engram": engram_available(),
    }
