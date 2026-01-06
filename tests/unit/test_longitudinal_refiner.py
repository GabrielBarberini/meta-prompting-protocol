from mpp_dspy.mpp_optimizer import MPPLongitudinalRefiner


def test_longitudinal_refiner_selects_best_template() -> None:
    template = "Start {{MPP_MUTABLE:block}}bad{{/MPP_MUTABLE}} end."
    dataset = ["example"]

    def mutate(blocks, _dataset):
        return {"block": blocks["block"].replace("bad", "good")}

    def score(candidate, _dataset):
        return 1.0 if "good" in candidate else 0.0

    refiner = MPPLongitudinalRefiner(mutate, score, max_iters=1)
    result = refiner.refine(template, dataset)
    assert "good" in result.template
    assert result.score == 1.0
