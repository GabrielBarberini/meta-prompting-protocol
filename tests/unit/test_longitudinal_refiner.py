from mpp_dspy.mpp_optimizer import (
    LongitudinalScore,
    LongitudinalTrace,
    MPPLongitudinalRefiner,
)


def test_longitudinal_refiner_selects_best_template() -> None:
    template = "Start {{MPP_MUTABLE:block}}bad{{/MPP_MUTABLE}} end."
    dataset = ["example"]

    def mutate_function(blocks, _dataset):
        return {"block": blocks["block"].replace("bad", "good")}

    def score_function(candidate, _dataset):
        return 1.0 if "good" in candidate else 0.0

    refiner = MPPLongitudinalRefiner(
        mutate_function=mutate_function,
        score_function=score_function,
        max_iters=1,
    )
    result = refiner.refine(template, dataset)
    assert "good" in result.template
    assert result.score == 1.0
    assert result.blocks["block"] == "good"


def test_longitudinal_refiner_passes_traces_to_mutate_function() -> None:
    template = "Start {{MPP_MUTABLE:block}}bad{{/MPP_MUTABLE}} end."
    dataset = ["example"]
    seen = {}

    def mutate_function(blocks, _dataset, traces):
        seen["traces"] = traces
        return {"block": blocks["block"].replace("bad", "good")}

    def score_function(candidate, _dataset):
        return LongitudinalScore(
            score=1.0 if "good" in candidate else 0.0,
            traces=[LongitudinalTrace(case="example", bundle_refinements=2)],
        )

    refiner = MPPLongitudinalRefiner(
        mutate_function=mutate_function,
        score_function=score_function,
        max_iters=1,
    )
    refiner.refine(template, dataset)
    assert seen["traces"]
    assert isinstance(seen["traces"][0], LongitudinalTrace)
