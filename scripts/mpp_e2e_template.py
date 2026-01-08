#!/usr/bin/env python3
"""Provider-agnostic template to run MPPAutoAdapter end-to-end."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import dspy
from dspy.clients.base_lm import BaseLM

from mpp_dspy import (
    DefaultLongitudinalMutator,
    MPPAutoAdapter,
    MPPAutoAdapterOptimizer,
)
from mpp_dspy.metrics import TraceCostMetric

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


class ProviderLM(BaseLM):
    """Replace forward() with your provider-specific call."""

    def forward(
        self,
        prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ):
        raise NotImplementedError("Implement ProviderLM.forward with your client.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longitudinal-iters", type=int, default=5)
    parser.add_argument("--architect-max-iters", type=int, default=5)
    parser.add_argument("--executor-max-iters", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/mpp_e2e_template.txt"),
    )
    return parser.parse_args()


def _default_case() -> dict[str, object]:
    return {
        "user_goal": (
            "Produce a vendor onboarding risk assessment and checklist. "
            "Return JSON with reasoning and final fields."
        ),
        "open_world": True,
    }


def main() -> None:
    args = _parse_args()
    case = _default_case()
    metric = TraceCostMetric()

    architect_lm = ProviderLM(model="provider-architect")
    executor_lm = ProviderLM(model="provider-executor")
    qa_lm = ProviderLM(model="provider-qa")
    optimizer_lm = ProviderLM(model="provider-optimizer")
    dspy.configure(lm=executor_lm)

    base_program = MPPAutoAdapter(
        architect_lm=architect_lm,
        executor_lm=executor_lm,
        qa_lm=qa_lm,
    )
    mutator = DefaultLongitudinalMutator(optimizer_lm)
    optimizer = MPPAutoAdapterOptimizer(
        template=DEFAULT_TEMPLATE,
        mutate_function=mutator,
        longitudinal_iters=args.longitudinal_iters,
        metric=metric,
    )
    optimized = optimizer.compile(
        base_program,
        trainset=case,
        architect_max_iters=args.architect_max_iters,
        executor_max_iters=args.executor_max_iters,
    )
    result = optimized.longitudinal_result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.template, encoding="utf-8")
    print(f"Saved template to {args.output}")


if __name__ == "__main__":
    main()
