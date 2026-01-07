from __future__ import annotations

import pytest


@pytest.fixture()
def mpp_bundle_minimal() -> dict:
    """Return a minimal, valid MPP bundle for tests."""
    return {
        "meta_protocol_version": "1.3.0",
        "derivative_protocol_specification": {
            "protocol_name": "Minimal Protocol",
            "abstract": "Minimal protocol used for unit tests.",
            "tag_definition_schema": ["description"],
            "core_tag_library": {
                "$task": {
                    "description": "The task to execute.",
                }
            },
            "processor_semantics": {},
            "guiding_principles": {
                "fidelity": "Follow the payload exactly.",
            },
        },
        "derivative_protocol_payload": {
            "$task": "Run a small test.",
        },
    }
