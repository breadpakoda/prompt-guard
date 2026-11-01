import pytest

from ai_engine.llm.ensemble import combine_detector_scores


def test_either_strong_detector_signal_can_trigger_combined_alert() -> None:
    classifier_alert = combine_detector_scores(0.9, 0.05)
    similarity_alert = combine_detector_scores(0.05, 0.95)

    assert classifier_alert["detected"] is True
    assert similarity_alert["detected"] is True


def test_moderate_evidence_from_both_detectors_combines_to_alert() -> None:
    result = combine_detector_scores(0.25, 0.42)

    assert result["detected"] is True
    assert result["combined_score"] == pytest.approx(
        1 - (1 - 0.25) * (1 - result["layer2_evidence"])
    )


def test_weak_independent_signals_do_not_trigger_alert() -> None:
    result = combine_detector_scores(0.05, 0.05)

    assert result["detected"] is False
    assert result["combined_score"] < 0.5


@pytest.mark.parametrize(
    ("layer1_score", "layer2_score"),
    [(-0.1, 0.2), (1.1, 0.2), (0.2, -1.1), (0.2, 1.1)],
)
def test_invalid_detector_scores_raise(
    layer1_score: float, layer2_score: float
) -> None:
    with pytest.raises(ValueError):
        combine_detector_scores(layer1_score, layer2_score)
