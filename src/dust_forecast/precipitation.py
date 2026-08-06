"""積算降水量からの時間降水量差分 (仕様書 5.4節)。

GSMの降水量は初期時刻からの積算値である。`forecastTime` のみで判断せず、
実際には隣接する時刻の積算値の差分として時間降水量を求める。

    hourly_precip(t) = max(accum_precip(t) - accum_precip(t-1), 0)

積算のリセットや欠損があれば警告ログを出す。
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from dust_forecast.logging_config import get_logger

logger = get_logger("precipitation")


def hourly_from_accumulated(accum: xr.DataArray, time_dim: str = "step") -> xr.DataArray:
    """積算降水量DataArrayから時間降水量DataArrayを求める。

    - `time_dim` に沿って昇順ソートしてから差分を取る。
    - 先頭の時刻がすべてNaN(GSMではforecast hour 0にAPCPフィールドが
      存在しないため)の場合は、初期時刻の積算量は定義上0であるとみなし、
      0で補完してから差分計算に用いる。
    - それ以外のNaN・負の差分(積算のリセット/欠損の可能性)は警告ログを
      出したうえで0へ切り詰める。
    """
    sorted_da = accum.sortby(time_dim)

    first_slice = sorted_da.isel({time_dim: 0})
    if bool(first_slice.isnull().all()):
        logger.info(
            "先頭時刻(%s)の積算降水量が全セルNaNのため、初期時刻の積算量0として補完します。",
            str(sorted_da[time_dim].values[0]),
        )
        sorted_da = xr.concat(
            [first_slice.fillna(0.0).expand_dims({time_dim: [sorted_da[time_dim].values[0]]}), sorted_da.isel({time_dim: slice(1, None)})],
            dim=time_dim,
        )

    diff = sorted_da.diff(dim=time_dim)

    nan_mask = diff.isnull()
    if bool(nan_mask.any()):
        n_nan = int(nan_mask.sum())
        logger.warning("時間降水量の差分計算でNaNが%d件検出されました(欠損の可能性)。0として扱います。", n_nan)

    negative_mask = diff < -1e-6
    if bool((negative_mask & ~nan_mask).any()):
        n_neg = int((negative_mask & ~nan_mask).sum())
        logger.warning(
            "積算降水量が減少している箇所が%d件検出されました(積算のリセットまたは欠損の可能性)。0へ切り詰めます。",
            n_neg,
        )

    hourly = diff.fillna(0.0).clip(min=0.0)

    first = xr.full_like(sorted_da.isel({time_dim: [0]}), np.nan)
    hourly = xr.concat([first, hourly], dim=time_dim)
    hourly.name = "hourly_precip"
    hourly.attrs["units"] = "mm/h"
    hourly.attrs["description"] = "隣接時刻の積算降水量の差分 (先頭時刻は基準無しのためNaN)"
    return hourly
