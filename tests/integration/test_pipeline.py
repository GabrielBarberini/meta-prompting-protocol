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
        return {"final_response": next(responses)}

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


def test_execute_passes_qa_feedback_to_executor(mpp_bundle_minimal) -> None:
    """Provide QA verdict/issues when refinement follows a QA failure."""
    # Arrange: record feedbacks passed into the executor adapter.
    feedbacks: list[dict[str, Any] | None] = []

    def set_feedback(value: dict[str, Any] | None) -> None:
        feedbacks.append(value)

    responses = iter(["bad-output", "good-output"])

    def executor(**_kwargs: Any) -> dict[str, Any]:
        return {"final_response": next(responses)}

    qa_calls = {"count": 0}

    def qa(**_kwargs: Any) -> dict[str, Any]:
        qa_calls["count"] += 1
        if qa_calls["count"] == 1:
            return {"verdict": "fail", "issues": ["missing field"]}
        return {"verdict": "pass", "issues": []}

    pipeline = MPPAdapterPipeline(
        architect=lambda **_kwargs: mpp_bundle_minimal,
        executor=executor,
        qa=qa,
        set_executor_feedback=set_feedback,
        executor_max_iters=2,
    )

    # Act: run open-world execution with QA feedback enabled.
    result = pipeline.execute(mpp_bundle_minimal, open_world=True)

    # Assert: QA feedback is passed after a failure, then cleared on exit.
    assert result.qa_passed is True
    assert feedbacks[0] is None
    assert feedbacks[1]["verdict"] == "fail"
    assert feedbacks[1]["previous_response"] == "bad-output"
    assert feedbacks[-1] is None


def test_execute_requires_reasoning_when_expected(mpp_bundle_minimal) -> None:
    """Raise when Chain-of-Thought is expected but reasoning is absent."""

    # Arrange: executor returns only final_response.
    def executor(**_kwargs: Any) -> dict[str, Any]:
        return {"final_response": "ok"}

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
