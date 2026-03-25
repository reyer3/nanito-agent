"""Tests for playbook executor — command generation and compilation."""

import json
from pathlib import Path

from nanito_agent.agents import AgentDef, discover_agents
from nanito_agent.executor import (
    AgentCommand,
    build_agent_prompt,
    compile_execution,
)
from nanito_agent.runner import plan_execution


PLAYBOOK_YAML = """\
name: test-exec
description: Test execution

steps:
  - agent: architect
    task: "Design system for CRM"
    output: spec.md

  - parallel:
    - agent: implementer
      task: "Build backend"
      worktree: true
    - agent: tester
      task: "Write tests"
"""


def test_agent_command_to_claude_args():
    """AgentCommand generates valid claude CLI args."""
    cmd = AgentCommand(
        agent_name="architect",
        prompt="Design a CRM",
        model="opus",
        worktree=False,
    )
    args = cmd.to_claude_args()
    assert "claude" in args
    assert "--model" in args
    assert "opus" in args[args.index("--model") + 1]
    assert "--worktree" not in args


def test_agent_command_worktree():
    """Worktree flag appears in CLI args."""
    cmd = AgentCommand(
        agent_name="impl",
        prompt="Build it",
        worktree=True,
    )
    args = cmd.to_claude_args()
    assert "--worktree" in args


def test_agent_command_to_tool_call():
    """to_agent_tool_call generates valid Agent tool spec."""
    cmd = AgentCommand(
        agent_name="arch",
        prompt="Design",
        model="opus",
        worktree=True,
    )
    spec = cmd.to_agent_tool_call()
    assert spec["model"] == "opus"
    assert spec["isolation"] == "worktree"
    assert "arch" in spec["description"]


def test_build_agent_prompt():
    """build_agent_prompt combines agent def + task."""
    agent_def = AgentDef(
        name="architect",
        description="System architect",
        prompt="You design systems.",
    )
    from nanito_agent.runner import ResolvedStep

    step = ResolvedStep(
        agent="architect",
        task="Design a CRM",
        output="spec.md",
        worktree=False,
    )
    prompt = build_agent_prompt(step, agent_def, Path("/project"))
    assert "architect" in prompt
    assert "Design a CRM" in prompt
    assert "spec.md" in prompt
    assert "You design systems" in prompt


def test_compile_execution():
    """compile_execution creates commands from plan + agents."""
    agents = discover_agents()
    plan = plan_execution(PLAYBOOK_YAML, variables={})
    script = compile_execution(plan, agents)

    assert script.playbook_name == "test-exec"
    assert len(script.phases) == 2
    assert script.total_agents == 3

    # Phase 1: sequential architect
    p1 = script.phases[0]
    assert p1.parallel is False
    assert len(p1.commands) == 1
    assert p1.commands[0].agent_name == "architect"

    # Phase 2: parallel implementer + tester
    p2 = script.phases[1]
    assert p2.parallel is True
    assert len(p2.commands) == 2


def test_execution_script_summary():
    """to_summary produces readable output."""
    agents = discover_agents()
    plan = plan_execution(PLAYBOOK_YAML)
    script = compile_execution(plan, agents)
    summary = script.to_summary()
    assert "SEQUENTIAL" in summary
    assert "PARALLEL" in summary
    assert "architect" in summary
    assert "Total agents to spawn: 3" in summary


def test_execution_script_json():
    """to_json produces valid JSON."""
    agents = discover_agents()
    plan = plan_execution(PLAYBOOK_YAML)
    script = compile_execution(plan, agents)
    data = json.loads(script.to_json())
    assert data["playbook"] == "test-exec"
    assert data["total_agents"] == 3
    assert len(data["phases"]) == 2


def test_worktree_inheritance():
    """Agent def worktree is OR'd with step worktree."""
    agents = discover_agents()
    plan = plan_execution(PLAYBOOK_YAML)
    script = compile_execution(plan, agents)
    # implementer agent def has worktree=true, step also has worktree=true
    impl_cmd = [
        c for p in script.phases for c in p.commands
        if c.agent_name == "implementer"
    ][0]
    assert impl_cmd.worktree is True
