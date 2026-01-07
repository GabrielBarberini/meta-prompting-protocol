from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import dspy
from dspy.primitives.prediction import Prediction

from .dspy_adapters import MPPArchitectAdapter, MPPExecutorAdapter, MPPQAAdapter
from .metrics import LongitudinalMetric, TraceCostMetric
from .mpp_adapter import ExecutionResult, MPPAdapterPipeline
from .mpp_optimizer import (
    LongitudinalResult,
    LongitudinalScore,
    LongitudinalTrace,
    MPPBundleOptimizer,
    MPPLongitudinalRefiner,
    MutateFunction,
)
from .mpp_signatures import ProtocolArchitect, ProtocolExecutor, QualityAssurance


def _wrap_with_adapter(
    predictor: Callable[..., object],
    adapter: dspy.Adapter,
    *,
    lm: dspy.BaseLM | None = None,
):
    def _call(**kwargs):
        context_kwargs = {"adapter": adapter}
        if lm is not None:
            context_kwargs["lm"] = lm
        with dspy.settings.context(**context_kwargs):
            return predictor(**kwargs)

    return _call


def _predictor_uses_cot(predictor: object) -> bool:
    return isinstance(predictor, dspy.ChainOfThought)


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


def _strip_reasoning_for_feedback(response: str) -> str:
    text = response.strip()
    if not text:
        return text
    stripped = _strip_code_fences(text)
    for candidate in (stripped, text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            parsed = dict(parsed)
            parsed.pop("reasoning", None)
            parsed.pop("rationale", None)
        return json.dumps(parsed, indent=2, ensure_ascii=True)
    return response


def _format_executor_feedback(exec_result: ExecutionResult) -> str:
    refinements = max(exec_result.iterations - 1, 0)
    lines = [
        "Executor failed to stabilize within the configured iteration cap.",
        f"Executor refinements: {refinements}.",
    ]
    if exec_result.qa_result is not None:
        verdict = exec_result.qa_result.get("verdict")
        issues = exec_result.qa_result.get("issues")
        lines.append(f"QA verdict: {verdict}")
        if issues:
            lines.append(f"QA issues: {issues}")
    if exec_result.final_response:
        lines.append(
            "Last executor response (reasoning removed where possible):\n"
            f"{_strip_reasoning_for_feedback(exec_result.final_response)}"
        )
    return "\n".join(lines)


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
        architect_lm: dspy.BaseLM | None = None,
        executor_lm: dspy.BaseLM | None = None,
        qa_lm: dspy.BaseLM | None = None,
        architect_role_instructions: str | None = None,
        executor_role_instructions: str | None = None,
        qa_role_instructions: str | None = None,
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
        self.architect_expect_reasoning = _predictor_uses_cot(self.architect)
        self.executor_expect_reasoning = _predictor_uses_cot(self.executor)
        self.architect_lm = architect_lm
        self.executor_lm = executor_lm
        self.qa_lm = qa_lm
        self.executor_role_instructions = executor_role_instructions
        self.qa_role_instructions = qa_role_instructions

        architect_kwargs = {"spec_text": spec_text}
        if architect_role_instructions is not None:
            architect_kwargs["role_instructions"] = architect_role_instructions
        architect_kwargs["expect_reasoning"] = self.architect_expect_reasoning
        self.architect_adapter = MPPArchitectAdapter(**architect_kwargs)
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

        architect_call = _wrap_with_adapter(
            self.architect, self.architect_adapter, lm=self.architect_lm
        )
        previous_bundle = None
        feedback = None
        bundle_result = None
        exec_result = None
        qa_result = None
        qa_passed = None
        architect_cycles = 0
        bundle_refinements_total = 0
        executor_refinements_total = 0

        for _ in range(bundle_iters):
            architect_cycles += 1
            bundle_result = self.bundle_optimizer.refine(
                architect_call,
                user_goal,
                max_iters=bundle_iters,
                previous_bundle=previous_bundle,
                error_message=feedback,
            )
            bundle_refinements_total += max(bundle_result.iterations - 1, 0)

            executor_kwargs = {
                "spec_text": self.spec_text,
                "bundle": bundle_result.bundle,
                "expect_reasoning": self.executor_expect_reasoning,
            }
            if self.executor_role_instructions is not None:
                executor_kwargs["role_instructions"] = self.executor_role_instructions
            executor_adapter = MPPExecutorAdapter(**executor_kwargs)
            executor_call = _wrap_with_adapter(
                self.executor, executor_adapter, lm=self.executor_lm
            )

            def set_executor_feedback(value):
                executor_adapter.qa_feedback = value

            if self.qa is None:
                raise ValueError("QA predictor is required for QA gating.")
            qa_kwargs = {
                "spec_text": self.spec_text,
                "bundle": bundle_result.bundle,
            }
            if self.qa_role_instructions is not None:
                qa_kwargs["role_instructions"] = self.qa_role_instructions
            qa_adapter = MPPQAAdapter(**qa_kwargs)
            qa_call = _wrap_with_adapter(self.qa, qa_adapter, lm=self.qa_lm)

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
                final_qa=not open_world,
                expect_reasoning=self.executor_expect_reasoning,
            )
            qa_result = exec_result.qa_result
            qa_passed = exec_result.qa_passed
            executor_refinements_total += max(exec_result.iterations - 1, 0)
            if open_world:
                success = bool(qa_passed)
            else:
                success = exec_result.stable and qa_passed is True
            if success:
                break
            feedback = _format_executor_feedback(
                exec_result,
            )
            previous_bundle = bundle_result.bundle

        if bundle_result is None or exec_result is None:
            raise ValueError("Failed to produce a bundle/executor result.")

        return Prediction(
            bundle=bundle_result.bundle,
            final_response=exec_result.final_response,
            executor_reasoning=exec_result.reasoning,
            qa_result=qa_result,
            qa_passed=qa_passed,
            bundle_iterations=bundle_result.iterations,
            bundle_refinements=max(bundle_result.iterations - 1, 0),
            bundle_refinements_total=bundle_refinements_total,
            bundle_stable=bundle_result.stable,
            bundle_steps=bundle_result.steps,
            executor_iterations=exec_result.iterations,
            executor_refinements=max(exec_result.iterations - 1, 0),
            executor_refinements_total=executor_refinements_total,
            executor_stable=exec_result.stable,
            executor_steps=exec_result.steps,
            architect_cycles=architect_cycles,
            open_world=open_world,
        )


@dataclass(frozen=True)
class LongitudinalCase:
    user_goal: str
    open_world: bool
    use_cot: bool = False


@dataclass(frozen=True)
class FullPipelineResult:
    longitudinal_result: LongitudinalResult
    prediction: Prediction


class MPPFullPipeline:
    """Run longitudinal optimization around the vertical MPPAutoAdapter loop."""

    def __init__(
        self,
        *,
        template: str,
        mutate_function: MutateFunction,
        longitudinal_iters: int = 2,
        metric: LongitudinalMetric | None = None,
        adapter_kwargs: Mapping[str, object] | None = None,
    ) -> None:
        self.template = template
        self.mutate_function = mutate_function
        self.longitudinal_iters = longitudinal_iters
        self.metric = metric or TraceCostMetric()
        self.adapter_kwargs = dict(adapter_kwargs or {})

    def run(
        self,
        *,
        user_goal: str,
        open_world: bool,
        cases: Sequence[LongitudinalCase],
        architect_max_iters: int | None = None,
        executor_max_iters: int | None = None,
        use_cot: bool = False,
    ) -> FullPipelineResult:
        if not cases:
            raise ValueError("cases must be non-empty for longitudinal optimization")

        def score_function(
            _template: str, dataset: Sequence[LongitudinalCase], blocks
        ) -> LongitudinalScore:
            program_default = self._build_program(blocks, use_cot=False)
            program_cot = self._build_program(blocks, use_cot=True)
            traces: list[LongitudinalTrace] = []
            for case in dataset:
                program = program_cot if case.use_cot else program_default
                goal = self._apply_blocks(blocks, case.user_goal)
                try:
                    result = program(
                        user_goal=goal,
                        open_world=case.open_world,
                        architect_max_iters=architect_max_iters,
                        executor_max_iters=executor_max_iters,
                    )
                except Exception as exc:  # noqa: BLE001
                    traces.append(
                        LongitudinalTrace(
                            case=case,
                            errors=[f"{type(exc).__name__}: {exc}"],
                        )
                    )
                    continue
                bundle_refinements = getattr(
                    result,
                    "bundle_refinements_total",
                    result.bundle_refinements,
                )
                executor_refinements = getattr(
                    result,
                    "executor_refinements_total",
                    result.executor_refinements,
                )
                traces.append(
                    LongitudinalTrace(
                        case=case,
                        bundle_refinements=bundle_refinements,
                        executor_refinements=executor_refinements,
                        bundle_steps=getattr(result, "bundle_steps", None),
                        execution_steps=getattr(result, "executor_steps", None),
                        qa_passed=result.qa_passed,
                        executor_stable=result.executor_stable,
                    )
                )
            return LongitudinalScore(score=self.metric.score(traces), traces=traces)

        refiner = MPPLongitudinalRefiner(
            mutate_function=self.mutate_function,
            score_function=score_function,
            max_iters=self.longitudinal_iters,
        )
        longitudinal_result = refiner.refine(self.template, cases)
        blocks = longitudinal_result.blocks
        program = self._build_program(blocks, use_cot=use_cot)
        goal = self._apply_blocks(blocks, user_goal)
        prediction = program(
            user_goal=goal,
            open_world=open_world,
            architect_max_iters=architect_max_iters,
            executor_max_iters=executor_max_iters,
        )
        return FullPipelineResult(
            longitudinal_result=longitudinal_result,
            prediction=prediction,
        )

    def _build_program(
        self, blocks: Mapping[str, str], *, use_cot: bool
    ) -> MPPAutoAdapter:
        kwargs = dict(self.adapter_kwargs)
        kwargs.setdefault("architect_role_instructions", blocks.get("architect_primer"))
        kwargs.setdefault("executor_role_instructions", blocks.get("executor_primer"))
        kwargs.setdefault("qa_role_instructions", blocks.get("qa_primer"))
        if use_cot and "executor" not in kwargs:
            kwargs["executor"] = dspy.ChainOfThought(ProtocolExecutor)
        return MPPAutoAdapter(**kwargs)

    @staticmethod
    def _apply_blocks(blocks: Mapping[str, str], goal: str) -> str:
        entry_prompt = (blocks.get("entry_prompt") or "").strip()
        strategy_payload = (blocks.get("strategy_payload") or "").strip()
        parts = []
        if entry_prompt:
            parts.append(entry_prompt)
        if strategy_payload:
            parts.append(f"Strategy guidance:\n{strategy_payload}")
        parts.append(f"User goal:\n{goal}")
        return "\n\n".join(parts)
