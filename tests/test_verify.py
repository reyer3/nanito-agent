"""Tests for composite metric verification."""

from nanito_agent.playbook import VerifySignal
from nanito_agent.verify import (
    SignalResult,
    VerifyResult,
    _extract_number,
    run_signal,
    run_verification,
)


def test_extract_number_integer():
    assert _extract_number("42") == 42.0


def test_extract_number_float():
    assert _extract_number("coverage: 87.5%") == 87.5


def test_extract_number_last():
    """Extracts the last number when multiple present."""
    assert _extract_number("3 passed, 1 failed, 92.5% coverage") == 92.5


def test_extract_number_none():
    assert _extract_number("no numbers here") is None


def test_run_signal_echo():
    """Run a simple echo command as signal."""
    signal = VerifySignal(
        name="test-count",
        command="echo 42",
        weight=1.0,
        direction="higher",
    )
    result = run_signal(signal)
    assert result.success is True
    assert result.value == 42.0
    assert result.name == "test-count"


def test_run_signal_failure():
    """Failed command produces unsuccessful result."""
    signal = VerifySignal(
        name="bad",
        command="exit 1",
        weight=1.0,
    )
    result = run_signal(signal)
    assert result.success is False


def test_verify_result_score():
    """Composite score is weighted average."""
    result = VerifyResult(signals=[
        SignalResult("a", 80.0, "", True, 0.6, "higher"),
        SignalResult("b", 100.0, "", True, 0.4, "higher"),
    ])
    # (80*0.6 + 100*0.4) / (0.6+0.4) = 88.0
    assert result.score == 88.0


def test_verify_result_partial_failure():
    """Failed signals contribute 0 to score."""
    result = VerifyResult(signals=[
        SignalResult("a", 80.0, "", True, 0.5, "higher"),
        SignalResult("b", 0.0, "", False, 0.5, "higher"),
    ])
    # (80*0.5 + 0) / 1.0 = 40.0
    assert result.score == 40.0


def test_verify_result_all_passed():
    result = VerifyResult(signals=[
        SignalResult("a", 80.0, "", True, 1.0, "higher"),
        SignalResult("b", 90.0, "", True, 1.0, "higher"),
    ])
    assert result.all_passed is True


def test_verify_result_not_all_passed():
    result = VerifyResult(signals=[
        SignalResult("a", 80.0, "", True, 1.0, "higher"),
        SignalResult("b", 0.0, "", False, 1.0, "higher"),
    ])
    assert result.all_passed is False


def test_verify_result_summary():
    result = VerifyResult(signals=[
        SignalResult("tests", 42.0, "", True, 1.0, "higher"),
    ])
    summary = result.summary
    assert "PASS" in summary
    assert "tests" in summary
    assert "42.0" in summary


def test_run_verification():
    """Full pipeline: run multiple signals."""
    signals = [
        VerifySignal("echo-a", "echo 10", weight=0.5),
        VerifySignal("echo-b", "echo 20", weight=0.5),
    ]
    result = run_verification(signals)
    assert len(result.signals) == 2
    assert result.all_passed is True
    # (10*0.5 + 20*0.5) / 1.0 = 15.0
    assert result.score == 15.0


def test_verify_empty():
    """Empty signals list gives 0 score."""
    result = VerifyResult(signals=[])
    assert result.score == 0.0


def test_parse_playbook_with_verify():
    """Playbook YAML with verify section parses correctly."""
    from nanito_agent.playbook import parse_playbook

    yaml_str = """\
name: test-verify
description: Test
steps:
  - agent: architect
    task: Design it
verify:
  - name: tests
    command: echo 42
    weight: 0.6
    direction: higher
  - name: lint
    command: echo 0
    weight: 0.4
    direction: lower
"""
    pb = parse_playbook(yaml_str)
    assert len(pb.verify) == 2
    assert pb.verify[0].name == "tests"
    assert pb.verify[0].weight == 0.6
    assert pb.verify[1].direction == "lower"
