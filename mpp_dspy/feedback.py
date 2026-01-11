from __future__ import annotations

import json
from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field


class FeedbackEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal[
        "executor_nonconvergent",
        "qa_failed",
        "executor_exception",
        "bundle_invalid",
    ]
    summary: str

    qa_verdict: Optional[str] = None
    qa_issues: list[str] = Field(default_factory=list)
    qa_repair_examples: list[str] = Field(default_factory=list)
    last_response: Optional[str] = None

    executor_iterations: Optional[int] = None
    executor_stable: Optional[bool] = None
    executor_refinements: Optional[int] = None

    @staticmethod
    def from_execution_result(exec_result: Any) -> "FeedbackEvent":
        # Import lazily to avoid cycles; exec_result is an ExecutionResult.
        qa_result = getattr(exec_result, "qa_result", None)
        qa_verdict = None
        qa_issues: list[str] = []
        qa_repair_examples: list[str] = []
        if isinstance(qa_result, Mapping):
            qa_verdict = (
                str(qa_result.get("verdict")) if qa_result.get("verdict") else None
            )
            issues = qa_result.get("issues")
            if isinstance(issues, list):
                qa_issues = [str(issue) for issue in issues if issue is not None]
            repair_examples = qa_result.get("repair_examples")
            if isinstance(repair_examples, list):
                qa_repair_examples = [
                    str(example) for example in repair_examples if example is not None
                ]

        iterations = getattr(exec_result, "iterations", None)
        refinements = None
        if isinstance(iterations, int) and iterations >= 1:
            refinements = max(iterations - 1, 0)
        stable = getattr(exec_result, "stable", None)
        decoded_bundle = getattr(exec_result, "decoded_bundle", None)
        if not isinstance(decoded_bundle, str):
            decoded_bundle = None

        if qa_verdict and qa_verdict.strip().lower() != "pass":
            kind: FeedbackEvent["kind"] = "qa_failed"
            summary = "QA failed for executor output."
        else:
            kind = "executor_nonconvergent"
            summary = (
                "Executor failed to stabilize within the configured iteration cap."
            )

        return FeedbackEvent(
            kind=kind,
            summary=summary,
            qa_verdict=qa_verdict,
            qa_issues=qa_issues,
            qa_repair_examples=qa_repair_examples,
            last_response=decoded_bundle,
            executor_iterations=iterations if isinstance(iterations, int) else None,
            executor_stable=stable if isinstance(stable, bool) else None,
            executor_refinements=refinements,
        )


class FeedbackTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str = "1"
    events: list[FeedbackEvent] = Field(default_factory=list)

    def append(self, event: FeedbackEvent) -> "FeedbackTrace":
        return FeedbackTrace(version=self.version, events=[*self.events, event])

    def to_prompt_text(self) -> str:
        """Stable JSON rendering for embedding into refinement prompts."""
        return json.dumps(
            self.model_dump(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
