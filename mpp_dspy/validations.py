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


def validate_payload(spec: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """Ensure payload tags are declared in the core tag library."""
    core_tag_library = _require_mapping(
        spec["core_tag_library"], "derivative_protocol_specification.core_tag_library"
    )
    unknown_tags = set(payload.keys()) - set(core_tag_library.keys())
    if unknown_tags:
        unknown = ", ".join(sorted(unknown_tags))
        raise ValueError(f"payload includes unknown tags: {unknown}")


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _require_keys(container: Mapping[str, Any], required: Iterable[str], label: str) -> None:
    missing = [key for key in required if key not in container]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"{label} is missing required keys: {missing_list}")


def _is_string_list(value: Any) -> bool:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return False
    return all(isinstance(item, str) for item in value)
