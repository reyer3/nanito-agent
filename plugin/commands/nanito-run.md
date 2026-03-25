---
name: nanito-run
description: "Run a nanito-agent playbook to orchestrate agent swarms"
---

The user wants to run a nanito-agent playbook. Follow the playbook-runner skill workflow:

1. Parse the arguments to identify the playbook and variables
2. Run `nanito-agent run <playbook> --var key=val` to generate the execution plan
3. Show the plan to the user
4. Execute each phase by spawning agents (parallel phases = multiple Agent calls in one message)
5. Collect outputs and feed them forward
6. Run the reviewer at the end

Arguments format: `/nanito-run <playbook> [--var key=val ...]`

Example: `/nanito-run build-saas --var idea="debt collection CRM" --var stack="python"`

If no playbook is specified, list available playbooks by running `nanito-agent run --help` or show:
- build-saas: Full SaaS from idea
- build-api: REST API from spec
- build-dashboard: BI dashboard from data
