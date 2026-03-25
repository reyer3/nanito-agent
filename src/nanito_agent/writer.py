"""Config writer — generates and installs Claude Code configuration."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

console = Console()

CLAUDE_DIR = Path.home() / ".claude"
HOOKS_DIR = CLAUDE_DIR / "hooks"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
CLAUDE_MD = CLAUDE_DIR / "CLAUDE.md"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def install_config(profile: dict) -> None:
    """Install nanito-agent configuration based on user profile."""
    _backup_existing()
    _write_claude_md(profile)
    _install_hooks()
    _patch_settings(profile)
    _check_engram()
    _check_ccboard()
    _check_superclaude()


def _backup_existing() -> None:
    """Backup existing config files before overwriting."""
    backup_dir = CLAUDE_DIR / "backups" / f"nanito-{datetime.now():%Y%m%d-%H%M%S}"

    files_to_backup = [CLAUDE_MD, SETTINGS_FILE]
    existing = [f for f in files_to_backup if f.exists()]

    if not existing:
        return

    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in existing:
        shutil.copy2(f, backup_dir / f.name)
        console.print(f"  [dim]Backup: {f.name} → {backup_dir.name}/[/dim]")


def _write_claude_md(profile: dict) -> None:
    """Render and write CLAUDE.md from template."""
    templates_dir = _find_templates_dir()
    env = Environment(loader=FileSystemLoader(str(templates_dir)), keep_trailing_newline=True)
    template = env.get_template("CLAUDE.md.j2")

    content = template.render(**profile)
    CLAUDE_MD.write_text(content)
    console.print("  [green]CLAUDE.md[/green] written")


def _install_hooks() -> None:
    """Copy hook scripts to ~/.claude/hooks/."""
    templates_dir = _find_templates_dir()
    hooks_src = templates_dir / "hooks"

    if not hooks_src.exists():
        console.print("  [yellow]No hooks found in templates[/yellow]")
        return

    HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for pattern in ("*.sh", "*.py"):
        for hook_file in hooks_src.glob(pattern):
            dest = HOOKS_DIR / hook_file.name
            shutil.copy2(hook_file, dest)
            dest.chmod(0o755)
            count += 1

    console.print(f"  [green]{count} hooks[/green] installed")


def _patch_settings(profile: dict) -> None:
    """Merge nanito config into settings.json: plugins, hooks, MCP, env, flags."""
    from nanito_agent.plugins import (
        GLOBAL_ENV,
        GLOBAL_SETTINGS,
        MARKETPLACES,
        PLUGIN_PRESETS,
    )

    settings = {}
    if SETTINGS_FILE.exists():
        settings = json.loads(SETTINGS_FILE.read_text())

    # --- Global settings flags ---
    for key, value in GLOBAL_SETTINGS.items():
        settings[key] = value

    # --- Environment variables ---
    env = settings.setdefault("env", {})
    for key, value in GLOBAL_ENV.items():
        env[key] = value

    # --- Permission mode ---
    permissions = settings.setdefault("permissions", {})
    perm_mode = profile.get("permission_mode", "default")
    if perm_mode == "bypass":
        permissions["defaultMode"] = "bypassPermissions"
        settings["skipDangerousModePermissionPrompt"] = True
    else:
        permissions.pop("defaultMode", None)
        settings.pop("skipDangerousModePermissionPrompt", None)

    # --- Deny list ---
    deny = permissions.setdefault("deny", [])
    nanito_deny = [
        "Bash(rm -rf /)",
        "Bash(rm -rf ~)",
        "Bash(*fork bomb*)",
        "Bash(chmod -R 777*)",
        "Bash(curl*|sh)",
        "Bash(wget*|sh)",
    ]
    for rule in nanito_deny:
        if rule not in deny:
            deny.append(rule)

    # --- Plugins ---
    preset_id = profile.get("plugin_preset", "core")
    preset_plugins = PLUGIN_PRESETS.get(preset_id, PLUGIN_PRESETS["core"])
    enabled = settings.setdefault("enabledPlugins", {})
    for plugin_name, is_enabled in preset_plugins.items():
        enabled[plugin_name] = is_enabled

    # --- Marketplaces ---
    marketplaces = settings.setdefault("extraKnownMarketplaces", {})
    for name, source in MARKETPLACES.items():
        if name not in marketplaces:
            marketplaces[name] = {"source": source}

    # --- Engram MCP ---
    mcp_servers = settings.setdefault("mcpServers", {})
    if "engram" not in mcp_servers:
        mcp_servers["engram"] = {
            "command": "engram",
            "args": ["mcp", "--tools=all"],
            "timeout": 30000,
            "env": {},
        }

    # --- Timeouts for MCPs that lack them ---
    # NOTE: Do NOT add "env": {} to existing MCPs — it kills environment
    # variable inheritance and breaks servers that need credentials (email, etc.)
    for _server_name, server_config in mcp_servers.items():
        if isinstance(server_config, dict) and "timeout" not in server_config:
            server_config["timeout"] = 30000

    # Ensure hooks
    hooks_dir_str = str(HOOKS_DIR)
    hooks = settings.setdefault("hooks", {})

    _ensure_hook(hooks, "PreToolUse", "Bash", [
        f"bash {hooks_dir_str}/block-no-verify.sh",
        f"bash {hooks_dir_str}/git-push-guard.sh",
    ])
    _ensure_hook(hooks, "PreToolUse", "Edit|Write", [
        f"bash {hooks_dir_str}/config-protection.sh",
    ])
    _ensure_hook(hooks, "PostToolUse", "Edit|Write", [
        f"bash {hooks_dir_str}/console-warn.sh",
        f"bash {hooks_dir_str}/test-nudge.sh",
    ])
    # Session monitor — logs all events to SQLite
    monitor_cmd = f"python3 {hooks_dir_str}/session-monitor.py"
    _ensure_hook(hooks, "PreToolUse", "*", [monitor_cmd])
    _ensure_hook(hooks, "SessionStart", "*", [
        f"bash {hooks_dir_str}/session-start.sh",
        monitor_cmd,
    ], timeout=5000)
    _ensure_hook(hooks, "Stop", "*", [
        f"bash {hooks_dir_str}/session-end.sh",
        monitor_cmd,
    ], timeout=5000)
    _ensure_hook(hooks, "PreCompact", "*", [
        f"bash {hooks_dir_str}/pre-compact.sh",
        monitor_cmd,
    ], timeout=5000)

    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    console.print(f"  [green]settings.json[/green] patched:")
    console.print(f"    Plugins: {preset_id} ({len(preset_plugins)} enabled)")
    console.print(f"    Marketplaces: {len(MARKETPLACES)} registered")
    console.print(f"    Hooks: 6 lifecycle events")
    console.print(f"    Security: deny list + MCP timeouts + env isolation")


def _ensure_hook(
    hooks: dict,
    event: str,
    matcher: str,
    commands: list[str],
    timeout: int | None = None,
) -> None:
    """Add hook commands if not already present."""
    event_hooks = hooks.setdefault(event, [])

    # Find existing matcher group or create one
    group = None
    for g in event_hooks:
        if g.get("matcher") == matcher:
            group = g
            break

    if group is None:
        group = {"matcher": matcher, "hooks": []}
        event_hooks.append(group)

    existing_commands = {h.get("command") for h in group["hooks"]}
    for cmd in commands:
        if cmd not in existing_commands:
            hook_entry: dict = {"type": "command", "command": cmd}
            if timeout:
                hook_entry["timeout"] = timeout
            group["hooks"].append(hook_entry)


def _check_engram() -> None:
    """Check if Engram is installed. Offer to install if not."""
    import subprocess

    if shutil.which("engram"):
        console.print("  [green]Engram[/green] detected")
        return

    console.print("  [yellow]Engram not found.[/yellow]")

    if not shutil.which("go"):
        console.print(
            "    Go not installed. Install Engram manually:"
            "\n    [dim]https://github.com/Gentleman-Programming/engram/releases[/dim]"
        )
        return

    from rich.prompt import Confirm

    if Confirm.ask("    Install Engram via go install?", default=True):
        console.print("    [dim]Installing...[/dim]")
        result = subprocess.run(
            ["go", "install", "github.com/Gentleman-Programming/engram/cmd/engram@latest"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("    [green]Engram installed[/green]")
        else:
            console.print(f"    [red]Install failed:[/red] {result.stderr[:200]}")
    else:
        console.print(
            "    Install later: "
            "[dim]go install github.com/Gentleman-Programming/engram/cmd/engram@latest[/dim]"
        )


def _check_ccboard() -> None:
    """Check if ccboard is installed for real-time session monitoring."""
    if shutil.which("ccboard"):
        console.print("  [green]ccboard[/green] detected")
        return

    console.print(
        "  [yellow]ccboard not found.[/yellow] Recommended for real-time session monitoring."
        "\n    Install:"
        "\n    [dim]curl -sSL https://raw.githubusercontent.com/FlorianBruniaux/ccboard/main/install.sh | bash[/dim]"
        "\n    Or download: [dim]https://github.com/FlorianBruniaux/ccboard/releases/latest[/dim]"
    )


def _check_superclaude() -> None:
    """Check if SuperClaude commands are installed."""
    sc_dir = CLAUDE_DIR / "commands" / "sc"
    if sc_dir.exists() and len(list(sc_dir.glob("*.md"))) > 10:
        count = len(list(sc_dir.glob("*.md")))
        console.print(f"  [green]SuperClaude[/green] detected ({count} commands)")
    else:
        console.print(
            "  [yellow]SuperClaude not found.[/yellow] Optional but recommended:"
            "\n    [dim]npx superclaude install[/dim]"
            "\n    Adds 31 /sc commands (brainstorm, implement, test, review, etc.)"
        )


def _find_templates_dir() -> Path:
    """Find templates directory — works in dev and installed mode."""
    candidates = [
        Path(__file__).parent / "templates",            # installed package
        Path(__file__).parent.parent.parent / "templates",  # dev mode (repo root)
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "CLAUDE.md.j2").exists():
            return candidate

    msg = "Templates directory not found. Reinstall nanito-agent."
    raise FileNotFoundError(msg)
