import numpy as np
import pandas as pd
import pytest
import xarray as xr

from dust_forecast.precipitation import hourly_from_accumulated, rain_factor

BREAKPOINTS = [(0.1, 1.00), (1.0, 0.70), (3.0, 0.40), (float("inf"), 0.15)]


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


@pytest.mark.parametrize(
    "precip,expected",
    [
        (0.0, 1.00),
        (0.05, 1.00),
        (0.1, 0.70),  # 0.1 <= precip < 1.0
        (0.99, 0.70),
        (1.0, 0.40),  # 1.0 <= precip < 3.0
        (2.99, 0.40),
        (3.0, 0.15),  # >= 3.0
        (10.0, 0.15),
    ],
)
def test_rain_factor_breakpoints(precip, expected):
    assert rain_factor(precip, BREAKPOINTS) == pytest.approx(expected)


def test_rain_factor_more_rain_means_lower_factor():
    """降水量が増えるほどリスク(降水係数)が低下する(仕様書11章 項目6)。"""
    values = [rain_factor(p, BREAKPOINTS) for p in (0.0, 0.5, 2.0, 5.0)]
    assert values == sorted(values, reverse=True)
