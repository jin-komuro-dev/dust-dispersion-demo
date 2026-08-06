"""現場緯度経度が日本列島のどのあたりかを、ざっくり把握するための簡易地図。

オンライン地図タイル・地理院地図API・shapefile等の外部データには一切依存しない
(社内ネットワークでインターネット接続が無い環境でも動作させるため)。
列島の輪郭は国土地理院等の測量データではなく、手作業で簡略化した多角形であり、
位置関係の大まかな把握のみを目的とする。ナビゲーション・測量用途には使えない。

`grid.py`/`model.py` とは無関係の独立したモジュールであり、緯度経度2つの値
だけを入力とする純粋関数として提供する。
"""
from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

DISCLAIMER = "国土地理院等の測量データではない簡易な概略図です(位置の目安のみ)。"

# (経度, 緯度) の頂点リストによる簡略化した島の輪郭。手作業による概略であり、
# 海岸線の精密な形状は表現していない。
_ISLAND_OUTLINES: dict[str, list[tuple[float, float]]] = {
    "北海道": [
        (140.3, 41.5), (139.8, 43.0), (140.0, 44.3), (141.5, 45.5),
        (143.3, 44.5), (145.3, 43.8), (145.5, 43.3), (144.5, 42.0),
        (142.5, 41.5), (140.3, 41.5),
    ],
    "本州": [
        (140.9, 41.3), (141.9, 39.7), (141.9, 38.3), (140.9, 37.1),
        (140.9, 35.9), (139.9, 35.6), (138.9, 34.6), (135.9, 33.4),
        (133.9, 34.2), (132.0, 33.9), (130.9, 33.9), (131.5, 34.6),
        (133.0, 35.4), (135.0, 35.6), (136.9, 37.0), (137.4, 38.0),
        (139.9, 39.8), (140.0, 40.5), (140.9, 41.3),
    ],
    "四国": [
        (132.5, 33.5), (133.0, 33.3), (133.8, 33.4), (134.5, 33.8),
        (134.3, 34.2), (133.3, 34.1), (132.6, 33.9), (132.5, 33.5),
    ],
    "九州": [
        (130.9, 31.0), (131.5, 31.4), (131.9, 32.3), (131.6, 33.3),
        (130.9, 33.9), (130.2, 33.6), (129.6, 33.2), (129.7, 32.3),
        (130.2, 31.3), (130.9, 31.0),
    ],
}
# 沖縄本島は縮尺が小さく多角形では潰れるため、点として表示する。
_OKINAWA_POINT = (127.68, 26.22)

# 描画範囲(日本列島全体が収まる概略のバウンディングボックス)
_LON_RANGE = (122.0, 148.5)
_LAT_RANGE = (23.5, 46.5)


def plot_location_overview(latitude: float, longitude: float, label: str = "現場") -> Figure:
    """現場地点を日本列島の概略図に重ねたFigureを返す(オフライン、外部データ不要)。

    `latitude`/`longitude` の値が日本の範囲(概ね北海道〜沖縄)から外れている
    場合でも例外にはせず、範囲外である旨を図中に注記する。
    """
    fig, ax = plt.subplots(figsize=(3.6, 4.2), dpi=130)

    for name, coords in _ISLAND_OUTLINES.items():
        poly = Polygon(coords, closed=True, facecolor="#d8d5cc", edgecolor="#8a8778", linewidth=0.8, zorder=1)
        ax.add_patch(poly)

    ax.plot(*_OKINAWA_POINT, marker="o", markersize=4, color="#8a8778", zorder=1)
    ax.annotate("沖縄", _OKINAWA_POINT, textcoords="offset points", xytext=(4, -2), fontsize=6, color="#605d50")

    in_range = (_LON_RANGE[0] <= longitude <= _LON_RANGE[1]) and (_LAT_RANGE[0] <= latitude <= _LAT_RANGE[1])
    marker_color = "#d03b3b" if in_range else "#1c5cab"
    ax.plot(longitude, latitude, marker="*", markersize=16, color=marker_color,
             markeredgecolor="white", markeredgewidth=0.8, zorder=5)
    ax.annotate(
        f"{label}\n({latitude:.3f}, {longitude:.3f})",
        (longitude, latitude), textcoords="offset points", xytext=(6, 6),
        fontsize=7, weight="bold", zorder=6,
    )

    ax.set_xlim(*_LON_RANGE)
    ax.set_ylim(*_LAT_RANGE)
    # 中緯度での経度方向の見かけの縮みを大まかに補正する(正確な地図投影ではない)。
    ax.set_aspect(1.0 / np.cos(np.radians(35.0)))
    ax.set_xlabel("経度", fontsize=7)
    ax.set_ylabel("緯度", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title("現場位置(概略)", fontsize=9)

    if not in_range:
        ax.text(
            0.5, -0.16, "※ 指定座標は日本列島の概略範囲外です",
            transform=ax.transAxes, ha="center", fontsize=6.5, color="#1c5cab",
        )

    fig.text(0.02, 0.01, DISCLAIMER, fontsize=5.5, color="dimgray")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig
