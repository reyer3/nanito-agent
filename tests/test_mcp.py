"""Tests for MCP server detection and prompt injection."""

import json
from pathlib import Path
from unittest.mock import patch

from nanito_agent.mcp import MCP_CAPABILITIES, MCPContext


def _mock_settings(mcp_servers: dict, plugins: dict | None = None):
    """Create a mock settings.json content."""
    return json.dumps({
        "mcpServers": mcp_servers,
        "enabledPlugins": plugins or {},
    })


def test_detect_engram():
    """Detect engram from mcpServers."""
    settings = _mock_settings({"engram": {"command": "engram"}})
    with patch("nanito_agent.mcp.SETTINGS_FILE") as mock_path:
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = settings
        ctx = MCPContext.detect()
    assert ctx.has_engram is True


def test_detect_context_mode_from_plugin():
    """Detect context-mode from enabledPlugins."""
    settings = _mock_settings(
        {},
        {"context-mode@context-mode": True},
    )
    with patch("nanito_agent.mcp.SETTINGS_FILE") as mock_path:
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = settings
        ctx = MCPContext.detect()
    assert ctx.has_context_mode is True


def test_detect_nothing():
    """No MCP servers configured."""
    settings = _mock_settings({})
    with patch("nanito_agent.mcp.SETTINGS_FILE") as mock_path:
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = settings
        ctx = MCPContext.detect()
    assert len(ctx.available) == 0


def test_detect_no_settings_file():
    """Handle missing settings file."""
    with patch("nanito_agent.mcp.SETTINGS_FILE") as mock_path:
        mock_path.exists.return_value = False
        ctx = MCPContext.detect()
    assert len(ctx.available) == 0


def test_to_prompt_section_with_tools():
    """Generate prompt section with available tools."""
    ctx = MCPContext(available={
        "serena": MCP_CAPABILITIES["serena"],
    })
    section = ctx.to_prompt_section()
    assert section is not None
    assert "serena" in section
    assert "serena_get_symbols" in section
    assert "When to use" in section


def test_to_prompt_section_empty():
    """No section when no tools available."""
    ctx = MCPContext()
    assert ctx.to_prompt_section() is None


def test_has_properties():
    """Boolean properties for common servers."""
    ctx = MCPContext(available={
        "serena": MCP_CAPABILITIES["serena"],
        "engram": MCP_CAPABILITIES["engram"],
    })
    assert ctx.has_serena is True
    assert ctx.has_engram is True
    assert ctx.has_context_mode is False
