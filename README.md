# nanito-agent

Claude Code configurator for teams. One command to set up identity, memory, hooks, plugins, and security.

Born from real daily use building AI products at a LATAM contact center company — not a toy config, but a production-tested setup that handles context protection, persistent memory, implicit spec-driven development, and security hardening.

## What it does

`nanito-agent setup` asks 10 questions and configures your entire Claude Code environment:

| Component | What gets configured |
|---|---|
| **CLAUDE.md** | Personalized identity, coding standards, 15+ behavioral instincts, implicit SDD workflow, memory protocol, security boundaries |
| **8 hooks** | block-no-verify, git-push-guard, config-protection, console-warn, test-nudge, session-start, session-end, pre-compact |
| **13 plugins** | context-mode, autoresearch, superpowers, code-review, context7, playwright, and more (3 presets) |
| **Engram MCP** | Persistent memory across sessions (SQLite + FTS5 full-text search) |
| **Security** | Deny list (6 rules), MCP timeouts, env isolation, permission mode |
| **Settings** | effortLevel, teammateMode, agent teams, marketplaces |

## Install

```bash
# Setup (interactive — asks 10 questions, configures everything)
uvx nanito-agent setup

# Dry run (see what would be generated without writing)
uvx nanito-agent setup --dry-run

# Check current config status
uvx nanito-agent status
```

### Optional addons

```bash
# Persistent memory (recommended)
go install github.com/Gentleman-Programming/engram/cmd/engram@latest

# SuperClaude commands (31 /sc slash commands)
npx superclaude install
```

## The questionnaire

The setup asks 10 questions that customize the agent's personality and capabilities:

1. **Name** — How the agent addresses you
2. **Role** — Dev, BI Analyst, PM, Ops, Director
3. **Technical level** — Junior (guided), Mid (decisions explained), Senior (peer-level)
4. **Languages** — Python, TypeScript, SQL, Go, etc. (only relevant coding standards are included)
5. **Communication style** — Direct, Mentor, or Peer
6. **Structured responses** — ADHD-friendly formatting (key point first, no walls of text)
7. **Non-negotiables** — What you protect above all else
8. **Team context** — Optional: company, team, stack description
9. **Plugin preset** — Full (13), Core (4), or Minimal (2)
10. **Permission mode** — Bypass (no confirmations) or Default (confirms risky ops)

## What's inside

### Behavioral instincts

The generated CLAUDE.md includes 15+ trigger-based behavioral rules organized in four categories:

- **Security** — Never write secrets, never bypass hooks, never stage credentials, confirm before destructive ops
- **Code quality** — Preserve existing style, no premature abstractions, validate only at boundaries
- **Context management** — Use context-mode for large output, save to Engram before compaction, parallelize independent tasks
- **Implicit SDD** — Spec before code, plan if non-trivial, test alongside implementation, verify before claiming done, save learnings to memory

These aren't suggestions — they're encoded as instincts that fire automatically based on what Claude is doing.

### Hooks (8 scripts, 6 lifecycle events)

| Event | Hook | Effect |
|---|---|---|
| PreToolUse:Bash | `block-no-verify` | Hard-blocks `--no-verify` on git commands |
| PreToolUse:Bash | `git-push-guard` | Blocks force push, warns on push to main |
| PreToolUse:Edit/Write | `config-protection` | Warns before modifying linter/CI/Docker configs |
| PostToolUse:Edit/Write | `console-warn` | Detects leftover debug statements |
| PostToolUse:Edit/Write | `test-nudge` | Reminds about missing test files for edited source |
| SessionStart | `session-start` | Auto-loads Engram context for current project |
| Stop | `session-end` | Auto-saves session marker to Engram |
| PreCompact | `pre-compact` | Saves state to Engram before context compaction |

### Plugin presets

| Preset | Plugins | Use case |
|---|---|---|
| **full** | context-mode, autoresearch, superpowers, code-review, context7, playwright, skill-creator, agent-sdk-dev, document-skills, example-skills, frontend-design, ui-ux-pro-max, playground | Power users |
| **core** | context-mode, superpowers, code-review, context7 | Most developers |
| **minimal** | context-mode, context7 | Lightweight setup |

### Plugin side (optional)

nanito-agent also ships as a Claude Code plugin with:

- **3 agents**: planner (task breakdown), reviewer (code review), debugger (systematic debugging)
- **2 skills**: nanito-core (implicit SDD workflow), memory-protocol (Engram integration)
- **1 command**: `/nanito-setup` (setup instructions)

```bash
# Install the plugin (after CLI setup)
claude plugin marketplace add your-org/nanito-agent
claude plugin install nanito-agent
```

## How it works

The CLI generates config from Jinja2 templates based on your answers:

```
nanito-agent setup
  → Backup existing ~/.claude/CLAUDE.md and settings.json
  → Run 10-question questionnaire
  → Render CLAUDE.md from template with your profile
  → Copy 8 hook scripts to ~/.claude/hooks/
  → Patch settings.json (plugins, hooks, MCP, deny list, flags)
  → Check for Engram (offer install if Go available)
  → Check for SuperClaude (show install command if missing)
  → Done — restart Claude Code to activate
```

Existing settings.json values are preserved — nanito-agent merges, never overwrites.

## Security

- **Zero PII in the repo** — all personal info is generated at install time from your answers
- **Deny list** — blocks `rm -rf /`, `rm -rf ~`, fork bombs, `chmod -R 777`, pipe-to-shell
- **MCP hardening** — 30s timeout + explicit empty env block on all MCP servers
- **Hook protection** — blocks `--no-verify`, force push, warns on config changes
- **No secrets ever** — templates contain instructions to NEVER write secrets, not actual secrets

## Project structure

```
nanito-agent/
├── src/nanito_agent/
│   ├── cli.py              # Entry point: setup, status, --help
│   ├── questions.py         # 10-question interactive TUI (rich)
│   ├── writer.py            # Generates CLAUDE.md, patches settings.json, installs hooks
│   ├── status.py            # Shows current config status table
│   ├── plugins.py           # Plugin presets, marketplaces, global settings
│   └── templates/           # Bundled templates (for uvx installs)
├── templates/
│   ├── CLAUDE.md.j2         # Jinja2 template (identity + fixed instincts)
│   └── hooks/*.sh           # 8 hook scripts
├── plugin/                  # Claude Code plugin (agents, skills, commands)
├── .claude-plugin/          # Marketplace manifest
├── tests/                   # 22 tests
├── pyproject.toml           # uv package config
└── README.md
```

## Development

```bash
git clone https://github.com/your-org/nanito-agent
cd nanito-agent
uv sync --group dev
uv run pytest tests/ -v
```

## Inspired by

- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Hook architecture, instincts format, AgentShield
- [engram](https://github.com/Gentleman-Programming/engram) — Persistent memory via MCP
- [gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) — Ecosystem configurator concept, SDD workflow
- [agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) — Plugin architecture patterns

## License

MIT
