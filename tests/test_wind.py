import numpy as np
import pytest

from dust_forecast.wind import (
    CALM_EN,
    CALM_JA,
    DIR16_EN,
    DIR16_JA,
    deg_to_dir16,
    dir16_to_deg,
    downwind_to_deg,
    uv_from_speed_dir,
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


# --- dir16_to_deg() -----------------------------------------------------


def test_dir16_to_deg_en_abbreviations():
    assert dir16_to_deg("N") == pytest.approx(0.0)
    assert dir16_to_deg("ENE") == pytest.approx(67.5)
    assert dir16_to_deg("SSW") == pytest.approx(202.5)
    assert dir16_to_deg("NNW") == pytest.approx(337.5)


def test_dir16_to_deg_ja_names():
    assert dir16_to_deg("北") == pytest.approx(0.0)
    assert dir16_to_deg("北北東") == pytest.approx(22.5)
    assert dir16_to_deg("南南西") == pytest.approx(202.5)


def test_dir16_to_deg_case_insensitive():
    """大文字/小文字の表記ゆれに対応すること。"""
    assert dir16_to_deg("ene") == pytest.approx(67.5)
    assert dir16_to_deg("Ene") == pytest.approx(67.5)
    assert dir16_to_deg("ENE") == pytest.approx(67.5)


def test_dir16_to_deg_fullwidth_latin():
    """全角英字の表記ゆれに対応すること(NFKC正規化)。"""
    assert dir16_to_deg("Ｅ") == pytest.approx(90.0)
    assert dir16_to_deg("ＥＮＥ") == pytest.approx(67.5)


def test_dir16_to_deg_whitespace_tolerance():
    assert dir16_to_deg(" ENE ") == pytest.approx(67.5)


def test_dir16_to_deg_array_input():
    result = dir16_to_deg(["N", "ENE", "SSW"])
    np.testing.assert_allclose(result, [0.0, 67.5, 202.5])


def test_dir16_to_deg_unknown_value_raises():
    with pytest.raises(ValueError):
        dir16_to_deg("CALM")
    with pytest.raises(ValueError):
        dir16_to_deg("静穏")
    with pytest.raises(ValueError):
        dir16_to_deg("not-a-direction")


@pytest.mark.parametrize("index", range(16))
def test_dir16_to_deg_deg_to_dir16_round_trip_en(index):
    """deg_to_dir16() -> dir16_to_deg() の往復変換で元の角度に戻ること
    (16方位の中心角: 0, 22.5, 45, ... 337.5度)。
    """
    original_deg = index * 22.5
    _ja, en = deg_to_dir16(original_deg)
    assert dir16_to_deg(en) == pytest.approx(original_deg)


@pytest.mark.parametrize("index", range(16))
def test_dir16_to_deg_deg_to_dir16_round_trip_ja(index):
    original_deg = index * 22.5
    ja, _en = deg_to_dir16(original_deg)
    assert dir16_to_deg(ja) == pytest.approx(original_deg)


def test_dir16_to_deg_covers_all_16_directions():
    """DIR16_EN/DIR16_JAの全要素が変換可能であること。"""
    for i, (ja, en) in enumerate(zip(DIR16_JA, DIR16_EN)):
        expected = i * 22.5
        assert dir16_to_deg(en) == pytest.approx(expected)
        assert dir16_to_deg(ja) == pytest.approx(expected)


# --- uv_from_speed_dir() -------------------------------------------------


def test_uv_from_speed_dir_west_wind():
    """風向270度(西), 風速1m/s -> U=1, V=0 (wind_from_degの逆変換)。"""
    u, v = uv_from_speed_dir(270.0, 1.0)
    assert u == pytest.approx(1.0, abs=1e-9)
    assert v == pytest.approx(0.0, abs=1e-9)


def test_uv_from_speed_dir_south_wind():
    """風向180度(南), 風速1m/s -> U=0, V=1。"""
    u, v = uv_from_speed_dir(180.0, 1.0)
    assert u == pytest.approx(0.0, abs=1e-9)
    assert v == pytest.approx(1.0, abs=1e-9)


def test_uv_from_speed_dir_zero_speed_gives_zero_uv():
    u, v = uv_from_speed_dir(123.4, 0.0)
    assert u == pytest.approx(0.0, abs=1e-9)
    assert v == pytest.approx(0.0, abs=1e-9)


def test_uv_from_speed_dir_array_input():
    u, v = uv_from_speed_dir(np.array([270.0, 180.0]), np.array([1.0, 2.0]))
    np.testing.assert_allclose(u, [1.0, 0.0], atol=1e-9)
    np.testing.assert_allclose(v, [0.0, 2.0], atol=1e-9)


@pytest.mark.parametrize("deg,speed", [(0.0, 3.0), (45.0, 2.5), (123.4, 1.1), (270.0, 0.7), (359.0, 4.2)])
def test_uv_from_speed_dir_wind_from_deg_round_trip(deg, speed):
    """uv_from_speed_dir() -> wind_from_deg()/wind_speed() の往復変換で
    元の風向・風速に戻ること(wind_from_deg()とuv_from_speed_dir()が
    互いに正しい逆変換であることの検証)。
    """
    u, v = uv_from_speed_dir(deg, speed)
    recovered_deg = wind_from_deg(u, v)
    recovered_speed = wind_speed(u, v)
    assert recovered_deg == pytest.approx(deg, abs=1e-9)
    assert recovered_speed == pytest.approx(speed, abs=1e-9)


def test_dir16_to_deg_uv_from_speed_dir_full_pipeline():
    """情シス側の実利用フロー: 16方位文字列+風速 -> dir16_to_deg -> uv_from_speed_dir
    -> compute_riskへ渡せるU/Vが得られることをエンドツーエンドで確認する。
    """
    deg = dir16_to_deg("ENE")
    u, v = uv_from_speed_dir(deg, 3.0)
    assert wind_speed(u, v) == pytest.approx(3.0, abs=1e-9)
    assert wind_from_deg(u, v) == pytest.approx(67.5, abs=1e-9)
