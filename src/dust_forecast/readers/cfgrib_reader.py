"""cfgrib(ecCodes)を用いたGRIB2 Reader。標準採用Reader。

Phase 0での実ファイル比較の結果、以下の理由で標準Readerとして採用した
(詳細は docs/provenance.md, docs/architecture.md を参照)。

- 外部実行ファイル(wgrib2.exe)への依存が無く、pip一発で導入できる
- サブプロセス呼び出しや一時ファイルが不要で、日本語パス問題を回避できる
- xarrayへ直接ロードでき、`wgrib2 -netcdf` 経由より高速

ただし、気象庁GSMの積算降水量(APCP)・全雲量(TCDC)は、ecCodesの既定
パラメータテーブルに shortName の対応が無く "unknown" としてデコード
される。このため name/shortName に頼らず、`discipline` /
`parameterCategory` / `parameterNumber` を用いた `filter_by_keys` で
要素を特定する。
"""
from __future__ import annotations

from pathlib import Path

import eccodes
import pandas as pd
import xarray as xr

from dust_forecast.logging_config import get_logger
from dust_forecast.readers.base import (
    INVENTORY_COLUMNS,
    STANDARD_FIELDS,
    BaseGribReader,
    FieldSpec,
    GribFieldNotFoundError,
    GribReaderError,
)

logger = get_logger("readers.cfgrib")


class CfgribReader(BaseGribReader):
    backend_name = "cfgrib"

    def read(
        self,
        input_path: str | Path,
        fields: tuple[str, ...] = tuple(STANDARD_FIELDS.keys()),
    ) -> xr.Dataset:
        import cfgrib  # 遅延importでcfgrib未導入環境でも他backendを使えるようにする

        input_path = Path(input_path)
        if not input_path.exists():
            raise GribReaderError(f"GRIB2ファイルが見つかりません: {input_path}")

        data_arrays: dict[str, xr.DataArray] = {}
        for name in fields:
            if name not in STANDARD_FIELDS:
                raise GribReaderError(f"未知の要素名です: {name}")
            spec = STANDARD_FIELDS[name]
            try:
                ds = cfgrib.open_dataset(
                    str(input_path),
                    filter_by_keys=spec.filter_by_keys(),
                    backend_kwargs={"indexpath": ""},
                )
            except Exception as exc:  # cfgrib/eccodesの例外を独自例外へ変換
                raise GribReaderError(
                    f"cfgribでの読込に失敗しました (field={name}): {exc}"
                ) from exc

            data_vars = list(ds.data_vars)
            if not data_vars:
                raise GribFieldNotFoundError(
                    f"要素 {name} ({spec.description}) がファイル内に見つかりません"
                )
            if len(data_vars) > 1:
                logger.warning(
                    "field=%s で複数の変数が一致しました: %s (先頭を使用)",
                    name,
                    data_vars,
                )
            da = ds[data_vars[0]].rename(name)
            da.attrs["dust_forecast_field_description"] = spec.description
            data_arrays[name] = da

        merged = xr.merge(data_arrays.values(), join="outer", compat="override")
        merged.attrs["source_file"] = input_path.name
        merged.attrs["reader_backend"] = self.backend_name
        return merged

    def inventory(self, input_path: str | Path) -> pd.DataFrame:
        input_path = Path(input_path)
        if not input_path.exists():
            raise GribReaderError(f"GRIB2ファイルが見つかりません: {input_path}")

        eccodes.codes_grib_multi_support_on()
        rows: list[dict] = []
        try:
            with open(input_path, "rb") as f:
                record_index = 0
                while True:
                    gid = eccodes.codes_grib_new_from_file(f)
                    if gid is None:
                        break
                    record_index += 1
                    try:
                        rows.append(_inventory_row(gid, record_index))
                    finally:
                        eccodes.codes_release(gid)
        except OSError as exc:
            raise GribReaderError(f"GRIB2ファイルの読込に失敗しました: {exc}") from exc
        finally:
            eccodes.codes_grib_multi_support_off()

        return pd.DataFrame(rows, columns=INVENTORY_COLUMNS)


def _safe_get(gid: int, key: str, default=None):
    try:
        return eccodes.codes_get(gid, key)
    except Exception:
        return default


def _inventory_row(gid: int, record_index: int) -> dict:
    return {
        "record_index": record_index,
        "name": _safe_get(gid, "name"),
        "shortName": _safe_get(gid, "shortName"),
        "discipline": _safe_get(gid, "discipline"),
        "parameterCategory": _safe_get(gid, "parameterCategory"),
        "parameterNumber": _safe_get(gid, "parameterNumber"),
        "typeOfLevel": _safe_get(gid, "typeOfLevel"),
        "level": _safe_get(gid, "level"),
        "forecastTime": _safe_get(gid, "forecastTime"),
        "stepRange": _safe_get(gid, "stepRange"),
        "validDate": _safe_get(gid, "validityDate"),
        "units": _safe_get(gid, "units"),
        "gridType": _safe_get(gid, "gridType"),
        "Ni": _safe_get(gid, "Ni"),
        "Nj": _safe_get(gid, "Nj"),
    }
