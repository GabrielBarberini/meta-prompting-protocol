from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SchemaDescriptor = Sequence[str]


@dataclass(frozen=True)
class DerivativeProtocolSpecification:
    protocol_name: str
    abstract: str
    tag_definition_schema: SchemaDescriptor
    core_tag_library: Mapping[str, Mapping[str, Any]]
    processor_semantics: Mapping[str, str]
    guiding_principles: Mapping[str, Any]


@dataclass(frozen=True)
class MPPBundle:
    meta_protocol_version: str
    derivative_protocol_specification: DerivativeProtocolSpecification
    derivative_protocol_payload: Mapping[str, Any]
