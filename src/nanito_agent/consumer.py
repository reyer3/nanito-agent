"""Wish consumer — classifies, analyzes, and digests pending wishes.

Reads pending wishes from the inbox, classifies them into playbooks,
runs analysis, and produces structured digests for human approval.
"""

from __future__ import annotations

import re

from nanito_agent.inbox import Wish, pending_wishes, update_wish

# Keyword → playbook mapping. Checked in order; first match wins.
_PLAYBOOK_RULES: list[tuple[list[str], str]] = [
    (["bug", "error", "fix", "arregla", "arreglar", "falla", "roto", "broken"], "fix-bug"),
    (["deploy", "ship", "subir", "desplegar", "release"], "ship"),
    (["dashboard", "reporte", "metricas", "metrics", "report", "chart"], "build-dashboard"),
    (["saas", "app", "aplicacion", "aplicaci\u00f3n", "producto", "product"], "build-saas"),
    (["build", "crear", "construir", "api", "endpoint", "feature", "nueva"], "build-api"),
    (["edge case", "scenario", "que pasa si", "what if", "escenario"], "explore-scenarios"),
]

# Fields required in a valid digest
_DIGEST_FIELDS = ("QUE:", "POR QUE:", "IMPACTO:", "ACCION:", "RIESGO:", "DECISION:")


def classify_wish(wish: Wish) -> tuple[str, dict]:
    """Classify a wish into a playbook + variables.

    Returns (playbook_name, variables_dict).
    Uses keyword matching against the raw wish text (case-insensitive).
    """
    text = wish.raw.lower()
    for keywords, playbook in _PLAYBOOK_RULES:
        for kw in keywords:
            if kw in text:
                return playbook, {"wish": wish.raw}
    return "manual", {"wish": wish.raw}


def analyze_wish(wish: Wish) -> str:
    """Run predictor-style analysis on a wish.

    Returns a structured analysis string.
    Actual Claude Code dispatch comes in a later phase — for now
    this produces a structured stub that downstream (digest) can consume.
    """
    playbook = wish.playbook or "unknown"
    return (
        f"## Analysis: {wish.raw}\n\n"
        f"Playbook: {playbook}\n"
        f"Project: {wish.project or 'not specified'}\n"
        f"Source: {wish.source}\n\n"
        f"### Scope\n"
        f"Wish requests: {wish.raw}\n\n"
        f"### Risk Assessment\n"
        f"Pending full predictor analysis via Claude Code dispatch.\n"
    )


def digest_wish(wish: Wish, analysis: str) -> str:
    """Generate digest from analysis.

    Formats the analysis into the standard QUE/POR QUE/IMPACTO/ACCION/RIESGO/DECISION
    structure. Full Claude-powered digestion comes in a later phase.
    """
    playbook = wish.playbook or "manual"
    project = wish.project or "no especificado"
    return (
        f"QUE: {wish.raw}\n"
        f"POR QUE: Solicitud del usuario via {wish.source}\n"
        f"IMPACTO: Proyecto {project}, playbook {playbook}\n"
        f"ACCION: Ejecutar playbook {playbook} con los parametros detectados\n"
        f"RIESGO: Sin analisis completo del predictor aun. Revisar antes de aprobar.\n"
        f"DECISION: need more info — confirmar alcance y proyecto destino"
    )


def process_pending() -> list[Wish]:
    """Process all pending wishes: classify -> analyze -> digest -> ready.

    Returns list of processed wishes (now in 'ready' status).
    """
    wishes = pending_wishes()
    processed: list[Wish] = []

    for wish in wishes:
        # Step 1: Classify
        update_wish(wish.id, status="analyzing")
        playbook, variables = classify_wish(wish)

        # Step 2: Analyze
        update_wish(wish.id, playbook=playbook, variables=variables)
        wish.playbook = playbook
        wish.variables = variables
        analysis = analyze_wish(wish)

        # Step 3: Digest
        digest = digest_wish(wish, analysis)

        # Step 4: Mark ready
        update_wish(
            wish.id,
            status="ready",
            analysis=analysis,
            digest=digest,
        )
        wish.status = "ready"
        wish.analysis = analysis
        wish.digest = digest
        processed.append(wish)

    return processed
