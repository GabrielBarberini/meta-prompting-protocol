from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import dspy
from dspy.primitives.prediction import Prediction
from dspy.teleprompt.teleprompt import Teleprompter

from .dspy_adapters import MPPArchitectAdapter, MPPExecutorAdapter, MPPQAAdapter
from .feedback import FeedbackEvent, FeedbackTrace
from .metrics import AllPassMetric, LongitudinalMetric
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


def _append_executor_feedback(
    trace: FeedbackTrace, exec_result: ExecutionResult
) -> FeedbackTrace:
    event = FeedbackEvent.from_execution_result(exec_result)
    if event.last_response:
        event = event.model_copy(
            update={"last_response": _strip_reasoning_for_feedback(event.last_response)}
        )
    return trace.append(event)


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
        feedback_trace = FeedbackTrace()
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
                "expect_reasoning": self.executor_expect_reasoning,
            }
            if self.executor_role_instructions is not None:
                executor_kwargs["role_instructions"] = self.executor_role_instructions
            executor_adapter = MPPExecutorAdapter(**executor_kwargs)
            executor_call = _wrap_with_adapter(
                self.executor, executor_adapter, lm=self.executor_lm
            )

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
            feedback_trace = _append_executor_feedback(feedback_trace, exec_result)
            feedback = feedback_trace.to_prompt_text()
            previous_bundle = bundle_result.bundle

        if bundle_result is None or exec_result is None:
            raise ValueError("Failed to produce a bundle/executor result.")

        return Prediction(
            bundle=bundle_result.bundle,
            decoded_bundle=exec_result.decoded_bundle,
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
class FullPipelineResult:
    longitudinal_result: LongitudinalResult
    prediction: Prediction


class _OptimizedMPPAutoAdapter(dspy.Module):
    def __init__(
        self,
        base_adapter: MPPAutoAdapter,
        blocks: Mapping[str, str],
        longitudinal_result: LongitudinalResult,
    ) -> None:
        super().__init__()
        self.base_adapter = base_adapter
        self.blocks = dict(blocks)
        self.template = longitudinal_result.template
        self.longitudinal_result = longitudinal_result

    def forward(
        self,
        *,
        user_goal: str,
        open_world: bool,
        architect_max_iters: int | None = None,
        executor_max_iters: int | None = None,
    ) -> Prediction:
        goal = MPPAutoAdapterOptimizer._apply_blocks(self.blocks, user_goal)
        return self.base_adapter(
            user_goal=goal,
            open_world=open_world,
            architect_max_iters=architect_max_iters,
            executor_max_iters=executor_max_iters,
        )


class MPPAutoAdapterOptimizer(Teleprompter):
    """DSPy teleprompter that optimizes MPPAutoAdapter prompt blocks."""

    def __init__(
        self,
        *,
        template: str,
        mutate_function: MutateFunction,
        longitudinal_iters: int = 2,
        longitudinal_patience: int | None = None,
        longitudinal_min_delta: float = 0.0,
        metric: LongitudinalMetric | None = None,
        adapter_kwargs: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__()
        self.template = template
        self.mutate_function = mutate_function
        self.longitudinal_iters = longitudinal_iters
        self.longitudinal_patience = longitudinal_patience
        self.longitudinal_min_delta = longitudinal_min_delta
        self.metric = metric or AllPassMetric()
        self.adapter_kwargs = dict(adapter_kwargs or {})

    def compile(
        self,
        student: MPPAutoAdapter,
        *,
        trainset: Any,
        teacher=None,
        valset=None,
        **kwargs,
    ) -> dspy.Module:
        if not isinstance(student, MPPAutoAdapter):
            raise TypeError(
                "MPPAutoAdapterOptimizer expects an MPPAutoAdapter student."
            )
        case = self._normalize_case(trainset)
        architect_max_iters = kwargs.get("architect_max_iters")
        executor_max_iters = kwargs.get("executor_max_iters")
        adapter_kwargs = self._resolve_adapter_kwargs(student)
        adapter_kwargs.update(self.adapter_kwargs)
        longitudinal_result = self._optimize_template(
            case,
            adapter_kwargs=adapter_kwargs,
            architect_max_iters=architect_max_iters,
            executor_max_iters=executor_max_iters,
        )
        blocks = longitudinal_result.blocks
        base_program = self._build_program(
            blocks,
            use_cot=False,
            adapter_kwargs=adapter_kwargs,
        )
        return _OptimizedMPPAutoAdapter(
            base_program,
            blocks,
            longitudinal_result,
        )

    def run(
        self,
        *,
        user_goal: str,
        open_world: bool,
        case: Any,
        architect_max_iters: int | None = None,
        executor_max_iters: int | None = None,
        use_cot: bool = False,
    ) -> FullPipelineResult:
        case = self._normalize_case(case)
        adapter_kwargs = dict(self.adapter_kwargs)
        longitudinal_result = self._optimize_template(
            case,
            adapter_kwargs=adapter_kwargs,
            architect_max_iters=architect_max_iters,
            executor_max_iters=executor_max_iters,
        )
        blocks = longitudinal_result.blocks
        program = self._build_program(
            blocks,
            use_cot=use_cot,
            adapter_kwargs=adapter_kwargs,
        )
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

    def _optimize_template(
        self,
        case: Any,
        *,
        adapter_kwargs: Mapping[str, object],
        architect_max_iters: int | None,
        executor_max_iters: int | None,
    ) -> LongitudinalResult:
        def score_function(
            _template: str, dataset: Sequence[Any], blocks
        ) -> LongitudinalScore:
            program_default = self._build_program(
                blocks,
                use_cot=False,
                adapter_kwargs=adapter_kwargs,
            )
            program_cot = self._build_program(
                blocks,
                use_cot=True,
                adapter_kwargs=adapter_kwargs,
            )
            traces: list[LongitudinalTrace] = []
            for case in dataset:
                user_goal = self._case_user_goal(case)
                open_world = self._case_open_world(case)
                use_cot = self._case_use_cot(case)
                program = program_cot if use_cot else program_default
                goal = self._apply_blocks(blocks, user_goal)
                try:
                    result = program(
                        user_goal=goal,
                        open_world=open_world,
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
                issues = []
                if result.qa_passed is False and result.qa_result:
                    issues = list(result.qa_result.get("issues") or [])
                traces.append(
                    LongitudinalTrace(
                        case=case,
                        bundle_refinements=bundle_refinements,
                        executor_refinements=executor_refinements,
                        bundle_steps=getattr(result, "bundle_steps", None),
                        execution_steps=getattr(result, "executor_steps", None),
                        bundle_stable=getattr(result, "bundle_stable", None),
                        qa_passed=result.qa_passed,
                        executor_stable=result.executor_stable,
                        errors=issues,
                    )
                )
            return LongitudinalScore(score=self.metric.score(traces), traces=traces)

        refiner = MPPLongitudinalRefiner(
            mutate_function=self.mutate_function,
            score_function=score_function,
            max_iters=self.longitudinal_iters,
            patience=self.longitudinal_patience,
            min_delta=self.longitudinal_min_delta,
        )
        return refiner.refine(self.template, case)

    @staticmethod
    def _normalize_case(trainset: Any) -> Any:
        if isinstance(trainset, Mapping):
            return trainset
        if isinstance(trainset, Sequence) and not isinstance(trainset, (str, bytes)):
            if len(trainset) != 1:
                raise ValueError(
                    "MPPAutoAdapterOptimizer expects a single case; "
                    "run multiple cases separately."
                )
            return trainset[0]
        if trainset is None:
            raise ValueError("A case is required for longitudinal optimization.")
        return trainset

    def _resolve_adapter_kwargs(self, student: MPPAutoAdapter) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "spec_text": student.spec_text,
            "max_iters": student.max_iters,
            "architect_max_iters": student.architect_max_iters,
            "executor_max_iters": student.executor_max_iters,
            "architect": student.architect,
            "executor": student.executor,
            "qa": student.qa,
            "architect_lm": student.architect_lm,
            "executor_lm": student.executor_lm,
            "qa_lm": student.qa_lm,
        }
        if student.executor_role_instructions is not None:
            kwargs["executor_role_instructions"] = student.executor_role_instructions
        if student.qa_role_instructions is not None:
            kwargs["qa_role_instructions"] = student.qa_role_instructions
        return kwargs

    @staticmethod
    def _case_user_goal(case: Any) -> str:
        if isinstance(case, Mapping):
            value = case.get("user_goal")
        else:
            value = getattr(case, "user_goal", None)
        if not isinstance(value, str):
            raise ValueError("Each case must provide a string user_goal.")
        return value

    @staticmethod
    def _case_open_world(case: Any) -> bool:
        if isinstance(case, Mapping):
            return bool(case.get("open_world", False))
        return bool(getattr(case, "open_world", False))

    @staticmethod
    def _case_use_cot(case: Any) -> bool:
        if isinstance(case, Mapping):
            return bool(case.get("use_cot", False))
        return bool(getattr(case, "use_cot", False))

    def _build_program(
        self,
        blocks: Mapping[str, str],
        *,
        use_cot: bool,
        adapter_kwargs: Mapping[str, object],
    ) -> MPPAutoAdapter:
        kwargs = dict(adapter_kwargs)
        kwargs["architect_role_instructions"] = blocks.get("architect_primer")
        kwargs["executor_role_instructions"] = blocks.get("executor_primer")
        kwargs["qa_role_instructions"] = blocks.get("qa_primer")
        if use_cot:
            executor = kwargs.get("executor")
            if executor is None or not _predictor_uses_cot(executor):
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
