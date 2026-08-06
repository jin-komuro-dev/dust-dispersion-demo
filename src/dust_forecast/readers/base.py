"""GRIB Reader共通インターフェースと要素識別情報。

気象庁GSMのGRIB2は、要素によっては shortName が "unknown" として
デコードされる(積算降水量・雲量など、eccodesの既定テーブルに
JMA固有の discipline/parameterCategory/parameterNumber の組合せが
無いため)。そのため name/shortName だけに依存せず、GRIB2識別情報
(discipline, parameterCategory, parameterNumber, typeOfLevel, level)
をフォールバックとして使用する。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import xarray as xr


class GribReaderError(Exception):
    """GRIB読込に関する独自例外。上位層で捕捉して処理する。

    ライブラリ内部では sys.exit() を使わず、必ずこの例外(またはサブクラス)
    を送出すること。
    """


class GribToolNotFoundError(GribReaderError):
    """wgrib2等の外部実行ファイルが見つからない場合。"""


class GribFieldNotFoundError(GribReaderError):
    """要求した気象要素がGRIB2ファイル内に存在しない場合。"""


@dataclass(frozen=True)
class FieldSpec:
    """1つの気象要素をGRIB2識別情報で特定するための仕様。"""

    name: str
    discipline: int
    parameter_category: int
    parameter_number: int
    type_of_level: str | None = None
    level: float | None = None
    short_name_hints: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    def filter_by_keys(self) -> dict:
        keys: dict = {
            "discipline": self.discipline,
            "parameterCategory": self.parameter_category,
            "parameterNumber": self.parameter_number,
        }
        return keys


# 5.1 要素の特定 (仕様書 v2) に基づく標準フィールド定義。
# 粉じん計算で必須: u10, v10, apcp。それ以外は画面表示用の補助値。
STANDARD_FIELDS: dict[str, FieldSpec] = {
    "u10": FieldSpec(
        name="u10",
        discipline=0,
        parameter_category=2,
        parameter_number=2,
        type_of_level="heightAboveGround",
        level=10,
        short_name_hints=("u10", "UGRD"),
        description="10m U風(東西成分, 東向き正)",
    ),
    "v10": FieldSpec(
        name="v10",
        discipline=0,
        parameter_category=2,
        parameter_number=3,
        type_of_level="heightAboveGround",
        level=10,
        short_name_hints=("v10", "VGRD"),
        description="10m V風(南北成分, 北向き正)",
    ),
    "t2m": FieldSpec(
        name="t2m",
        discipline=0,
        parameter_category=0,
        parameter_number=0,
        type_of_level="heightAboveGround",
        level=2,
        short_name_hints=("t2m", "TMP"),
        description="2m気温[K]",
    ),
    "r2": FieldSpec(
        name="r2",
        discipline=0,
        parameter_category=1,
        parameter_number=1,
        type_of_level="heightAboveGround",
        level=2,
        short_name_hints=("r2", "RH"),
        description="2m相対湿度[%]",
    ),
    "tcc": FieldSpec(
        name="tcc",
        discipline=0,
        parameter_category=6,
        parameter_number=1,
        type_of_level="surface",
        level=None,
        short_name_hints=("tcc", "TCDC"),
        description="全雲量[%] (shortNameがunknownになる場合がある)",
    ),
    "apcp": FieldSpec(
        name="apcp",
        discipline=0,
        parameter_category=1,
        parameter_number=8,
        type_of_level="surface",
        level=None,
        short_name_hints=("apcp", "tp", "APCP"),
        description="積算降水量[mm] (初期時刻からの累積, shortNameがunknownになる場合がある)",
    ),
}

REQUIRED_FIELDS: tuple[str, ...] = ("u10", "v10", "apcp")
OPTIONAL_FIELDS: tuple[str, ...] = ("t2m", "r2", "tcc")

INVENTORY_COLUMNS: list[str] = [
    "record_index",
    "name",
    "shortName",
    "discipline",
    "parameterCategory",
    "parameterNumber",
    "typeOfLevel",
    "level",
    "forecastTime",
    "stepRange",
    "validDate",
    "units",
    "gridType",
    "Ni",
    "Nj",
]


class BaseGribReader(abc.ABC):
    """GRIB2 Reader Adapterの共通インターフェース。"""

    backend_name: str = "base"

    @abc.abstractmethod
    def read(
        self,
        input_path: str | Path,
        fields: tuple[str, ...] = tuple(STANDARD_FIELDS.keys()),
    ) -> xr.Dataset:
        """指定した気象要素をxarray.Datasetとして読み込む。

        戻り値の次元は (step|time, latitude, longitude) を基本とし、
        変数名は STANDARD_FIELDS のキー (u10, v10, t2m, r2, tcc, apcp) に
        統一する。緯度・経度は degrees、時刻はUTC。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def inventory(self, input_path: str | Path) -> pd.DataFrame:
        """GRIB2ファイルの全レコードのインベントリをDataFrameで返す。

        列は INVENTORY_COLUMNS に従う。
        """
        raise NotImplementedError
