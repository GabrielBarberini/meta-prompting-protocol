from __future__ import annotations

from mpp_dspy.feedback import FeedbackEvent, FeedbackTrace


def test_feedback_trace_serializes_stably() -> None:
    trace = FeedbackTrace()
    trace = trace.append(
        FeedbackEvent(
            kind="qa_failed",
            summary="QA failed.",
            qa_verdict="fail",
            qa_issues=["missing field"],
            last_response="bad-output",
            executor_iterations=2,
            executor_stable=False,
            executor_refinements=1,
        )
    )
    text = trace.to_prompt_text()
    assert text.startswith('{"events":[{"executor_iterations":2,')
    assert '"kind":"qa_failed"' in text
    assert text.endswith('}],"version":"1"}')
