"""Tests for the nanito-agent web UI."""

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
