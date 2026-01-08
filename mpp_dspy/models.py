from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class DerivativeProtocolSpecification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    protocol_name: str
    abstract: str
    tag_definition_schema: list[str]
    core_tag_library: dict[str, dict[str, Any]]
    processor_semantics: dict[str, Any]
    guiding_principles: dict[str, Any]
    protocol_version: str | None = None
    payload_order: list[str] | None = None
    processor_pipeline: list[str] | None = None
    mcp_tooling: dict[str, Any] | None = None


class MPPBundle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    meta_protocol_version: str
    derivative_protocol_specification: DerivativeProtocolSpecification
    derivative_protocol_payload: dict[str, Any]
