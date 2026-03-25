"""Web UI for nanito-agent — FastAPI + HTMX dashboard."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from nanito_agent.agents import discover_agents
from nanito_agent.mcp import MCPContext
from nanito_agent.memory import engram_available
from nanito_agent.monitor import DB_PATH
from nanito_agent.playbook import ParallelGroup, parse_playbook
from nanito_agent.runner import plan_execution, render_plan

try:
    from dataclasses import asdict

    from nanito_agent.inbox import (
        approve_wish,
        create_wish,
        get_wish,
        list_wishes,
        update_wish,
    )

    HAS_INBOX = True
except ImportError:
    HAS_INBOX = False

app = FastAPI(title="nanito-agent", docs_url="/docs")

WISHES_DB = Path.home() / ".claude" / "nanito-wishes.db"

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
    .badge-pending {{ background: #b8860b; color: #fff; }}
    .badge-analyzing {{ background: #2563eb; color: #fff; }}
    .badge-ready {{ background: #ea580c; color: #fff; }}
    .badge-approved {{ background: #16a34a; color: #fff; }}
    .badge-executing {{ background: #2563eb; color: #fff; animation: pulse 1.5s infinite; }}
    .badge-done {{ background: #166534; color: #9ca3af; }}
    .badge-failed {{ background: #dc2626; color: #fff; }}
    .badge-rejected {{ background: #6b7280; color: #fff; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
    .wish-card {{ border: 1px solid var(--pico-muted-border-color); border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1rem; }}
    .wish-card:hover {{ border-color: var(--pico-primary); }}
    .wish-meta {{ color: var(--pico-muted-color); font-size: 0.85rem; }}
    .wish-filters {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
    .wish-filters a {{ padding: 0.3rem 0.8rem; border-radius: 4px; text-decoration: none; font-size: 0.85rem; border: 1px solid var(--pico-muted-border-color); }}
    .wish-filters a.active {{ background: var(--pico-primary); color: #fff; }}
    .digest-box {{ background: var(--pico-card-background-color); border: 1px solid var(--pico-muted-border-color); border-radius: 8px; padding: 1.5rem; margin: 1rem 0; white-space: pre-wrap; font-family: monospace; font-size: 0.9rem; }}
    .action-buttons {{ display: flex; gap: 0.5rem; margin-top: 1rem; }}
    pre {{ font-size: 0.85rem; }}
    nav ul {{ list-style: none; padding: 0; }}
  </style>
</head>
<body>
  <nav class="container-fluid">
    <ul><li><strong>nanito-agent</strong></li></ul>
    <ul>
      {_nav_link("/", "Dashboard")}
      {_nav_link("/wishes", "Mission Control")}
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


# ---------------------------------------------------------------------------
# Wishes / Mission Control — DB helpers
# ---------------------------------------------------------------------------

_WISH_STATUSES = ("pending", "analyzing", "ready", "approved", "executing", "done", "failed", "rejected")


def _wishes_db_connect() -> sqlite3.Connection | None:
    if not WISHES_DB.exists():
        return None
    conn = sqlite3.connect(str(WISHES_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _wish_to_dict(wish: Any) -> dict[str, Any]:
    """Convert a Wish dataclass or dict to a plain dict."""
    if isinstance(wish, dict):
        return wish
    if HAS_INBOX:
        return asdict(wish)
    return {}


def _wishes_list(status: str | None = None) -> list[dict[str, Any]]:
    if HAS_INBOX:
        try:
            wishes = list_wishes(status=status)
            return [_wish_to_dict(w) for w in wishes]
        except Exception:
            pass
    conn = _wishes_db_connect()
    if not conn:
        return []
    try:
        if status and status in _WISH_STATUSES:
            rows = conn.execute(
                "SELECT * FROM wishes WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM wishes ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _wish_get(wish_id: str) -> dict[str, Any] | None:
    if HAS_INBOX:
        try:
            w = get_wish(wish_id)
            return _wish_to_dict(w) if w else None
        except Exception:
            pass
    conn = _wishes_db_connect()
    if not conn:
        return None
    try:
        row = conn.execute("SELECT * FROM wishes WHERE id = ?", (wish_id,)).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _wish_create(raw: str, source: str = "web") -> dict[str, Any] | None:
    if HAS_INBOX:
        try:
            w = create_wish(source=source, raw=raw)
            return _wish_to_dict(w)
        except Exception:
            pass
    # Fallback: direct DB access
    WISHES_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WISHES_DB))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS wishes (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            raw TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            project TEXT,
            playbook TEXT,
            variables TEXT DEFAULT '{}',
            analysis TEXT,
            digest TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    try:
        import uuid

        now = datetime.now(timezone.utc).isoformat()
        wid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO wishes (id, source, raw, status, variables, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', '{}', ?, ?)",
            (wid, source, raw, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM wishes WHERE id = ?", (wid,)).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _wish_set_status(wish_id: str, status: str) -> dict[str, Any] | None:
    if HAS_INBOX:
        try:
            if status == "approved":
                approve_wish(wish_id)
            else:
                update_wish(wish_id, status=status)
            w = get_wish(wish_id)
            return _wish_to_dict(w) if w else None
        except Exception:
            pass
    conn = _wishes_db_connect()
    if not conn:
        return None
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE wishes SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, wish_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM wishes WHERE id = ?", (wish_id,)).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _wish_count() -> int:
    if HAS_INBOX:
        try:
            return len(list_wishes())
        except Exception:
            pass
    conn = _wishes_db_connect()
    if not conn:
        return 0
    try:
        row = conn.execute("SELECT COUNT(*) FROM wishes").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def _status_badge(status: str) -> str:
    css_class = f"badge-{status}" if status in _WISH_STATUSES else "badge-seq"
    return f'<span class="badge {css_class}">{status}</span>'


def _time_ago(timestamp: str | None) -> str:
    if not timestamp:
        return "?"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except (ValueError, TypeError):
        return timestamp or "?"


def _wish_card_html(wish: dict[str, Any]) -> str:
    wid = wish.get("id", "?")
    raw = wish.get("raw", "")
    status = wish.get("status", "pending")
    playbook = wish.get("playbook") or ""
    created = wish.get("created_at")
    playbook_tag = f' | <strong>{playbook}</strong>' if playbook else ""
    return (
        f'<article class="wish-card">'
        f'<a href="/wishes/{wid}" style="text-decoration:none;color:inherit;">'
        f"<p><strong>{raw[:120]}</strong></p>"
        f'<p class="wish-meta">{_status_badge(status)}{playbook_tag} | {_time_ago(created)}</p>'
        f"</a></article>"
    )


# ---------------------------------------------------------------------------
# Routes — Mission Control (Wishes)
# ---------------------------------------------------------------------------


@app.get("/wishes", response_class=HTMLResponse)
async def wishes_list(request: Request) -> str:
    status_filter = request.query_params.get("status")
    wishes = _wishes_list(status=status_filter)

    # Filters
    all_active = ' class="active"' if not status_filter else ""
    filters = f'<a href="/wishes"{all_active}>All</a>'
    for s in ("pending", "ready", "executing", "done"):
        active = ' class="active"' if status_filter == s else ""
        filters += f'<a href="/wishes?status={s}"{active}>{s.capitalize()}</a>'

    # New wish form
    form = (
        '<form method="post" action="/wishes" style="margin-bottom:1.5rem;">'
        '<fieldset role="group">'
        '<input type="text" name="raw" placeholder="Describe your wish..." required>'
        "<button type=\"submit\">Send</button>"
        "</fieldset></form>"
    )

    # Wish cards
    if wishes:
        cards = "".join(_wish_card_html(w) for w in wishes)
    else:
        cards = (
            '<article class="wish-card">'
            "<p>No wishes yet. Type one above to get started.</p>"
            "</article>"
        )

    body = (
        "<h1>Mission Control</h1>"
        f"{form}"
        f'<div class="wish-filters">{filters}</div>'
        f'<div id="wish-list">{cards}</div>'
    )
    return _layout("Mission Control", body, active="Mission Control")


@app.get("/wishes/{wish_id}", response_class=HTMLResponse)
async def wish_detail(wish_id: str) -> str:
    wish = _wish_get(wish_id)
    if not wish:
        body = f"<h1>Wish not found</h1><p>ID: {wish_id}</p><p><a href=\"/wishes\">Back to Mission Control</a></p>"
        return _layout("Not Found", body, active="Mission Control")

    wid = wish.get("id", wish_id)
    raw = wish.get("raw", "")
    status = wish.get("status", "pending")
    playbook = wish.get("playbook") or "unclassified"
    created = wish.get("created_at")
    digest = wish.get("digest") or ""
    analysis = wish.get("analysis") or ""
    project = wish.get("project") or ""

    # Digest display
    digest_content = digest or analysis or "No analysis available yet."
    digest_html = f'<div class="digest-box">{digest_content}</div>'

    # Action buttons (only for actionable statuses)
    actions = ""
    if status in ("ready", "pending", "analyzing"):
        actions = (
            '<div class="action-buttons">'
            f'<button hx-post="/wishes/{wid}/approve" hx-target="#wish-status" '
            f'hx-swap="outerHTML" style="background:#16a34a;">Approve</button>'
            f'<button hx-post="/wishes/{wid}/reject" hx-target="#wish-status" '
            f'hx-swap="outerHTML" class="secondary">Reject</button>'
            "</div>"
        )

    # Info grid
    meta_rows = [
        ["Status", _status_badge(status)],
        ["Playbook", playbook],
        ["Project", project or "unassigned"],
        ["Created", _time_ago(created)],
    ]
    meta_html = "".join(
        f"<tr><td><strong>{r[0]}</strong></td><td>{r[1]}</td></tr>" for r in meta_rows
    )

    short_id = str(wid)[:8]
    body = (
        f"<h1>Wish {short_id}...</h1>"
        f'<article class="card">'
        f"<p><strong>{raw}</strong></p>"
        f'<table id="wish-status"><tbody>{meta_html}</tbody></table>'
        f"<h3>Digest</h3>{digest_html}"
        f"{actions}"
        f"</article>"
        f'<p><a href="/wishes">Back to Mission Control</a></p>'
    )
    return _layout(f"Wish {short_id}", body, active="Mission Control")


@app.post("/wishes", response_class=HTMLResponse)
async def wish_create_form(raw: str = Form(...)) -> HTMLResponse:
    wish = _wish_create(raw=raw, source="web")
    if wish:
        from starlette.responses import RedirectResponse

        return RedirectResponse(url="/wishes", status_code=303)  # type: ignore[return-value]
    return HTMLResponse("<p>Failed to create wish.</p>", status_code=500)


@app.post("/wishes/{wish_id}/approve", response_class=HTMLResponse)
async def wish_approve(wish_id: str) -> str:
    wish = _wish_set_status(wish_id, "approved")
    if not wish:
        return "<p>Wish not found.</p>"
    status = wish.get("status", "approved")
    return (
        f'<table id="wish-status"><tbody>'
        f"<tr><td><strong>Status</strong></td><td>{_status_badge(status)}</td></tr>"
        f"<tr><td><strong>Playbook</strong></td><td>{wish.get('playbook') or 'unclassified'}</td></tr>"
        f"<tr><td><strong>Project</strong></td><td>{wish.get('project') or 'unassigned'}</td></tr>"
        f"<tr><td><strong>Created</strong></td><td>{_time_ago(wish.get('created_at'))}</td></tr>"
        f"</tbody></table>"
    )


@app.post("/wishes/{wish_id}/reject", response_class=HTMLResponse)
async def wish_reject(wish_id: str) -> str:
    wish = _wish_set_status(wish_id, "rejected")
    if not wish:
        return "<p>Wish not found.</p>"
    status = wish.get("status", "rejected")
    return (
        f'<table id="wish-status"><tbody>'
        f"<tr><td><strong>Status</strong></td><td>{_status_badge(status)}</td></tr>"
        f"<tr><td><strong>Playbook</strong></td><td>{wish.get('playbook') or 'unclassified'}</td></tr>"
        f"<tr><td><strong>Project</strong></td><td>{wish.get('project') or 'unassigned'}</td></tr>"
        f"<tr><td><strong>Created</strong></td><td>{_time_ago(wish.get('created_at'))}</td></tr>"
        f"</tbody></table>"
    )


# ---------------------------------------------------------------------------
# SSE — Server-Sent Events for real-time updates
# ---------------------------------------------------------------------------


@app.get("/events")
async def event_stream(request: Request) -> StreamingResponse:
    async def generate():  # type: ignore[no-untyped-def]
        while True:
            if await request.is_disconnected():
                break
            # Heartbeat + wish count for now; real events will come from consumer
            count = _wish_count()
            data = json.dumps({"type": "heartbeat", "wishes": count})
            yield f"data: {data}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# API — JSON endpoints for wishes (future Flutter/PWA)
# ---------------------------------------------------------------------------


@app.get("/api/wishes", response_class=JSONResponse)
async def api_wishes_list(request: Request) -> JSONResponse:
    status = request.query_params.get("status")
    page = int(request.query_params.get("page", "1"))
    per_page = int(request.query_params.get("per_page", "20"))
    wishes = _wishes_list(status=status)
    # Simple pagination
    start = (page - 1) * per_page
    end = start + per_page
    return JSONResponse(
        {
            "wishes": wishes[start:end],
            "total": len(wishes),
            "page": page,
            "per_page": per_page,
        }
    )


@app.get("/api/wishes/{wish_id}", response_class=JSONResponse)
async def api_wish_detail(wish_id: str) -> JSONResponse:
    wish = _wish_get(wish_id)
    if not wish:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(wish)


@app.post("/api/wishes", response_class=JSONResponse)
async def api_wish_create(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        raw = body.get("raw", "").strip()
        source = body.get("source", "api")
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not raw:
        return JSONResponse({"error": "raw is required"}, status_code=400)
    wish = _wish_create(raw=raw, source=source)
    if not wish:
        return JSONResponse({"error": "failed to create wish"}, status_code=500)
    return JSONResponse(wish, status_code=201)


@app.post("/api/wishes/{wish_id}/approve", response_class=JSONResponse)
async def api_wish_approve(wish_id: str) -> JSONResponse:
    wish = _wish_set_status(wish_id, "approved")
    if not wish:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(wish)


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
        "wishes": _wish_count(),
        "mcp": {
            "available": list(mcp.available.keys()),
        },
        "engram": engram_available(),
    }
