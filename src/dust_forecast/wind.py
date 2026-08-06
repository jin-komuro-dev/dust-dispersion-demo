"""風向・風速、飛散方向、16方位変換。

`reference/wxparams.py` の `UV_to_SpdDir` / `Deg_to_Dir16` を設計参考資料として
利用したが、コードは直接流用せず、以下を満たすよう独自実装した
(詳細は docs/provenance.md 第2章)。

- 気象学的風向(吹いてくる方向)と、粉じんの移流方向(吹いていく方向)を明確に分離する
- NumPy配列・Pythonスカラーの両方で正しく動く
- 0m/s(静穏)を特別に扱える
"""
from __future__ import annotations

import numpy as np

DIR16_JA: tuple[str, ...] = (
    "北", "北北東", "北東", "東北東",
    "東", "東南東", "南東", "南南東",
    "南", "南南西", "南西", "西南西",
    "西", "西北西", "北西", "北北西",
)
DIR16_EN: tuple[str, ...] = (
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
)
CALM_JA = "静穏"
CALM_EN = "CALM"


def wind_speed(u, v):
    """風速 S = sqrt(U^2 + V^2)。スカラー・配列両対応。"""
    return np.hypot(u, v)


def wind_from_deg(u, v):
    """気象学的な風向(風が吹いてくる方向)[度, 0-360)。

    wind_from_deg = (degrees(atan2(-U, -V)) + 360) % 360
    """
    return np.mod(np.degrees(np.arctan2(-u, -v)) + 360.0, 360.0)


def downwind_to_deg(u, v):
    """飛散注意方向(粉じんが流れていく風下方向)[度, 0-360)。

    downwind_to_deg = (degrees(atan2(U, V)) + 360) % 360
    """
    return np.mod(np.degrees(np.arctan2(u, v)) + 360.0, 360.0)


def deg_to_dir8(deg):
    """0-360度を8方位(日本語名称, 英字略号)へ変換する。スカラー・配列両対応。"""
    return _deg_to_dir(deg, ("北", "北東", "東", "南東", "南", "南西", "西", "北西"),
                        ("N", "NE", "E", "SE", "S", "SW", "W", "NW"), n=8)


def deg_to_dir16(deg):
    """0-360度を16方位(日本語名称, 英字略号)へ変換する。スカラー・配列両対応。

    境界値(例: 11.25度)は次の方位(時計回りに進んだ側)に丸める
    (`(deg + half_width) // width` 方式。round-half-to-evenによる
    非直感的な丸めを避けるため)。
    """
    return _deg_to_dir(deg, DIR16_JA, DIR16_EN, n=16)


def _deg_to_dir(deg, names_ja: tuple[str, ...], names_en: tuple[str, ...], n: int):
    width = 360.0 / n
    scalar_input = np.ndim(deg) == 0
    deg_arr = np.atleast_1d(np.asarray(deg, dtype=float))
    idx = (np.floor((deg_arr + width / 2.0) / width).astype(int)) % n
    ja = np.array(names_ja, dtype=object)[idx]
    en = np.array(names_en, dtype=object)[idx]
    if scalar_input:
        return str(ja[0]), str(en[0])
    return ja.astype(str), en.astype(str)


def wind_direction_label(u, v, calm_threshold: float = 0.0, n: int = 16):
    """風向を方位名(日本語名称, 英字略号)で返す。

    風速が `calm_threshold` 以下の場合は方位を計算せず「静穏」/「CALM」を返す。
    スカラー・配列両対応。
    """
    speed = wind_speed(u, v)
    from_deg = wind_from_deg(u, v)
    convert = deg_to_dir16 if n == 16 else deg_to_dir8
    ja, en = convert(from_deg)

    is_calm = speed <= calm_threshold
    scalar_input = np.ndim(is_calm) == 0
    if scalar_input:
        if bool(is_calm):
            return CALM_JA, CALM_EN
        return ja, en

    ja_arr = np.where(is_calm, CALM_JA, ja)
    en_arr = np.where(is_calm, CALM_EN, en)
    return ja_arr, en_arr
