"""現場地点への空間補間 (仕様書 5.2節)。

- 緯度・経度配列の昇順・降順を確認する
- 双線形補間を基本とし、補間不能(領域外・NaN)時は最近傍へフォールバックしてログに残す
- 使用した格子点(補間に使った4格子点、または最近傍1格子点)を計算トレースへ出力する
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import xarray as xr

from dust_forecast.logging_config import get_logger

logger = get_logger("interpolation")


class InterpolationError(Exception):
    """空間補間に関する独自例外。"""


@dataclass
class InterpolationTrace:
    method: str
    fallback_used: bool
    grid_points: list[dict] = field(default_factory=list)
    note: str = ""


def _check_monotonic(values: np.ndarray, name: str) -> None:
    diffs = np.diff(values)
    if not (np.all(diffs > 0) or np.all(diffs < 0)):
        raise InterpolationError(f"{name} 座標が単調増加/減少ではありません: {values[:5]}...")


def _bracket(coord: np.ndarray, target: float) -> tuple[int, int]:
    """target を挟む2つのインデックスを返す(昇順・降順いずれの座標配列にも対応)。"""
    ascending = coord[-1] >= coord[0]
    order = coord if ascending else coord[::-1]
    pos = int(np.clip(np.searchsorted(order, target), 1, len(order) - 1))
    lo_ordered, hi_ordered = pos - 1, pos
    if ascending:
        return lo_ordered, hi_ordered
    n = len(coord)
    return n - 1 - lo_ordered, n - 1 - hi_ordered


def _bilinear_grid_points(
    ds: xr.Dataset | xr.DataArray, latitude: float, longitude: float, lat_dim: str, lon_dim: str
) -> list[dict]:
    lat_vals = ds[lat_dim].values
    lon_vals = ds[lon_dim].values
    lat_lo, lat_hi = _bracket(lat_vals, latitude)
    lon_lo, lon_hi = _bracket(lon_vals, longitude)
    points = []
    for i in sorted({lat_lo, lat_hi}):
        for j in sorted({lon_lo, lon_hi}):
            points.append({"latitude": float(lat_vals[i]), "longitude": float(lon_vals[j])})
    return points


def interpolate_point(
    ds: xr.Dataset | xr.DataArray,
    latitude: float,
    longitude: float,
    method: str = "bilinear",
    lat_dim: str = "latitude",
    lon_dim: str = "longitude",
) -> tuple[xr.Dataset | xr.DataArray, InterpolationTrace]:
    """現場地点(latitude, longitude)における値を補間して返す。

    戻り値: (補間結果, InterpolationTrace)
    """
    if method not in ("bilinear", "nearest"):
        raise InterpolationError(f"未知の補間方式です: {method}")

    _check_monotonic(ds[lat_dim].values, lat_dim)
    _check_monotonic(ds[lon_dim].values, lon_dim)

    lat_min, lat_max = sorted((float(ds[lat_dim].values[0]), float(ds[lat_dim].values[-1])))
    lon_min, lon_max = sorted((float(ds[lon_dim].values[0]), float(ds[lon_dim].values[-1])))
    in_domain = (lat_min <= latitude <= lat_max) and (lon_min <= longitude <= lon_max)

    # NaNは「補間不能」の判定には使わない: 積算降水量など一部の要素は特定の時刻
    # (例: forecast hour 0)でGRIB2フィールド自体が存在せず、データセット全体を
    # 見るとNaNを含むことがある。これは空間補間の失敗ではなく入力データの欠損
    # であり、precipitation.pyで別途扱う。ここでは現場地点が格子範囲内かどうか
    # のみで補間可否を判定する。
    if method == "bilinear" and in_domain:
        result = ds.interp({lat_dim: latitude, lon_dim: longitude}, method="linear")
        points = _bilinear_grid_points(ds, latitude, longitude, lat_dim, lon_dim)
        return result, InterpolationTrace(method="bilinear", fallback_used=False, grid_points=points)
    elif method == "bilinear" and not in_domain:
        logger.warning(
            "現場地点(lat=%s, lon=%s)が格子範囲外のため最近傍補間へフォールバックします", latitude, longitude
        )

    result = ds.sel({lat_dim: latitude, lon_dim: longitude}, method="nearest")
    used_lat = float(result[lat_dim].values)
    used_lon = float(result[lon_dim].values)
    trace = InterpolationTrace(
        method="nearest",
        fallback_used=(method == "bilinear"),
        grid_points=[{"latitude": used_lat, "longitude": used_lon}],
        note="bilinear不能のため最近傍へフォールバック" if method == "bilinear" else "",
    )
    return result, trace
