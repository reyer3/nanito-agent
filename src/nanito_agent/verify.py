"""Composite metric verification — runs multiple signals and scores results."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from nanito_agent.playbook import VerifySignal


@dataclass
class SignalResult:
    """Result of running a single verification signal."""

    name: str
    value: float
    raw_output: str
    success: bool
    weight: float
    direction: str


@dataclass
class VerifyResult:
    """Composite result of all verification signals."""

    signals: list[SignalResult]

    @property
    def score(self) -> float:
        """Weighted composite score (0-100)."""
        if not self.signals:
            return 0.0
        total_weight = sum(s.weight for s in self.signals)
        if total_weight == 0:
            return 0.0
        weighted = sum(
            (s.value * s.weight) for s in self.signals if s.success
        )
        return round(weighted / total_weight, 2)

    @property
    def all_passed(self) -> bool:
        return all(s.success for s in self.signals)

    @property
    def summary(self) -> str:
        lines = [f"Composite score: {self.score}"]
        for s in self.signals:
            status = "PASS" if s.success else "FAIL"
            lines.append(
                f"  [{status}] {s.name}: {s.value} "
                f"(weight={s.weight}, {s.direction})"
            )
        return "\n".join(lines)


def run_signal(signal: VerifySignal) -> SignalResult:
    """Execute a single verification signal and extract metric."""
    try:
        result = subprocess.run(
            signal.command,
            shell=True,  # noqa: S602 — user-defined verify commands
            capture_output=True,
            text=True,
            timeout=120,
        )
        raw = result.stdout.strip()
        # Try to extract a number from the output
        value = _extract_number(raw)
        success = result.returncode == 0 and value is not None
        return SignalResult(
            name=signal.name,
            value=value if value is not None else 0.0,
            raw_output=raw[:500],
            success=success,
            weight=signal.weight,
            direction=signal.direction,
        )
    except subprocess.TimeoutExpired:
        return SignalResult(
            name=signal.name,
            value=0.0,
            raw_output="TIMEOUT",
            success=False,
            weight=signal.weight,
            direction=signal.direction,
        )


def run_verification(signals: list[VerifySignal]) -> VerifyResult:
    """Run all verification signals and compute composite score."""
    return VerifyResult(
        signals=[run_signal(s) for s in signals],
    )


def _extract_number(text: str) -> float | None:
    """Extract the last number from command output."""
    import re

    numbers = re.findall(r"[-+]?\d*\.?\d+", text)
    if numbers:
        return float(numbers[-1])
    return None
