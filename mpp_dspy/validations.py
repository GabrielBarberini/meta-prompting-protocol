from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

REQUIRED_BUNDLE_FIELDS = (
    "meta_protocol_version",
    "derivative_protocol_specification",
    "derivative_protocol_payload",
)
REQUIRED_SPEC_FIELDS = (
    "protocol_name",
    "abstract",
    "tag_definition_schema",
    "core_tag_library",
    "processor_semantics",
    "guiding_principles",
)
ALLOWED_SPEC_FIELDS = set(REQUIRED_SPEC_FIELDS) | {
    "protocol_version",
    "payload_order",
    "processor_pipeline",
}


def validate_mpp_bundle(bundle: Mapping[str, Any]) -> None:
    """Lightweight structural checks for an MPP bundle dictionary."""
    _require_keys(bundle, REQUIRED_BUNDLE_FIELDS, "bundle")
    if not isinstance(bundle["meta_protocol_version"], str):
        raise TypeError("bundle.meta_protocol_version must be a string")

    spec = _require_mapping(
        bundle["derivative_protocol_specification"],
        "bundle.derivative_protocol_specification",
    )
    payload = _require_mapping(
        bundle["derivative_protocol_payload"],
        "bundle.derivative_protocol_payload",
    )
    validate_derivative_spec(spec)
    validate_payload(spec, payload)


def validate_derivative_spec(spec: Mapping[str, Any]) -> None:
    """Validate that the derivative spec matches the schema descriptor."""
    _require_keys(spec, REQUIRED_SPEC_FIELDS, "derivative_protocol_specification")
    extra_fields = set(spec.keys()) - ALLOWED_SPEC_FIELDS
    if extra_fields:
        extras = ", ".join(sorted(extra_fields))
        raise ValueError(
            f"derivative_protocol_specification has unknown keys: {extras}"
        )
    schema = spec["tag_definition_schema"]
    if not _is_string_list(schema):
        raise TypeError(
            "tag_definition_schema must be an array of strings (e.g., ['description'])"
        )

    core_tag_library = _require_mapping(
        spec["core_tag_library"], "derivative_protocol_specification.core_tag_library"
    )
    processor_semantics = _require_mapping(
        spec["processor_semantics"],
        "derivative_protocol_specification.processor_semantics",
    )
    _require_mapping(
        spec["guiding_principles"],
        "derivative_protocol_specification.guiding_principles",
    )

    schema_fields = set(schema)
    for tag, tag_def in core_tag_library.items():
        tag_map = _require_mapping(tag_def, f"core_tag_library[{tag}]")
        required_value = tag_map.get("required", True)
        if not isinstance(required_value, bool):
            raise TypeError(f"tag {tag} required must be a boolean when provided")
        missing_fields = schema_fields - set(tag_map.keys())
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"tag {tag} is missing required fields: {missing}")

        if "processor" in schema_fields:
            processor = tag_map.get("processor")
            if processor not in processor_semantics:
                raise ValueError(
                    f"tag {tag} references undefined processor: {processor}"
                )

    protocol_version = spec.get("protocol_version")
    if protocol_version is not None and not isinstance(protocol_version, str):
        raise TypeError("protocol_version must be a string when provided")

    payload_order = spec.get("payload_order")
    if payload_order is not None:
        if not _is_string_list(payload_order):
            raise TypeError("payload_order must be an array of strings when provided")
        if len(payload_order) != len(set(payload_order)):
            raise ValueError("payload_order must not contain duplicate entries")
        unknown_tags = set(payload_order) - set(core_tag_library.keys())
        if unknown_tags:
            unknown = ", ".join(sorted(unknown_tags))
            raise ValueError(f"payload_order includes unknown tags: {unknown}")

    processor_pipeline = spec.get("processor_pipeline")
    if processor_pipeline is not None:
        if not _is_string_list(processor_pipeline):
            raise TypeError(
                "processor_pipeline must be an array of strings when provided"
            )
        if payload_order is None:
            raise ValueError(
                "processor_pipeline requires payload_order to define ordering"
            )
        if len(processor_pipeline) != len(set(processor_pipeline)):
            raise ValueError("processor_pipeline must not contain duplicate entries")
        unknown_processors = set(processor_pipeline) - set(processor_semantics.keys())
        if unknown_processors:
            unknown = ", ".join(sorted(unknown_processors))
            raise ValueError(
                f"processor_pipeline includes unknown processors: {unknown}"
            )


def validate_payload(spec: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """Ensure payload tags are declared in the core tag library."""
    core_tag_library = _require_mapping(
        spec["core_tag_library"], "derivative_protocol_specification.core_tag_library"
    )
    unknown_tags = set(payload.keys()) - set(core_tag_library.keys())
    if unknown_tags:
        unknown = ", ".join(sorted(unknown_tags))
        raise ValueError(f"payload includes unknown tags: {unknown}")

    payload_order = spec.get("payload_order")
    if payload_order is not None:
        missing_from_order = set(payload.keys()) - set(payload_order)
        if missing_from_order:
            missing = ", ".join(sorted(missing_from_order))
            raise ValueError(f"payload_order missing payload tags: {missing}")
        extra_in_order = set(payload_order) - set(payload.keys())
        if extra_in_order:
            extra = ", ".join(sorted(extra_in_order))
            raise ValueError(f"payload_order includes tags not in payload: {extra}")
        if list(payload.keys()) != list(payload_order):
            raise ValueError("payload tags do not match payload_order sequence")

    processor_pipeline = spec.get("processor_pipeline")
    schema = spec.get("tag_definition_schema") or []
    if processor_pipeline is not None and "processor" in schema:
        processors_used = set()
        processors_in_order = []
        for tag in payload.keys():
            tag_def = core_tag_library.get(tag, {})
            if isinstance(tag_def, Mapping):
                processor = tag_def.get("processor")
                if isinstance(processor, str):
                    processors_used.add(processor)
                    if processor not in processors_in_order:
                        processors_in_order.append(processor)
        missing_processors = processors_used - set(processor_pipeline)
        if missing_processors:
            missing = ", ".join(sorted(missing_processors))
            raise ValueError(
                f"processor_pipeline missing processors used by payload: {missing}"
            )
        extra_processors = set(processor_pipeline) - processors_used
        if extra_processors:
            extra = ", ".join(sorted(extra_processors))
            raise ValueError(
                f"processor_pipeline includes processors not used by payload: {extra}"
            )
        if (
            payload_order is not None
            and list(processor_pipeline) != processors_in_order
        ):
            raise ValueError("processor_pipeline order does not match payload order")

    missing_required = []
    for tag, tag_def in core_tag_library.items():
        if tag in payload:
            continue
        tag_map = _require_mapping(tag_def, f"core_tag_library[{tag}]")
        required_value = tag_map.get("required", True)
        if required_value:
            missing_required.append(tag)
    if missing_required:
        missing = ", ".join(sorted(missing_required))
        raise ValueError(f"payload missing required tags: {missing}")


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _require_keys(
    container: Mapping[str, Any], required: Iterable[str], label: str
) -> None:
    missing = [key for key in required if key not in container]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"{label} is missing required keys: {missing_list}")


def _is_string_list(value: Any) -> bool:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return False
    return all(isinstance(item, str) for item in value)
