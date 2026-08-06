# 相対飛散リスクモデル仕様

## 1. 位置づけ

本モデルは粉じん濃度[μg/m³]を厳密に予測するGaussian Plumeの物理実装ではない。
気象条件(風向風速・降水量)と工事条件(工事強度・散水)から算出する、
**説明可能な相対リスクスコア(0-100)** である。法令・環境基準の判定には使用しない。

## 2. 座標系

現場を原点とするローカル平面直角座標系(x: 東向き正[m], y: 北向き正[m])を用いる。
`pyproj` による現場中心のAzimuthal Equidistant投影、またはUTM座標系で構築する。

## 3. 風下距離・横風距離

セル中心の相対座標 `(x, y)`、GSMから補間した風ベクトル `(U, V)` [m/s]、風速 `S` について:

```
S = sqrt(U^2 + V^2)
s = (x*U + y*V) / max(S, eps)      # 風下距離 [m] (正: 風下, 負: 風上)
c = (-x*V + y*U) / max(S, eps)     # 横風距離 [m]
```

`s < 0` は風上側であり、`upwind_background` (既定0.0)を下限としたバックグラウンド値として扱う。

## 4. 無風判定

`wind_speed_mps < model.calm_threshold_mps` (既定0.3 m/s) の場合、特定方向へ細長く
伸ばすのではなく、発生源周辺に弱い等方分布を与える(`calm`ブランチ)。
このとき `s`, `c` の代わりに発生源からの直線距離 `r = sqrt(x^2+y^2)` を用い、
`downwind_decay = exp(-r/L)`, `crosswind_spread = 1.0` として評価する。

## 5. 各係数

### 5.1 発生量基準値 (工事強度別)

```
E_base:
  small  = model.e_base.small   (既定0.6)
  medium = model.e_base.medium  (既定1.0)
  large  = model.e_base.large   (既定1.5)
```

### 5.2 風活性化係数

```
wind_activation = clip((S - wind_start) / (wind_full - wind_start), 0, wind_max_factor)
```

`wind_start_mps`(既定0.5)未満では発生しにくく、`wind_full_mps`(既定4.0)以上で
`wind_max_factor`(既定1.2)まで線形に増加してクリップする。

### 5.3 降水係数

`model.rain_factor_breakpoints` の階段関数(昇順の `max_mm_h` に対応する `factor`)で決定する。既定値:

```
hourly_precip < 0.1 mm/h       -> 1.00
0.1 <= precip < 1.0 mm/h       -> 0.70
1.0 <= precip < 3.0 mm/h       -> 0.40
precip >= 3.0 mm/h             -> 0.15
```

### 5.4 散水低減係数

```
mitigation_factor:
  none    = model.mitigation_factor.none   (既定1.00)
  normal  = model.mitigation_factor.normal (既定0.60)
  strong  = model.mitigation_factor.strong (既定0.35)
```

### 5.5 拡散パラメータ

```
sigma_y(s) = sigma0_m + spread_rate * max(s, 0)
L(S)       = decay_base_m + decay_per_ms * S
```

### 5.6 減衰・広がり関数

```
downwind_decay    = exp(-max(s, 0) / L)
crosswind_spread  = exp(-0.5 * (c / sigma_y)^2)
```

## 6. リスクスコア

```
raw_risk = 100 * E_base * wind_activation * rain_factor
           * mitigation_factor * downwind_decay * crosswind_spread

risk = clip(raw_risk, 0, 100)
```

風上側(`s < 0`、無風以外)は `raw_risk` の代わりに `upwind_background` を用いる。

## 7. 色分け(表示区分)

`config.thresholds` (既定 `low_max=25`, `moderate_max=50`, `high_max=75`) により4段階に分類する。

| risk | 区分 |
|---|---|
| 0 〜 low_max | 少ない |
| low_max 超 〜 moderate_max | やや多い |
| moderate_max 超 〜 high_max | 多い |
| high_max 超 〜 100 | 非常に多い |

**時刻ごとの最大値による再正規化は行わない。** 時刻間でリスクの絶対値を比較できる固定スケールとする。

## 8. 風向と飛散方向の区別

- 気象学的「風向」(風が吹いてくる方向): `wind_from_deg = (degrees(atan2(-U, -V)) + 360) % 360`
- 「飛散注意方向」(粉じんが流れていく風下方向): `downwind_to_deg = (degrees(atan2(U, V)) + 360) % 360`

両者は180度反対の関係にあり、画面の矢印表示には必ず `downwind_to_deg` を使用する。

## 9. 計算式バージョン

`config.output.formula_version` で管理する(既定 `"1.0.0"`)。将来モデル式を変更した場合は
このバージョン文字列を更新し、JSON出力に記録することでトレーサビリティを確保する。
