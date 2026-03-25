"""Tests for the wish inbox — SQLite-backed pub/sub."""

from __future__ import annotations

import os

import pytest

from nanito_agent.inbox import (
    DB_PATH,
    approve_wish,
    create_wish,
    get_wish,
    init_db,
    list_wishes,
    pending_wishes,
    reject_wish,
    update_wish,
)


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp dir for test isolation."""
    test_db = tmp_path / "nanito-wishes.db"
    monkeypatch.setattr("nanito_agent.inbox.DB_PATH", test_db)
    yield


def test_create_wish():
    wish = create_wish(source="terminal", raw="quiero un dashboard")
    assert wish.id
    assert wish.source == "terminal"
    assert wish.raw == "quiero un dashboard"
    assert wish.status == "pending"
    assert wish.created_at
    assert wish.updated_at


def test_create_wish_with_project():
    wish = create_wish(source="web", raw="build an API", project="my-project")
    assert wish.project == "my-project"


def test_list_wishes():
    create_wish(source="terminal", raw="wish 1")
    create_wish(source="web", raw="wish 2")
    create_wish(source="whatsapp", raw="wish 3")

    wishes = list_wishes()
    assert len(wishes) == 3


def test_list_wishes_filtered_by_status():
    w1 = create_wish(source="terminal", raw="pending one")
    w2 = create_wish(source="terminal", raw="will be approved")
    approve_wish(w2.id)

    pending = list_wishes(status="pending")
    assert len(pending) == 1
    assert pending[0].id == w1.id

    approved = list_wishes(status="approved")
    assert len(approved) == 1
    assert approved[0].id == w2.id


def test_update_wish_status():
    wish = create_wish(source="terminal", raw="test wish")
    update_wish(wish.id, status="analyzing")

    updated = get_wish(wish.id)
    assert updated is not None
    assert updated.status == "analyzing"


def test_update_wish_multiple_fields():
    wish = create_wish(source="terminal", raw="test wish")
    update_wish(wish.id, status="ready", playbook="fix-bug", analysis="found the bug")

    updated = get_wish(wish.id)
    assert updated is not None
    assert updated.status == "ready"
    assert updated.playbook == "fix-bug"
    assert updated.analysis == "found the bug"


def test_pending_wishes():
    create_wish(source="terminal", raw="pending 1")
    create_wish(source="terminal", raw="pending 2")
    w3 = create_wish(source="terminal", raw="will approve")
    approve_wish(w3.id)

    pending = pending_wishes()
    assert len(pending) == 2


def test_approve_wish():
    wish = create_wish(source="terminal", raw="approve me")
    approve_wish(wish.id)

    updated = get_wish(wish.id)
    assert updated is not None
    assert updated.status == "approved"


def test_reject_wish():
    wish = create_wish(source="terminal", raw="reject me")
    reject_wish(wish.id)

    updated = get_wish(wish.id)
    assert updated is not None
    assert updated.status == "failed"


def test_get_nonexistent_wish():
    init_db()
    result = get_wish("nonexistent-id-that-does-not-exist")
    assert result is None


def test_update_wish_variables():
    wish = create_wish(source="terminal", raw="test vars")
    update_wish(wish.id, variables={"key": "value", "project": "test"})

    updated = get_wish(wish.id)
    assert updated is not None
    assert updated.variables == {"key": "value", "project": "test"}


def test_list_wishes_respects_limit():
    for i in range(5):
        create_wish(source="terminal", raw=f"wish {i}")

    wishes = list_wishes(limit=3)
    assert len(wishes) == 3
