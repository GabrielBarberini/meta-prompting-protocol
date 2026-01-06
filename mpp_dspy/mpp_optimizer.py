from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Optional

import dspy
from dspy.primitives.prediction import Prediction
from dspy.teleprompt.teleprompt import Teleprompter

from .mpp_adapter import BundleResult
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
                continue
            last_error = None
            if last_valid_bundle == bundle:
                return BundleResult(bundle=bundle, iterations=i + 1, stable=True)
            last_bundle = bundle
            last_valid_bundle = bundle
        if last_valid_bundle is None:
            detail = last_error or "Unknown error."
            raise ValueError(
                "Failed to produce a valid MPP bundle after "
                f"{max_iters} iterations. Last error: {detail}"
            )
        return BundleResult(
            bundle=last_valid_bundle, iterations=max_iters, stable=False
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
