import pytest

from mpp_dspy.metrics import TraceCostMetric
from mpp_dspy.mpp_optimizer import LongitudinalTrace


def test_trace_cost_metric_scores_zero_on_failure() -> None:
    metric = TraceCostMetric()
    trace = LongitudinalTrace(
        case="example",
        bundle_stable=True,
        executor_stable=True,
        qa_passed=False,
        bundle_refinements=0,
        executor_refinements=0,
    )
    assert metric.score([trace]) == 0.0


def test_trace_cost_metric_weights_refinements() -> None:
    metric = TraceCostMetric(final_weight=4.0)
    trace = LongitudinalTrace(
        case="example",
        bundle_stable=True,
        executor_stable=True,
        qa_passed=True,
        bundle_refinements=1,
        executor_refinements=2,
    )
    expected = metric.final_weight / (
        metric.final_weight
        + (metric.architect_weight * 1)
        + (metric.executor_weight * 2)
    )
    assert metric.score([trace]) == pytest.approx(expected)
