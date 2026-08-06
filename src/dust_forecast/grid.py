"""可変ローカルメッシュ生成 (仕様書 4.1節)。

`nx = width_m / cell_size_x_m`、`ny = height_m / cell_size_y_m` を実行時に
算出し、正方形範囲・正方形セル・特定の間隔をコードへ埋め込まない。

ローカル座標系は現場中心(site緯度経度)を原点とする東向きx・北向きyの
平面直角座標(pyprojの方位等距離図法, AEQD)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pyproj

from dust_forecast.config import GridConfig, SiteConfig
from dust_forecast.logging_config import get_logger

logger = get_logger("grid")


class GridConfigError(Exception):
    """グリッド設定に関する独自例外。"""


@dataclass
class GridResult:
    nx: int
    ny: int
    actual_width_m: float
    actual_height_m: float
    cell_size_x_m: float
    cell_size_y_m: float
    rotation_deg: float
    site_latitude: float
    site_longitude: float
    source_x_m: float
    source_y_m: float
    source_latitude: float
    source_longitude: float
    row_index: np.ndarray  # shape (ny, nx)
    col_index: np.ndarray  # shape (ny, nx)
    center_x_m: np.ndarray  # 東向き正 [m], shape (ny, nx)
    center_y_m: np.ndarray  # 北向き正 [m], shape (ny, nx)
    center_latitude: np.ndarray
    center_longitude: np.ndarray
    edge_policy_applied: str
    warnings: list[str] = field(default_factory=list)

    @property
    def total_cells(self) -> int:
        return self.nx * self.ny


def _resolve_cell_count(
    extent_m: float, cell_size_m: float, edge_policy: str, axis_label: str
) -> tuple[int, float, str]:
    raw = extent_m / cell_size_m
    n_exact = round(raw)
    if abs(raw - n_exact) < 1e-9:
        return int(n_exact), float(extent_m), "exact"

    if edge_policy == "error":
        raise GridConfigError(
            f"{axis_label}の範囲({extent_m}m)がセル間隔({cell_size_m}m)で割り切れません。"
            "edge_policy を trim または pad にするか、値を調整してください。"
        )
    if edge_policy == "trim":
        n = max(int(np.floor(raw)), 1)
        return n, n * cell_size_m, "trim"
    if edge_policy == "pad":
        n = int(np.ceil(raw))
        return n, n * cell_size_m, "pad"
    raise GridConfigError(f"未知のedge_policyです: {edge_policy}")


def _rotate_cw(x: np.ndarray | float, y: np.ndarray | float, rotation_deg: float):
    """グリッドのローカル軸を時計回りに rotation_deg 回転し、東向きx・北向きyへ変換する。"""
    theta = np.radians(rotation_deg)
    east = x * np.cos(theta) + y * np.sin(theta)
    north = -x * np.sin(theta) + y * np.cos(theta)
    return east, north


def _resolve_source_position(
    grid: GridConfig,
    actual_width_m: float,
    actual_height_m: float,
    nx: int,
    ny: int,
    projector: pyproj.Proj,
) -> tuple[float, float, float, float]:
    """作業現場(発生源)の位置を東向きx・北向きy[m]と緯度経度で返す。"""
    mode = grid.source_position_mode
    if mode == "offset_m":
        x, y = grid.source_offset_x_m, grid.source_offset_y_m
    elif mode == "latlon":
        x, y = projector(grid.source_longitude, grid.source_latitude)
    elif mode == "rowcol":
        if not (0 <= grid.source_row < ny and 0 <= grid.source_col < nx):
            raise GridConfigError(
                f"source_row/source_col がグリッド範囲外です: "
                f"row={grid.source_row}, col={grid.source_col}, ny={ny}, nx={nx}"
            )
        x_local = -actual_width_m / 2 + (grid.source_col + 0.5) * grid.cell_size_x_m
        y_local = actual_height_m / 2 - (grid.source_row + 0.5) * grid.cell_size_y_m
        x, y = _rotate_cw(x_local, y_local, grid.rotation_deg)
    else:
        raise GridConfigError(f"未知のsource_position_modeです: {mode}")

    lon, lat = projector(x, y, inverse=True)
    return float(x), float(y), float(lat), float(lon)


def build_grid(site: SiteConfig, grid: GridConfig) -> GridResult:
    """設定からローカルメッシュを構築する。"""
    nx, actual_width, w_policy = _resolve_cell_count(grid.width_m, grid.cell_size_x_m, grid.edge_policy, "幅(width_m)")
    ny, actual_height, h_policy = _resolve_cell_count(grid.height_m, grid.cell_size_y_m, grid.edge_policy, "高さ(height_m)")

    warnings_list: list[str] = []
    if w_policy != "exact":
        msg = f"width_mがcell_size_x_mで割り切れないためedge_policy={w_policy}を適用しました(実効幅={actual_width}m)"
        logger.warning(msg)
        warnings_list.append(msg)
    if h_policy != "exact":
        msg = f"height_mがcell_size_y_mで割り切れないためedge_policy={h_policy}を適用しました(実効高さ={actual_height}m)"
        logger.warning(msg)
        warnings_list.append(msg)

    total_cells = nx * ny
    if total_cells > grid.max_cells:
        raise GridConfigError(
            f"総セル数({total_cells} = {nx}x{ny})がmax_cells({grid.max_cells})を超えています。"
        )

    projector = pyproj.Proj(proj="aeqd", lat_0=site.latitude, lon_0=site.longitude, datum="WGS84", units="m")

    col_idx, row_idx = np.meshgrid(np.arange(nx), np.arange(ny))
    x_local = -actual_width / 2 + (col_idx + 0.5) * grid.cell_size_x_m
    y_local = actual_height / 2 - (row_idx + 0.5) * grid.cell_size_y_m
    east, north = _rotate_cw(x_local, y_local, grid.rotation_deg)
    lon, lat = projector(east, north, inverse=True)

    source_x, source_y, source_lat, source_lon = _resolve_source_position(
        grid, actual_width, actual_height, nx, ny, projector
    )

    return GridResult(
        nx=nx,
        ny=ny,
        actual_width_m=actual_width,
        actual_height_m=actual_height,
        cell_size_x_m=grid.cell_size_x_m,
        cell_size_y_m=grid.cell_size_y_m,
        rotation_deg=grid.rotation_deg,
        site_latitude=site.latitude,
        site_longitude=site.longitude,
        source_x_m=source_x,
        source_y_m=source_y,
        source_latitude=source_lat,
        source_longitude=source_lon,
        row_index=row_idx,
        col_index=col_idx,
        center_x_m=east,
        center_y_m=north,
        center_latitude=lat,
        center_longitude=lon,
        edge_policy_applied=grid.edge_policy,
        warnings=warnings_list,
    )
