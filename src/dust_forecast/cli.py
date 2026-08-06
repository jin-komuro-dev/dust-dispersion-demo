"""CLIエントリポイント (仕様書 3.2節)。

- `python -m dust_forecast.cli inspect-grib --input <path>`
- `python -m dust_forecast.cli generate --input <path> --config <path>`

`run_pipeline()` は計算の中核ロジックであり、CLIとStreamlit(app.py)の
どちらからも同じ関数を呼び出す(ロジックと画面の分離)。
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import xarray as xr

from dust_forecast.categories import classify
from dust_forecast.config import AppConfig, load_config
from dust_forecast.grib_reader import get_reader
from dust_forecast.grid import GridResult, build_grid
from dust_forecast.interpolation import InterpolationTrace, interpolate_point
from dust_forecast.logging_config import get_logger, setup_logging
from dust_forecast.model import compute_risk
from dust_forecast.paths import ensure_outputs_dir
from dust_forecast.plotting import TimeFrameData, plot_dashboard, plot_time_map
from dust_forecast.precipitation import hourly_from_accumulated
from dust_forecast.readers.base import OPTIONAL_FIELDS, REQUIRED_FIELDS
from dust_forecast.reports import build_cell_dataframe, build_time_summary, write_cell_csv, write_time_json
from dust_forecast.weather import classify_weather
from dust_forecast.wind import downwind_to_deg, wind_direction_label, wind_from_deg, wind_speed

logger = get_logger("cli")

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")


@dataclass
class PipelineResult:
    grid: GridResult
    frames: list[TimeFrameData]
    cell_dataframes: dict[datetime, pd.DataFrame]
    summaries: dict[datetime, dict]
    map_paths: dict[datetime, Path] = field(default_factory=dict)
    dashboard_path: Path | None = None
    interpolation_trace: InterpolationTrace | None = None
    warnings: list[str] = field(default_factory=list)


def _resolve_time_axis(ds: xr.Dataset) -> tuple[str, np.ndarray]:
    """データセットの時刻軸の次元名と、有効時刻(UTC, datetime64)配列を返す。"""
    if "valid_time" in ds.coords:
        return "step", ds["valid_time"].values
    if "time" in ds.coords and ds["time"].ndim == 1:
        return ds["time"].dims[0], ds["time"].values
    raise ValueError("時刻座標(valid_time または time)を特定できませんでした")


def _to_jst(dt64: np.datetime64) -> datetime:
    ts = pd.Timestamp(dt64)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(JST).to_pydatetime()


def _to_utc(dt64: np.datetime64) -> datetime:
    ts = pd.Timestamp(dt64)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(UTC).to_pydatetime()


def _select_target_indices(times_utc: np.ndarray, start_jst: str, end_jst: str) -> list[int]:
    start = datetime.fromisoformat(start_jst).replace(tzinfo=JST)
    end = datetime.fromisoformat(end_jst).replace(tzinfo=JST)
    indices = []
    for i, t in enumerate(times_utc):
        jst = _to_jst(t)
        if start <= jst <= end:
            indices.append(i)
    return indices


def run_pipeline(
    config: AppConfig,
    input_path: str | Path,
    write_outputs: bool = True,
    output_dir: Path | None = None,
) -> PipelineResult:
    """GRIB読込から画像・CSV/JSON出力までの一連の計算パイプライン。"""
    input_path = Path(input_path)
    output_dir = output_dir or ensure_outputs_dir()

    reader = get_reader(config.grib)
    fields = tuple(REQUIRED_FIELDS) + tuple(OPTIONAL_FIELDS)
    logger.info("GRIB読込を開始します: backend=%s, input=%s", config.grib.reader_backend, input_path)
    ds = reader.read(input_path, fields=fields)

    time_dim, times_utc = _resolve_time_axis(ds)

    logger.info("現場地点への空間補間を実施します: method=%s", config.grib.interpolation)
    ds_site, interp_trace = interpolate_point(
        ds, config.site.latitude, config.site.longitude, method=config.grib.interpolation
    )

    hourly_precip = hourly_from_accumulated(ds_site["apcp"], time_dim=time_dim)

    grid = build_grid(config.site, config.grid)
    logger.info(
        "グリッドを構築しました: %dx%d=%dセル (実効範囲 %.1fm x %.1fm)",
        grid.nx, grid.ny, grid.total_cells, grid.actual_width_m, grid.actual_height_m,
    )

    target_indices = _select_target_indices(times_utc, config.grib.target_start_jst, config.grib.target_end_jst)
    if not target_indices:
        raise ValueError(
            f"対象期間内の時刻がGRIBデータに見つかりません: "
            f"{config.grib.target_start_jst} 〜 {config.grib.target_end_jst} (JST)"
        )
    logger.info("対象時刻数: %d", len(target_indices))

    frames: list[TimeFrameData] = []
    cell_dataframes: dict[datetime, pd.DataFrame] = {}
    summaries: dict[datetime, dict] = {}
    map_paths: dict[datetime, Path] = {}
    pipeline_warnings: list[str] = list(grid.warnings)

    x_rel = grid.center_x_m - grid.source_x_m
    y_rel = grid.center_y_m - grid.source_y_m

    for idx in target_indices:
        valid_time_utc = _to_utc(times_utc[idx])
        valid_time_jst = _to_jst(times_utc[idx])

        u = float(ds_site["u10"].isel({time_dim: idx}).values)
        v = float(ds_site["v10"].isel({time_dim: idx}).values)
        precip = float(hourly_precip.isel({time_dim: idx}).values)
        if np.isnan(precip):
            precip = 0.0

        tcc_raw = float(ds_site["tcc"].isel({time_dim: idx}).values)
        tcc_pct = tcc_raw * 100.0 if tcc_raw <= 1.0 else tcc_raw

        speed = float(wind_speed(u, v))
        from_deg = float(wind_from_deg(u, v))
        to_deg = float(downwind_to_deg(u, v))
        from_ja, _from_en = wind_direction_label(u, v, calm_threshold=config.model.calm_threshold_mps)
        weather_label = classify_weather(precip, tcc_pct, config.weather_display)

        risk_result = compute_risk(
            x_rel, y_rel, u, v, precip,
            config.construction.intensity, config.construction.watering, config.model,
        )

        frame = TimeFrameData(
            valid_time_utc=valid_time_utc,
            valid_time_jst=valid_time_jst,
            risk_2d=risk_result.risk,
            u10_mps=u,
            v10_mps=v,
            wind_speed_mps=speed,
            wind_from_label_ja=str(from_ja),
            downwind_to_deg=to_deg,
            hourly_precip_mm=precip,
            weather_label=weather_label,
        )
        frames.append(frame)

        cell_df = build_cell_dataframe(
            valid_time_utc, valid_time_jst, grid, u, v, from_deg, to_deg, precip, risk_result, config
        )
        cell_dataframes[valid_time_utc] = cell_df

        summary = build_time_summary(
            input_filename=input_path.name,
            init_time_utc=_to_utc(times_utc[0]),
            valid_time_utc=valid_time_utc,
            valid_time_jst=valid_time_jst,
            config=config,
            grid=grid,
            interpolation_method=interp_trace.method,
            used_fields=list(fields),
            risk_result=risk_result,
            warnings=pipeline_warnings,
        )
        summaries[valid_time_utc] = summary

        if write_outputs:
            write_cell_csv(cell_df, output_dir / "cells", valid_time_utc)
            write_time_json(summary, output_dir / "summary", valid_time_utc)
            map_path = plot_time_map(grid, frame, config, output_dir / "maps" / f"map_{valid_time_utc:%Y%m%dT%H%MZ}.png")
            map_paths[valid_time_utc] = map_path

    dashboard_path = None
    if write_outputs and frames:
        max_risk_per_frame = [float(np.max(f.risk_2d)) for f in frames]
        selected_index = int(np.argmax(max_risk_per_frame))
        dashboard_path = plot_dashboard(
            grid, frames, config, output_dir / "dashboard.png", selected_index=selected_index
        )

    return PipelineResult(
        grid=grid,
        frames=frames,
        cell_dataframes=cell_dataframes,
        summaries=summaries,
        map_paths=map_paths,
        dashboard_path=dashboard_path,
        interpolation_trace=interp_trace,
        warnings=pipeline_warnings,
    )


def cmd_inspect_grib(input_path: str, config_path: str | None) -> None:
    config = load_config(config_path)
    reader = get_reader(config.grib)
    logger.info("GRIB2インベントリを取得します: %s (backend=%s)", input_path, config.grib.reader_backend)
    inventory = reader.inventory(input_path)
    out_path = ensure_outputs_dir() / "grib_inventory.csv"
    inventory.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"レコード数: {len(inventory)}")
    print(f"インベントリ出力先: {out_path}")


def cmd_generate(input_path: str | None, config_path: str | None) -> None:
    config = load_config(config_path)
    resolved_input = Path(input_path) if input_path else (
        Path(config.grib.input_path) if config.grib.input_path else None
    )
    if resolved_input is None:
        raise SystemExit("--input が指定されておらず、config.grib.input_path も未設定です")
    if not resolved_input.exists():
        raise SystemExit(f"入力GRIB2ファイルが見つかりません: {resolved_input}")

    result = run_pipeline(config, resolved_input, write_outputs=True)

    print(f"対象時刻数: {len(result.frames)}")
    print(f"グリッド: {result.grid.nx}x{result.grid.ny}={result.grid.total_cells}セル")
    for f in result.frames:
        max_risk = float(np.max(f.risk_2d))
        print(f"  {f.valid_time_jst:%Y-%m-%d %H:%M} JST  最大リスク={max_risk:.1f}  区分={classify(max_risk, config.thresholds)}")
    if result.dashboard_path:
        print(f"ダッシュボード: {result.dashboard_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dust_forecast.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect-grib", help="GRIB2ファイルのインベントリをCSVへ出力する")
    p_inspect.add_argument("--input", required=True, help="GRIB2ファイルのパス")
    p_inspect.add_argument("--config", default=None, help="設定YAMLのパス(省略時はconfig/sample.yaml)")

    p_generate = sub.add_parser("generate", help="時刻別マップ・ダッシュボード・CSV/JSONを生成する")
    p_generate.add_argument("--input", default=None, help="GRIB2ファイルのパス(省略時はconfigのgrib.input_path)")
    p_generate.add_argument("--config", default=None, help="設定YAMLのパス(省略時はconfig/sample.yaml)")

    return parser


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "inspect-grib":
        cmd_inspect_grib(args.input, args.config)
    elif args.command == "generate":
        cmd_generate(args.input, args.config)
    else:  # pragma: no cover
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
