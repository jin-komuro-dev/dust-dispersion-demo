"""相対飛散リスクモデル (仕様書 6章, docs/model_spec.md)。

物理濃度を厳密に予測するGaussian Plumeの実装ではなく、気象条件と工事条件から
算出する説明可能な相対リスクモデルである。UIから独立させ、全係数はconfig経由で
注入する(コードへ数値を埋め込まない)。

GSMの気象格子(0.1度x0.125度)はローカルメッシュ(10-20m)よりはるかに粗いため、
現場地点で補間した風・降水量をローカルメッシュ全体に一様に与える。したがって
本モジュールの入力 `u_mps`/`v_mps`/`hourly_precip_mm` は時刻ごとにスカラーであり、
セルごとの座標 `x_m`/`y_m` (NumPy配列可)との組合せでリスクを計算する。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dust_forecast.config import Intensity, ModelConfig, Watering
from dust_forecast.precipitation import rain_factor
from dust_forecast.wind import wind_speed


@dataclass
class RiskResult:
    wind_speed_mps: np.ndarray
    downwind_distance_m: np.ndarray  # s
    crosswind_distance_m: np.ndarray  # c
    sigma_y_m: np.ndarray
    downwind_decay: np.ndarray
    crosswind_spread: np.ndarray
    emission_factor: float
    wind_activation: float
    rain_factor: float
    mitigation_factor: float
    raw_risk: np.ndarray
    risk: np.ndarray
    is_calm: bool
    is_upwind: np.ndarray


def compute_risk(
    x_m: np.ndarray,
    y_m: np.ndarray,
    u_mps: float,
    v_mps: float,
    hourly_precip_mm: float,
    intensity: Intensity,
    watering: Watering,
    model_cfg: ModelConfig,
) -> RiskResult:
    """ローカルメッシュ全セルの相対飛散リスクを計算する。

    `x_m`, `y_m` は発生源からの相対座標[m](東・北が正)で、スカラーまたは
    同形状のNumPy配列を受け付ける。
    """
    x_m = np.asarray(x_m, dtype=float)
    y_m = np.asarray(y_m, dtype=float)

    speed = float(wind_speed(u_mps, v_mps))
    eps = model_cfg.eps

    e_base = model_cfg.e_base.for_intensity(intensity)
    mitigation = model_cfg.mitigation_factor.for_watering(watering)
    rfactor = rain_factor(
        hourly_precip_mm,
        [(bp.max_mm_h, bp.factor) for bp in model_cfg.rain_factor_breakpoints],
    )
    wind_activation = float(
        np.clip(
            (speed - model_cfg.wind_start_mps) / (model_cfg.wind_full_mps - model_cfg.wind_start_mps),
            0.0,
            model_cfg.wind_max_factor,
        )
    )

    is_calm = speed < model_cfg.calm_threshold_mps
    L = model_cfg.decay_base_m + model_cfg.decay_per_ms * speed

    if is_calm:
        r = np.hypot(x_m, y_m)
        s = r
        c = np.zeros_like(r)
        sigma_y = np.full_like(r, model_cfg.sigma0_m)
        downwind_decay = np.exp(-r / max(L, eps))
        crosswind_spread = np.ones_like(r)
        is_upwind = np.zeros_like(r, dtype=bool)
    else:
        s = (x_m * u_mps + y_m * v_mps) / max(speed, eps)
        c = (-x_m * v_mps + y_m * u_mps) / max(speed, eps)
        sigma_y = model_cfg.sigma0_m + model_cfg.spread_rate * np.clip(s, 0, None)
        downwind_decay = np.exp(-np.clip(s, 0, None) / max(L, eps))
        crosswind_spread = np.exp(-0.5 * (c / np.clip(sigma_y, eps, None)) ** 2)
        is_upwind = s < 0

    full_raw_risk = (
        100.0 * e_base * wind_activation * rfactor * mitigation * downwind_decay * crosswind_spread
    )
    upwind_raw_risk = np.full_like(full_raw_risk, 100.0 * model_cfg.upwind_background)
    raw_risk = np.where(is_upwind, upwind_raw_risk, full_raw_risk)
    risk = np.clip(raw_risk, 0.0, 100.0)

    return RiskResult(
        wind_speed_mps=np.full_like(x_m, speed),
        downwind_distance_m=s,
        crosswind_distance_m=c,
        sigma_y_m=sigma_y,
        downwind_decay=downwind_decay,
        crosswind_spread=crosswind_spread,
        emission_factor=e_base,
        wind_activation=wind_activation,
        rain_factor=rfactor,
        mitigation_factor=mitigation,
        raw_risk=raw_risk,
        risk=risk,
        is_calm=is_calm,
        is_upwind=is_upwind,
    )
