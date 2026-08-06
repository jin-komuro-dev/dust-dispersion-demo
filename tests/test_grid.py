import pytest

from dust_forecast.config import GridConfig, SiteConfig
from dust_forecast.grid import GridConfigError, build_grid

SITE = SiteConfig(name="テスト現場", latitude=35.6812, longitude=139.7671)


def _grid_config(**overrides):
    base = dict(
        width_m=200.0,
        height_m=200.0,
        cell_size_x_m=20.0,
        cell_size_y_m=20.0,
        rotation_deg=0.0,
        source_position_mode="offset_m",
        source_offset_x_m=-20.0,
        source_offset_y_m=-40.0,
        edge_policy="error",
        max_cells=10000,
    )
    base.update(overrides)
    return GridConfig(**base)


def test_200m_20m_gives_10x10():
    """200m x 200m, 20mセル -> 10x10=100セル(仕様書11章 項目13)。"""
    grid = build_grid(SITE, _grid_config(cell_size_x_m=20.0, cell_size_y_m=20.0))
    assert (grid.nx, grid.ny) == (10, 10)
    assert grid.total_cells == 100


def test_200m_10m_gives_20x20():
    """200m x 200m, 10mセル -> 20x20=400セル(仕様書11章 項目13)。"""
    grid = build_grid(SITE, _grid_config(cell_size_x_m=10.0, cell_size_y_m=10.0))
    assert (grid.nx, grid.ny) == (20, 20)
    assert grid.total_cells == 400


def test_500x300_25m_gives_20x12():
    """500m x 300m, 25mセル -> 20x12=240セル(仕様書11章 項目13)。"""
    grid = build_grid(SITE, _grid_config(width_m=500.0, height_m=300.0, cell_size_x_m=25.0, cell_size_y_m=25.0))
    assert (grid.nx, grid.ny) == (20, 12)
    assert grid.total_cells == 240


def test_cell_count_matches_nx_times_ny():
    """出力セル数が設定から算出したnx*nyと一致する(仕様書11章 項目12)。"""
    grid = build_grid(SITE, _grid_config())
    assert grid.center_x_m.size == grid.nx * grid.ny
    assert grid.row_index.shape == (grid.ny, grid.nx)


def test_edge_policy_error_raises_on_indivisible():
    with pytest.raises(GridConfigError):
        build_grid(SITE, _grid_config(width_m=205.0, cell_size_x_m=20.0, edge_policy="error"))


def test_edge_policy_trim_shrinks_to_inside():
    grid = build_grid(SITE, _grid_config(width_m=205.0, cell_size_x_m=20.0, edge_policy="trim"))
    assert grid.nx == 10
    assert grid.actual_width_m == pytest.approx(200.0)
    assert grid.actual_width_m <= 205.0


def test_edge_policy_pad_expands_to_outside():
    grid = build_grid(SITE, _grid_config(width_m=205.0, cell_size_x_m=20.0, edge_policy="pad"))
    assert grid.nx == 11
    assert grid.actual_width_m == pytest.approx(220.0)
    assert grid.actual_width_m >= 205.0


def test_max_cells_exceeded_raises():
    with pytest.raises(GridConfigError):
        build_grid(SITE, _grid_config(width_m=1000.0, height_m=1000.0, cell_size_x_m=1.0, cell_size_y_m=1.0, max_cells=100))


def test_source_offset_mode_position():
    grid = build_grid(SITE, _grid_config(source_offset_x_m=-20.0, source_offset_y_m=-40.0))
    assert grid.source_x_m == pytest.approx(-20.0)
    assert grid.source_y_m == pytest.approx(-40.0)


def test_source_rowcol_mode_position():
    cfg = GridConfig(
        width_m=200.0, height_m=200.0, cell_size_x_m=20.0, cell_size_y_m=20.0,
        rotation_deg=0.0, source_position_mode="rowcol", source_row=0, source_col=0,
        edge_policy="error", max_cells=10000,
    )
    grid = build_grid(SITE, cfg)
    # row=0,col=0 は北西端セルの中心
    assert grid.source_x_m == pytest.approx(-90.0)
    assert grid.source_y_m == pytest.approx(90.0)


def test_source_rowcol_out_of_range_raises():
    cfg = GridConfig(**{
        **_grid_config().model_dump(exclude={"source_offset_x_m", "source_offset_y_m"}),
        "source_position_mode": "rowcol",
        "source_row": 99,
        "source_col": 0,
    })
    with pytest.raises(GridConfigError):
        build_grid(SITE, cfg)


def test_north_is_up_east_is_right():
    """北が上、東が右になるようセル中心座標が並んでいることを確認する。"""
    grid = build_grid(SITE, _grid_config())
    # row=0(北端)のy座標が row=ny-1(南端)のy座標より大きい
    assert grid.center_y_m[0, 0] > grid.center_y_m[-1, 0]
    # col=0(西端)のx座標が col=nx-1(東端)のx座標より小さい
    assert grid.center_x_m[0, 0] < grid.center_x_m[0, -1]
