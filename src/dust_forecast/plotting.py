"""Matplotlibによる時刻別リスクマップ・総合ダッシュボード画像 (仕様書 8章)。

実際のGRIB値と計算結果から決定的に再生成できる出力とする(AI画像生成は使わない)。
背景はオフラインで動く簡易平面図(現場ローカル座標: 東=右, 北=上)とする。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

# 既定のDejaVu SansはCJKグリフを含まないため、日本語表示可能なフォントを
# 優先的に使用する(Windows環境に同梱されているフォントを想定)。
plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from dust_forecast.categories import CATEGORY_COLORS, CATEGORY_LABELS  # noqa: E402
from dust_forecast.config import AppConfig, ThresholdsConfig  # noqa: E402
from dust_forecast.grid import GridResult, _rotate_cw  # noqa: E402

FOOTER_SOURCE = "気象データ出典：気象庁 GSM GPV"
FOOTER_NOTE = "相対飛散リスクの試算値(テスト版) — 濃度予測ではありません"

_CMAP = ListedColormap([CATEGORY_COLORS[label] for label in CATEGORY_LABELS])


@dataclass
class TimeFrameData:
    """1時刻分の描画に必要な情報をまとめたもの。"""

    valid_time_utc: datetime
    valid_time_jst: datetime
    risk_2d: np.ndarray  # shape (ny, nx)
    u10_mps: float
    v10_mps: float
    wind_speed_mps: float
    wind_from_label_ja: str
    downwind_to_deg: float
    hourly_precip_mm: float
    weather_label: str


def _boundary_norm(thresholds: ThresholdsConfig) -> BoundaryNorm:
    boundaries = [0.0, thresholds.low_max, thresholds.moderate_max, thresholds.high_max, 100.0]
    return BoundaryNorm(boundaries, ncolors=4)


def _cell_edges_local(grid: GridResult) -> tuple[np.ndarray, np.ndarray]:
    x_edges = np.linspace(-grid.actual_width_m / 2, grid.actual_width_m / 2, grid.nx + 1)
    y_edges = np.linspace(grid.actual_height_m / 2, -grid.actual_height_m / 2, grid.ny + 1)
    return np.meshgrid(x_edges, y_edges)


def _draw_risk_map(ax, grid: GridResult, risk_2d: np.ndarray, thresholds: ThresholdsConfig, downwind_to_deg: float):
    x_local, y_local = _cell_edges_local(grid)
    east, north = _rotate_cw(x_local, y_local, grid.rotation_deg)

    ax.pcolormesh(
        east, north, risk_2d, cmap=_CMAP, norm=_boundary_norm(thresholds), edgecolors="white", linewidth=0.2
    )
    ax.plot(
        grid.source_x_m, grid.source_y_m, marker="X", color="black", markersize=11,
        markeredgecolor="white", markeredgewidth=1.2, linestyle="none", zorder=5,
    )
    ax.annotate(
        "作業現場", (grid.source_x_m, grid.source_y_m), textcoords="offset points",
        xytext=(8, 8), fontsize=8, weight="bold",
    )

    half_w, half_h = grid.actual_width_m / 2, grid.actual_height_m / 2
    margin = max(half_w, half_h) * 0.18
    ax.set_xlim(-half_w - margin, half_w + margin)
    ax.set_ylim(-half_h - margin, half_h + margin)
    ax.set_aspect("equal")
    ax.set_xlabel("東方向 [m]")
    ax.set_ylabel("北方向 [m]")

    # 風下矢印(飛散注意方向): 左上に固定表示
    theta = np.radians(downwind_to_deg)
    arrow_len = max(half_w, half_h) * 0.22
    ax_x0, ax_y0 = -half_w * 0.72, half_h * 0.78
    ax.annotate(
        "",
        xy=(ax_x0 + arrow_len * np.sin(theta), ax_y0 + arrow_len * np.cos(theta)),
        xytext=(ax_x0, ax_y0),
        arrowprops=dict(facecolor="dimgray", edgecolor="dimgray", width=2.5, headwidth=9, headlength=9),
    )
    ax.annotate("飛散注意方向", (ax_x0, ax_y0), textcoords="offset points", xytext=(6, -14), fontsize=7.5)

    # 北矢印(凡例と重ならないよう左上に配置)
    ax.annotate(
        "N", xy=(-half_w - margin * 0.15, half_h + margin * 0.35), fontsize=10, weight="bold", ha="center",
    )
    ax.annotate(
        "", xy=(-half_w - margin * 0.15, half_h + margin * 0.55), xytext=(-half_w - margin * 0.15, half_h + margin * 0.05),
        arrowprops=dict(facecolor="black", edgecolor="black", width=1.5, headwidth=6, headlength=6),
    )

    # スケールバー
    nice_lengths = np.array([1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000])
    target = grid.actual_width_m / 4
    scale_len = float(nice_lengths[np.argmin(np.abs(nice_lengths - target))])
    bar_x0 = -half_w * 0.85
    bar_y = -half_h - margin * 0.6
    ax.plot([bar_x0, bar_x0 + scale_len], [bar_y, bar_y], color="black", linewidth=2, clip_on=False)
    ax.annotate(f"{scale_len:g} m", ((bar_x0 + bar_x0 + scale_len) / 2, bar_y), textcoords="offset points",
                xytext=(0, 4), fontsize=7.5, ha="center")


def _legend_handles():
    from matplotlib.patches import Patch

    return [Patch(facecolor=CATEGORY_COLORS[label], edgecolor="white", label=label) for label in CATEGORY_LABELS]


def plot_time_map(
    grid: GridResult,
    frame: TimeFrameData,
    config: AppConfig,
    output_path: Path,
) -> Path:
    """時刻ごとの飛散リスクマップPNGを1枚出力する(仕様書8.1節)。"""
    fig, ax = plt.subplots(figsize=(7.2, 7.6), dpi=150)

    _draw_risk_map(ax, grid, frame.risk_2d, config.thresholds, frame.downwind_to_deg)

    title = (
        f"{config.site.name} 粉じん飛散リスク(相対値, テスト版)\n"
        f"初期時刻 2023-03-14 12:00 UTC(21:00 JST) / 予報時刻 "
        f"{frame.valid_time_utc:%Y-%m-%d %H:%M} UTC ({frame.valid_time_jst:%Y-%m-%d %H:%M} JST)"
    )
    ax.set_title(title, fontsize=10)

    ax.legend(handles=_legend_handles(), loc="upper right", fontsize=8, title="飛散リスク区分", framealpha=0.9)

    info_lines = [
        f"風向: {frame.wind_from_label_ja} / 風速: {frame.wind_speed_mps:.1f} m/s "
        f"(U={frame.u10_mps:.1f}, V={frame.v10_mps:.1f} m/s)",
        f"時間降水量: {frame.hourly_precip_mm:.1f} mm/h / 天気(簡易判定): {frame.weather_label}",
        f"工事強度: {config.construction.intensity} / 散水: {config.construction.watering} "
        f"/ 稼働時間: {config.construction.work_start_jst}-{config.construction.work_end_jst} JST",
    ]
    fig.text(0.02, 0.055, "\n".join(info_lines), fontsize=7.5, va="bottom")
    fig.text(0.02, 0.015, f"{FOOTER_SOURCE}  |  {FOOTER_NOTE}", fontsize=7, color="dimgray")

    fig.tight_layout(rect=(0, 0.10, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def plot_dashboard(
    grid: GridResult,
    frames: list[TimeFrameData],
    config: AppConfig,
    output_path: Path,
    selected_index: int = 0,
) -> Path:
    """総合ダッシュボードPNG(選択時刻マップ+時刻別一覧表)を1枚出力する(仕様書8.2節)。"""
    from dust_forecast.categories import classify

    fig = plt.figure(figsize=(11, 7.2), dpi=150)
    gs = fig.add_gridspec(1, 2, width_ratios=(1.1, 1.0), wspace=0.28, top=0.80, bottom=0.10, left=0.06, right=0.97)

    ax_map = fig.add_subplot(gs[0, 0])
    frame = frames[selected_index]
    _draw_risk_map(ax_map, grid, frame.risk_2d, config.thresholds, frame.downwind_to_deg)
    ax_map.set_title(
        f"{frame.valid_time_jst:%H:%M} JST 時点の飛散リスクマップ", fontsize=10
    )
    ax_map.legend(handles=_legend_handles(), loc="upper right", fontsize=7.5, framealpha=0.9)

    ax_table = fig.add_subplot(gs[0, 1])
    ax_table.axis("off")

    rows = []
    for f in frames:
        max_risk = float(np.max(f.risk_2d))
        rows.append([
            f"{f.valid_time_jst:%H:%M}",
            f"{f.wind_from_label_ja}",
            f"{f.wind_speed_mps:.1f}",
            f"{f.hourly_precip_mm:.1f}",
            f"{max_risk:.0f}",
            classify(max_risk, config.thresholds),
        ])
    col_labels = ["時刻(JST)", "風向", "風速[m/s]", "降水[mm/h]", "最大リスク", "区分"]
    table = ax_table.table(cellText=rows, colLabels=col_labels, loc="upper center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.5)

    fig.suptitle(
        f"{config.site.name} 粉じん飛散リスク 総合ダッシュボード(相対値, テスト版)\n"
        f"初期時刻 2023-03-14 12:00 UTC(21:00 JST) 予報時刻 2023-03-15 09:00〜16:00 JST",
        fontsize=12,
    )

    condition_text = (
        f"【現場】{config.site.name}  緯度{config.site.latitude:.4f} 経度{config.site.longitude:.4f}\n"
        f"【グリッド】{grid.actual_width_m:g}m x {grid.actual_height_m:g}m, "
        f"セル{grid.cell_size_x_m:g}m x {grid.cell_size_y_m:g}m, {grid.nx}x{grid.ny}={grid.total_cells}セル\n"
        f"【工事】強度:{config.construction.intensity} 散水:{config.construction.watering} "
        f"稼働:{config.construction.work_start_jst}-{config.construction.work_end_jst} JST\n\n"
        "【モデルの注意書き】\n"
        "本図は物理濃度[μg/m^3]を厳密に予測する\n"
        "ものではなく、気象・工事条件から算出した\n"
        "説明可能な相対飛散リスク(0-100)の\n"
        "テスト版試算値です。建物風の回り込み・\n"
        "乱流は未考慮です。GSMの気象格子(約10km)は\n"
        "ローカルメッシュより粗いため、現場地点の風を\n"
        "ローカルメッシュ全体に一様に適用しています。"
    )
    fig.text(0.60, 0.46, condition_text, fontsize=8.2, va="top", ha="left")
    fig.text(0.02, 0.01, f"{FOOTER_SOURCE}  |  {FOOTER_NOTE}", fontsize=8, color="dimgray")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return output_path
