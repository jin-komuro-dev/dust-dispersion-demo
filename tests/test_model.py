import numpy as np
import pytest

from dust_forecast.config import EmissionBase, MitigationFactor, ModelConfig, RainFactorBreakpoint
from dust_forecast.model import compute_risk


def _model_config(**overrides) -> ModelConfig:
    base = dict(
        wind_start_mps=0.5,
        wind_full_mps=4.0,
        wind_max_factor=1.2,
        sigma0_m=8.0,
        spread_rate=0.18,
        decay_base_m=35.0,
        decay_per_ms=18.0,
        upwind_background=0.0,
        calm_threshold_mps=0.3,
        eps=1.0e-6,
        e_base=EmissionBase(small=0.6, medium=1.0, large=1.5),
        rain_factor_breakpoints=[
            RainFactorBreakpoint(max_mm_h=0.1, factor=1.00),
            RainFactorBreakpoint(max_mm_h=1.0, factor=0.70),
            RainFactorBreakpoint(max_mm_h=3.0, factor=0.40),
            RainFactorBreakpoint(max_mm_h=float("inf"), factor=0.15),
        ],
        mitigation_factor=MitigationFactor(none=1.00, normal=0.60, strong=0.35),
    )
    base.update(overrides)
    return ModelConfig(**base)


def test_downwind_higher_risk_than_upwind():
    """発生源の風下側が風上側より高リスクになる(仕様書11章 項目3)。"""
    cfg = _model_config()
    # 風はV=5(北向き)。風下(y>0)と風上(y<0)を比較する。
    downwind = compute_risk(0.0, 30.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    upwind = compute_risk(0.0, -30.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    assert downwind.risk[()] > upwind.risk[()]


def test_larger_crosswind_distance_lower_risk():
    """横風距離が大きいほどリスクが低下する(仕様書11章 項目4)。"""
    cfg = _model_config()
    near = compute_risk(0.0, 30.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    far = compute_risk(40.0, 30.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    assert far.risk[()] < near.risk[()]


def test_farther_downwind_distance_lower_risk():
    """距離が遠いほどリスクが低下する(仕様書11章 項目5)。"""
    cfg = _model_config()
    close = compute_risk(0.0, 20.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    far = compute_risk(0.0, 150.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    assert far.risk[()] < close.risk[()]


def test_more_rain_lower_risk():
    """降水量が増えるほどリスクが低下する(仕様書11章 項目6)。"""
    cfg = _model_config()
    dry = compute_risk(0.0, 30.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    wet = compute_risk(0.0, 30.0, 0.0, 5.0, 5.0, "medium", "none", cfg)
    assert wet.risk[()] < dry.risk[()]


def test_watering_lower_risk():
    """散水ありでリスクが低下する(仕様書11章 項目7)。"""
    cfg = _model_config()
    no_watering = compute_risk(0.0, 30.0, 0.0, 5.0, 0.0, "medium", "none", cfg)
    watered = compute_risk(0.0, 30.0, 0.0, 5.0, 0.0, "medium", "strong", cfg)
    assert watered.risk[()] < no_watering.risk[()]


def test_deterministic_same_input_same_output():
    """同じ入力なら同じ出力になる(仕様書11章 項目8)。"""
    cfg = _model_config()
    r1 = compute_risk(10.0, 25.0, 1.0, 4.0, 0.5, "medium", "normal", cfg)
    r2 = compute_risk(10.0, 25.0, 1.0, 4.0, 0.5, "medium", "normal", cfg)
    np.testing.assert_array_equal(r1.risk, r2.risk)
    assert r1.raw_risk[()] == r2.raw_risk[()]


def test_calm_wind_gives_isotropic_distribution():
    """無風時は特定方向へ伸びず等方分布になる。"""
    cfg = _model_config()
    north = compute_risk(0.0, 30.0, 0.0, 0.0, 0.0, "medium", "none", cfg)
    east = compute_risk(30.0, 0.0, 0.0, 0.0, 0.0, "medium", "none", cfg)
    assert north.is_calm is True
    assert north.risk[()] == pytest.approx(east.risk[()])


def test_risk_clipped_to_0_100_range():
    cfg = _model_config()
    result = compute_risk(np.array([0.0, 500.0]), np.array([30.0, 500.0]), 0.0, 10.0, 0.0, "large", "none", cfg)
    assert np.all(result.risk >= 0.0)
    assert np.all(result.risk <= 100.0)


def test_array_input_shapes_preserved():
    cfg = _model_config()
    x = np.array([[0.0, 10.0], [0.0, 10.0]])
    y = np.array([[20.0, 20.0], [40.0, 40.0]])
    result = compute_risk(x, y, 0.0, 5.0, 0.0, "medium", "none", cfg)
    assert result.risk.shape == x.shape
