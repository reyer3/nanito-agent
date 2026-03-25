"""Tests for CLAUDE.md template rendering."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _render(profile: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), keep_trailing_newline=True)
    template = env.get_template("CLAUDE.md.j2")
    return template.render(**profile)


def _base_profile(**overrides) -> dict:
    defaults = {
        "name": "Test User",
        "role_id": "dev",
        "role_label": "Software Developer",
        "level_id": "senior",
        "level_label": "Senior",
        "languages": ["Python", "TypeScript"],
        "primary_language": "Python",
        "style_id": "direct",
        "style_label": "Directo",
        "adhd": False,
        "non_negotiables": "Technical quality",
        "team_context": "",
    }
    defaults.update(overrides)
    return defaults


def test_renders_without_error():
    result = _render(_base_profile())
    assert "Test User" in result
    assert "## Identity" in result


def test_includes_python_standards():
    result = _render(_base_profile(languages=["Python"]))
    assert "### Python" in result
    assert "uv" in result


def test_excludes_python_when_not_selected():
    result = _render(_base_profile(languages=["Go"]))
    assert "### Python" not in result
    assert "### Go" in result


def test_includes_typescript_standards():
    result = _render(_base_profile(languages=["TypeScript"]))
    assert "### TypeScript" in result


def test_adhd_adds_structure_rules():
    result = _render(_base_profile(adhd=True))
    assert "key point first" in result
    assert "should we continue" in result


def test_no_adhd_skips_structure_rules():
    result = _render(_base_profile(adhd=False))
    assert "key point first" not in result


def test_senior_peer_treatment():
    result = _render(_base_profile(level_id="senior"))
    assert "peer" in result.lower()


def test_junior_guide_treatment():
    result = _render(_base_profile(level_id="junior"))
    assert "learning" in result.lower() or "guide" in result.lower()


def test_mentor_style():
    result = _render(_base_profile(style_id="mentor"))
    assert "Explain the why" in result


def test_direct_style():
    result = _render(_base_profile(style_id="direct"))
    assert "Be direct" in result


def test_team_context_included():
    result = _render(_base_profile(team_context="Fintech startup, 5 devs"))
    assert "Fintech startup" in result


def test_team_context_empty():
    result = _render(_base_profile(team_context=""))
    assert "Fintech" not in result


def test_non_negotiables_present():
    result = _render(_base_profile(non_negotiables="Security and family"))
    assert "Security and family" in result


def test_security_section_always_present():
    result = _render(_base_profile())
    assert "## Security Boundaries" in result
    assert "Never Do" in result


def test_instincts_always_present():
    result = _render(_base_profile())
    assert "## Behavioral Rules" in result
    assert "Spec-Driven Development" in result


def test_memory_protocol_always_present():
    result = _render(_base_profile())
    assert "## Memory Protocol" in result
    assert "mem_save" in result


def test_sql_standards():
    result = _render(_base_profile(languages=["SQL"]))
    assert "### SQL" in result
    assert "parameterized" in result
