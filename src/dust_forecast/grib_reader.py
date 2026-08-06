"""GRIB Reader Adapterの選択(ファクトリ)。

呼出側(cli.py, app.py)はこのモジュールが返す `BaseGribReader` の
インターフェースのみに依存し、具象クラス(cfgrib/wgrib2/pygrib)を
直接importしない。これにより `config.grib.reader_backend` を変更するだけで
実装方式を切り替えられる。
"""
from __future__ import annotations

from dust_forecast.config import GribConfig
from dust_forecast.readers.base import BaseGribReader, GribReaderError


def get_reader(grib_config: GribConfig) -> BaseGribReader:
    """設定に従ってGRIB Readerを生成する。"""
    backend = grib_config.reader_backend

    if backend == "cfgrib":
        from dust_forecast.readers.cfgrib_reader import CfgribReader

        return CfgribReader()

    if backend == "wgrib2_netcdf":
        from dust_forecast.readers.wgrib2_netcdf import Wgrib2NetcdfReader

        return Wgrib2NetcdfReader(wgrib2_exe=grib_config.wgrib2_exe)

    if backend == "pygrib":
        from dust_forecast.readers.pygrib_reader import PygribReader

        return PygribReader()

    raise GribReaderError(f"未知のreader_backendです: {backend}")
