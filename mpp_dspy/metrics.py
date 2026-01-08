from __future__ import annotations

from typing import Protocol, Sequence

from .mpp_optimizer import LongitudinalTrace


class LongitudinalMetric(Protocol):
    """Interface for scoring longitudinal traces."""

    def score(self, traces: Sequence[LongitudinalTrace]) -> float:
        """Return a scalar score where higher is better."""


class TraceCostMetric:
    """Default metric: reward success and penalize vertical refinements.

    The final response weight dominates architect refinements, which dominate
    executor refinements to favor fast, stable convergence.
    """

    name = "trace_cost"

    def __init__(
        self,
        *,
        final_weight: float = 4.0,
        architect_weight: float | None = None,
        executor_weight: float | None = None,
        weight_multiplier: float = 2.0,
    ) -> None:
        self.final_weight = final_weight
        if architect_weight is None:
            architect_weight = final_weight / weight_multiplier
        if executor_weight is None:
            executor_weight = final_weight / (weight_multiplier**2)
        self.architect_weight = architect_weight
        self.executor_weight = executor_weight

    def score(self, traces: Sequence[LongitudinalTrace]) -> float:
        if not traces:
            return 0.0
        total = 0.0
        for trace in traces:
            stable = (
                trace.bundle_stable is True
                and trace.executor_stable is True
                and trace.qa_passed is True
            )
            if not stable:
                total += 0.0
                continue
            refinements = (self.architect_weight * (trace.bundle_refinements or 0)) + (
                self.executor_weight * (trace.executor_refinements or 0)
            )
            case_score = self.final_weight / (self.final_weight + refinements)
            total += case_score
        return total / len(traces)
