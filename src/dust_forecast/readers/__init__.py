"""GRIB2 Reader Adapter群。

呼出側 (grib_reader.py) は本パッケージが提供する共通インターフェース
(`BaseGribReader`, `read_result` の構造) のみに依存し、実装方式
(cfgrib / wgrib2-netcdf / pygrib) の違いを意識しない。
"""
