"""設定ファイル(YAML)のスキーマ定義と読み込み。

すべての係数・しきい値・グリッド仕様はここで定義するモデルを介して
YAMLファイルから読み込む。コード中に数値を埋め込まない。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from dust_forecast.paths import DEFAULT_CONFIG_PATH


class SiteConfig(BaseModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


SourcePositionMode = Literal["offset_m", "latlon", "rowcol"]
EdgePolicy = Literal["error", "trim", "pad"]


class GridConfig(BaseModel):
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    cell_size_x_m: float = Field(gt=0)
    cell_size_y_m: float = Field(gt=0)
    rotation_deg: float = 0.0
    source_position_mode: SourcePositionMode = "offset_m"
    source_offset_x_m: float | None = None
    source_offset_y_m: float | None = None
    source_latitude: float | None = None
    source_longitude: float | None = None
    source_row: int | None = None
    source_col: int | None = None
    edge_policy: EdgePolicy = "error"
    max_cells: int = Field(default=10000, gt=0)

    @model_validator(mode="after")
    def _check_source_fields(self) -> "GridConfig":
        mode = self.source_position_mode
        if mode == "offset_m":
            if self.source_offset_x_m is None or self.source_offset_y_m is None:
                raise ValueError(
                    "source_position_mode=offset_m には "
                    "source_offset_x_m / source_offset_y_m が必要です"
                )
        elif mode == "latlon":
            if self.source_latitude is None or self.source_longitude is None:
                raise ValueError(
                    "source_position_mode=latlon には "
                    "source_latitude / source_longitude が必要です"
                )
        elif mode == "rowcol":
            if self.source_row is None or self.source_col is None:
                raise ValueError(
                    "source_position_mode=rowcol には "
                    "source_row / source_col が必要です"
                )
        return self


Intensity = Literal["small", "medium", "large"]
Watering = Literal["none", "normal", "strong"]


class ConstructionConfig(BaseModel):
    intensity: Intensity = "medium"
    work_start_jst: str = "09:00"
    work_end_jst: str = "16:00"
    watering: Watering = "none"


ReaderBackend = Literal["cfgrib", "wgrib2_netcdf", "pygrib"]
InterpolationMethod = Literal["bilinear", "nearest"]


class GribConfig(BaseModel):
    input_path: str | None = None
    reader_backend: ReaderBackend = "cfgrib"
    wgrib2_exe: str | None = None
    target_start_jst: str = "2023-03-15T09:00:00"
    target_end_jst: str = "2023-03-15T16:00:00"
    interpolation: InterpolationMethod = "bilinear"


class RainFactorBreakpoint(BaseModel):
    max_mm_h: float
    factor: float = Field(ge=0, le=1)


class EmissionBase(BaseModel):
    small: float = Field(gt=0)
    medium: float = Field(gt=0)
    large: float = Field(gt=0)

    def for_intensity(self, intensity: Intensity) -> float:
        return getattr(self, intensity)


class MitigationFactor(BaseModel):
    none: float = Field(ge=0, le=1)
    normal: float = Field(ge=0, le=1)
    strong: float = Field(ge=0, le=1)

    def for_watering(self, watering: Watering) -> float:
        return getattr(self, watering)


class ModelConfig(BaseModel):
    wind_start_mps: float = Field(ge=0)
    wind_full_mps: float = Field(gt=0)
    wind_max_factor: float = Field(gt=0)
    sigma0_m: float = Field(gt=0)
    spread_rate: float = Field(ge=0)
    decay_base_m: float = Field(gt=0)
    decay_per_ms: float = Field(ge=0)
    upwind_background: float = Field(ge=0)
    calm_threshold_mps: float = Field(ge=0, default=0.3)
    eps: float = Field(gt=0, default=1.0e-6)
    e_base: EmissionBase
    rain_factor_breakpoints: list[RainFactorBreakpoint]
    mitigation_factor: MitigationFactor

    @field_validator("wind_full_mps")
    @classmethod
    def _wind_full_gt_start(cls, v: float, info) -> float:
        start = info.data.get("wind_start_mps")
        if start is not None and v <= start:
            raise ValueError("wind_full_mps は wind_start_mps より大きい必要があります")
        return v


class ThresholdsConfig(BaseModel):
    low_max: float = Field(gt=0)
    moderate_max: float
    high_max: float

    @model_validator(mode="after")
    def _check_order(self) -> "ThresholdsConfig":
        if not (self.low_max < self.moderate_max < self.high_max):
            raise ValueError("thresholds は low_max < moderate_max < high_max である必要があります")
        return self


class WeatherDisplayConfig(BaseModel):
    rain_mm_h: float = 1.0
    light_rain_mm_h: float = 0.1
    cloudy_cloud_pct: float = 80.0
    partly_cloudy_cloud_pct: float = 50.0


class OutputConfig(BaseModel):
    formula_version: str = "1.0.0"


class AppConfig(BaseModel):
    site: SiteConfig
    grid: GridConfig
    construction: ConstructionConfig
    grib: GribConfig
    model: ModelConfig
    thresholds: ThresholdsConfig
    weather_display: WeatherDisplayConfig = WeatherDisplayConfig()
    output: OutputConfig = OutputConfig()


def load_config(path: str | Path | None = None) -> AppConfig:
    """YAML設定ファイルを読み込み、検証済みの AppConfig を返す。"""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
