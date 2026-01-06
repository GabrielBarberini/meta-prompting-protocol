from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Optional

from pydantic import BaseModel, ConfigDict

from .validations import normalize_mpp_bundle, validate_mpp_bundle

Predictor = Callable[..., Any]
Bundle = dict[str, Any]


class VerticalStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    iteration: int
    output: Any
    qa_result: Optional[dict[str, Any]] = None
    qa_passed: Optional[bool] = None
    error: Optional[str] = None


class BundleResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    bundle: Bundle
    iterations: int
    stable: bool
    steps: Optional[list[VerticalStep]] = None


class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    final_response: str
    reasoning: Optional[str]
    iterations: int
    stable: bool
    qa_result: Optional[dict[str, Any]]
    qa_passed: Optional[bool]
    steps: Optional[list[VerticalStep]] = None


class VerticalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    bundle_result: BundleResult
    execution_result: ExecutionResult


def _get_field(prediction: Any, name: str) -> Any:
    if isinstance(prediction, Mapping):
        if name not in prediction:
            raise KeyError(f"Prediction missing field: {name}")
        return prediction[name]
    if hasattr(prediction, name):
        return getattr(prediction, name)
    raise AttributeError(f"Prediction missing attribute: {name}")


def _refined_goal(user_goal: str, previous_bundle: Optional[Mapping[str, Any]]) -> str:
    if previous_bundle is None:
        return user_goal
    return (
        f"{user_goal}\n\nPrevious bundle:\n"
        f"{json.dumps(previous_bundle, indent=2, ensure_ascii=True)}\n"
        "Refine for stability and correctness. If the previous bundle is valid, "
        "return it verbatim."
    )


def _qa_passed(qa_result: Mapping[str, Any]) -> bool:
    verdict = qa_result.get("verdict")
    return isinstance(verdict, str) and verdict.strip().lower() == "pass"


def _get_optional_field(prediction: Any, name: str) -> Any:
    if isinstance(prediction, Mapping):
        return prediction.get(name)
    return getattr(prediction, name, None)


def _extract_reasoning(prediction: Any) -> Optional[str]:
    for key in ("reasoning", "rationale"):
        value = _get_optional_field(prediction, key)
        if value is None:
            continue
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        if value:
            return value
    return None


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _drop_reasoning_fields(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    data = dict(value)
    data.pop("reasoning", None)
    data.pop("rationale", None)
    return data


def _normalize_response_for_stability(response: str) -> str:
    text = response.strip()
    if not text:
        return text
    stripped = _strip_code_fences(text)
    for candidate in (stripped, text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        parsed = _drop_reasoning_fields(parsed)
        return json.dumps(
            parsed,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    return " ".join(stripped.split())


class MPPAdapterPipeline:
    """Two-stage adapter pipeline: architect -> derived spec -> executor."""

    def __init__(
        self,
        architect: Predictor,
        executor: Predictor,
        qa: Optional[Predictor] = None,
        validate_bundle: Callable[[Mapping[str, Any]], None] = validate_mpp_bundle,
        set_executor_feedback: Optional[
            Callable[[Optional[Mapping[str, Any]]], None]
        ] = None,
        architect_max_iters: int = 10,
        executor_max_iters: int = 10,
    ) -> None:
        self.architect = architect
        self.executor = executor
        self.qa = qa
        self.validate_bundle = validate_bundle
        self.set_executor_feedback = set_executor_feedback
        self.architect_max_iters = architect_max_iters
        self.executor_max_iters = executor_max_iters

    def build_bundle(
        self, user_goal: str, max_iters: int | None = None
    ) -> BundleResult:
        max_iters = self.architect_max_iters if max_iters is None else max_iters
        last_bundle: Optional[Bundle] = None
        steps: list[VerticalStep] = []
        for i in range(max_iters):
            prompt = _refined_goal(user_goal, last_bundle)
            prediction = self.architect(user_goal=prompt)
            bundle = {
                "meta_protocol_version": _get_field(
                    prediction, "meta_protocol_version"
                ),
                "derivative_protocol_specification": _get_field(
                    prediction, "derivative_protocol_specification"
                ),
                "derivative_protocol_payload": _get_field(
                    prediction, "derivative_protocol_payload"
                ),
            }
            bundle = normalize_mpp_bundle(bundle)
            self.validate_bundle(bundle)
            steps.append(VerticalStep(iteration=i + 1, output=bundle))
            if last_bundle == bundle:
                return BundleResult(
                    bundle=bundle, iterations=i + 1, stable=True, steps=steps
                )
            last_bundle = bundle
        return BundleResult(
            bundle=last_bundle or {},
            iterations=max_iters,
            stable=False,
            steps=steps,
        )

    def execute(
        self,
        bundle: Mapping[str, Any],
        max_iters: int | None = None,
        open_world: bool = False,
        expect_reasoning: bool = False,
    ) -> ExecutionResult:
        max_iters = self.executor_max_iters if max_iters is None else max_iters
        bundle = normalize_mpp_bundle(bundle)
        self.validate_bundle(bundle)
        last_response: Optional[str] = None
        last_comparable: Optional[str] = None
        qa_result: Optional[Mapping[str, Any]] = None
        qa_passed: Optional[bool] = None
        reasoning: Optional[str] = None
        stable = False
        iterations = max_iters
        final_response = ""
        qa_feedback: Optional[Mapping[str, Any]] = None
        steps: list[VerticalStep] = []

        if open_world and self.qa is None:
            raise ValueError("open_world execution requires a QA predictor.")

        try:
            for i in range(max_iters):
                if open_world and self.set_executor_feedback is not None:
                    self.set_executor_feedback(qa_feedback)
                prediction = self.executor(
                    meta_protocol_version=bundle["meta_protocol_version"],
                    derivative_protocol_specification=bundle[
                        "derivative_protocol_specification"
                    ],
                    derivative_protocol_payload=bundle["derivative_protocol_payload"],
                )
                response = _get_field(prediction, "final_response")
                if not isinstance(response, str):
                    response = str(response)
                reasoning = _extract_reasoning(prediction)
                if expect_reasoning and reasoning is None:
                    raise ValueError(
                        "Executor is configured for ChainOfThought but no reasoning "
                        "was returned."
                    )

                comparable = _normalize_response_for_stability(response)

                if open_world and self.qa is not None:
                    qa_result = self._run_qa(bundle, response)
                    qa_passed = _qa_passed(qa_result)
                    if qa_passed:
                        stable = True
                        iterations = i + 1
                        final_response = response
                        break
                    qa_feedback = {
                        "verdict": qa_result.get("verdict"),
                        "issues": qa_result.get("issues"),
                        "previous_response": response,
                    }

                steps.append(
                    VerticalStep(
                        iteration=i + 1,
                        output=response,
                        qa_result=qa_result,
                        qa_passed=qa_passed,
                    )
                )

                if last_comparable == comparable:
                    stable = True
                    iterations = i + 1
                    final_response = response
                    break
                last_response = response
                last_comparable = comparable
        finally:
            if self.set_executor_feedback is not None:
                self.set_executor_feedback(None)

        if not stable:
            final_response = last_response or ""

        return ExecutionResult(
            final_response=final_response,
            reasoning=reasoning,
            iterations=iterations,
            stable=stable,
            qa_result=qa_result,
            qa_passed=qa_passed,
            steps=steps,
        )

    def _run_qa(
        self, bundle: Mapping[str, Any], final_response: str
    ) -> Mapping[str, Any]:
        if self.qa is None:
            raise ValueError("QA predictor is not configured.")
        prediction = self.qa(
            meta_protocol_version=bundle["meta_protocol_version"],
            derivative_protocol_specification=bundle[
                "derivative_protocol_specification"
            ],
            derivative_protocol_payload=bundle["derivative_protocol_payload"],
            final_response=final_response,
        )
        return {
            "verdict": _get_field(prediction, "verdict"),
            "issues": _get_field(prediction, "issues"),
        }


class MPPVerticalRefiner:
    """Wrapper for running the vertical refinement loops as a single module."""

    def __init__(
        self,
        architect: Predictor,
        executor: Predictor,
        qa: Optional[Predictor] = None,
        validate_bundle: Callable[[Mapping[str, Any]], None] = validate_mpp_bundle,
        set_executor_feedback: Optional[
            Callable[[Optional[Mapping[str, Any]]], None]
        ] = None,
        architect_max_iters: int = 10,
        executor_max_iters: int = 10,
    ) -> None:
        self.pipeline = MPPAdapterPipeline(
            architect=architect,
            executor=executor,
            qa=qa,
            validate_bundle=validate_bundle,
            set_executor_feedback=set_executor_feedback,
            architect_max_iters=architect_max_iters,
            executor_max_iters=executor_max_iters,
        )

    def build_bundle(
        self, user_goal: str, max_iters: int | None = None
    ) -> BundleResult:
        return self.pipeline.build_bundle(user_goal, max_iters=max_iters)

    def execute(
        self,
        bundle: Mapping[str, Any],
        max_iters: int | None = None,
        open_world: bool = False,
        expect_reasoning: bool = False,
    ) -> ExecutionResult:
        return self.pipeline.execute(
            bundle,
            max_iters=max_iters,
            open_world=open_world,
            expect_reasoning=expect_reasoning,
        )

    def run(
        self,
        user_goal: str,
        *,
        open_world: bool,
        architect_max_iters: int | None = None,
        executor_max_iters: int | None = None,
        expect_reasoning: bool = False,
    ) -> VerticalResult:
        bundle_result = self.build_bundle(user_goal, max_iters=architect_max_iters)
        execution_result = self.execute(
            bundle_result.bundle,
            max_iters=executor_max_iters,
            open_world=open_world,
            expect_reasoning=expect_reasoning,
        )
        return VerticalResult(
            bundle_result=bundle_result,
            execution_result=execution_result,
        )
