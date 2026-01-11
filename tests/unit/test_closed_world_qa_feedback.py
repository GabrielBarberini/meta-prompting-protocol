from __future__ import annotations

from typing import Any

import pytest


def test_closed_world_qa_failure_triggers_retry(mpp_bundle_minimal) -> None:
    """Closed-world QA failure should trigger another outer cycle."""

    dspy = pytest.importorskip("dspy")
    from mpp_dspy.mpp_auto_adapter import MPPAutoAdapter

    class DummyArchitect(dspy.Module):
        def forward(self, *, user_goal: str):  # noqa: ARG002
            return mpp_bundle_minimal

    class DummyExecutor(dspy.Module):
        def forward(self, *, bundle_text: str):  # noqa: ARG002
            # Return a stable response regardless; QA decides pass/fail.
            return {"decoded_bundle": "ok"}

    qa_calls = {"count": 0}

    class DummyQA(dspy.Module):
        def forward(
            self,
            *,
            meta_protocol_version: str,  # noqa: ARG002
            derivative_protocol_specification: dict[str, Any],  # noqa: ARG002
            derivative_protocol_payload: dict[str, Any],  # noqa: ARG002
            decoded_bundle: str,  # noqa: ARG002
        ):
            qa_calls["count"] += 1
            if qa_calls["count"] == 1:
                return {
                    "verdict": "fail",
                    "issues": ["format wrong"],
                    "repair_examples": ['{"final":"ok"}'],
                }
            return {"verdict": "pass", "issues": [], "repair_examples": []}

    program = MPPAutoAdapter(
        architect=DummyArchitect(),
        executor=DummyExecutor(),
        qa=DummyQA(),
        max_iters=2,
        architect_max_iters=2,
        executor_max_iters=1,
    )

    # Closed world: QA runs at the end;
    # first cycle fails QA, second should have feedback.
    result = program(user_goal="x", open_world=False)
    assert result.qa_passed is True
    assert qa_calls["count"] == 2
