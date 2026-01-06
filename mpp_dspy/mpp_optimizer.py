from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Optional, Sequence

import dspy
from dspy.primitives.prediction import Prediction
from dspy.teleprompt.teleprompt import Teleprompter
from pydantic import BaseModel, ConfigDict

from .mpp_adapter import BundleResult, VerticalStep
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
    if previous_bundle is None and error_message is None:
        return user_goal
    parts = [user_goal]
    if previous_bundle is not None:
        parts.append(
            "Previous bundle:\n"
            f"{json.dumps(previous_bundle, indent=2, ensure_ascii=True)}"
        )
    if error_message:
        parts.append(f"Validation error:\n{error_message}")
    parts.append(
        "Refine for stability and correctness. If the previous bundle is valid, "
        "return it verbatim."
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
        self, architect: Predictor, user_goal: str, max_iters: int | None = None
    ) -> BundleResult:
        max_iters = self.max_iters if max_iters is None else max_iters
        last_bundle: Optional[Bundle] = None
        last_valid_bundle: Optional[Bundle] = None
        last_error: Optional[str] = None
        steps: list[VerticalStep] = []
        for i in range(max_iters):
            prompt = _refined_goal(user_goal, last_bundle, last_error)
            prediction = architect(user_goal=prompt)
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


MutateFn = Callable[[Mapping[str, str], Sequence[Any]], Mapping[str, str]]
ScoreFn = Callable[[str, Sequence[Any]], float]


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


class MPPLongitudinalRefiner(Teleprompter):
    """Longitudinal (dataset-level) refinement scaffold for TextGrad-style loops."""

    def __init__(
        self,
        mutate_fn: MutateFn,
        score_fn: ScoreFn,
        *,
        max_iters: int = 5,
        maximize: bool = True,
    ) -> None:
        super().__init__()
        self.mutate_fn = mutate_fn
        self.score_fn = score_fn
        self.max_iters = max_iters
        self.maximize = maximize

    def refine(
        self,
        template: str,
        dataset: Sequence[Any],
        *,
        initial_overrides: Mapping[str, str] | None = None,
    ) -> LongitudinalResult:
        current_template = template
        if initial_overrides:
            current_template = render_mutable_template(
                current_template, initial_overrides
            )
        current_blocks = extract_mutable_blocks(current_template)
        if not current_blocks:
            raise ValueError(
                "No mutable blocks found. Add {{MPP_MUTABLE:...}} tokens to the "
                "template before running longitudinal refinement."
            )
        best_template = current_template
        best_score = self.score_fn(best_template, dataset)
        history = [
            LongitudinalStep(iteration=0, template=best_template, score=best_score)
        ]

        for i in range(1, self.max_iters + 1):
            proposed_blocks = self.mutate_fn(current_blocks, dataset)
            candidate_template = render_mutable_template(
                current_template, proposed_blocks
            )
            candidate_blocks = extract_mutable_blocks(candidate_template)
            candidate_score = self.score_fn(candidate_template, dataset)
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
                current_template = candidate_template
                current_blocks = candidate_blocks

        return LongitudinalResult(
            template=best_template,
            score=best_score,
            iterations=len(history) - 1,
            history=history,
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
