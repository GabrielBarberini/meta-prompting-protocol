from __future__ import annotations

from typing import Any

import pytest

from mpp_dspy.mpp_adapter import MPPAdapterPipeline


def test_execute_stabilizes_with_equivalent_json(mpp_bundle_minimal) -> None:
    """Normalize JSON outputs so reasoning changes do not prevent stabilization."""
    # Arrange: executor returns equivalent JSON with different reasoning text.
    responses = iter(
        [
            '{"reasoning": "first", "final": {"value": 1}}',
            '{"final": {"value": 1}, "reasoning": "second"}',
        ]
    )

    def executor(**_kwargs: Any) -> dict[str, Any]:
        return {"decoded_bundle": next(responses)}

    pipeline = MPPAdapterPipeline(
        architect=lambda **_kwargs: mpp_bundle_minimal,
        executor=executor,
        executor_max_iters=2,
    )

    # Act: run the executor loop.
    result = pipeline.execute(mpp_bundle_minimal, open_world=False)

    # Assert: convergence happens on the second equivalent response.
    assert result.stable is True
    assert result.iterations == 2


def test_execute_open_world_short_circuits_on_qa_fail(mpp_bundle_minimal) -> None:
    """Open-world execution returns after the first QA failure."""

    responses = iter(["bad-output", "good-output"])
    executor_calls = {"count": 0}

    def executor(**_kwargs: Any) -> dict[str, Any]:
        executor_calls["count"] += 1
        return {"decoded_bundle": next(responses)}

    qa_calls = {"count": 0}

    def qa(**_kwargs: Any) -> dict[str, Any]:
        qa_calls["count"] += 1
        return {
            "verdict": "fail",
            "issues": ["missing field"],
            "repair_examples": ['{"reasoning":"...","final":{"value":1}}'],
        }

    pipeline = MPPAdapterPipeline(
        architect=lambda **_kwargs: mpp_bundle_minimal,
        executor=executor,
        qa=qa,
        executor_max_iters=2,
    )

    # Act: run open-world execution with QA feedback enabled.
    result = pipeline.execute(mpp_bundle_minimal, open_world=True)

    # Assert: QA failure returns after the first attempt.
    assert result.qa_passed is False
    assert result.iterations == 1
    assert executor_calls["count"] == 1
    assert qa_calls["count"] == 1


def test_execute_requires_reasoning_when_expected(mpp_bundle_minimal) -> None:
    """Raise when Chain-of-Thought is expected but reasoning is absent."""

    # Arrange: executor returns only decoded_bundle.
    def executor(**_kwargs: Any) -> dict[str, Any]:
        return {"decoded_bundle": "ok"}

    pipeline = MPPAdapterPipeline(
        architect=lambda **_kwargs: mpp_bundle_minimal,
        executor=executor,
        executor_max_iters=1,
    )

    # Act + Assert: missing reasoning triggers a ValueError.
    with pytest.raises(ValueError, match="no reasoning was returned"):
        pipeline.execute(
            mpp_bundle_minimal,
            open_world=False,
            expect_reasoning=True,
        )
