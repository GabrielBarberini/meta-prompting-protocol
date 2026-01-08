from .metrics import LongitudinalMetric, TraceCostMetric
from .models import DerivativeProtocolSpecification, MPPBundle
from .mpp_adapter import (
    BundleResult,
    ExecutionResult,
    MPPAdapterPipeline,
    MPPVerticalRefiner,
    VerticalResult,
    VerticalStep,
)
from .mpp_optimizer import (
    LongitudinalResult,
    LongitudinalScore,
    LongitudinalStep,
    LongitudinalTrace,
    MPPLongitudinalRefiner,
)
from .mutations import DefaultLongitudinalMutator
from .template_tokens import (
    extract_mutable_blocks,
    list_mutable_blocks,
    render_mutable_template,
)
from .validations import validate_derivative_spec, validate_mpp_bundle, validate_payload

try:
    from .dspy_adapters import MPPArchitectAdapter, MPPExecutorAdapter, MPPQAAdapter
    from .mpp_auto_adapter import (
        FullPipelineResult,
        MPPAutoAdapter,
        MPPAutoAdapterOptimizer,
    )
    from .mpp_signatures import ProtocolArchitect, ProtocolExecutor, QualityAssurance
except Exception as exc:
    _DSPY_IMPORT_ERROR = exc

    class _DSPyMissing:
        def __init__(self, *_args, **_kwargs) -> None:
            raise ImportError(
                "DSPy is required for "
                "ProtocolArchitect/ProtocolExecutor/QualityAssurance and MPP adapters."
            ) from _DSPY_IMPORT_ERROR

    ProtocolArchitect = _DSPyMissing
    ProtocolExecutor = _DSPyMissing
    QualityAssurance = _DSPyMissing
    MPPArchitectAdapter = _DSPyMissing
    MPPExecutorAdapter = _DSPyMissing
    MPPQAAdapter = _DSPyMissing
    MPPAutoAdapter = _DSPyMissing
    MPPAutoAdapterOptimizer = _DSPyMissing
    FullPipelineResult = _DSPyMissing

__all__ = [
    "DerivativeProtocolSpecification",
    "MPPBundle",
    "validate_mpp_bundle",
    "validate_derivative_spec",
    "validate_payload",
    "ProtocolArchitect",
    "ProtocolExecutor",
    "QualityAssurance",
    "MPPArchitectAdapter",
    "MPPExecutorAdapter",
    "MPPQAAdapter",
    "MPPAutoAdapter",
    "MPPAutoAdapterOptimizer",
    "FullPipelineResult",
    "BundleResult",
    "ExecutionResult",
    "MPPAdapterPipeline",
    "VerticalStep",
    "VerticalResult",
    "MPPVerticalRefiner",
    "extract_mutable_blocks",
    "list_mutable_blocks",
    "render_mutable_template",
    "LongitudinalResult",
    "LongitudinalScore",
    "LongitudinalStep",
    "LongitudinalTrace",
    "MPPLongitudinalRefiner",
    "LongitudinalMetric",
    "TraceCostMetric",
    "DefaultLongitudinalMutator",
]
