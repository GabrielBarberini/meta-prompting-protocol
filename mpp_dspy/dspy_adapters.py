from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from dspy.adapters.json_adapter import JSONAdapter
from dspy.signatures.signature import Signature

_ARCHITECT_PRIMER = (
    "You are the Meta-prompting protocol Architect.\n"
    "- Follow the MPP specification strictly.\n"
    "- Derive a task-specific derivative protocol (schema, tags, processors).\n"
    "- Encode the user goal into the payload using the derived protocol.\n"
    "- The goal is a self-contained bundle: an Executor will only receive the final "
    "bundle and nothing else.\n"
    "- If refinement feedback is provided (see <MPP_REFINEMENT_TRACE>), treat it as a "
    "change log and update the derivative protocol specification and/or payload so "
    "the next bundle passes QA without any external side-channel context.\n"
    "- When QA feedback indicates format/schema issues, strengthen the derivative "
    "protocol with explicit output constraints and (when helpful) include small "
    "canonical examples inside the derivative protocol specification.\n"
    "- The raw user goal is provided between <RAW_USER_GOAL>...</RAW_USER_GOAL>.\n"
    "- Preserve the raw user goal verbatim inside the payload's primary task/"
    "instruction tag.\n"
    "- Do not paraphrase or truncate the raw user goal.\n"
    "- Preserve minimalism and fidelity.\n"
    "- Do not add extra top-level keys beyond the required fields.\n"
    "- Output a single JSON object and nothing else."
)

_EXECUTOR_PRIMER = (
    "Decode the bundle and execute the task at hand.\n"
    "- Output a single JSON object and nothing else.\n"
    "- The top-level response must include only the `decoded_bundle` field.\n"
    "- The `decoded_bundle` value must follow the derivative protocol's output schema."
)

_QA_PRIMER = (
    "You are an MPP QA agent.\n"
    "- Follow the Meta-prompting protocol specification strictly.\n"
    "- Validate the executor response against the bundle constraints.\n"
    "- Derive all expectations (especially output format/schema) from the bundle's "
    "derivative protocol specification and payload.\n"
    "- Return a JSON object with 'verdict', 'issues', and 'repair_examples'.\n"
    "- 'repair_examples' must be an array of short strings; use [] when there is "
    "nothing to repair.\n"
    "- Ensure repair_examples entries conform to the required output schema and use "
    "valid JSON (double quotes).\n"
    "- 'verdict' must be 'pass' or 'fail'.\n"
    "- 'issues' must be an array of short strings (empty if pass)."
)


def _default_spec_path() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "docs" / "meta_prompting_protocol_spec.md"
    )


def _load_spec_text(spec_text: str | None, spec_path: str | Path | None) -> str:
    if spec_text is not None:
        return spec_text.strip()
    path = Path(spec_path) if spec_path else _default_spec_path()
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class MPPBaseAdapter(JSONAdapter):
    """Base adapter that injects the MPP specification and role instructions."""

    def __init__(
        self,
        spec_text: str | None = None,
        spec_path: str | Path | None = None,
        role_instructions: str | None = None,
        base_role_instructions: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.spec_text = _load_spec_text(spec_text, spec_path)
        self.base_role_instructions = (base_role_instructions or "").strip()
        self.role_instructions = (role_instructions or "").strip()

    def format_task_description(self, signature: type[Signature]) -> str:
        parts = []
        if self.spec_text:
            parts.append(f"MPP specification:\n{self.spec_text}")
        if self.base_role_instructions:
            parts.append(self.base_role_instructions)
        if self.role_instructions:
            parts.append(self.role_instructions)
        if signature.instructions:
            parts.append(signature.instructions.strip())
        return "\n\n".join(parts).strip()


class MPPArchitectAdapter(MPPBaseAdapter):
    def __init__(
        self,
        *args,
        expect_reasoning: bool = False,
        **kwargs,
    ) -> None:
        role_instructions = kwargs.pop("role_instructions", "")
        base_role_instructions = kwargs.pop("base_role_instructions", _ARCHITECT_PRIMER)
        if expect_reasoning:
            role_instructions = (
                f"{role_instructions}\n"
                "- If a reasoning field is required, provide chain-of-thought in it."
            )
        super().__init__(
            *args,
            role_instructions=role_instructions,
            base_role_instructions=base_role_instructions,
            **kwargs,
        )


class MPPExecutorAdapter(MPPBaseAdapter):
    def __init__(
        self,
        *args,
        expect_reasoning: bool = False,
        **kwargs,
    ) -> None:
        role_instructions = kwargs.pop("role_instructions", "")
        base_role_instructions = kwargs.pop("base_role_instructions", _EXECUTOR_PRIMER)
        if expect_reasoning:
            role_instructions = (
                f"{role_instructions}\n"
                "- If a reasoning field is required, provide chain-of-thought in it."
            )
        super().__init__(
            *args,
            role_instructions=role_instructions,
            base_role_instructions=base_role_instructions,
            **kwargs,
        )
        self.expect_reasoning = expect_reasoning

    def format_task_description(self, signature: type[Signature]) -> str:
        base = super().format_task_description(signature)
        parts = [base] if base else []
        return "\n\n".join(parts).strip()


class MPPQAAdapter(MPPBaseAdapter):
    def __init__(
        self,
        *args,
        bundle: Mapping[str, Any] | None = None,
        **kwargs,
    ) -> None:
        role_instructions = kwargs.pop("role_instructions", "")
        base_role_instructions = kwargs.pop("base_role_instructions", _QA_PRIMER)
        super().__init__(
            *args,
            role_instructions=role_instructions,
            base_role_instructions=base_role_instructions,
            **kwargs,
        )
        self.bundle = bundle

    def format_task_description(self, signature: type[Signature]) -> str:
        base = super().format_task_description(signature)
        parts = [base] if base else []
        return "\n\n".join(parts).strip()
