"""風向・風速、飛散方向、16方位変換。

`reference/wxparams.py` の `UV_to_SpdDir` / `Deg_to_Dir16` を設計参考資料として
利用したが、コードは直接流用せず、以下を満たすよう独自実装した
(詳細は docs/provenance.md 第2章)。

- 気象学的風向(吹いてくる方向)と、粉じんの移流方向(吹いていく方向)を明確に分離する
- NumPy配列・Pythonスカラーの両方で正しく動く
- 0m/s(静穏)を特別に扱える

情シス側の気象データが「16方位(ENE等)+風速[m/s]」形式で提供される場合は、
`dir16_to_deg()` で角度へ変換した後、`uv_from_speed_dir()` でU/V成分に変換
してから `model.compute_risk()` に渡す(利用フローの詳細は
docs/model_spec.md 8.1節を参照)。
"""
from __future__ import annotations

import unicodedata

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


def uv_from_speed_dir(wind_from_deg_value, speed_mps):
    """風向角度[度](気象学的な、風が吹いてくる方向)と風速[m/s]から、
    10m風のU成分・V成分[m/s]を求める(`wind_from_deg()` の逆変換)。

    docs/model_spec.md 8章の定義
        wind_from_deg = (degrees(atan2(-U, -V)) + 360) % 360
    と整合するよう、この式をUについて解いて導出した:

        U = -S * sin(radians(wind_from_deg))
        V = -S * cos(radians(wind_from_deg))

    (検算: U=1,V=0 のとき wind_from_deg=270度。上式に270度とS=1を代入すると
    U=-1*sin(270°)=-1*(-1)=1, V=-1*cos(270°)=-1*0=0 となり、元のU,Vに一致する)

    スカラー・NumPy配列の両方に対応する(`speed_mps` が0の場合、
    `wind_from_deg_value` の値によらず U=V=0 になる)。
    """
    theta = np.radians(wind_from_deg_value)
    u = -speed_mps * np.sin(theta)
    v = -speed_mps * np.cos(theta)
    return u, v


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


# deg_to_dir16() の逆引き用テーブル。キーは正規化済み(NFKC + upper)の
# 日本語名称・英字略号。英字は大文字化、日本語・英字とも全角/半角の
# 表記ゆれをNFKC正規化で吸収する。
_DIR16_LOOKUP: dict[str, float] = {}
for _idx, (_ja, _en) in enumerate(zip(DIR16_JA, DIR16_EN)):
    _deg_value = _idx * (360.0 / 16)
    _DIR16_LOOKUP[unicodedata.normalize("NFKC", _ja).strip().upper()] = _deg_value
    _DIR16_LOOKUP[unicodedata.normalize("NFKC", _en).strip().upper()] = _deg_value
del _idx, _ja, _en, _deg_value


def _normalize_dir_token(token) -> str:
    """16方位文字列の表記ゆれ(大文字/小文字、全角/半角)を正規化する。"""
    return unicodedata.normalize("NFKC", str(token)).strip().upper()


def dir16_to_deg(direction):
    """16方位文字列(日本語名称または英字略号)を角度[度, 0-360)へ変換する。

    `deg_to_dir16()` の逆変換。大文字/小文字("ene"/"ENE")、全角/半角
    ("Ｅ"/"E")の表記ゆれは `unicodedata.normalize("NFKC", ...)` で吸収する。
    スカラー文字列・文字列のリスト/NumPy配列の両方に対応する。

    「静穏」「CALM」等、無風を表す値には対応しない
    (16方位の名称ではないため `ValueError` を送出する)。実データに
    無風マーカーが含まれる場合は、本関数を呼ぶ前に呼出側で検出し、
    風速0として `uv_from_speed_dir()` に渡す(その場合、角度の値によらず
    U=V=0 になるため、角度は任意の値でよい)。
    """
    scalar_input = np.ndim(direction) == 0
    tokens = np.atleast_1d(np.asarray(direction, dtype=object))

    degrees = np.empty(tokens.shape, dtype=float)
    for idx, token in np.ndenumerate(tokens):
        key = _normalize_dir_token(token)
        value = _DIR16_LOOKUP.get(key)
        if value is None:
            raise ValueError(
                f"未知の16方位文字列です: {token!r}。"
                f"有効な値(英字略号): {DIR16_EN} / (日本語名称): {DIR16_JA}"
            )
        degrees[idx] = value

    if scalar_input:
        return float(degrees.reshape(-1)[0])
    return degrees


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
