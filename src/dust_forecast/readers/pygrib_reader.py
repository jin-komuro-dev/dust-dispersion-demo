"""pygribを用いたGRIB Reader(Windows未対応のプレースホルダ)。

Phase 0で `pip install pygrib` を試行したところ、Windows上でのビルドが
`eccodes.h が見つからない` というエラーで失敗した。pygribはCソースを
ecCodesの開発用ヘッダ・ライブラリに対して自前でコンパイルする構成で
あり、Windows版ecCodesの開発用パッケージはconda-forgeのwin-64
チャンネルにも存在しない(2026年時点)。したがって本プロジェクトの
Windows環境では pygrib を標準Readerに採用できないと判断した。

このファイルはAdapter構造を維持するためのプレースホルダであり、
`reader_backend: pygrib` を指定した場合は明確なエラーメッセージで
`GribReaderError` を送出する。Linux/macOS環境等でpygribが利用可能に
なった場合は、本クラスへ実装を追加するだけで切り替えられる設計である。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

from dust_forecast.readers.base import STANDARD_FIELDS, BaseGribReader, GribReaderError


class PygribReader(BaseGribReader):
    backend_name = "pygrib"

    _UNAVAILABLE_MESSAGE = (
        "pygrib Readerは現在の環境では利用できません。"
        "Windows上ではpygribのビルドに必要なecCodes開発用ヘッダが"
        "conda-forge(win-64)にも存在せず、pipビルドがeccodes.h不足で"
        "失敗することを確認済みです(docs/provenance.md参照)。"
        "reader_backend に cfgrib または wgrib2_netcdf を指定してください。"
    )

    def read(
        self,
        input_path: str | Path,
        fields: tuple[str, ...] = tuple(STANDARD_FIELDS.keys()),
    ) -> xr.Dataset:
        raise GribReaderError(self._UNAVAILABLE_MESSAGE)

    def inventory(self, input_path: str | Path) -> pd.DataFrame:
        raise GribReaderError(self._UNAVAILABLE_MESSAGE)
