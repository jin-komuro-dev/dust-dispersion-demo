"""CSV/JSON出力 (仕様書 7章: 追跡可能性・説明可能性)。

各時刻・各セルの中間計算値をCSVに、時刻ごとの計算根拠サマリをJSONに出力する。
画面の色がどの入力・計算から得られたか追跡できるようにする。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dust_forecast.categories import classify_array
from dust_forecast.config import AppConfig
from dust_forecast.grid import GridResult
from dust_forecast.model import RiskResult

CELL_CSV_COLUMNS: list[str] = [
    "valid_time_utc",
    "valid_time_jst",
    "row",
    "column",
    "center_x_m",
    "center_y_m",
    "latitude",
    "longitude",
    "source_x_m",
    "source_y_m",
    "grid_width_m",
    "grid_height_m",
    "cell_size_x_m",
    "cell_size_y_m",
    "nx",
    "ny",
    "u10_mps",
    "v10_mps",
    "wind_speed_mps",
    "wind_from_deg",
    "downwind_to_deg",
    "hourly_precip_mm",
    "emission_factor",
    "wind_activation",
    "rain_factor",
    "mitigation_factor",
    "downwind_distance_m",
    "crosswind_distance_m",
    "sigma_y_m",
    "downwind_decay",
    "crosswind_spread",
    "raw_risk",
    "risk",
    "category",
]


def build_cell_dataframe(
    valid_time_utc: datetime,
    valid_time_jst: datetime,
    grid: GridResult,
    u10_mps: float,
    v10_mps: float,
    wind_from_deg: float,
    downwind_to_deg: float,
    hourly_precip_mm: float,
    risk_result: RiskResult,
    config: AppConfig,
) -> pd.DataFrame:
    """1時刻分の全セルの中間計算値をDataFrameへ整形する。"""
    n = grid.total_cells
    category = classify_array(risk_result.risk, config.thresholds)

    data = {
        "valid_time_utc": valid_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valid_time_jst": valid_time_jst.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "row": grid.row_index.ravel(),
        "column": grid.col_index.ravel(),
        "center_x_m": grid.center_x_m.ravel(),
        "center_y_m": grid.center_y_m.ravel(),
        "latitude": grid.center_latitude.ravel(),
        "longitude": grid.center_longitude.ravel(),
        "source_x_m": grid.source_x_m,
        "source_y_m": grid.source_y_m,
        "grid_width_m": grid.actual_width_m,
        "grid_height_m": grid.actual_height_m,
        "cell_size_x_m": grid.cell_size_x_m,
        "cell_size_y_m": grid.cell_size_y_m,
        "nx": grid.nx,
        "ny": grid.ny,
        "u10_mps": u10_mps,
        "v10_mps": v10_mps,
        "wind_speed_mps": risk_result.wind_speed_mps.ravel(),
        "wind_from_deg": wind_from_deg,
        "downwind_to_deg": downwind_to_deg,
        "hourly_precip_mm": hourly_precip_mm,
        "emission_factor": risk_result.emission_factor,
        "wind_activation": risk_result.wind_activation,
        "rain_factor": risk_result.rain_factor,
        "mitigation_factor": risk_result.mitigation_factor,
        "downwind_distance_m": risk_result.downwind_distance_m.ravel(),
        "crosswind_distance_m": risk_result.crosswind_distance_m.ravel(),
        "sigma_y_m": risk_result.sigma_y_m.ravel(),
        "downwind_decay": risk_result.downwind_decay.ravel(),
        "crosswind_spread": risk_result.crosswind_spread.ravel(),
        "raw_risk": risk_result.raw_risk.ravel(),
        "risk": risk_result.risk.ravel(),
        "category": category.ravel(),
    }
    df = pd.DataFrame({k: (v if np.ndim(v) else np.full(n, v)) for k, v in data.items()})
    return df[CELL_CSV_COLUMNS]


def write_cell_csv(df: pd.DataFrame, output_dir: Path, valid_time_utc: datetime) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"cells_{valid_time_utc:%Y%m%dT%H%MZ}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_time_summary(
    *,
    input_filename: str,
    init_time_utc: datetime,
    valid_time_utc: datetime,
    valid_time_jst: datetime,
    config: AppConfig,
    grid: GridResult,
    interpolation_method: str,
    used_fields: list[str],
    risk_result: RiskResult,
    warnings: list[str],
) -> dict[str, Any]:
    """1時刻分の計算根拠サマリをdictへ整形する(そのままJSON化可能)。"""
    flat_risk = risk_result.risk.ravel()
    max_idx = int(np.argmax(flat_risk))
    row = int(grid.row_index.ravel()[max_idx])
    col = int(grid.col_index.ravel()[max_idx])

    return {
        "input_filename": input_filename,
        "init_time_utc": init_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valid_time_utc": valid_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valid_time_jst": valid_time_jst.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "site": {
            "name": config.site.name,
            "latitude": config.site.latitude,
            "longitude": config.site.longitude,
        },
        "grid": {
            "width_m": grid.actual_width_m,
            "height_m": grid.actual_height_m,
            "cell_size_x_m": grid.cell_size_x_m,
            "cell_size_y_m": grid.cell_size_y_m,
            "nx": grid.nx,
            "ny": grid.ny,
            "rotation_deg": grid.rotation_deg,
            "edge_policy": grid.edge_policy_applied,
            "source_x_m": grid.source_x_m,
            "source_y_m": grid.source_y_m,
            "source_latitude": grid.source_latitude,
            "source_longitude": grid.source_longitude,
        },
        "interpolation_method": interpolation_method,
        "used_grib_fields": used_fields,
        "construction": {
            "intensity": config.construction.intensity,
            "work_start_jst": config.construction.work_start_jst,
            "work_end_jst": config.construction.work_end_jst,
            "watering": config.construction.watering,
        },
        "model_coefficients": config.model.model_dump(),
        "formula_version": config.output.formula_version,
        "thresholds": config.thresholds.model_dump(),
        "max_risk": float(np.max(flat_risk)),
        "max_risk_cell": {"row": row, "column": col},
        "warnings": warnings,
    }


def write_time_json(summary: dict[str, Any], output_dir: Path, valid_time_utc: datetime) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"summary_{valid_time_utc:%Y%m%dT%H%MZ}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path
