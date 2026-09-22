import pytest
from arena.metrics import evaluate, percentiles, temperature_scale


def test_percentiles_interpolate_and_empty_is_null():
    assert percentiles([])["p50"] is None
    assert percentiles([10, 20])["p50"] == 15
    assert percentiles([10, 20])["p95"] == 19.5


def test_metrics_use_probabilities_not_provider_confidence():
    rows = [
        {
            "expected": {"x": "a"},
            "answers": {
                "x": {
                    "type": "choice",
                    "value": "a",
                    "confidence": 0.1,
                    "probabilities": {"a": 0.8, "b": 0.2},
                }
            },
        }
    ]
    m = evaluate(rows)
    assert m["accuracy"] == 1 and m["macro_f1"] == 1
    assert m["brier"] == pytest.approx(0.08)
    assert m["ece"] == pytest.approx(0.2)


def test_ambiguous_labels_not_used_for_calibration():
    rows = [
        {
            "expected": {"x": ["a", "b"]},
            "answers": {"x": {"type": "choice", "value": "b", "probabilities": {"a": 0.1, "b": 0.9}}},
        }
    ]
    m = evaluate(rows)
    assert m["accuracy"] == 1 and m["ece"] is None


def test_temperature_preserves_normalization_and_softens():
    result = temperature_scale({"a": 0.9, "b": 0.1}, 2)
    assert sum(result.values()) == pytest.approx(1)
    assert 0.5 < result["a"] < 0.9


def test_threshold_changes_false_positive_rate():
    rows = [{"expected": {"x": 0}, "answers": {"x": {"type": "boolean_probability", "value": 0.6}}}]
    assert evaluate(rows, 0.5)["accuracy"] == 0
    assert evaluate(rows, 0.7)["accuracy"] == 1
