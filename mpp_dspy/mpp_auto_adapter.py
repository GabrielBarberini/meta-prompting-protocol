from __future__ import annotations

from typing import Callable

import dspy
from dspy.primitives.prediction import Prediction

from .dspy_adapters import MPPArchitectAdapter, MPPExecutorAdapter, MPPQAAdapter
from .mpp_adapter import MPPAdapterPipeline
from .mpp_optimizer import MPPBundleOptimizer
from .mpp_signatures import ProtocolArchitect, ProtocolExecutor, QualityAssurance


def _wrap_with_adapter(predictor: Callable[..., object], adapter: dspy.Adapter):
    def _call(**kwargs):
        with dspy.settings.context(adapter=adapter):
            return predictor(**kwargs)

    return _call


def _predictor_uses_cot(predictor: object) -> bool:
    return isinstance(predictor, dspy.ChainOfThought)


class MPPAutoAdapter(dspy.Module):
    """DSPy module that runs the MPP adapter pipeline end-to-end."""

    def __init__(
        self,
        *,
        spec_text: str | None = None,
        max_iters: int = 10,
        architect_max_iters: int | None = None,
        executor_max_iters: int | None = None,
        architect: dspy.Predict | None = None,
        executor: dspy.Predict | None = None,
        qa: dspy.Predict | None = None,
    ) -> None:
        super().__init__()
        self.spec_text = spec_text
        self.max_iters = max_iters
        self.architect_max_iters = (
            max_iters if architect_max_iters is None else architect_max_iters
        )
        self.executor_max_iters = (
            max_iters if executor_max_iters is None else executor_max_iters
        )

        self.architect = architect or dspy.ChainOfThought(ProtocolArchitect)
        self.executor = executor or dspy.Predict(ProtocolExecutor)
        self.qa = qa or dspy.Predict(QualityAssurance)
        self.executor_expect_reasoning = _predictor_uses_cot(self.executor)

        self.architect_adapter = MPPArchitectAdapter(spec_text=spec_text)
        self.bundle_optimizer = MPPBundleOptimizer(max_iters=self.architect_max_iters)

    def forward(
        self,
        *,
        user_goal: str,
        open_world: bool,
        max_iters: int | None = None,
        architect_max_iters: int | None = None,
        executor_max_iters: int | None = None,
    ) -> Prediction:
        if max_iters is not None:
            bundle_iters = (
                max_iters if architect_max_iters is None else architect_max_iters
            )
            executor_iters = (
                max_iters if executor_max_iters is None else executor_max_iters
            )
        else:
            bundle_iters = (
                self.architect_max_iters
                if architect_max_iters is None
                else architect_max_iters
            )
            executor_iters = (
                self.executor_max_iters
                if executor_max_iters is None
                else executor_max_iters
            )

        architect_call = _wrap_with_adapter(self.architect, self.architect_adapter)
        bundle_result = self.bundle_optimizer.refine(
            architect_call, user_goal, max_iters=bundle_iters
        )

        executor_adapter = MPPExecutorAdapter(
            spec_text=self.spec_text,
            bundle=bundle_result.bundle,
            expect_reasoning=self.executor_expect_reasoning,
        )
        executor_call = _wrap_with_adapter(self.executor, executor_adapter)

        def set_executor_feedback(feedback):
            executor_adapter.qa_feedback = feedback

        qa_call = None
        qa_result = None
        qa_passed = None
        if open_world:
            qa_adapter = MPPQAAdapter(
                spec_text=self.spec_text,
                bundle=bundle_result.bundle,
            )
            qa_call = _wrap_with_adapter(self.qa, qa_adapter)

        exec_pipeline = MPPAdapterPipeline(
            architect=architect_call,
            executor=executor_call,
            qa=qa_call,
            set_executor_feedback=set_executor_feedback,
        )
        exec_result = exec_pipeline.execute(
            bundle_result.bundle,
            max_iters=executor_iters,
            open_world=open_world,
            expect_reasoning=self.executor_expect_reasoning,
        )
        qa_result = exec_result.qa_result
        qa_passed = exec_result.qa_passed

        return Prediction(
            bundle=bundle_result.bundle,
            final_response=exec_result.final_response,
            executor_reasoning=exec_result.reasoning,
            qa_result=qa_result,
            qa_passed=qa_passed,
            bundle_iterations=bundle_result.iterations,
            bundle_refinements=max(bundle_result.iterations - 1, 0),
            bundle_stable=bundle_result.stable,
            executor_iterations=exec_result.iterations,
            executor_refinements=max(exec_result.iterations - 1, 0),
            executor_stable=exec_result.stable,
            open_world=open_world,
        )
