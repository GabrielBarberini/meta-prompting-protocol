# DSPy Integration Notes

DSPy usage notes for the `mpp_dspy` package.

## Usage Example (Short)

```python
import json

import dspy

from mpp_dspy import ProtocolArchitect, ProtocolExecutor, QualityAssurance, validate_mpp_bundle

lm = dspy.OpenAI(model="gpt-4o-mini")  # Or any DSPy-compatible LM.
dspy.settings.configure(lm=lm)

architect = dspy.ChainOfThought(ProtocolArchitect)
executor = dspy.ChainOfThought(ProtocolExecutor)
qa = dspy.Predict(QualityAssurance)


def mpp_architect(user_goal: str, max_iters: int = 10) -> dict:
    last_bundle = None
    for _ in range(max_iters):
        prompt = user_goal
        if last_bundle is not None:
            prompt = (
                f"{user_goal}\n\nPrevious bundle:\n"
                f"{json.dumps(last_bundle, indent=2)}\n"
                "Refine for stability and correctness."
            )
        pred = architect(user_goal=prompt)
        bundle = {
            "meta_protocol_version": pred.meta_protocol_version,
            "derivative_protocol_specification": pred.derivative_protocol_specification,
            "derivative_protocol_payload": pred.derivative_protocol_payload,
        }
        validate_mpp_bundle(bundle)
        if last_bundle == bundle:
            return bundle
        last_bundle = bundle
    return last_bundle or {}


def mpp_execute(bundle: dict, max_iters: int = 10) -> str:
    last_response = None
    for _ in range(max_iters):
        pred = executor(
            meta_protocol_version=bundle["meta_protocol_version"],
            derivative_protocol_specification=bundle["derivative_protocol_specification"],
            derivative_protocol_payload=bundle["derivative_protocol_payload"],
        )
        response = pred.final_response
        if last_response == response:
            return response
        last_response = response
    return last_response or ""


bundle = mpp_architect(
    "Write a horror story about a lighthouse keeper in Lovecraftian tone."
)
final_response = mpp_execute(bundle)
qa_result = qa(
    meta_protocol_version=bundle["meta_protocol_version"],
    derivative_protocol_specification=bundle["derivative_protocol_specification"],
    derivative_protocol_payload=bundle["derivative_protocol_payload"],
    final_response=final_response,
)
if str(qa_result.verdict).strip().lower() != "pass":
    print(f"QA issues: {qa_result.issues}")
print(final_response)
```

Notes:
- The refinement loops mirror the monadic polishing approach: propose -> validate
  -> refine until the bundle/output stabilizes.
- Closed-world tasks: use stability checks as convergence and run QA as the last
  gate. Open-world tasks: evaluate QA inside the loop and stop on QA pass or
  max-iteration bounds.
- Swap the stability check with a domain-specific comparison if needed.
- Suggested refinement criteria for MPP: spec completeness, all processors defined,
  payload tags declared, minimalism (no unused tags), and executor output passes
  QA + format validation.
