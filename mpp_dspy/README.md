# DSPy Integration Notes

DSPy usage notes for the `mpp_dspy` package.

## Adapter Framing
MPP can be treated as a two-stage adapter pipeline:
1. An "Architect" adapter turns a user goal into a task-specific protocol
   (spec + payload).
2. A derived "Executor" adapter uses that protocol to produce the final output.


## Default convergence pipeline example

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

See the repository `README.md` for template optimizer examples and parallel
candidate guidance.


## Custom convergence pipeline example

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
exec_result = adapter.execute(bundle_result.bundle, open_world=True)
print(exec_result.final_response)
```

`MPPAdapterPipeline` wraps the refinement loops so this pattern drops cleanly
into DSPy modules and predictors. The bundle refinement loop is formalized as an
internal DSPy teleprompter (`MPPBundleOptimizer`) and used by `MPPAutoAdapter`
to keep the adapter a single black-box module.

## Client Interface

`MPPAutoAdapter` works with any DSPy-compatible LM. Configure DSPy with the
provider of your choice and pass it to `dspy.settings.configure`.

## Notes
- The refinement loops mirror the monadic polishing approach: propose -> validate
  -> refine until the bundle/output stabilizes.
- Longitudinal refinement (TextGrad-style) can be run separately over templates
  with `{{MPP_MUTABLE:...}}` tokens to optimize prompt segments for a case.
- `MPPAutoAdapterOptimizer` is a DSPy teleprompter: call `compile()` with a base
  `MPPAutoAdapter` and a single case (mapping or object with `user_goal` /
  `open_world`) to get an optimized module. It accepts a `metric` implementing
  `LongitudinalMetric` so you can replace the default trace-cost scoring.
- `MPPLongitudinalRefiner` is the generic teleprompter used internally by
  `MPPAutoAdapterOptimizer`. Use it directly when you want a custom
  `score_function` or to optimize non-MPPAutoAdapter templates. The
  `mutate_function` may accept traces and history (optional); if you accept them,
  you can use `LongitudinalScore` + `traces` to surface iteration counts and QA
  errors.
- `DefaultLongitudinalMutator` ships with MPP: it preserves `entry_prompt` and
  only mutates `strategy_payload`, `architect_primer`, and `executor_primer`.
- `mcp_tooling` (optional spec field) lets the Architect declare tool schemas
  and call order when the Executor must run MCP tools before responding.
- `TraceCostMetric` uses a dominant final-response weight and doubles weights
  as you move outward (defaults: final=4, architect=2, executor=1). Override
  `final_weight` to scale the set or pass explicit weights. If the
  bundle/executor fails to stabilize or QA fails, the case score is 0.
- Monadic refinement returns per-iteration telemetry in `steps` on
  `BundleResult` and `ExecutionResult` (includes outputs plus QA/errors).
- For symmetry with template optimization, `MPPVerticalRefiner` wraps the
  bundle and execution loops and returns a `VerticalResult`.
- `MPPAutoAdapter` accepts `architect_role_instructions`,
  `executor_role_instructions`, and `qa_role_instructions` to override the
  default role primers (useful for template optimization).
- `MPPAutoAdapter` also accepts `architect_lm`, `executor_lm`, and `qa_lm` so
  each stage can use a different LM (or temperature/RAG wrapper) while still
  sharing the same adapters.
- `MPPAutoAdapterOptimizer` runs template optimization around the monadic
  loop, so each optimization step evaluates full MPP executions before
  selecting the best template blocks.
- If the executor uses `dspy.ChainOfThought`, `ExecutionResult.reasoning` is
  populated and the loop enforces that reasoning is returned.
- Closed-world tasks: use stability checks as convergence and run QA once at the
  end.
- Open-world tasks: set `open_world=True` to run QA-augmented refinement on every
  iteration and stop on QA pass or max-iteration bounds.
- If the executor fails to converge within its cap, MPPAutoAdapter feeds the
  failure signal back into the architect and rebuilds the bundle, resetting the
  executor loop.
- Use `architect_max_iters`/`executor_max_iters` to cap the monadic loops.
  (If you instantiate `MPPAdapterPipeline` directly, it accepts the same
  parameters.)
- Swap the stability check with a domain-specific comparison if needed.
- Suggested refinement criteria for MPP: spec completeness, all processors defined,
  payload tags declared, minimalism (no unused tags), and executor output passes
  QA + format validation.
