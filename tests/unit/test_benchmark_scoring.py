from __future__ import annotations

from mpp_dspy.benchmarks.runner import (
    BenchmarkCase,
    _extract_gsm8k_answer,
    _extract_math_answer,
    _score_case,
    _valid_game24,
)


def test_extract_math_answer_from_boxed() -> None:
    text = "Solution: ... Final: \\\\boxed{42}."
    assert _extract_math_answer(text) == "42"


def test_extract_gsm8k_answer_from_hashes() -> None:
    text = "Compute steps. #### 17"
    assert _extract_gsm8k_answer(text) == "17"


def test_game24_expression_validation() -> None:
    expression = "6/(1-3/4)"
    assert _valid_game24(expression, [1, 3, 4, 6], 24)


def test_score_case_math() -> None:
    case = BenchmarkCase(
        case_id="1",
        dataset="math",
        question="Compute 6*7.",
        answer="Final: \\\\boxed{42}.",
        meta={},
    )
    assert _score_case(case, "Answer: \\\\boxed{42}")
