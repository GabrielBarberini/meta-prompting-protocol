from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping, Sequence

from .mpp_optimizer import LongitudinalStep, LongitudinalTrace

LLMCall = Callable[[str], Any]


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


def _parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = _strip_code_fences(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, Mapping):
        for key in ("text", "content"):
            value = response.get(key)
            if isinstance(value, str):
                return value
    if hasattr(response, "text"):
        value = getattr(response, "text")
        if isinstance(value, str):
            return value
    return str(response)


def _call_llm(llm_call: LLMCall, prompt: str) -> str:
    try:
        response = llm_call(prompt=prompt)
    except TypeError:
        response = llm_call(prompt)
    return _coerce_text(response)


def _summarize_cases(cases: Iterable[Any]) -> str:
    lines = []
    for idx, case in enumerate(cases, start=1):
        if isinstance(case, Mapping):
            name = case.get("name", f"Case {idx}")
            goal = case.get("user_goal", case.get("goal", str(case)))
            open_world = case.get("open_world")
            use_cot = case.get("use_cot")
        else:
            name = getattr(case, "name", f"Case {idx}")
            goal = getattr(case, "user_goal", getattr(case, "goal", str(case)))
            open_world = getattr(case, "open_world", None)
            use_cot = getattr(case, "use_cot", None)
        flags = []
        if open_world is not None:
            flags.append(f"open_world={open_world}")
        if use_cot is not None:
            flags.append(f"use_cot={use_cot}")
        header = f"- {name}"
        if flags:
            header += f" ({', '.join(flags)})"
        lines.append(f"{header}:\n{goal}")
    return "\n\n".join(lines)


def _summarize_traces(traces: Iterable[LongitudinalTrace] | None) -> str:
    if not traces:
        return ""
    lines = []
    for trace in traces:
        case = trace.case
        name = getattr(case, "name", str(case))
        refinements = (trace.bundle_refinements or 0) + (
            trace.executor_refinements or 0
        )
        issues = []
        if trace.errors:
            issues.extend(trace.errors)
        line = f"- {name}: refinements={refinements}"
        if trace.qa_passed is not None:
            line += f", qa_passed={trace.qa_passed}"
        if trace.bundle_stable is not None:
            line += f", bundle_stable={trace.bundle_stable}"
        if trace.executor_stable is not None:
            line += f", executor_stable={trace.executor_stable}"
        if issues:
            line += f", issues={issues}"
        lines.append(line)
    return "\n".join(lines)


def _summarize_history(history: Iterable[LongitudinalStep] | None) -> str:
    if not history:
        return ""
    steps = list(history)
    last = steps[-1]
    best = max(steps, key=lambda step: step.score)
    delta = last.score - steps[-2].score if len(steps) > 1 else 0.0
    return (
        f"last_score={last.score:.2f}, best_score={best.score:.2f}, delta={delta:.2f}"
    )


class DefaultLongitudinalMutator:
    """Default mutation policy for longitudinal refinement."""

    def __init__(
        self,
        lm: LLMCall,
        max_sentences: int = 3,
        allowed_keys: Sequence[str] = (
            "strategy_payload",
            "architect_primer",
            "executor_primer",
        ),
    ) -> None:
        self.lm = lm
        self.max_sentences = max_sentences
        self.allowed_keys = tuple(allowed_keys)

    def __call__(
        self,
        blocks: Mapping[str, str],
        dataset: Sequence[Any],
        traces: Iterable[LongitudinalTrace] | None = None,
        history: Iterable[LongitudinalStep] | None = None,
    ) -> Mapping[str, str]:
        case_summary = _summarize_cases(dataset)
        trace_summary = _summarize_traces(traces)
        history_summary = _summarize_history(history)
        prompt = (
            "You are optimizing prompt primers for an MPP system. "
            "Do not modify entry_prompt; keep it fixed. "
            "You may update architect_primer, executor_primer, and strategy_payload. "
            "These texts are prepended before the user goal or used as role primers. "
            f"Keep each block short (<= {self.max_sentences} sentences)."
            "\n\nCurrent blocks:\n"
            f"{json.dumps(dict(blocks), indent=2, ensure_ascii=True)}"
            "\n\nDataset goals:\n"
            f"{case_summary}\n\n"
        )
        if trace_summary:
            prompt += f"Recent vertical traces:\n{trace_summary}\n\n"
        if history_summary:
            prompt += f"Longitudinal score history: {history_summary}\n\n"
        prompt += (
            "Return JSON with keys: strategy_payload, architect_primer, "
            "executor_primer."
        )
        updated = _call_llm(self.lm, prompt)
        payload = _parse_json_object(updated)
        if payload is None:
            return {}
        return {
            key: str(payload[key])
            for key in self.allowed_keys
            if key in payload and payload[key] is not None
        }
