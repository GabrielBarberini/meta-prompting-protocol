from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dspy.adapters.json_adapter import JSONAdapter
from dspy.signatures.signature import Signature

_ARCHITECT_PRIMER = (
    "You are a Protocol Architect.\n"
    "- Follow the MPP specification strictly.\n"
    "- Derive a task-specific derivative protocol (schema, tags, processors).\n"
    "- Encode the user goal into the payload using the derived protocol.\n"
    "- The raw user goal is provided between <RAW_USER_GOAL>...</RAW_USER_GOAL>.\n"
    "- Preserve the raw user goal verbatim inside the payload's primary task/"
    "instruction tag.\n"
    "- Do not paraphrase or truncate the raw user goal.\n"
    "- Preserve minimalism and fidelity.\n"
    "- Do not add extra top-level keys beyond the required fields.\n"
    "- Output a single JSON object and nothing else."
)

_EXECUTOR_PRIMER = (
    "You are an Executor.\n"
    "- Follow the MPP specification strictly.\n"
    "- Parse the derivative_protocol_specification to learn tags and processors.\n"
    "- Decode the payload accordingly and generate the final response.\n"
    "- Output a single JSON object and nothing else."
)

_QA_PRIMER = (
    "You are a QA agent.\n"
    "- Follow the MPP specification strictly.\n"
    "- Validate the executor response against the bundle constraints.\n"
    "- Return a JSON object with 'verdict' and 'issues' only.\n"
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
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.spec_text = _load_spec_text(spec_text, spec_path)
        self.role_instructions = (role_instructions or "").strip()

    def format_task_description(self, signature: type[Signature]) -> str:
        parts = []
        if self.spec_text:
            parts.append(f"MPP specification:\n{self.spec_text}")
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
        role_instructions = kwargs.pop("role_instructions", _ARCHITECT_PRIMER)
        if expect_reasoning:
            role_instructions = (
                f"{role_instructions}\n"
                "- If a reasoning field is required, provide chain-of-thought in it."
            )
        super().__init__(*args, role_instructions=role_instructions, **kwargs)


class MPPExecutorAdapter(MPPBaseAdapter):
    def __init__(
        self,
        *args,
        bundle: Mapping[str, Any] | None = None,
        expect_reasoning: bool = False,
        qa_feedback: Mapping[str, Any] | None = None,
        **kwargs,
    ) -> None:
        role_instructions = kwargs.pop("role_instructions", _EXECUTOR_PRIMER)
        if expect_reasoning:
            role_instructions = (
                f"{role_instructions}\n"
                "- If a reasoning field is required, provide chain-of-thought in it."
            )
        super().__init__(*args, role_instructions=role_instructions, **kwargs)
        self.bundle = bundle
        self.expect_reasoning = expect_reasoning
        self.qa_feedback = qa_feedback

    def format_task_description(self, signature: type[Signature]) -> str:
        base = super().format_task_description(signature)
        parts = [base] if base else []
        if self.bundle and "derivative_protocol_specification" in self.bundle:
            spec = json.dumps(
                self.bundle["derivative_protocol_specification"],
                indent=2,
                ensure_ascii=True,
            )
            parts.append(f"Derived protocol specification:\n{spec}")
        if self.qa_feedback:
            feedback = json.dumps(
                self.qa_feedback,
                indent=2,
                ensure_ascii=True,
            )
            parts.append(f"QA feedback from previous attempt:\n{feedback}")
        return "\n\n".join(parts).strip()


class MPPQAAdapter(MPPBaseAdapter):
    def __init__(
        self,
        *args,
        bundle: Mapping[str, Any] | None = None,
        **kwargs,
    ) -> None:
        role_instructions = kwargs.pop("role_instructions", _QA_PRIMER)
        super().__init__(*args, role_instructions=role_instructions, **kwargs)
        self.bundle = bundle

    def format_task_description(self, signature: type[Signature]) -> str:
        base = super().format_task_description(signature)
        parts = [base] if base else []
        if self.bundle and "derivative_protocol_specification" in self.bundle:
            spec = json.dumps(
                self.bundle["derivative_protocol_specification"],
                indent=2,
                ensure_ascii=True,
            )
            parts.append(f"Derived protocol specification:\n{spec}")
        return "\n\n".join(parts).strip()
