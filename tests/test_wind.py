import numpy as np
import pytest

from dust_forecast.wind import (
    CALM_EN,
    CALM_JA,
    deg_to_dir16,
    downwind_to_deg,
    wind_direction_label,
    wind_from_deg,
    wind_speed,
)


def test_u1_v0_wind_from_west_downwind_east():
    """U=1, V=0のとき、風向は西、飛散方向は東になる(仕様書11章 項目1)。"""
    assert wind_from_deg(1.0, 0.0) == pytest.approx(270.0)
    assert downwind_to_deg(1.0, 0.0) == pytest.approx(90.0)


def test_u0_v1_wind_from_south_downwind_north():
    """U=0, V=1のとき、風向は南、飛散方向は北になる(仕様書11章 項目2)。"""
    assert wind_from_deg(0.0, 1.0) == pytest.approx(180.0)
    assert downwind_to_deg(0.0, 1.0) == pytest.approx(0.0)


def test_wind_speed_scalar_and_array():
    assert wind_speed(3.0, 4.0) == pytest.approx(5.0)
    u = np.array([1.0, 0.0, 3.0])
    v = np.array([0.0, 1.0, 4.0])
    np.testing.assert_allclose(wind_speed(u, v), [1.0, 1.0, 5.0])


def test_from_and_downwind_are_opposite():
    for u, v in [(2.0, -3.0), (-1.5, 0.7), (0.0, -2.0)]:
        from_deg = wind_from_deg(u, v)
        to_deg = downwind_to_deg(u, v)
        assert (from_deg - to_deg) % 360 == pytest.approx(180.0, abs=1e-6)


def test_deg_to_dir16_scalar():
    ja, en = deg_to_dir16(0.0)
    assert (ja, en) == ("北", "N")
    ja, en = deg_to_dir16(90.0)
    assert (ja, en) == ("東", "E")
    ja, en = deg_to_dir16(180.0)
    assert (ja, en) == ("南", "S")
    ja, en = deg_to_dir16(270.0)
    assert (ja, en) == ("西", "W")


def test_deg_to_dir16_boundary_values():
    """方位境界値の検証(仕様書11章 項目15 関連: 境界値をテストする)。"""
    ja, en = deg_to_dir16(11.24)
    assert (ja, en) == ("北", "N")
    ja, en = deg_to_dir16(11.25)
    assert (ja, en) == ("北北東", "NNE")
    ja, en = deg_to_dir16(348.75)
    assert (ja, en) == ("北", "N")
    ja, en = deg_to_dir16(348.74)
    assert (ja, en) == ("北北西", "NNW")


def test_deg_to_dir16_array():
    ja, en = deg_to_dir16(np.array([0.0, 90.0, 180.0, 270.0]))
    np.testing.assert_array_equal(ja, np.array(["北", "東", "南", "西"]))
    np.testing.assert_array_equal(en, np.array(["N", "E", "S", "W"]))


def test_calm_wind_direction_label_scalar():
    """0m/s時の風向を「静穏」として扱えること(仕様書5.3節/11章 項目15関連)。"""
    ja, en = wind_direction_label(0.0, 0.0, calm_threshold=0.0)
    assert (ja, en) == (CALM_JA, CALM_EN)


def test_calm_wind_direction_label_below_threshold():
    ja, en = wind_direction_label(0.1, 0.1, calm_threshold=0.5)
    assert (ja, en) == (CALM_JA, CALM_EN)


def test_wind_direction_label_array_mixed_calm():
    u = np.array([0.0, 1.0])
    v = np.array([0.0, 0.0])
    ja, en = wind_direction_label(u, v, calm_threshold=0.0)
    assert en[0] == CALM_EN
    assert en[1] == "W"  # U=1,V=0 -> wind_from West


def test_wind_direction_label_works_for_pandas_series():
    """NumPy配列だけでなくPython/pandas風の値でも正しく動くことを確認する。"""
    pd = pytest.importorskip("pandas")
    u = pd.Series([1.0, 0.0])
    v = pd.Series([0.0, 1.0])
    speed = wind_speed(u, v)
    assert list(np.round(speed.values, 3)) == [1.0, 1.0]
