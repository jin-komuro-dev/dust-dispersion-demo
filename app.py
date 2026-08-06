"""粉じん飛散リスク テスト版 Streamlit画面 (仕様書 8.3節)。

本ファイルは画面表示のみを担当し、計算ロジックは
`src/dust_forecast/cli.py` の `run_pipeline()` (CLIと共通)を呼び出す。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import streamlit as st

from dust_forecast.categories import CATEGORY_COLORS, classify
from dust_forecast.cli import run_pipeline
from dust_forecast.config import (
    AppConfig,
    ConstructionConfig,
    GribConfig,
    GridConfig,
    SiteConfig,
    load_config,
)
from dust_forecast.paths import CONFIG_DIR, DATA_INPUT_DIR, ensure_outputs_dir
from dust_forecast.weather import DISCLAIMER as WEATHER_DISCLAIMER

st.set_page_config(page_title="粉じん飛散リスク テスト版", layout="wide")


@st.cache_resource
def _load_base_config(config_path: str) -> AppConfig:
    return load_config(config_path)


def _build_config(base: AppConfig, sidebar: dict) -> AppConfig:
    site = SiteConfig(
        name=sidebar["site_name"],
        latitude=sidebar["site_lat"],
        longitude=sidebar["site_lon"],
    )
    grid_kwargs = dict(
        width_m=sidebar["width_m"],
        height_m=sidebar["height_m"],
        cell_size_x_m=sidebar["cell_size_x_m"],
        cell_size_y_m=sidebar["cell_size_y_m"],
        rotation_deg=sidebar["rotation_deg"],
        source_position_mode=sidebar["source_position_mode"],
        edge_policy=sidebar["edge_policy"],
        max_cells=base.grid.max_cells,
    )
    if sidebar["source_position_mode"] == "offset_m":
        grid_kwargs["source_offset_x_m"] = sidebar["source_offset_x_m"]
        grid_kwargs["source_offset_y_m"] = sidebar["source_offset_y_m"]
    elif sidebar["source_position_mode"] == "latlon":
        grid_kwargs["source_latitude"] = sidebar["source_latitude"]
        grid_kwargs["source_longitude"] = sidebar["source_longitude"]
    else:
        grid_kwargs["source_row"] = sidebar["source_row"]
        grid_kwargs["source_col"] = sidebar["source_col"]
    grid = GridConfig(**grid_kwargs)

    construction = ConstructionConfig(
        intensity=sidebar["intensity"],
        work_start_jst=sidebar["work_start_jst"],
        work_end_jst=sidebar["work_end_jst"],
        watering=sidebar["watering"],
    )

    grib = base.grib.model_copy(update={
        "reader_backend": sidebar["reader_backend"],
        "interpolation": sidebar["interpolation"],
    })

    return base.model_copy(update={"site": site, "grid": grid, "construction": construction, "grib": grib})


def _sidebar_inputs(base: AppConfig) -> dict:
    st.sidebar.header("現場・GRIB2設定")

    grib_files = sorted(DATA_INPUT_DIR.glob("*.bin"))
    if grib_files:
        input_path = st.sidebar.selectbox("GRIB2ファイル", grib_files, format_func=lambda p: p.name)
    else:
        st.sidebar.warning(f"{DATA_INPUT_DIR} にGRIB2ファイル(*.bin)が見つかりません")
        input_path = None

    reader_backend = st.sidebar.selectbox("GRIB Reader", ["cfgrib", "wgrib2_netcdf"], index=0)
    interpolation = st.sidebar.selectbox("空間補間方式", ["bilinear", "nearest"], index=0)

    st.sidebar.subheader("現場")
    site_name = st.sidebar.text_input("現場名", value=base.site.name)
    site_lat = st.sidebar.number_input("緯度", value=base.site.latitude, format="%.6f")
    site_lon = st.sidebar.number_input("経度", value=base.site.longitude, format="%.6f")

    st.sidebar.subheader("表示範囲・メッシュ")
    width_m = st.sidebar.number_input("表示範囲 幅 [m]", value=base.grid.width_m, min_value=1.0, step=10.0)
    height_m = st.sidebar.number_input("表示範囲 高さ [m]", value=base.grid.height_m, min_value=1.0, step=10.0)
    cell_size_x_m = st.sidebar.number_input("メッシュサイズ x方向 [m]", value=base.grid.cell_size_x_m, min_value=0.1, step=1.0)
    cell_size_y_m = st.sidebar.number_input("メッシュサイズ y方向 [m]", value=base.grid.cell_size_y_m, min_value=0.1, step=1.0)
    rotation_deg = st.sidebar.number_input("グリッド回転角 [度]", value=base.grid.rotation_deg, step=1.0)
    edge_policy = st.sidebar.selectbox("edge_policy(割り切れない場合)", ["error", "trim", "pad"], index=["error", "trim", "pad"].index(base.grid.edge_policy))

    st.sidebar.subheader("作業現場位置")
    source_position_mode = st.sidebar.selectbox("指定方式", ["offset_m", "latlon", "rowcol"], index=["offset_m", "latlon", "rowcol"].index(base.grid.source_position_mode))
    source_offset_x_m = source_offset_y_m = source_latitude = source_longitude = None
    source_row = source_col = None
    if source_position_mode == "offset_m":
        source_offset_x_m = st.sidebar.number_input("中心からのオフセット x(東+) [m]", value=base.grid.source_offset_x_m or 0.0)
        source_offset_y_m = st.sidebar.number_input("中心からのオフセット y(北+) [m]", value=base.grid.source_offset_y_m or 0.0)
    elif source_position_mode == "latlon":
        source_latitude = st.sidebar.number_input("作業現場 緯度", value=base.grid.source_latitude or base.site.latitude, format="%.6f")
        source_longitude = st.sidebar.number_input("作業現場 経度", value=base.grid.source_longitude or base.site.longitude, format="%.6f")
    else:
        source_row = st.sidebar.number_input("作業現場 行番号(row)", value=base.grid.source_row or 0, min_value=0, step=1)
        source_col = st.sidebar.number_input("作業現場 列番号(col)", value=base.grid.source_col or 0, min_value=0, step=1)

    st.sidebar.subheader("工事条件")
    intensity = st.sidebar.selectbox("工事強度", ["small", "medium", "large"], index=["small", "medium", "large"].index(base.construction.intensity))
    work_start_jst = st.sidebar.text_input("稼働開始(JST, HH:MM)", value=base.construction.work_start_jst)
    work_end_jst = st.sidebar.text_input("稼働終了(JST, HH:MM)", value=base.construction.work_end_jst)
    watering = st.sidebar.selectbox("散水レベル", ["none", "normal", "strong"], index=["none", "normal", "strong"].index(base.construction.watering))

    return dict(
        input_path=input_path, reader_backend=reader_backend, interpolation=interpolation,
        site_name=site_name, site_lat=site_lat, site_lon=site_lon,
        width_m=width_m, height_m=height_m, cell_size_x_m=cell_size_x_m, cell_size_y_m=cell_size_y_m,
        rotation_deg=rotation_deg, edge_policy=edge_policy,
        source_position_mode=source_position_mode,
        source_offset_x_m=source_offset_x_m, source_offset_y_m=source_offset_y_m,
        source_latitude=source_latitude, source_longitude=source_longitude,
        source_row=source_row, source_col=source_col,
        intensity=intensity, work_start_jst=work_start_jst, work_end_jst=work_end_jst, watering=watering,
    )


def main() -> None:
    st.title("粉じん飛散リスク テスト版(GSM GPV, 相対リスクモデル)")
    st.warning(
        "本モデルは相対飛散リスク(0-100)のテスト版試算であり、粉じん濃度[μg/m³]を厳密に予測するものではありません。"
        "法令・環境基準の判定には使用しないでください。"
    )

    config_files = sorted(CONFIG_DIR.glob("*.yaml"))
    config_choice = st.sidebar.selectbox("設定ファイル(初期値)", config_files, format_func=lambda p: p.name)
    base_config = _load_base_config(str(config_choice))

    sidebar = _sidebar_inputs(base_config)
    if sidebar["input_path"] is None:
        st.stop()

    config = _build_config(base_config, sidebar)

    if st.sidebar.button("計算実行", type="primary"):
        with st.spinner("GRIB読込・計算を実行しています..."):
            try:
                result = run_pipeline(config, sidebar["input_path"], write_outputs=True, output_dir=ensure_outputs_dir("streamlit"))
            except Exception as exc:  # noqa: BLE001
                st.error(f"計算に失敗しました: {exc}")
                st.stop()
        st.session_state["result"] = result
        st.session_state["config"] = config

    if "result" not in st.session_state:
        st.info("左のサイドバーで条件を設定し、「計算実行」を押してください。")
        st.stop()

    result = st.session_state["result"]
    config = st.session_state["config"]
    frames = result.frames

    st.subheader("対象時刻")
    labels = [f.valid_time_jst.strftime("%Y-%m-%d %H:%M JST") for f in frames]
    selected_label = st.select_slider("表示時刻", options=labels, value=labels[-1])
    selected_index = labels.index(selected_label)
    frame = frames[selected_index]
    valid_time_utc = frame.valid_time_utc

    col_map, col_info = st.columns([1.3, 1.0])

    with col_map:
        st.markdown("### マップ表示")
        map_path = result.map_paths.get(valid_time_utc)
        if map_path and map_path.exists():
            st.image(str(map_path), use_container_width=True)

    with col_info:
        st.markdown("### 入力気象値(現場地点補間値)")
        st.table({
            "項目": ["U風", "V風", "風速", "風向", "飛散注意方向", "時間降水量", "天気(簡易判定)"],
            "値": [
                f"{frame.u10_mps:.2f} m/s", f"{frame.v10_mps:.2f} m/s", f"{frame.wind_speed_mps:.2f} m/s",
                frame.wind_from_label_ja, f"{frame.downwind_to_deg:.0f} 度",
                f"{frame.hourly_precip_mm:.2f} mm/h", frame.weather_label,
            ],
        })
        st.caption(WEATHER_DISCLAIMER)

        st.markdown("### 時刻別一覧")
        table_rows = []
        for f in frames:
            max_risk = float(np.max(f.risk_2d))
            table_rows.append({
                "時刻(JST)": f.valid_time_jst.strftime("%H:%M"),
                "風向": f.wind_from_label_ja,
                "風速[m/s]": round(f.wind_speed_mps, 1),
                "降水[mm/h]": round(f.hourly_precip_mm, 1),
                "最大リスク": round(max_risk, 1),
                "区分": classify(max_risk, config.thresholds),
            })
        st.dataframe(table_rows, hide_index=True, use_container_width=True)

    st.markdown("### 選択セルの中間計算値")
    cell_df = result.cell_dataframes[valid_time_utc]
    c1, c2 = st.columns(2)
    row_sel = c1.number_input("行(row)", min_value=0, max_value=result.grid.ny - 1, value=0, step=1)
    col_sel = c2.number_input("列(column)", min_value=0, max_value=result.grid.nx - 1, value=0, step=1)
    cell_row = cell_df[(cell_df["row"] == row_sel) & (cell_df["column"] == col_sel)]
    st.dataframe(cell_row.T.rename(columns={cell_row.index[0]: "値"}) if not cell_row.empty else cell_row, use_container_width=True)

    st.markdown("### 計算式・係数")
    with st.expander("相対飛散リスクモデルの係数(config.model)"):
        st.json(config.model.model_dump())
    with st.expander("色分けしきい値(config.thresholds)"):
        st.json(config.thresholds.model_dump())
    st.caption("計算式の詳細は docs/model_spec.md を参照してください。")

    st.markdown("### ダウンロード")
    dl1, dl2, dl3, dl4 = st.columns(4)
    dl1.download_button(
        "セルCSV", data=cell_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"cells_{valid_time_utc:%Y%m%dT%H%MZ}.csv", mime="text/csv",
    )
    summary = result.summaries[valid_time_utc]
    dl2.download_button(
        "時刻サマリJSON", data=json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"summary_{valid_time_utc:%Y%m%dT%H%MZ}.json", mime="application/json",
    )
    if map_path and map_path.exists():
        dl3.download_button(
            "マップPNG", data=map_path.read_bytes(),
            file_name=map_path.name, mime="image/png",
        )
    if result.dashboard_path and result.dashboard_path.exists():
        dl4.download_button(
            "ダッシュボードPNG", data=result.dashboard_path.read_bytes(),
            file_name=result.dashboard_path.name, mime="image/png",
        )

    st.divider()
    st.caption(
        "気象データ出典: 気象庁 GSM GPV | 相対飛散リスクの試算値(テスト版) — 濃度予測ではありません | "
        "GSMの気象格子(約10km)はローカルメッシュより粗いため、現場地点の風をメッシュ全体に一様に適用しています。"
    )


if __name__ == "__main__":
    main()
