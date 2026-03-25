"""Plugin and marketplace definitions for nanito-agent."""

from __future__ import annotations

# Marketplaces to register (source repos for plugin discovery)
MARKETPLACES = {
    "context-mode": {"source": "github", "repo": "mksglu/context-mode"},
    "autoresearch": {"source": "github", "repo": "uditgoenka/autoresearch"},
    "anthropic-agent-skills": {"source": "github", "repo": "anthropics/skills"},
    "ui-ux-pro-max-skill": {"source": "github", "repo": "nextlevelbuilder/ui-ux-pro-max-skill"},
    "pipecat-skills": {"source": "github", "repo": "pipecat-ai/skills"},
}

# Plugin presets — which plugins to enable per preset level
PLUGIN_PRESETS: dict[str, dict[str, bool]] = {
    "full": {
        "context-mode@context-mode": True,
        "autoresearch@autoresearch": True,
        "superpowers@claude-plugins-official": True,
        "code-review@claude-plugins-official": True,
        "context7@claude-plugins-official": True,
        "playwright@claude-plugins-official": True,
        "skill-creator@claude-plugins-official": True,
        "agent-sdk-dev@claude-plugins-official": True,
        "document-skills@anthropic-agent-skills": True,
        "example-skills@anthropic-agent-skills": True,
        "frontend-design@claude-plugins-official": True,
        "ui-ux-pro-max@ui-ux-pro-max-skill": True,
        "playground@claude-plugins-official": True,
    },
    "core": {
        "context-mode@context-mode": True,
        "superpowers@claude-plugins-official": True,
        "code-review@claude-plugins-official": True,
        "context7@claude-plugins-official": True,
    },
    "minimal": {
        "context-mode@context-mode": True,
        "context7@claude-plugins-official": True,
    },
}

# Global settings that nanito-agent always configures
GLOBAL_SETTINGS = {
    "effortLevel": "high",
    "autoUpdatesChannel": "latest",
    "teammateMode": "tmux",
    "skipDangerousModePermissionPrompt": True,
}

GLOBAL_ENV = {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
}
