"""実GRIB2ファイルを用いた統合テスト (仕様書11章 項目11)。

外部ファイル(data/input/*.bin)が無い環境ではスキップする。
"""
from pathlib import Path

import pytest

from dust_forecast.cli import run_pipeline
from dust_forecast.config import load_config
from dust_forecast.grib_reader import get_reader
from dust_forecast.paths import CONFIG_DIR, DATA_INPUT_DIR

pytestmark = pytest.mark.skipif(
    not any(DATA_INPUT_DIR.glob("*.bin")),
    reason="data/input/*.bin が無いため統合テストをスキップします",
)


def _sample_input() -> Path:
    return sorted(DATA_INPUT_DIR.glob("*.bin"))[0]


def test_inspect_grib_reads_real_file():
    config = load_config(CONFIG_DIR / "sample.yaml")
    reader = get_reader(config.grib)
    inventory = reader.inventory(_sample_input())
    assert len(inventory) > 0
    assert {"discipline", "parameterCategory", "parameterNumber"}.issubset(inventory.columns)


def test_run_pipeline_extracts_8_target_hours_09_16_jst(tmp_path):
    """09〜16時JSTの8時刻を抽出できる(仕様書11章 項目11)。"""
    config = load_config(CONFIG_DIR / "sample.yaml")
    result = run_pipeline(config, _sample_input(), write_outputs=False)

    assert len(result.frames) == 8
    hours = sorted(f.valid_time_jst.hour for f in result.frames)
    assert hours == [9, 10, 11, 12, 13, 14, 15, 16]


def test_run_pipeline_cell_count_matches_grid(tmp_path):
    """各時刻の出力セル数が、設定から算出したnx*nyと一致する(仕様書11章 項目12)。"""
    config = load_config(CONFIG_DIR / "sample.yaml")
    result = run_pipeline(config, _sample_input(), write_outputs=False)

    expected = result.grid.nx * result.grid.ny
    assert expected == 100
    for frame in result.frames:
        assert frame.risk_2d.size == expected
    for df in result.cell_dataframes.values():
        assert len(df) == expected


def test_run_pipeline_10m_mesh_config(tmp_path):
    """10m/200m設定でもコード修正なしで動作する(仕様書12章 受入条件)。"""
    config = load_config(CONFIG_DIR / "sample_10m.yaml")
    result = run_pipeline(config, _sample_input(), write_outputs=False)
    assert result.grid.nx * result.grid.ny == 400
