import numpy as np
import pandas as pd
import pytest
import xarray as xr

from dust_forecast.precipitation import hourly_from_accumulated


def _accum_da(values, start="2023-03-15T00:00:00"):
    times = pd.date_range(start, periods=len(values), freq="h")
    return xr.DataArray(values, dims=["step"], coords={"step": times}, name="apcp")


def test_hourly_from_accumulated_basic_diff():
    """積算降水量から時間降水量を正しく差分化する(仕様書11章 項目10)。"""
    accum = _accum_da([np.nan, 0.0, 0.5, 0.5, 2.0])
    hourly = hourly_from_accumulated(accum, time_dim="step")
    result = hourly.values
    assert np.isnan(result[0])
    np.testing.assert_allclose(result[1:], [0.0, 0.5, 0.0, 1.5])


def test_hourly_from_accumulated_first_step_all_nan_treated_as_zero_baseline():
    accum = _accum_da([np.nan, 1.2])
    hourly = hourly_from_accumulated(accum, time_dim="step")
    assert hourly.values[1] == pytest.approx(1.2)


def test_hourly_from_accumulated_reset_clipped_to_zero():
    """積算のリセット(減少)が0へ切り詰められること。"""
    accum = _accum_da([0.0, 2.0, 0.5])  # 2.0 -> 0.5 はリセット/欠損とみなす
    hourly = hourly_from_accumulated(accum, time_dim="step")
    assert hourly.values[2] == 0.0


def test_hourly_from_accumulated_unsorted_input():
    times = pd.to_datetime(["2023-03-15T02:00", "2023-03-15T00:00", "2023-03-15T01:00"])
    da = xr.DataArray([2.0, 0.0, 1.0], dims=["step"], coords={"step": times})
    hourly = hourly_from_accumulated(da, time_dim="step").sortby("step")
    np.testing.assert_allclose(hourly.values[1:], [1.0, 1.0])
