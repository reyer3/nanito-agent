---
description: Interactive setup for nanito-agent — configure identity and preferences
---

# nanito-agent Setup

Run the nanito-agent CLI to configure your Claude Code environment:

```bash
uvx nanito-agent setup
```

This will:
1. Ask you a few questions about your role, style, and preferences
2. Generate a personalized CLAUDE.md
3. Install security hooks
4. Configure Engram MCP for persistent memory
5. Patch settings.json with deny list and timeouts

For a dry run (see what would be generated without writing):
```bash
uvx nanito-agent setup --dry-run
```

To check your current configuration:
```bash
uvx nanito-agent status
```
