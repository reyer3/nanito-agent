"""Tests for playbook schema and parser."""

import pytest

from nanito_agent.playbook import ParallelGroup, Step, parse_playbook


SIMPLE_PLAYBOOK = """\
name: build-api
description: Build a FastAPI backend from a spec
inputs:
  - idea: string
  - stack: string

steps:
  - agent: architect
    task: "Design the system for: {{idea}}"
    output: spec.md

  - agent: implementer
    task: "Build backend from spec"
    worktree: true

  - agent: tester
    task: "Write and run tests"
"""

PARALLEL_PLAYBOOK = """\
name: build-saas
description: Full SaaS from idea to deploy

steps:
  - agent: architect
    task: "Spec the system"
    output: spec.md

  - parallel:
    - agent: api-designer
      task: "Design API"
      output: api-spec.yaml
    - agent: frontend-builder
      task: "Design UI"
      output: ui-spec.md

  - agent: reviewer
    task: "Final review"
"""


def test_parse_simple_playbook():
    """Parse a simple sequential playbook."""
    pb = parse_playbook(SIMPLE_PLAYBOOK)
    assert pb.name == "build-api"
    assert pb.description == "Build a FastAPI backend from a spec"
    assert len(pb.inputs) == 2
    assert len(pb.steps) == 3
    assert all(isinstance(s, Step) for s in pb.steps)


def test_parse_parallel_playbook():
    """Parse a playbook with parallel steps."""
    pb = parse_playbook(PARALLEL_PLAYBOOK)
    assert pb.name == "build-saas"
    assert len(pb.steps) == 3
    assert isinstance(pb.steps[0], Step)
    assert isinstance(pb.steps[1], ParallelGroup)
    assert isinstance(pb.steps[2], Step)
    assert len(pb.steps[1].steps) == 2


def test_agent_names():
    """agent_names returns all unique agents."""
    pb = parse_playbook(PARALLEL_PLAYBOOK)
    names = pb.agent_names
    assert names == {"architect", "api-designer", "frontend-builder", "reviewer"}


def test_total_steps():
    """total_steps counts flattened steps."""
    pb = parse_playbook(PARALLEL_PLAYBOOK)
    assert pb.total_steps == 4  # 1 + 2 parallel + 1


def test_step_properties():
    """Step fields are parsed correctly."""
    pb = parse_playbook(SIMPLE_PLAYBOOK)
    arch = pb.steps[0]
    assert arch.agent == "architect"
    assert "{{idea}}" in arch.task
    assert arch.output == "spec.md"
    assert arch.worktree is False

    impl = pb.steps[1]
    assert impl.worktree is True


def test_parse_from_file(tmp_path):
    """Parse playbook from a file path."""
    f = tmp_path / "test.yaml"
    f.write_text(SIMPLE_PLAYBOOK)
    pb = parse_playbook(f)
    assert pb.name == "build-api"


def test_missing_name():
    """Raise on playbook without name."""
    with pytest.raises(ValueError, match="must have a 'name'"):
        parse_playbook("description: no name here\nsteps: []")


def test_missing_agent_in_step():
    """Raise on step without agent field."""
    bad = "name: bad\nsteps:\n  - task: do something"
    with pytest.raises(ValueError, match="must have 'agent'"):
        parse_playbook(bad)


def test_file_not_found():
    """Raise on nonexistent file."""
    with pytest.raises(FileNotFoundError):
        parse_playbook("/nonexistent/playbook.yaml")
