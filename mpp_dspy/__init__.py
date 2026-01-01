from .models import DerivativeProtocolSpecification, MPPBundle
from .validations import validate_derivative_spec, validate_mpp_bundle, validate_payload

try:
    from .mpp_signatures import ProtocolArchitect, ProtocolExecutor, QualityAssurance
except Exception as exc:
    _DSPY_IMPORT_ERROR = exc

    class _DSPyMissing:
        def __init__(self, *_args, **_kwargs) -> None:
            raise ImportError(
                "DSPy is required for ProtocolArchitect/ProtocolExecutor/QualityAssurance."
            ) from _DSPY_IMPORT_ERROR

    ProtocolArchitect = _DSPyMissing
    ProtocolExecutor = _DSPyMissing
    QualityAssurance = _DSPyMissing

__all__ = [
    "DerivativeProtocolSpecification",
    "MPPBundle",
    "validate_mpp_bundle",
    "validate_derivative_spec",
    "validate_payload",
    "ProtocolArchitect",
    "ProtocolExecutor",
    "QualityAssurance",
]
