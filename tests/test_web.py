"""Tests for the nanito-agent web UI."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from nanito_agent.web import app

client = TestClient(app)


def test_dashboard_returns_200() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_dashboard_contains_stat_cards() -> None:
    response = client.get("/")
    assert "Agents" in response.text
    assert "Playbooks" in response.text
    assert "Sessions" in response.text


def test_playbooks_returns_200() -> None:
    response = client.get("/playbooks")
    assert response.status_code == 200
    assert "build-saas" in response.text


def test_playbook_detail_returns_200() -> None:
    response = client.get("/playbooks/build-saas")
    assert response.status_code == 200
    assert "Phase" in response.text


def test_playbook_detail_not_found() -> None:
    response = client.get("/playbooks/nonexistent-playbook")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_playbook_run_post() -> None:
    response = client.post("/playbooks/build-saas/run")
    assert response.status_code == 200
    assert "plan" in response.text.lower() or "execution" in response.text.lower()


def test_agents_returns_200() -> None:
    response = client.get("/agents")
    assert response.status_code == 200
    assert "architect" in response.text.lower() or "Agents" in response.text


def test_sessions_returns_200() -> None:
    response = client.get("/sessions")
    assert response.status_code == 200
    assert "Sessions" in response.text


def test_api_status_returns_json() -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "agents" in data
    assert "playbooks" in data
    assert "mcp" in data
    assert "engram" in data
    assert data["status"] == "ok"


def test_session_detail_not_found() -> None:
    response = client.get("/sessions/nonexistent-id")
    assert response.status_code == 200
    assert "No events found" in response.text


# ---------------------------------------------------------------------------
# Mission Control / Wishes tests
# ---------------------------------------------------------------------------


def test_wishes_page_returns_200() -> None:
    response = client.get("/wishes")
    assert response.status_code == 200
    assert "Mission Control" in response.text


def test_wishes_page_shows_empty_state_without_db() -> None:
    """When inbox module and DB are unavailable, show empty state."""
    with (
        patch("nanito_agent.web.HAS_INBOX", False),
        patch("nanito_agent.web.WISHES_DB", Path("/tmp/nonexistent-nanito-test.db")),
    ):
        response = client.get("/wishes")
        assert response.status_code == 200
        assert "No wishes yet" in response.text


def test_wishes_api_returns_json() -> None:
    response = client.get("/api/wishes")
    assert response.status_code == 200
    data = response.json()
    assert "wishes" in data
    assert "total" in data
    assert "page" in data


def test_create_wish_via_form() -> None:
    response = client.post(
        "/wishes",
        data={"raw": "test wish from form"},
        follow_redirects=False,
    )
    # Should redirect to /wishes
    assert response.status_code == 303
    assert response.headers.get("location") == "/wishes"


def test_create_wish_via_api() -> None:
    response = client.post(
        "/api/wishes",
        json={"raw": "test wish from api", "source": "test"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["raw"] == "test wish from api"
    assert data["status"] == "pending"


def test_wish_detail_not_found() -> None:
    response = client.get("/wishes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_wish_detail_shows_content() -> None:
    # Create a wish first
    resp = client.post("/api/wishes", json={"raw": "detail test wish"})
    wish_id = resp.json()["id"]
    response = client.get(f"/wishes/{wish_id}")
    assert response.status_code == 200
    assert "detail test wish" in response.text


def test_wish_approve_via_api() -> None:
    resp = client.post("/api/wishes", json={"raw": "approve me"})
    wish_id = resp.json()["id"]
    response = client.post(f"/api/wishes/{wish_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_wish_approve_not_found() -> None:
    response = client.post("/api/wishes/00000000-0000-0000-0000-000000000000/approve")
    assert response.status_code == 404


def test_wish_reject_htmx() -> None:
    resp = client.post("/api/wishes", json={"raw": "reject me"})
    wish_id = resp.json()["id"]
    response = client.post(f"/wishes/{wish_id}/reject")
    assert response.status_code == 200
    assert "rejected" in response.text.lower()


def test_api_status_includes_wishes() -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "wishes" in data


def test_api_wish_detail_not_found() -> None:
    response = client.get("/api/wishes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"] == "not found"


def test_api_wish_create_missing_raw() -> None:
    response = client.post("/api/wishes", json={"source": "test"})
    assert response.status_code == 400


def test_navigation_includes_mission_control() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Mission Control" in response.text
