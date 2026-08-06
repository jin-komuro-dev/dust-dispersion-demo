import numpy as np
import pytest

from dust_forecast.categories import CATEGORY_LABELS, classify, classify_array
from dust_forecast.config import ThresholdsConfig

THRESHOLDS = ThresholdsConfig(low_max=25, moderate_max=50, high_max=75)


@pytest.mark.parametrize(
    "risk,expected",
    [
        (0, "少ない"),
        (25, "少ない"),          # low_max ちょうど -> 少ない
        (25.0001, "やや多い"),   # low_max超
        (50, "やや多い"),        # moderate_max ちょうど -> やや多い
        (50.0001, "多い"),       # moderate_max超
        (75, "多い"),            # high_max ちょうど -> 多い
        (75.0001, "非常に多い"), # high_max超
        (100, "非常に多い"),
    ],
)
def test_classify_boundary_values(risk, expected):
    """色区分の境界値が正しい(仕様書11章 項目9)。"""
    assert classify(risk, THRESHOLDS) == expected


def test_classify_array_matches_scalar():
    risks = np.array([0, 25, 25.0001, 50, 50.0001, 75, 75.0001, 100])
    expected = [classify(float(r), THRESHOLDS) for r in risks]
    result = classify_array(risks, THRESHOLDS)
    assert list(result) == expected


def test_all_labels_reachable():
    risks = [10, 30, 60, 90]
    labels = {classify(r, THRESHOLDS) for r in risks}
    assert labels == set(CATEGORY_LABELS)
