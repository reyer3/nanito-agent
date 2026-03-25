"""Interactive questionnaire for nanito-agent setup."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()

ROLES = {
    "1": ("dev", "Software Developer"),
    "2": ("analyst", "BI / Data Analyst"),
    "3": ("pm", "Project Manager"),
    "4": ("ops", "DevOps / Infrastructure"),
    "5": ("director", "Director / Tech Lead"),
}

LEVELS = {
    "1": ("junior", "Junior — explain concepts, guide step by step"),
    "2": ("mid", "Mid — explain decisions, not basics"),
    "3": ("senior", "Senior — be direct, peer-level, skip explanations"),
}

STYLES = {
    "1": ("direct", "Directo — al grano, sin explicaciones extra"),
    "2": ("mentor", "Mentor — explica el por qué, enseña mientras trabaja"),
    "3": ("peer", "Par — trata como colega, desafía ideas"),
}

LANGUAGES = ["Python", "TypeScript", "JavaScript", "SQL", "Go", "Rust", "Java"]

PLUGIN_PRESETS = {
    "1": ("full", "Full — context-mode, autoresearch, superpowers, code-review, context7, playwright, document-skills"),
    "2": ("core", "Core — context-mode, superpowers, code-review, context7"),
    "3": ("minimal", "Minimal — solo context-mode y context7"),
}

PERMISSION_MODES = {
    "1": ("bypass", "Bypass — sin confirmaciones (para usuarios avanzados)"),
    "2": ("default", "Default — pide confirmación para operaciones riesgosas"),
}


def run_questionnaire() -> dict:
    """Run the interactive setup questionnaire. Returns a profile dict."""
    console.print("[dim]Unas preguntas para configurar tu agente.[/dim]\n")

    # 1. Name
    name = Prompt.ask("[bold]Cómo te llamás?[/bold]")

    # 2. Role
    _show_options(ROLES)
    role_key = Prompt.ask("Tu rol", choices=list(ROLES.keys()) + ["other"], default="1")
    if role_key == "other":
        role_id = "custom"
        role_label = Prompt.ask("Describí tu rol en una frase")
    else:
        role_id, role_label = ROLES[role_key]

    # 3. Technical level
    _show_options(LEVELS)
    level_key = Prompt.ask("Nivel técnico", choices=list(LEVELS.keys()), default="3")
    level_id, level_label = LEVELS[level_key]

    # 4. Languages
    console.print(f"\n[bold]Qué lenguajes usás?[/bold] [dim]({', '.join(LANGUAGES)})[/dim]")
    langs_input = Prompt.ask("Separados por coma", default="Python, TypeScript")
    langs = [lang.strip() for lang in langs_input.split(",") if lang.strip()]

    # 5. Communication style
    _show_options(STYLES)
    style_key = Prompt.ask("Cómo preferís que te hable", choices=list(STYLES.keys()), default="1")
    style_id, style_label = STYLES[style_key]

    # 6. ADHD / structured responses
    adhd = Confirm.ask("\n[bold]Preferís respuestas ultra-estructuradas?[/bold] (key point first, no walls of text)", default=True)

    # 7. Non-negotiables
    non_negotiables = Prompt.ask(
        "\n[bold]Qué es lo que más te importa proteger?[/bold] [dim](ej: calidad técnica, mi equipo, seguridad)[/dim]",
        default="Technical quality",
    )

    # 8. Team context (optional)
    has_team_context = Confirm.ask("\n[bold]Querés agregar contexto de tu equipo/empresa?[/bold]", default=False)
    team_context = ""
    if has_team_context:
        team_context = Prompt.ask("Describí brevemente tu contexto (empresa, equipo, stack)")

    # 9. Plugin preset
    console.print("\n[bold]Qué plugins querés instalar?[/bold]")
    _show_options(PLUGIN_PRESETS)
    preset_key = Prompt.ask("Preset", choices=list(PLUGIN_PRESETS.keys()), default="1")
    preset_id, _ = PLUGIN_PRESETS[preset_key]

    # 10. Permission mode
    console.print("\n[bold]Modo de permisos?[/bold]")
    _show_options(PERMISSION_MODES)
    perm_key = Prompt.ask("Permisos", choices=list(PERMISSION_MODES.keys()), default="1")
    perm_id, _ = PERMISSION_MODES[perm_key]

    profile = {
        "name": name,
        "role_id": role_id,
        "role_label": role_label,
        "level_id": level_id,
        "level_label": level_label,
        "languages": langs,
        "primary_language": langs[0] if langs else "Python",
        "style_id": style_id,
        "style_label": style_label,
        "adhd": adhd,
        "non_negotiables": non_negotiables,
        "team_context": team_context,
        "plugin_preset": preset_id,
        "permission_mode": perm_id,
    }

    # Show summary
    _show_summary(profile)

    if not Confirm.ask("\n[bold]Todo bien?[/bold]", default=True):
        console.print("[yellow]Cancelado. Corré nanito-agent setup de nuevo.[/yellow]")
        raise SystemExit(0)

    return profile


def _show_options(options: dict[str, tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    for key, (_, label) in options.items():
        table.add_row(f"[bold]{key}[/bold]", label)
    console.print(table)


def _show_summary(profile: dict) -> None:
    console.print("\n[bold]--- Resumen ---[/bold]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Nombre", profile["name"])
    table.add_row("Rol", profile["role_label"])
    table.add_row("Nivel", profile["level_label"])
    table.add_row("Lenguajes", ", ".join(profile["languages"]))
    table.add_row("Estilo", profile["style_label"])
    table.add_row("Estructurado", "Sí" if profile["adhd"] else "No")
    table.add_row("Protege", profile["non_negotiables"])
    if profile["team_context"]:
        table.add_row("Contexto", profile["team_context"])
    table.add_row("Plugins", profile["plugin_preset"])
    table.add_row("Permisos", profile["permission_mode"])
    console.print(table)
