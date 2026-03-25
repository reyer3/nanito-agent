# memory-protocol

Engram memory protocol for persistent knowledge across sessions.

## When to Use

Use this skill whenever Engram MCP is available. It defines when and how to save memories.

## How It Works

### Mandatory Save Events

Save a memory after ANY of these:
- **Bug fixed** — What, root cause, solution, affected files
- **Decision made** — What was decided, why, alternatives rejected
- **Discovery** — Something non-obvious about codebase or domain
- **Pattern found** — A reusable approach that worked
- **User preference** — How the user likes things done

### Save Format

```
mem_save with:
- Topic: <descriptive-key> (use mem_suggest_topic_key for consistency)
- Content structured as: What / Why / Where / Learned
```

### Topic Key Conventions

- `project:<name>:architecture` — Architecture decisions
- `bug:<area>:<description>` — Bug fixes and root causes
- `decision:<area>:<choice>` — Technical decisions
- `pattern:<name>` — Reusable patterns

### Session Lifecycle

- **Start:** `mem_session_start` with project context and goals
- **Close:** `mem_session_summary` with goal, accomplished, discoveries, next steps
- **Post-compaction:** Call `mem_context` immediately to reload state

### Rules

- Always `mem_search` before `mem_save` to avoid duplicates
- Use `mem_update` to evolve existing memories, not create new ones
- Skip for trivial/routine work
