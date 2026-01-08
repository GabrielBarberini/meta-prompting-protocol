from __future__ import annotations

import inspect
import json
from typing import Any, Callable, Mapping, Optional, Sequence

try:
    import dspy
    from dspy.primitives.prediction import Prediction
    from dspy.teleprompt.teleprompt import Teleprompter
except Exception as exc:  # pragma: no cover - exercised in minimal envs
    dspy = None
    _DSPY_IMPORT_ERROR = exc

    class Teleprompter:  # type: ignore[override]
        pass

    class Prediction:  # type: ignore[override]
        pass


from pydantic import BaseModel, ConfigDict, Field

from .mpp_adapter import BundleResult, ExecutionResult, VerticalStep
from .template_tokens import extract_mutable_blocks, render_mutable_template
from .validations import normalize_mpp_bundle, validate_mpp_bundle

Predictor = Callable[..., Any]
Bundle = dict[str, Any]


def _get_field(prediction: Any, name: str) -> Any:
    if isinstance(prediction, Mapping):
        if name not in prediction:
            raise KeyError(f"Prediction missing field: {name}")
        return prediction[name]
    if hasattr(prediction, name):
        return getattr(prediction, name)
    raise AttributeError(f"Prediction missing attribute: {name}")


def _refined_goal(
    user_goal: str,
    previous_bundle: Optional[Mapping[str, Any]],
    error_message: Optional[str] = None,
) -> str:
    raw_goal = f"<RAW_USER_GOAL>\n{user_goal}\n</RAW_USER_GOAL>"
    parts = [raw_goal]
    if previous_bundle is not None:
        parts.append(
            "Previous bundle:\n"
            f"{json.dumps(previous_bundle, indent=2, ensure_ascii=True)}"
        )
    if error_message:
        parts.append(f"Refinement feedback:\n{error_message}")
    parts.append(
        "Refine for stability and correctness. If the previous bundle is valid and "
        "addresses the feedback, return it verbatim."
    )
    return "\n\n".join(parts)


class MPPBundleOptimizer(Teleprompter):
    """Internal optimizer that refines the architect output until it stabilizes."""

    def __init__(
        self,
        *,
        max_iters: int = 10,
        validate_bundle: Callable[[Mapping[str, Any]], None] = validate_mpp_bundle,
    ) -> None:
        super().__init__()
        self.max_iters = max_iters
        self.validate_bundle = validate_bundle

    def refine(
        self,
        architect: Predictor,
        user_goal: str,
        max_iters: int | None = None,
        *,
        previous_bundle: Optional[Mapping[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> BundleResult:
        max_iters = self.max_iters if max_iters is None else max_iters
        last_bundle: Optional[Bundle] = (
            dict(previous_bundle) if previous_bundle is not None else None
        )
        last_valid_bundle: Optional[Bundle] = None
        last_error: Optional[str] = error_message
        if previous_bundle is not None:
            try:
                self.validate_bundle(previous_bundle)
            except Exception:  # noqa: BLE001
                last_error = error_message
            else:
                last_valid_bundle = dict(previous_bundle)
        steps: list[VerticalStep] = []
        for i in range(max_iters):
            prompt = _refined_goal(user_goal, last_bundle, last_error)
            try:
                prediction = architect(user_goal=prompt)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                steps.append(
                    VerticalStep(
                        iteration=i + 1,
                        output=None,
                        error=last_error,
                    )
                )
                continue
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
            try:
                self.validate_bundle(bundle)
            except Exception as exc:  # noqa: BLE001
                last_bundle = bundle
                last_error = f"{type(exc).__name__}: {exc}"
                steps.append(
                    VerticalStep(
                        iteration=i + 1,
                        output=bundle,
                        error=last_error,
                    )
                )
                continue
            last_error = None
            steps.append(VerticalStep(iteration=i + 1, output=bundle))
            if last_valid_bundle == bundle:
                return BundleResult(
                    bundle=bundle, iterations=i + 1, stable=True, steps=steps
                )
            last_bundle = bundle
            last_valid_bundle = bundle
        if last_valid_bundle is None:
            detail = last_error or "Unknown error."
            raise ValueError(
                "Failed to produce a valid MPP bundle after "
                f"{max_iters} iterations. Last error: {detail}"
            )
        return BundleResult(
            bundle=last_valid_bundle,
            iterations=max_iters,
            stable=False,
            steps=steps,
        )

    def compile(
        self,
        student,
        *,
        trainset,
        teacher=None,
        valset=None,
        **kwargs,
    ):
        if dspy is None:
            raise ImportError("DSPy is required for compile().") from _DSPY_IMPORT_ERROR
        optimizer = self

        class _RefinedBundleModule(dspy.Module):
            def __init__(self, base):
                super().__init__()
                self.base = base

            def forward(self, *, user_goal: str):
                result = optimizer.refine(self.base, user_goal)
                bundle = result.bundle
                return Prediction(
                    meta_protocol_version=bundle.get("meta_protocol_version"),
                    derivative_protocol_specification=bundle.get(
                        "derivative_protocol_specification"
                    ),
                    derivative_protocol_payload=bundle.get(
                        "derivative_protocol_payload"
                    ),
                    bundle=bundle,
                    bundle_iterations=result.iterations,
                    bundle_stable=result.stable,
                )

        return _RefinedBundleModule(student)


MutateFunction = Callable[..., Mapping[str, str]]


class LongitudinalStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    iteration: int
    template: str
    score: float


class LongitudinalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    template: str
    score: float
    iterations: int
    history: list[LongitudinalStep]
    blocks: dict[str, str] = Field(default_factory=dict)


class LongitudinalTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    case: Any
    bundle_result: Optional[BundleResult] = None
    execution_result: Optional[ExecutionResult] = None
    bundle_stable: Optional[bool] = None
    bundle_refinements: Optional[int] = None
    executor_refinements: Optional[int] = None
    bundle_steps: Optional[list[VerticalStep]] = None
    execution_steps: Optional[list[VerticalStep]] = None
    qa_passed: Optional[bool] = None
    executor_stable: Optional[bool] = None
    errors: list[str] = Field(default_factory=list)


class LongitudinalScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float
    traces: list[LongitudinalTrace] = Field(default_factory=list)


ScoreFunction = Callable[..., float | LongitudinalScore | Mapping[str, Any]]


class MPPLongitudinalRefiner(Teleprompter):
    """Longitudinal (dataset-level) refinement scaffold for TextGrad-style loops."""

    def __init__(
        self,
        mutate_function: MutateFunction,
        score_function: ScoreFunction,
        *,
        max_iters: int = 5,
        maximize: bool = True,
    ) -> None:
        super().__init__()
        self.mutate_function = mutate_function
        self.score_function = score_function
        self.max_iters = max_iters
        self.maximize = maximize
        self._score_accepts_blocks = self._score_function_accepts_blocks(score_function)
        self._mutate_accepts_traces = self._mutate_function_accepts_traces(
            mutate_function
        )

    def refine(
        self,
        template: str,
        dataset: Sequence[Any],
        *,
        initial_overrides: Mapping[str, str] | None = None,
    ) -> LongitudinalResult:
        base_template = template
        current_blocks = extract_mutable_blocks(base_template)
        if initial_overrides:
            current_blocks = {**current_blocks, **initial_overrides}
        if not current_blocks:
            raise ValueError(
                "No mutable blocks found. Add {{MPP_MUTABLE:...}} tokens to the "
                "template before running longitudinal refinement."
            )
        best_template = render_mutable_template(base_template, current_blocks)
        best_score, current_traces = self._score(best_template, dataset, current_blocks)
        history = [
            LongitudinalStep(iteration=0, template=best_template, score=best_score)
        ]
        best_blocks = dict(current_blocks)

        for i in range(1, self.max_iters + 1):
            proposed_blocks = self._mutate(current_blocks, dataset, current_traces)
            merged_blocks = dict(current_blocks)
            merged_blocks.update(proposed_blocks)
            candidate_template = render_mutable_template(base_template, merged_blocks)
            candidate_score, candidate_traces = self._score(
                candidate_template, dataset, merged_blocks
            )
            history.append(
                LongitudinalStep(
                    iteration=i,
                    template=candidate_template,
                    score=candidate_score,
                )
            )

            if self._is_better(candidate_score, best_score):
                best_score = candidate_score
                best_template = candidate_template
                current_blocks = merged_blocks
                current_traces = candidate_traces
                best_blocks = dict(merged_blocks)

        return LongitudinalResult(
            template=best_template,
            score=best_score,
            iterations=len(history) - 1,
            history=history,
            blocks=best_blocks,
        )

    def compile(
        self,
        student,
        *,
        trainset,
        teacher=None,
        valset=None,
        **kwargs,
    ):
        if dspy is None:
            raise ImportError("DSPy is required for compile().") from _DSPY_IMPORT_ERROR
        template = getattr(student, "template", None)
        if template is None:
            raise ValueError(
                "MPPLongitudinalRefiner requires a student with a .template attribute."
            )
        result = self.refine(template, trainset, **kwargs)
        if hasattr(student, "with_template"):
            return student.with_template(result.template)
        setattr(student, "template", result.template)
        return student

    def _is_better(self, candidate: float, best: float) -> bool:
        return candidate > best if self.maximize else candidate < best

    @staticmethod
    def _score_function_accepts_blocks(score_function: ScoreFunction) -> bool:
        try:
            signature = inspect.signature(score_function)
        except (TypeError, ValueError):
            return False
        for param in signature.parameters.values():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                return True
        return len(signature.parameters) >= 3

    @staticmethod
    def _mutate_function_accepts_traces(
        mutate_function: MutateFunction,
    ) -> bool:
        try:
            signature = inspect.signature(mutate_function)
        except (TypeError, ValueError):
            return False
        for param in signature.parameters.values():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                return True
        return len(signature.parameters) >= 3

    def _score(
        self,
        template: str,
        dataset: Sequence[Any],
        blocks: Mapping[str, str],
    ) -> tuple[float, list[LongitudinalTrace]]:
        if self._score_accepts_blocks:
            result = self.score_function(template, dataset, blocks)
        else:
            result = self.score_function(template, dataset)
        if isinstance(result, LongitudinalScore):
            return float(result.score), list(result.traces)
        if isinstance(result, Mapping) and "score" in result:
            score = float(result["score"])
            traces = result.get("traces") or []
            return score, list(traces)
        return float(result), []

    def _mutate(
        self,
        blocks: Mapping[str, str],
        dataset: Sequence[Any],
        traces: Sequence[LongitudinalTrace] | None,
    ) -> Mapping[str, str]:
        if self._mutate_accepts_traces:
            return self.mutate_function(blocks, dataset, traces)
        return self.mutate_function(blocks, dataset)
