"""しきい値による4段階の表示区分 (仕様書 6.3節)。

色は dataviz スキルの「ステータスパレット」(good/warning/serious/critical、
固定・非テーマ化)を、意味の対応が一致するため流用する。
少ない=good, やや多い=warning, 多い=serious, 非常に多い=critical。
"""
from __future__ import annotations

import numpy as np

from dust_forecast.config import ThresholdsConfig

CATEGORY_LABELS: tuple[str, ...] = ("少ない", "やや多い", "多い", "非常に多い")

CATEGORY_COLORS: dict[str, str] = {
    "少ない": "#0ca30c",
    "やや多い": "#fab219",
    "多い": "#ec835a",
    "非常に多い": "#d03b3b",
}


def classify(risk: float, thresholds: ThresholdsConfig) -> str:
    """1つのリスク値[0-100]を表示区分(日本語ラベル)へ分類する。"""
    if risk <= thresholds.low_max:
        return CATEGORY_LABELS[0]
    if risk <= thresholds.moderate_max:
        return CATEGORY_LABELS[1]
    if risk <= thresholds.high_max:
        return CATEGORY_LABELS[2]
    return CATEGORY_LABELS[3]


def classify_array(risk: np.ndarray, thresholds: ThresholdsConfig) -> np.ndarray:
    """リスク値の配列を表示区分の配列(dtype=object)へ分類する。"""
    risk = np.asarray(risk, dtype=float)
    result = np.full(risk.shape, CATEGORY_LABELS[3], dtype=object)
    result[risk <= thresholds.high_max] = CATEGORY_LABELS[2]
    result[risk <= thresholds.moderate_max] = CATEGORY_LABELS[1]
    result[risk <= thresholds.low_max] = CATEGORY_LABELS[0]
    return result
