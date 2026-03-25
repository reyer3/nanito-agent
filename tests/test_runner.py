"""Tests for playbook runner — execution planning and variable resolution."""

from nanito_agent.playbook import parse_playbook
from nanito_agent.runner import (
    ExecutionPlan,
    Phase,
    RunContext,
    plan_execution,
    render_plan,
)


SAAS_PLAYBOOK = """\
name: build-saas
description: Build a SaaS from an idea

steps:
  - agent: architect
    task: "Design system for: {{idea}}"
    output: spec.md

  - parallel:
    - agent: api-designer
      task: "Design API from {{spec.md}}"
      output: api-spec.yaml
    - agent: frontend-builder
      task: "Design UI from {{spec.md}}"
      output: ui-spec.md
      worktree: true

  - agent: implementer
    task: "Build from {{api-spec.yaml}}"
    worktree: true

  - agent: reviewer
    task: "Review everything"
"""


def test_plan_execution_basic():
    """plan_execution creates phases from playbook."""
    plan = plan_execution(SAAS_PLAYBOOK, variables={"idea": "CRM app"})
    assert isinstance(plan, ExecutionPlan)
    assert plan.playbook_name == "build-saas"
    assert len(plan.phases) == 4


def test_variable_resolution():
    """Variables are resolved in task strings."""
    plan = plan_execution(SAAS_PLAYBOOK, variables={"idea": "CRM app"})
    first_step = plan.phases[0].steps[0]
    assert "CRM app" in first_step.task
    assert "{{idea}}" not in first_step.task


def test_parallel_phase():
    """Parallel steps create a parallel phase."""
    plan = plan_execution(SAAS_PLAYBOOK)
    phase2 = plan.phases[1]
    assert phase2.parallel is True
    assert len(phase2.steps) == 2


def test_sequential_phase():
    """Non-parallel steps create sequential phases."""
    plan = plan_execution(SAAS_PLAYBOOK)
    assert plan.phases[0].parallel is False
    assert plan.phases[2].parallel is False


def test_worktree_flag():
    """Worktree flag is preserved in resolved steps."""
    plan = plan_execution(SAAS_PLAYBOOK)
    # frontend-builder in parallel group has worktree=true
    parallel_steps = plan.phases[1].steps
    fb = [s for s in parallel_steps if s.agent == "frontend-builder"][0]
    assert fb.worktree is True


def test_output_preserved():
    """Output file references are preserved."""
    plan = plan_execution(SAAS_PLAYBOOK)
    assert plan.phases[0].steps[0].output == "spec.md"


def test_run_context_resolve():
    """RunContext resolves template variables."""
    ctx = RunContext(variables={"name": "Ricky", "role": "Director"})
    assert ctx.resolve("Hello {{name}}, you are {{role}}") == (
        "Hello Ricky, you are Director"
    )


def test_run_context_unresolved():
    """Unresolved variables are left as-is."""
    ctx = RunContext(variables={"name": "Ricky"})
    result = ctx.resolve("{{name}} works on {{project}}")
    assert "Ricky" in result
    assert "{{project}}" in result


def test_render_plan():
    """render_plan produces readable output."""
    plan = plan_execution(SAAS_PLAYBOOK, variables={"idea": "CRM"})
    output = render_plan(plan)
    assert "build-saas" in output
    assert "architect" in output
    assert "parallel" in output
    assert "Total steps:" in output
    assert "Agents needed:" in output


def test_plan_from_file(tmp_path):
    """plan_execution accepts a file path."""
    f = tmp_path / "pb.yaml"
    f.write_text(SAAS_PLAYBOOK)
    plan = plan_execution(f, variables={"idea": "test"})
    assert plan.playbook_name == "build-saas"
