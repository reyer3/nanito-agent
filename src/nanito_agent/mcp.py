"""MCP server detection — discovers available MCP tools for agent prompts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SETTINGS_FILE = Path.home() / ".claude" / "settings.json"

# MCP capabilities that agents can leverage
MCP_CAPABILITIES = {
    "serena": {
        "description": "Semantic code analysis via LSP",
        "tools": [
            "serena_get_symbols — list functions/classes/imports in a file",
            "serena_find_references — find all usages of a symbol",
            "serena_get_definition — jump to symbol definition",
            "serena_get_hover — get type info and docs for a symbol",
            "serena_edit_symbol — edit a function/class by name (token-efficient)",
            "serena_search_symbols — search across codebase by symbol name",
        ],
        "when_to_use": (
            "Use Serena for code navigation and understanding. "
            "Prefer serena_get_symbols over Grep for finding functions. "
            "Prefer serena_edit_symbol over Edit for modifying functions. "
            "Use serena_find_references before refactoring to find all callers."
        ),
    },
    "context-mode": {
        "description": "Sandboxed execution with FTS5 indexing",
        "tools": [
            "ctx_batch_execute — run multiple commands + search in ONE call",
            "ctx_execute — run code in sandbox (11 languages), output stays indexed",
            "ctx_search — query previously indexed content",
            "ctx_fetch_and_index — fetch web docs and auto-index",
        ],
        "when_to_use": (
            "Use context-mode for ANY command producing >20 lines of output. "
            "Use ctx_batch_execute instead of multiple Bash calls. "
            "Use ctx_execute for test runs, build output, log analysis. "
            "Index agent outputs with ctx_index for efficient cross-phase search."
        ),
    },
    "engram": {
        "description": "Persistent memory across sessions",
        "tools": [
            "mem_save — save a memory for future sessions",
            "mem_search — search past memories",
            "mem_context — load project context",
        ],
        "when_to_use": (
            "Save notable discoveries, decisions, and bug fixes to Engram. "
            "Search Engram before starting work to check for prior learnings."
        ),
    },
}


@dataclass
class MCPContext:
    """Available MCP servers and their capabilities for agent injection."""

    available: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def detect(cls) -> MCPContext:
        """Detect which MCP servers are configured in settings."""
        ctx = cls()
        if not SETTINGS_FILE.exists():
            return ctx

        try:
            settings = json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return ctx

        mcp_servers = settings.get("mcpServers", {})
        # Also check plugins that provide MCP servers
        enabled_plugins = settings.get("enabledPlugins", {})

        for name, caps in MCP_CAPABILITIES.items():
            # Check direct MCP server config
            if name in mcp_servers:
                ctx.available[name] = caps
                continue
            # Check if provided by an enabled plugin
            for plugin_key in enabled_plugins:
                if name in plugin_key and enabled_plugins[plugin_key]:
                    ctx.available[name] = caps
                    break

        return ctx

    @property
    def has_serena(self) -> bool:
        return "serena" in self.available

    @property
    def has_context_mode(self) -> bool:
        return "context-mode" in self.available

    @property
    def has_engram(self) -> bool:
        return "engram" in self.available

    def to_prompt_section(self) -> str | None:
        """Generate a prompt section describing available MCP tools."""
        if not self.available:
            return None

        lines = ["## Available MCP Tools", ""]
        for name, caps in self.available.items():
            lines.append(f"### {name} — {caps['description']}")
            lines.append("")
            for tool in caps["tools"]:
                lines.append(f"- `{tool}`")
            lines.append("")
            lines.append(f"**When to use:** {caps['when_to_use']}")
            lines.append("")

        return "\n".join(lines)
