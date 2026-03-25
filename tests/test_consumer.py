"""Tests for the wish consumer — classify, analyze, digest, process."""

from __future__ import annotations

import pytest

from nanito_agent.consumer import (
    analyze_wish,
    classify_wish,
    digest_wish,
    process_pending,
)
from nanito_agent.inbox import create_wish, get_wish, init_db, pending_wishes


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp dir for test isolation."""
    test_db = tmp_path / "nanito-wishes.db"
    monkeypatch.setattr("nanito_agent.inbox.DB_PATH", test_db)
    yield


# --- classify_wish ---


def test_classify_bug():
    wish = create_wish(source="terminal", raw="hay un bug en el login")
    playbook, variables = classify_wish(wish)
    assert playbook == "fix-bug"
    assert "wish" in variables


def test_classify_bug_english():
    wish = create_wish(source="terminal", raw="fix the error in payment module")
    playbook, _ = classify_wish(wish)
    assert playbook == "fix-bug"


def test_classify_build_api():
    wish = create_wish(source="terminal", raw="build a REST API for users")
    playbook, _ = classify_wish(wish)
    assert playbook == "build-api"


def test_classify_build_api_spanish():
    wish = create_wish(source="terminal", raw="crear un endpoint para usuarios")
    playbook, _ = classify_wish(wish)
    assert playbook == "build-api"


def test_classify_saas():
    wish = create_wish(source="terminal", raw="quiero una app SaaS para facturacion")
    playbook, _ = classify_wish(wish)
    assert playbook == "build-saas"


def test_classify_dashboard():
    wish = create_wish(source="terminal", raw="necesito un dashboard de metricas")
    playbook, _ = classify_wish(wish)
    assert playbook == "build-dashboard"


def test_classify_ship():
    wish = create_wish(source="terminal", raw="deploy the latest version")
    playbook, _ = classify_wish(wish)
    assert playbook == "ship"


def test_classify_scenarios():
    wish = create_wish(source="terminal", raw="que pasa si el servidor se cae")
    playbook, _ = classify_wish(wish)
    assert playbook == "explore-scenarios"


def test_classify_unknown():
    wish = create_wish(source="terminal", raw="necesito algo completamente diferente")
    playbook, _ = classify_wish(wish)
    assert playbook == "manual"


# --- analyze_wish ---


def test_analyze_wish_returns_structured():
    wish = create_wish(source="terminal", raw="fix the auth bug")
    wish.playbook = "fix-bug"
    analysis = analyze_wish(wish)
    assert "fix-bug" in analysis
    assert "fix the auth bug" in analysis


# --- digest_wish ---


def test_digest_format_has_all_fields():
    wish = create_wish(source="terminal", raw="build a metrics dashboard")
    wish.playbook = "build-dashboard"
    wish.project = "bi-engine"
    analysis = analyze_wish(wish)
    digest = digest_wish(wish, analysis)

    assert "QUE:" in digest
    assert "POR QUE:" in digest
    assert "IMPACTO:" in digest
    assert "ACCION:" in digest
    assert "RIESGO:" in digest
    assert "DECISION:" in digest


def test_digest_includes_wish_text():
    wish = create_wish(source="terminal", raw="quiero un reporte de ventas")
    wish.playbook = "build-dashboard"
    analysis = analyze_wish(wish)
    digest = digest_wish(wish, analysis)

    assert "quiero un reporte de ventas" in digest


def test_digest_includes_source():
    wish = create_wish(source="whatsapp", raw="something")
    wish.playbook = "manual"
    analysis = analyze_wish(wish)
    digest = digest_wish(wish, analysis)

    assert "whatsapp" in digest


# --- process_pending ---


def test_process_pending_updates_status():
    create_wish(source="terminal", raw="hay un error en produccion")
    create_wish(source="web", raw="build a new feature API")

    processed = process_pending()
    assert len(processed) == 2

    for wish in processed:
        assert wish.status == "ready"
        assert wish.playbook is not None
        assert wish.analysis is not None
        assert wish.digest is not None

    # Verify DB was updated
    remaining_pending = pending_wishes()
    assert len(remaining_pending) == 0


def test_process_pending_classifies_correctly():
    create_wish(source="terminal", raw="fix this bug now")
    processed = process_pending()
    assert len(processed) == 1
    assert processed[0].playbook == "fix-bug"


def test_process_pending_empty():
    init_db()
    processed = process_pending()
    assert processed == []
