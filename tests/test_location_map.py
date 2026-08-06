from matplotlib.figure import Figure

from dust_forecast.location_map import plot_location_overview


def test_plot_location_overview_returns_figure_for_typical_site():
    fig = plot_location_overview(35.6812, 139.7671, label="テスト工事現場A")
    assert isinstance(fig, Figure)


def test_plot_location_overview_handles_out_of_range_coordinates():
    """日本列島の概略範囲外の座標でも例外を送出しないこと。"""
    fig = plot_location_overview(0.0, 0.0, label="範囲外テスト")
    assert isinstance(fig, Figure)


def test_plot_location_overview_hokkaido_and_kyushu():
    fig_north = plot_location_overview(43.0, 141.3, label="札幌付近")
    fig_south = plot_location_overview(31.6, 130.5, label="鹿児島付近")
    assert isinstance(fig_north, Figure)
    assert isinstance(fig_south, Figure)


def test_module_has_no_grib_or_ui_imports():
    """location_map.pyがGRIB読込やStreamlit UIに依存しない独立モジュールであること。"""
    import ast
    import inspect

    import dust_forecast.location_map as module

    tree = ast.parse(inspect.getsource(module))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    forbidden = {"xarray", "cfgrib", "eccodes", "pygrib", "streamlit"}
    assert not (imported_roots & forbidden)
