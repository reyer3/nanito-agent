"""Wish inbox — SQLite-backed pub/sub for nanito autonomous mode.

Self-contained module. No dependency on playbook/runner/executor.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DB_PATH = Path.home() / ".claude" / "nanito-wishes.db"


@dataclass
class Wish:
    id: str
    source: str  # terminal | whatsapp | web | cron
    raw: str  # original user input
    status: str  # pending | analyzing | ready | approved | executing | done | failed
    project: str | None = None
    playbook: str | None = None
    variables: dict = field(default_factory=dict)
    analysis: str | None = None
    digest: str | None = None
    created_at: str = ""
    updated_at: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_wish(row: sqlite3.Row) -> Wish:
    return Wish(
        id=row["id"],
        source=row["source"],
        raw=row["raw"],
        status=row["status"],
        project=row["project"],
        playbook=row["playbook"],
        variables=json.loads(row["variables"]) if row["variables"] else {},
        analysis=row["analysis"],
        digest=row["digest"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def init_db() -> None:
    """Create wishes table if it doesn't exist."""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wishes (
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
        )
    """)
    conn.commit()
    conn.close()


def create_wish(source: str, raw: str, project: str | None = None) -> Wish:
    """Insert a new wish and return it."""
    init_db()
    now = _now()
    wish = Wish(
        id=str(uuid4()),
        source=source,
        raw=raw,
        status="pending",
        project=project,
        created_at=now,
        updated_at=now,
    )
    conn = _connect()
    conn.execute(
        """
        INSERT INTO wishes (id, source, raw, status, project, playbook,
                            variables, analysis, digest, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wish.id, wish.source, wish.raw, wish.status,
            wish.project, wish.playbook, json.dumps(wish.variables),
            wish.analysis, wish.digest, wish.created_at, wish.updated_at,
        ),
    )
    conn.commit()
    conn.close()
    return wish


def get_wish(wish_id: str) -> Wish | None:
    """Fetch a wish by ID. Returns None if not found."""
    init_db()
    conn = _connect()
    row = conn.execute("SELECT * FROM wishes WHERE id = ?", (wish_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_wish(row)


def list_wishes(status: str | None = None, limit: int = 20) -> list[Wish]:
    """List wishes, optionally filtered by status."""
    init_db()
    conn = _connect()
    if status:
        rows = conn.execute(
            "SELECT * FROM wishes WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM wishes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [_row_to_wish(r) for r in rows]


def update_wish(wish_id: str, **fields: str | dict | None) -> None:
    """Update any fields on a wish."""
    if not fields:
        return
    # Serialize variables dict to JSON if present
    if "variables" in fields and isinstance(fields["variables"], dict):
        fields["variables"] = json.dumps(fields["variables"])
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [wish_id]
    conn = _connect()
    conn.execute(f"UPDATE wishes SET {set_clause} WHERE id = ?", values)  # noqa: S608
    conn.commit()
    conn.close()


def pending_wishes() -> list[Wish]:
    """Shortcut: list all pending wishes."""
    return list_wishes(status="pending")


def approve_wish(wish_id: str) -> None:
    """Set wish status to approved."""
    update_wish(wish_id, status="approved")


def reject_wish(wish_id: str) -> None:
    """Set wish status to failed."""
    update_wish(wish_id, status="failed")
