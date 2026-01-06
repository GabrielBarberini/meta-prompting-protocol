from __future__ import annotations

import copy
import json

import pytest

from mpp_dspy.validations import normalize_mpp_bundle, validate_mpp_bundle


def test_validate_mpp_bundle_accepts_minimal(mpp_bundle_minimal) -> None:
    """Validate that a minimal bundle passes structural checks."""
    # Arrange: minimal bundle fixture.

    # Act + Assert: no exception should be raised.
    validate_mpp_bundle(mpp_bundle_minimal)


def test_validate_mpp_bundle_rejects_unknown_payload_tags(mpp_bundle_minimal) -> None:
    """Validate that payload tags must be declared in the tag library."""
    # Arrange: inject an unknown payload tag.
    bundle = copy.deepcopy(mpp_bundle_minimal)
    bundle["derivative_protocol_payload"]["$unknown"] = "unexpected"

    # Act + Assert: validation should fail.
    with pytest.raises(ValueError, match="payload includes unknown tags"):
        validate_mpp_bundle(bundle)


def test_normalize_mpp_bundle_parses_json_strings(mpp_bundle_minimal) -> None:
    """Normalize bundle fields when spec/payload are JSON strings."""
    # Arrange: encode spec and payload as JSON strings.
    bundle = {
        "meta_protocol_version": mpp_bundle_minimal["meta_protocol_version"],
        "derivative_protocol_specification": json.dumps(
            mpp_bundle_minimal["derivative_protocol_specification"]
        ),
        "derivative_protocol_payload": json.dumps(
            mpp_bundle_minimal["derivative_protocol_payload"]
        ),
    }

    # Act: normalize the bundle.
    normalized = normalize_mpp_bundle(bundle)

    # Assert: normalized fields are mappings with expected values.
    spec = normalized["derivative_protocol_specification"]
    assert spec["protocol_name"] == "Minimal Protocol"
    assert normalized["derivative_protocol_payload"]["$task"] == "Run a small test."
