"""簡易天気判定 (仕様書 9章)。

GSMの時間降水量と全雲量からの簡易判定であり、気象庁の正式な天気予報表現ではない。
画面・出力物には必ずその旨を明記すること。
"""
from __future__ import annotations

from dust_forecast.config import WeatherDisplayConfig

DISCLAIMER = "本表示は時間降水量・全雲量からの簡易判定であり、気象庁の正式な天気予報ではありません。"


def classify_weather(
    hourly_precip_mm: float,
    total_cloud_cover_pct: float | None,
    cfg: WeatherDisplayConfig,
) -> str:
    """時間降水量[mm/h]と全雲量[%]から簡易天気を判定する。"""
    if hourly_precip_mm >= cfg.rain_mm_h:
        return "雨"
    if hourly_precip_mm >= cfg.light_rain_mm_h:
        return "弱い雨"

    if total_cloud_cover_pct is None:
        return "不明"
    if total_cloud_cover_pct >= cfg.cloudy_cloud_pct:
        return "くもり"
    if total_cloud_cover_pct >= cfg.partly_cloudy_cloud_pct:
        return "晴れ時々くもり"
    return "晴れ"
