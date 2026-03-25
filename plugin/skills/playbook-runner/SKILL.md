---
name: nanito-run
description: "Run a nanito-agent playbook to orchestrate multiple agents. Use when the user wants to build a SaaS, API, dashboard, or any multi-step project from an idea. Triggers on: 'run playbook', 'build saas', 'build api', 'build dashboard', 'nanito run', 'deploy agents', 'orchestrate agents', 'materialize idea'."
---

# Nanito Playbook Runner

You have access to nanito-agent's playbook orchestration system. When the user wants to build something from an idea, use this workflow.

## Available Playbooks

- **build-saas**: Full SaaS from idea → spec → API + frontend in parallel → tests → review
- **build-api**: REST API → spec → OpenAPI → implementation → tests → review
- **build-dashboard**: BI dashboard → spec → data API + UI in parallel → tests → review

## Workflow

### Step 1: Identify the playbook and variables

Ask the user (if not already clear):
- What to build (determines playbook)
- The idea/description (main variable)
- Stack preferences (if applicable)

### Step 2: Plan the execution

Run the nanito-agent CLI to generate the execution plan:

```bash
nanito-agent run <playbook> --var idea="<user's idea>" --var stack="<stack>"
```

Show the user the plan and get confirmation.

### Step 3: Execute phases

For each phase in the plan:

**Sequential phases:** Spawn one Agent at a time, wait for completion.

```
Agent tool call:
  description: "[agent-name] phase N"
  prompt: <agent prompt from the plan>
  model: <model from agent def>
  isolation: "worktree" (if worktree=true)
```

**Parallel phases:** Spawn ALL agents in the phase simultaneously using multiple Agent tool calls in a single message.

### Step 4: Collect and integrate outputs

After each phase completes:
1. Review the agent's output
2. If the step has an `output` file, verify it was created
3. Feed outputs as context into the next phase's agents

### Step 5: Final report

After all phases complete, provide:
- Summary of what was built
- Files created/modified
- Any issues or decisions that need user input
- Next steps (deploy, configure, etc.)

## Rules

- Always show the plan before executing
- For parallel phases, launch ALL agents in one message (maximizes speed)
- Use worktree isolation for implementers to avoid conflicts
- If an agent fails, report the error and ask the user how to proceed
- Never skip the reviewer phase — quality is non-negotiable
