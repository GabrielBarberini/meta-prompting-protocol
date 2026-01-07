from __future__ import annotations

from typing import Protocol, Sequence

from .mpp_optimizer import LongitudinalTrace


class LongitudinalMetric(Protocol):
    """Interface for scoring longitudinal traces."""

    def score(self, traces: Sequence[LongitudinalTrace]) -> float:
        """Return a scalar score where higher is better."""


class TraceCostMetric:
    """Default metric: reward success and penalize vertical refinements."""

    name = "trace_cost"

    def score(self, traces: Sequence[LongitudinalTrace]) -> float:
        if not traces:
            return 0.0
        total = 0.0
        for trace in traces:
            case = trace.case
            open_world = bool(getattr(case, "open_world", False))
            success = trace.qa_passed if open_world else trace.executor_stable
            refinements = (trace.bundle_refinements or 0) + (
                trace.executor_refinements or 0
            )
            case_score = (1.0 / (1.0 + refinements)) if success else 0.0
            total += case_score
        return total / len(traces)
