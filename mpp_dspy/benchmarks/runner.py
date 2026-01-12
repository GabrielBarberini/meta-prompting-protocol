from __future__ import annotations

import argparse
import ast
import json
import logging
import math
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import dspy

from mpp_dspy import DefaultLongitudinalMutator, MPPAutoAdapter, MPPAutoAdapterOptimizer
from mpp_dspy.metrics import AllPassMetric
from mpp_dspy.template_tokens import extract_mutable_blocks

from .langdock import LangdockLM, create_chat_completion

DEFAULT_TEMPLATE = """\
[ENTRY_PROMPT]
{{MPP_MUTABLE:entry_prompt}}
Follow the user goal precisely and preserve all constraints.
Do not add new requirements.
{{/MPP_MUTABLE}}
[STRATEGY_PAYLOAD]
{{MPP_MUTABLE:strategy_payload}}
Use any strategy tag needed, but keep it minimal.
{{/MPP_MUTABLE}}
[ARCHITECT_PRIMER]
{{MPP_MUTABLE:architect_primer}}
Keep protocols compact, explicit, and schema-compliant.
{{/MPP_MUTABLE}}
[EXECUTOR_PRIMER]
{{MPP_MUTABLE:executor_primer}}
Execute the bundle precisely and follow the payload order.
{{/MPP_MUTABLE}}
"""

DATASET_NAMES = {"math", "gsm8k", "game24"}
METHOD_NAMES = {
    "raw",
    "zero_shot",
    "few_shot",
    "cot",
    "react",
    "self_consistency",
    "mpp",
    "mpp_optimized",
}

FORMAT_HINTS = {
    "math": "Return the final answer in \\boxed{...}.",
    "gsm8k": "Return the final numeric answer after '#### '.",
    "game24": (
        "Return a single arithmetic expression that equals 24 using the given "
        "numbers."
    ),
}

FEW_SHOT = {
    "math": [
        {
            "question": "Compute 2 + 5.",
            "answer": "Solution: 2 + 5 = 7. Final: \\boxed{7}.",
        },
        {
            "question": "Compute 10 - 3.",
            "answer": "Solution: 10 - 3 = 7. Final: \\boxed{7}.",
        },
    ],
    "gsm8k": [
        {
            "question": "Alice has 3 apples and buys 2 more. How many apples now?",
            "answer": "She has 3 + 2 = 5 apples. #### 5",
        },
        {
            "question": "A book costs 4 dollars. You buy 3 books. Total cost?",
            "answer": "3 * 4 = 12. #### 12",
        },
    ],
    "game24": [
        {
            "question": "Numbers: 3, 3, 8, 8. Target: 24.",
            "answer": "(8 / (3 - 8 / 3))",
        },
        {
            "question": "Numbers: 1, 3, 4, 6. Target: 24.",
            "answer": "(6 / (1 - 3 / 4))",
        },
    ],
}


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    dataset: str
    question: str
    answer: str
    meta: dict[str, Any]


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    path: Path
    limit: int | None = None


@dataclass(frozen=True)
class ModelGroup:
    name: str
    baseline_model: str
    architect_model: str
    executor_model: str
    qa_model: str


def run_benchmarks(
    config: Mapping[str, Any],
    *,
    log_every: int | None = None,
    logger: logging.Logger | None = None,
    continue_on_error: bool = False,
    max_errors: int | None = None,
) -> dict[str, Any]:
    datasets = _load_dataset_configs(config)
    methods = _normalize_methods(config)
    model_groups = _load_model_groups(config)
    temperatures = config.get("temperatures", {})
    langdock_settings = _load_langdock_settings(config)
    model_fallbacks = _load_model_fallbacks(config)
    optimizer_config = _load_optimizer_config(config)
    optimizer_template = _load_optimizer_template(config)
    sc_samples = int(config.get("self_consistency_samples", 5))
    record_samples = bool(config.get("record_samples", True))
    mpp_blocks = _load_blocks_config(config, "mpp_blocks", "mpp_template")
    optimized_blocks = _load_blocks_config(
        config, "mpp_optimized_blocks", "mpp_optimized_template"
    )

    report: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "results": [],
    }

    for dataset_config in datasets:
        cases = _load_cases(dataset_config)
        _log_info(
            logger,
            "Loaded dataset=%s cases=%d",
            dataset_config.name,
            len(cases),
        )
        for group in model_groups:
            _log_info(
                logger,
                ("Model group=%s baseline=%s architect=%s executor=%s qa=%s"),
                group.name,
                group.baseline_model,
                group.architect_model,
                group.executor_model,
                group.qa_model,
            )
            runner = _ModelRunner(
                group, temperatures, langdock_settings, model_fallbacks
            )
            mpp_runner = _MPPRunner(
                group, mpp_blocks, optimized_blocks, langdock_settings, model_fallbacks
            )
            optimized_blocks_override = None
            optimizer_meta = None
            if "mpp_optimized" in methods:
                optimized_blocks_override, optimizer_meta = _prepare_optimizer_blocks(
                    cases=cases,
                    mpp_runner=mpp_runner,
                    template=optimizer_template,
                    optimizer_config=optimizer_config,
                    logger=logger,
                )
            dspy.settings.configure(lm=mpp_runner.executor_lm)
            for method in methods:
                if (
                    method == "mpp_optimized"
                    and optimized_blocks is None
                    and optimized_blocks_override is None
                ):
                    raise ValueError(
                        "mpp_optimized requires optimized blocks/template."
                    )
                _log_info(
                    logger,
                    "Start dataset=%s group=%s method=%s cases=%d",
                    dataset_config.name,
                    group.name,
                    method,
                    len(cases),
                )
                result = _run_method(
                    method,
                    cases,
                    runner,
                    mpp_runner,
                    sc_samples,
                    record_samples,
                    dataset_name=dataset_config.name,
                    group_name=group.name,
                    log_every=log_every,
                    logger=logger,
                    continue_on_error=continue_on_error,
                    max_errors=max_errors,
                    optimized_blocks=(
                        optimized_blocks_override if method == "mpp_optimized" else None
                    ),
                )
                _log_info(
                    logger,
                    (
                        "Done dataset=%s group=%s method=%s accuracy=%.4f"
                        " correct=%d total=%d"
                    ),
                    dataset_config.name,
                    group.name,
                    method,
                    result["accuracy"],
                    result["correct"],
                    result["total"],
                )
                result.update(
                    {
                        "dataset": dataset_config.name,
                        "model_group": group.name,
                        "method": method,
                        "optimizer_enabled": bool(
                            optimizer_meta
                            and method == "mpp_optimized"
                            and optimizer_meta.get("used")
                        ),
                        "optimizer_iters_actual": (
                            optimizer_meta["iterations"]
                            if optimizer_meta and method == "mpp_optimized"
                            else 0
                        ),
                        "optimizer_iters_max": (
                            optimizer_meta["max_iters"]
                            if optimizer_meta and method == "mpp_optimized"
                            else 0
                        ),
                        "optimizer_early_stop": (
                            optimizer_meta["early_stop"]
                            if optimizer_meta and method == "mpp_optimized"
                            else False
                        ),
                    }
                )
                report["results"].append(result)
    return report


def _load_dataset_configs(config: Mapping[str, Any]) -> list[DatasetConfig]:
    datasets = config.get("datasets", [])
    if not datasets:
        raise ValueError("No datasets configured.")
    result = []
    for item in datasets:
        name = str(item.get("name", "")).strip()
        if name not in DATASET_NAMES:
            raise ValueError(f"Unsupported dataset: {name}")
        path = Path(item.get("path", ""))
        if not path:
            raise ValueError(f"Missing path for dataset {name}.")
        limit = item.get("limit")
        result.append(DatasetConfig(name=name, path=path, limit=limit))
    return result


def _load_model_groups(config: Mapping[str, Any]) -> list[ModelGroup]:
    groups = config.get("model_groups", [])
    if not groups:
        raise ValueError("No model_groups configured.")
    result = []
    for item in groups:
        name = str(item.get("name", "")).strip() or "default"
        baseline = str(item.get("baseline_model", "")).strip()
        architect = str(item.get("architect_model", baseline)).strip()
        executor = str(item.get("executor_model", baseline)).strip()
        qa = str(item.get("qa_model", executor)).strip()
        if not baseline:
            raise ValueError(f"Missing baseline_model for {name}.")
        result.append(
            ModelGroup(
                name=name,
                baseline_model=baseline,
                architect_model=architect,
                executor_model=executor,
                qa_model=qa,
            )
        )
    return result


def _normalize_methods(config: Mapping[str, Any]) -> list[str]:
    methods = config.get("methods", [])
    if not methods:
        raise ValueError("No methods configured.")
    normalized = []
    for method in methods:
        method = str(method).strip()
        if method not in METHOD_NAMES:
            raise ValueError(f"Unsupported method: {method}")
        normalized.append(method)
    return normalized


def _load_langdock_settings(config: Mapping[str, Any]) -> dict[str, Any]:
    settings = dict(config.get("langdock", {}))
    for key in ("timeout", "retries", "base_delay"):
        if key in config and key not in settings:
            settings[key] = config[key]

    timeout = settings.get("timeout")
    retries = settings.get("retries")
    base_delay = settings.get("base_delay")

    return {
        "timeout": float(timeout) if timeout is not None else None,
        "retries": int(retries) if retries is not None else None,
        "base_delay": float(base_delay) if base_delay is not None else None,
    }


def _load_model_fallbacks(config: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = config.get("model_fallbacks")
    if raw is None:
        raw = config.get("langdock", {}).get("model_fallbacks", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("model_fallbacks must be a mapping of model -> list.")
    fallbacks: dict[str, list[str]] = {}
    for key, value in raw.items():
        model = str(key).strip()
        if not model:
            continue
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            raise ValueError(f"Fallbacks for {model} must be a list of model names.")
        cleaned = []
        seen = set()
        for item in items:
            name = str(item).strip()
            if not name or name == model or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        if cleaned:
            fallbacks[model] = cleaned
    return fallbacks


def _load_optimizer_config(config: Mapping[str, Any]) -> dict[str, Any]:
    optimizer_iters = 0
    for key in ("optimizer_iters", "longitudinal_iters"):
        if key in config:
            optimizer_iters = int(config[key])
            break
    patience = None
    for key in ("optimizer_patience", "longitudinal_patience"):
        if key in config:
            patience = int(config[key])
            break
    min_delta = 0.0
    for key in ("optimizer_min_delta", "longitudinal_min_delta"):
        if key in config:
            min_delta = float(config[key])
            break
    return {
        "max_iters": optimizer_iters,
        "patience": patience,
        "min_delta": min_delta,
    }


def _load_optimizer_template(config: Mapping[str, Any]) -> str:
    template_path = config.get("optimizer_template") or config.get("mpp_template")
    if template_path:
        return Path(template_path).read_text(encoding="utf-8")
    return DEFAULT_TEMPLATE


def _prepare_optimizer_blocks(
    *,
    cases: list[BenchmarkCase],
    mpp_runner: "_MPPRunner",
    template: str,
    optimizer_config: Mapping[str, Any],
    logger: logging.Logger | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    max_iters = int(optimizer_config.get("max_iters", 0) or 0)
    patience = optimizer_config.get("patience")
    min_delta = float(optimizer_config.get("min_delta", 0.0) or 0.0)
    if max_iters <= 0:
        if mpp_runner.optimized_blocks:
            return mpp_runner.optimized_blocks, {
                "used": False,
                "iterations": 0,
                "max_iters": 0,
                "early_stop": False,
            }
        raise ValueError(
            "mpp_optimized requires optimizer_iters > 0 or optimized blocks/template."
        )
    if not cases:
        raise ValueError("Optimizer requires at least one case.")
    case = _build_optimizer_case(cases[0])
    _log_info(
        logger,
        "Optimizer start iters=%d patience=%s min_delta=%s",
        max_iters,
        patience,
        min_delta,
    )
    mutator = DefaultLongitudinalMutator(mpp_runner.architect_lm)
    optimizer = MPPAutoAdapterOptimizer(
        template=template,
        mutate_function=mutator,
        longitudinal_iters=max_iters,
        longitudinal_patience=patience,
        longitudinal_min_delta=min_delta,
        metric=AllPassMetric(),
    )
    base_program = MPPAutoAdapter(
        architect_lm=mpp_runner.architect_lm,
        executor_lm=mpp_runner.executor_lm,
        qa_lm=mpp_runner.qa_lm,
    )
    optimized_program = optimizer.compile(base_program, trainset=case)
    iterations = optimized_program.longitudinal_result.iterations
    early_stop = iterations < max_iters
    _log_info(
        logger,
        "Optimizer done iterations=%d early_stop=%s",
        iterations,
        early_stop,
    )
    return optimized_program.blocks, {
        "used": True,
        "iterations": iterations,
        "max_iters": max_iters,
        "early_stop": early_stop,
    }


def _build_optimizer_case(case: BenchmarkCase) -> dict[str, Any]:
    return {
        "name": case.case_id,
        "user_goal": case.question,
        "open_world": False,
        "use_cot": False,
    }


def _parse_methods_arg(value: str) -> list[str]:
    methods = [item.strip() for item in value.split(",") if item.strip()]
    if not methods:
        raise ValueError("No methods provided.")
    for method in methods:
        if method not in METHOD_NAMES:
            raise ValueError(f"Unsupported method: {method}")
    return methods


def _apply_methods_config(
    config: Mapping[str, Any],
    *,
    methods_override: str | None,
    skip_methods: list[str] | None,
) -> dict[str, Any]:
    updated = dict(config)
    methods = _normalize_methods(updated)
    if methods_override:
        methods = _parse_methods_arg(methods_override)
    if skip_methods:
        skip_set = {method.strip() for method in skip_methods if method.strip()}
        methods = [method for method in methods if method not in skip_set]
    if not methods:
        raise ValueError("No methods configured after overrides.")
    updated["methods"] = methods
    return updated


def _parse_model_groups_arg(value: str) -> list[str]:
    groups = [item.strip() for item in value.split(",") if item.strip()]
    if not groups:
        raise ValueError("No model groups provided.")
    return groups


def _apply_model_groups_config(
    config: Mapping[str, Any],
    *,
    groups_override: str | None,
    skip_groups: list[str] | None,
) -> dict[str, Any]:
    updated = dict(config)
    groups = config.get("model_groups", [])
    if not isinstance(groups, list):
        raise ValueError("model_groups must be a list.")

    if groups_override:
        selected = set(_parse_model_groups_arg(groups_override))
        groups = [group for group in groups if group.get("name") in selected]
    if skip_groups:
        skip_set = {group.strip() for group in skip_groups if group.strip()}
        groups = [group for group in groups if group.get("name") not in skip_set]

    if not groups:
        raise ValueError("No model groups configured after overrides.")
    updated["model_groups"] = groups
    return updated


def _load_blocks_config(
    config: Mapping[str, Any], blocks_key: str, template_key: str
) -> dict[str, str] | None:
    blocks_path = config.get(blocks_key)
    if blocks_path:
        return _read_blocks(Path(blocks_path))
    template_path = config.get(template_key)
    if template_path:
        return _read_template_blocks(Path(template_path))
    if blocks_key == "mpp_blocks":
        return extract_mutable_blocks(DEFAULT_TEMPLATE)
    return None


def _read_template_blocks(path: Path) -> dict[str, str]:
    template = path.read_text(encoding="utf-8")
    return extract_mutable_blocks(template)


def _read_blocks(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Blocks file must be a JSON object: {path}")
    return {str(k): str(v) for k, v in payload.items()}


def _load_cases(dataset_config: DatasetConfig) -> list[BenchmarkCase]:
    records = _read_records(dataset_config.path)
    cases = []
    for idx, record in enumerate(records):
        cases.append(_build_case(dataset_config.name, record, idx))
    if dataset_config.limit:
        cases = cases[: dataset_config.limit]
    return cases


def _read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported dataset format: {path}")


def _build_case(dataset: str, record: Mapping[str, Any], index: int) -> BenchmarkCase:
    match dataset:
        case "math":
            question = record.get("problem") or record.get("question")
            answer = record.get("solution") or record.get("answer")
            if not question or not answer:
                raise ValueError("MATH record missing problem/solution.")
            return BenchmarkCase(
                case_id=str(record.get("id", index)),
                dataset=dataset,
                question=str(question).strip(),
                answer=str(answer),
                meta={},
            )
        case "gsm8k":
            question = record.get("question")
            answer = record.get("answer")
            if not question or not answer:
                raise ValueError("GSM8K record missing question/answer.")
            return BenchmarkCase(
                case_id=str(record.get("id", index)),
                dataset=dataset,
                question=str(question).strip(),
                answer=str(answer),
                meta={},
            )
        case "game24":
            numbers = record.get("numbers")
            if not isinstance(numbers, list):
                numbers = _parse_numbers(record.get("question") or record.get("input"))
            if not numbers:
                raise ValueError("Game24 record missing numbers.")
            target = record.get("target", 24)
            question = (
                f"Numbers: {', '.join(str(n) for n in numbers)}. Target: {target}."
            )
            return BenchmarkCase(
                case_id=str(record.get("id", index)),
                dataset=dataset,
                question=question,
                answer=str(target),
                meta={"numbers": numbers, "target": target},
            )
    raise ValueError(f"Unsupported dataset: {dataset}")


def _parse_numbers(text: Any) -> list[int]:
    if not isinstance(text, str):
        return []
    return [int(value) for value in re.findall(r"-?\d+", text)]


class _ModelRunner:
    def __init__(
        self,
        group: ModelGroup,
        temperatures: Mapping[str, Any],
        langdock_settings: Mapping[str, Any] | None = None,
        model_fallbacks: Mapping[str, list[str]] | None = None,
    ) -> None:
        self.group = group
        self.temperatures = temperatures
        settings = langdock_settings or {}
        self.request_timeout = settings.get("timeout")
        self.request_retries = settings.get("retries")
        self.request_base_delay = settings.get("base_delay")
        self.model_fallbacks = dict(model_fallbacks or {})
        self.active_model = group.baseline_model

    def generate(self, prompt: str, method: str) -> str:
        temperature = self._temperature_for(method)
        fallbacks = self.model_fallbacks.get(self.group.baseline_model, [])
        response = create_chat_completion(
            [{"role": "user", "content": prompt}],
            model=self.active_model,
            assistant_name="mpp-benchmark",
            assistant_instructions="You are a helpful assistant.",
            temperature=temperature,
            timeout=self.request_timeout,
            retries=self.request_retries,
            base_delay=self.request_base_delay,
            fallback_models=fallbacks,
        )
        if isinstance(response, dict):
            resolved = response.get("model")
            if isinstance(resolved, str) and resolved:
                self.active_model = resolved
        return _normalize_text(_assistant_text(response))

    def _temperature_for(self, method: str) -> float | None:
        raw = self.temperatures.get(method)
        if raw is not None:
            return float(raw)
        default = self.temperatures.get("default")
        return float(default) if default is not None else None


class _MPPRunner:
    def __init__(
        self,
        group: ModelGroup,
        blocks: Mapping[str, str] | None,
        optimized_blocks: Mapping[str, str] | None,
        langdock_settings: Mapping[str, Any] | None,
        model_fallbacks: Mapping[str, list[str]] | None,
    ) -> None:
        self.group = group
        self.blocks = dict(blocks or {})
        self.optimized_blocks = dict(optimized_blocks or {})
        settings = langdock_settings or {}
        fallbacks = dict(model_fallbacks or {})
        self.architect_lm = LangdockLM(
            model=group.architect_model,
            fallback_models=fallbacks.get(group.architect_model, []),
            **settings,
        )
        self.executor_lm = LangdockLM(
            model=group.executor_model,
            fallback_models=fallbacks.get(group.executor_model, []),
            **settings,
        )
        self.qa_lm = LangdockLM(
            model=group.qa_model,
            fallback_models=fallbacks.get(group.qa_model, []),
            **settings,
        )

    def run(
        self,
        case: BenchmarkCase,
        *,
        optimized: bool,
        blocks_override: Mapping[str, str] | None = None,
    ) -> str:
        if blocks_override is not None:
            blocks = dict(blocks_override)
        else:
            blocks = self.optimized_blocks if optimized else self.blocks
        goal = _apply_prompt_blocks(blocks, case.question)
        adapter = MPPAutoAdapter(
            architect_lm=self.architect_lm,
            executor_lm=self.executor_lm,
            qa_lm=self.qa_lm,
            architect_role_instructions=blocks.get("architect_primer"),
            executor_role_instructions=blocks.get("executor_primer"),
            qa_role_instructions=blocks.get("qa_primer"),
        )
        result = adapter(user_goal=goal, open_world=False)
        decoded_bundle = result.decoded_bundle
        if not isinstance(decoded_bundle, str):
            decoded_bundle = json.dumps(decoded_bundle, ensure_ascii=True)
        return _normalize_text(decoded_bundle)


def _apply_prompt_blocks(blocks: Mapping[str, str], goal: str) -> str:
    entry_prompt = (blocks.get("entry_prompt") or "").strip()
    strategy_payload = (blocks.get("strategy_payload") or "").strip()
    parts = []
    if entry_prompt:
        parts.append(entry_prompt)
    if strategy_payload:
        parts.append(f"Strategy guidance:\n{strategy_payload}")
    parts.append(f"User goal:\n{goal}")
    return "\n\n".join(parts)


def _run_method(
    method: str,
    cases: list[BenchmarkCase],
    runner: _ModelRunner,
    mpp_runner: _MPPRunner,
    sc_samples: int,
    record_samples: bool,
    *,
    dataset_name: str,
    group_name: str,
    log_every: int | None,
    logger: logging.Logger | None,
    continue_on_error: bool,
    max_errors: int | None,
    optimized_blocks: Mapping[str, str] | None,
) -> dict[str, Any]:
    correct = 0
    total = 0
    samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    aborted = False
    total_cases = len(cases)
    for idx, case in enumerate(cases, start=1):
        prediction = None
        error_message = None
        try:
            if method in {"mpp", "mpp_optimized"}:
                prediction = mpp_runner.run(
                    case,
                    optimized=method == "mpp_optimized",
                    blocks_override=(
                        optimized_blocks if method == "mpp_optimized" else None
                    ),
                )
            else:
                prediction = _run_prompt_method(
                    method, case, runner, sc_samples=sc_samples
                )
            is_correct = _score_case(case, prediction)
        except Exception as exc:
            if not continue_on_error:
                raise
            error_message = f"{type(exc).__name__}: {exc}"
            _log_error(
                logger,
                "Error dataset=%s group=%s method=%s case=%s error=%s",
                dataset_name,
                group_name,
                method,
                case.case_id,
                error_message,
            )
            errors.append({"case_id": case.case_id, "error": error_message})
            is_correct = False
            if max_errors is not None and len(errors) >= max_errors:
                aborted = True
                _log_info(
                    logger,
                    "Abort dataset=%s group=%s method=%s errors=%d",
                    dataset_name,
                    group_name,
                    method,
                    len(errors),
                )
                total += 1
                if record_samples:
                    sample = {
                        "case_id": case.case_id,
                        "prediction": prediction,
                        "correct": is_correct,
                        "error": error_message,
                    }
                    samples.append(sample)
                break
        total += 1
        if is_correct:
            correct += 1
        if record_samples:
            sample = {
                "case_id": case.case_id,
                "prediction": prediction,
                "correct": is_correct,
            }
            if error_message:
                sample["error"] = error_message
            samples.append(sample)
        if log_every and (idx % log_every == 0 or idx == total_cases):
            _log_info(
                logger,
                ("Progress dataset=%s group=%s method=%s" " %d/%d (%.1f%%)"),
                dataset_name,
                group_name,
                method,
                idx,
                total_cases,
                (idx / total_cases) * 100 if total_cases else 100.0,
            )
    accuracy = correct / total if total else 0.0
    result = {"total": total, "correct": correct, "accuracy": accuracy}
    if record_samples:
        result["samples"] = samples
    if errors:
        result["error_count"] = len(errors)
        result["errors"] = errors
    if aborted:
        result["aborted"] = True
    return result


def _run_prompt_method(
    method: str,
    case: BenchmarkCase,
    runner: _ModelRunner,
    *,
    sc_samples: int,
) -> str:
    match method:
        case "raw":
            return runner.generate(case.question, method)
        case "zero_shot":
            prompt = _build_prompt(case, include_instruction=True)
            return runner.generate(prompt, method)
        case "few_shot":
            prompt = _build_few_shot_prompt(case)
            return runner.generate(prompt, method)
        case "cot":
            prompt = _build_cot_prompt(case)
            return runner.generate(prompt, method)
        case "react":
            prompt = _build_react_prompt(case)
            return runner.generate(prompt, method)
        case "self_consistency":
            return _run_self_consistency(case, runner, sc_samples)
    raise ValueError(f"Unsupported method: {method}")


def _build_prompt(case: BenchmarkCase, *, include_instruction: bool) -> str:
    parts = [case.question]
    if include_instruction:
        parts.append(FORMAT_HINTS.get(case.dataset, ""))
    return "\n\n".join(part for part in parts if part)


def _build_few_shot_prompt(case: BenchmarkCase) -> str:
    examples = FEW_SHOT.get(case.dataset, [])
    parts = []
    for example in examples:
        parts.append(f"Q: {example['question']}")
        parts.append(f"A: {example['answer']}")
    parts.append(f"Q: {case.question}")
    parts.append("A:")
    parts.append(FORMAT_HINTS.get(case.dataset, ""))
    return "\n\n".join(part for part in parts if part)


def _build_cot_prompt(case: BenchmarkCase) -> str:
    return "\n\n".join(
        [
            case.question,
            "Let's think step by step.",
            FORMAT_HINTS.get(case.dataset, ""),
        ]
    )


def _build_react_prompt(case: BenchmarkCase) -> str:
    return "\n\n".join(
        [
            case.question,
            "Use the format: Thought, Action, Observation, Answer.",
            FORMAT_HINTS.get(case.dataset, ""),
        ]
    )


def _run_self_consistency(
    case: BenchmarkCase,
    runner: _ModelRunner,
    samples: int,
) -> str:
    prompt = _build_cot_prompt(case)
    outputs = [runner.generate(prompt, "self_consistency") for _ in range(samples)]
    normalized = [_extract_answer(case, text) for text in outputs]
    counts = Counter(item for item in normalized if item is not None)
    if not counts:
        return outputs[0]
    best = counts.most_common(1)[0][0]
    idx = normalized.index(best)
    return outputs[idx]


def _score_case(case: BenchmarkCase, prediction: str) -> bool:
    predicted = _extract_answer(case, prediction)
    if predicted is None:
        return False
    match case.dataset:
        case "math":
            gold = _extract_math_answer(case.answer)
            return gold is not None and _normalize_math(gold) == _normalize_math(
                predicted
            )
        case "gsm8k":
            gold = _extract_gsm8k_answer(case.answer)
            return _numeric_equal(predicted, gold)
        case "game24":
            numbers = case.meta.get("numbers", [])
            target = case.meta.get("target", 24)
            return _valid_game24(predicted, numbers, target)
    return False


def _extract_answer(case: BenchmarkCase, text: str) -> str | None:
    text = _normalize_text(text)
    json_value = _extract_json_value(text)
    if json_value is not None:
        return json_value
    match case.dataset:
        case "math":
            return _extract_math_answer(text)
        case "gsm8k":
            return _extract_gsm8k_answer(text)
        case "game24":
            return _extract_game24_expression(text)
    return None


def _extract_json_value(text: str) -> str | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        for key in ("final", "answer", "result", "output", "decoded_bundle"):
            if key in parsed:
                return str(parsed[key])
    return None


def _extract_math_answer(text: str) -> str | None:
    boxed = re.findall(r"\\boxed\{([^}]*)\}", text)
    if boxed:
        return boxed[-1].strip()
    match = re.search(r"Answer\s*[:=]\s*(.+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    tokens = re.findall(r"-?\d+\.?\d*", text)
    if tokens:
        return tokens[-1]
    return None


def _extract_gsm8k_answer(text: str) -> str | None:
    match = re.search(r"####\s*(-?[\d,]+\.?\d*)", text)
    if match:
        return match.group(1)
    tokens = re.findall(r"-?\d+\.?\d*", text)
    if tokens:
        return tokens[-1]
    return None


def _extract_game24_expression(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1]


def _normalize_math(text: str) -> str:
    cleaned = text.replace("\n", " ").strip()
    cleaned = re.sub(r"\\s+", "", cleaned)
    return cleaned.strip("$")


def _numeric_equal(predicted: str | None, gold: str | None) -> bool:
    if predicted is None or gold is None:
        return False
    try:
        pred = float(str(predicted).replace(",", ""))
        gold_val = float(str(gold).replace(",", ""))
    except ValueError:
        return False
    return math.isclose(pred, gold_val, rel_tol=1e-6, abs_tol=1e-6)


def _valid_game24(expression: str, numbers: Iterable[int], target: int) -> bool:
    if not expression:
        return False
    expr = expression.replace(" ", "")
    if not re.fullmatch(r"[0-9+*/().-]+", expr):
        return False
    expected = Counter(str(n) for n in numbers)
    used = Counter(re.findall(r"\d+", expr))
    if used != expected:
        return False
    result = _safe_eval(expr)
    if result is None:
        return False
    return math.isclose(result, float(target), rel_tol=1e-6, abs_tol=1e-6)


def _safe_eval(expr: str) -> float | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Pow,
                ast.USub,
                ast.UAdd,
                ast.Load,
                ast.Constant,
                ast.Mod,
                ast.FloorDiv,
            ),
        ):
            return None
    try:
        return float(eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}))
    except Exception:
        return None


def _normalize_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = "\n".join(stripped.splitlines()[1:-1]).strip()
    return stripped


def _assistant_text(response: Any) -> str:
    if isinstance(response, dict):
        if "choices" in response:
            choices = response.get("choices")
            if isinstance(choices, list) and choices:
                choice = choices[0]
                if isinstance(choice, dict):
                    message = choice.get("message")
                    if isinstance(message, dict) and "content" in message:
                        return str(message["content"])
                    if "text" in choice:
                        return str(choice["text"])
                else:
                    message = getattr(choice, "message", None)
                    if message is not None and hasattr(message, "content"):
                        return str(message.content)
        if "data" in response:
            return _assistant_text(response.get("data"))
        if "result" in response:
            return _assistant_text(response.get("result"))
        message = response.get("message")
        if isinstance(message, dict) and "content" in message:
            return str(message["content"])
        if "content" in response:
            return str(response["content"])
    if isinstance(response, list) and response:
        return _assistant_text(response[0])
    return str(response)


def _parse_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Config must be a JSON object.")
    return payload


def _write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")


def _configure_logger(
    log_path: Path | None,
    *,
    verbose: bool,
) -> logging.Logger:
    logger = logging.getLogger("mpp_benchmarks")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def _log_info(logger: logging.Logger | None, message: str, *args: Any) -> None:
    if logger is None:
        return
    logger.info(message, *args)


def _log_error(logger: logging.Logger | None, message: str, *args: Any) -> None:
    if logger is None:
        return
    logger.error(message, *args)


def _apply_smoke_config(config: Mapping[str, Any]) -> dict[str, Any]:
    updated = dict(config)
    datasets = []
    for item in config.get("datasets", []):
        if not isinstance(item, dict):
            continue
        dataset = dict(item)
        dataset["limit"] = 1
        datasets.append(dataset)
    if datasets:
        updated["datasets"] = datasets

    model_groups = config.get("model_groups", [])
    if isinstance(model_groups, list) and len(model_groups) > 2:
        updated["model_groups"] = model_groups[:2]

    updated["self_consistency_samples"] = 1
    return updated


def _apply_seed(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(seed)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to JSON config.")
    parser.add_argument("--report", required=True, help="Output report JSON path.")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--log", help="Optional path to write execution logs.")
    parser.add_argument(
        "--log-every",
        type=int,
        default=100,
        help="Log progress every N cases (0 disables per-case logs).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running after per-case errors.",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=5,
        help="Stop a method after N errors when continue-on-error is set.",
    )
    parser.add_argument(
        "--methods",
        help="Comma-separated list of methods to run (overrides config).",
    )
    parser.add_argument(
        "--skip-method",
        action="append",
        default=[],
        help="Method to skip (repeatable).",
    )
    parser.add_argument(
        "--model-groups",
        help="Comma-separated list of model group names to run (overrides config).",
    )
    parser.add_argument(
        "--skip-model-group",
        action="append",
        default=[],
        help="Model group name to skip (repeatable).",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a minimal subset (1 case per dataset, first two model groups).",
    )
    args = parser.parse_args(argv)
    _apply_seed(args.seed)
    config = _parse_config(Path(args.config))
    if args.smoke:
        config = _apply_smoke_config(config)
    if args.methods or args.skip_method:
        config = _apply_methods_config(
            config,
            methods_override=args.methods,
            skip_methods=args.skip_method,
        )
    if args.model_groups or args.skip_model_group:
        config = _apply_model_groups_config(
            config,
            groups_override=args.model_groups,
            skip_groups=args.skip_model_group,
        )
    log_every = None if args.log_every <= 0 else args.log_every
    logger = _configure_logger(
        Path(args.log) if args.log else None, verbose=args.verbose
    )
    report = run_benchmarks(
        config,
        log_every=log_every,
        logger=logger,
        continue_on_error=args.continue_on_error,
        max_errors=args.max_errors if args.continue_on_error else None,
    )
    _write_report(report, Path(args.report))


if __name__ == "__main__":
    main()
