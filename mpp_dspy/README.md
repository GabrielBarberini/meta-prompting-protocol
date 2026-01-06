# DSPy Integration Notes

DSPy usage notes for the `mpp_dspy` package.

## Adapter Framing
MPP can be treated as a two-stage adapter pipeline:
1. A fixed "architect" adapter turns a user goal into a task-specific protocol
   (spec + payload).
2. A derived "executor" adapter uses that protocol to produce the final output.

`MPPAdapterPipeline` wraps the refinement loops so this pattern drops cleanly
into DSPy modules and predictors. The bundle refinement loop is formalized as an
internal DSPy teleprompter (`MPPBundleOptimizer`) and used by `MPPAutoAdapter`
to keep the adapter a single black-box module.

## Usage Example (Short)

```python
import dspy

from mpp_dspy import (
    MPPAdapterPipeline,
    ProtocolArchitect,
    ProtocolExecutor,
    QualityAssurance,
)

lm = dspy.OpenAI(model="gpt-4o-mini")  # Or any DSPy-compatible LM.
dspy.settings.configure(lm=lm)

adapter = MPPAdapterPipeline(
    architect=dspy.ChainOfThought(ProtocolArchitect),
    executor=dspy.Predict(ProtocolExecutor),
    qa=dspy.Predict(QualityAssurance),
)


bundle_result = adapter.build_bundle(
    "Write a horror story about a lighthouse keeper in Lovecraftian tone."
)
exec_result = adapter.execute(bundle_result.bundle, open_world=False)
print(exec_result.final_response)
```

Notes:
- The refinement loops mirror the monadic polishing approach: propose -> validate
  -> refine until the bundle/output stabilizes.
- Longitudinal refinement (TextGrad-style) can be run separately over templates
  with `{{MPP_MUTABLE:...}}` tokens to optimize prompt segments across datasets.
- Vertical refinement returns per-iteration telemetry in `steps` on
  `BundleResult` and `ExecutionResult` (includes outputs plus QA/errors).
- For symmetry with longitudinal refinement, `MPPVerticalRefiner` wraps the
  bundle and execution loops and returns a `VerticalResult`.
- If the executor uses `dspy.ChainOfThought`, `ExecutionResult.reasoning` is
  populated and the loop enforces that reasoning is returned.
- Closed-world tasks: use stability checks as convergence.
- Open-world tasks: set `open_world=True` to run QA-augmented refinement and
  stop on QA pass or max-iteration bounds.
- Use `max_iters` to cap both loops. `MPPAutoAdapter` exposes per-stage limits
  via `architect_max_iters`/`executor_max_iters`. (If you instantiate
  `MPPAdapterPipeline` directly, it accepts the same parameters.)
- Swap the stability check with a domain-specific comparison if needed.
- Suggested refinement criteria for MPP: spec completeness, all processors defined,
  payload tags declared, minimalism (no unused tags), and executor output passes
  QA + format validation.

## Adapter + Module Example

```python
import dspy

from mpp_dspy import MPPAutoAdapter

lm = dspy.OpenAI(model="gpt-4o-mini")
dspy.settings.configure(lm=lm)

program = MPPAutoAdapter()
result = program(
    user_goal="Draft a crisp product launch email.",
    open_world=True,
)
print(result.final_response)
```

If you pass a `dspy.ChainOfThought` executor into `MPPAutoAdapter`, the result
includes `executor_reasoning`.

## Client Interface

`MPPAutoAdapter` works with any DSPy-compatible LM. Configure DSPy with the
provider of your choice and pass it to `dspy.settings.configure`.
