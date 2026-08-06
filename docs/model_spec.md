# 相対飛散リスクモデル仕様

## 0. 独立性(第三者利用・別システムへの組込みについて)

`src/dust_forecast/model.py` はGRIB2読込(xarray/cfgrib/wgrib2/eccodes)にも
Streamlit UIにも一切依存しない。入力は単純な数値・文字列と `ModelConfig`
(後述)のみであり、風向風速・降水量の取得元は気象庁GSM GPVに限らず、他社製品や
実測値など何でもよい。本ファイル(`docs/model_spec.md`)を読むだけで、
コード(`model.py`本体)を読まなくても `compute_risk()` / `rain_factor()` を
単独で呼び出せることを目標にしている。入出力の完全な定義は9章を参照。

依存モジュールは `dust_forecast.config`(pydanticスキーマ、I/O無し)と
`dust_forecast.wind`(NumPyのみ)の2つだけであり、いずれもGRIB/UIとは無関係。

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

## 10. Python APIリファレンス

`model.py` が公開する2つの純粋関数の完全な入出力定義。数式(2〜8章)と
実装上の型・単位・データ構造を対応づける。

### 10.1 `compute_risk(x_m, y_m, u_mps, v_mps, hourly_precip_mm, intensity, watering, model_cfg) -> RiskResult`

セル(1つまたは複数)の相対飛散リスクを計算する。

**入力パラメータ**

| 引数 | 型 | 単位・値域 | 意味 |
|---|---|---|---|
| `x_m` | `float` または `numpy.ndarray` | m(東向き正) | セル中心の**発生源からの相対**東西座標。2章の `x` |
| `y_m` | 同上(`x_m`と同じ形状) | m(北向き正) | セル中心の**発生源からの相対**南北座標。2章の `y` |
| `u_mps` | `float` | m/s(東向き正) | 10m風のU成分(スカラー、時刻ごとに1つ)。3章の `U` |
| `v_mps` | `float` | m/s(北向き正) | 10m風のV成分(スカラー、時刻ごとに1つ)。3章の `V` |
| `hourly_precip_mm` | `float` | mm/h、NaN可(0扱い) | 時間降水量(スカラー)。5.3章 |
| `intensity` | `"small"` \| `"medium"` \| `"large"` (plain str) | - | 工事強度。5.1章の `E_base` 選択キー |
| `watering` | `"none"` \| `"normal"` \| `"strong"` (plain str) | - | 散水レベル。5.4章の `mitigation_factor` 選択キー |
| `model_cfg` | `ModelConfig` 相当のオブジェクト | - | 10.3節参照。全係数の注入元 |

`x_m`/`y_m` はスカラーでも、同じ形状の`numpy.ndarray`(1次元・2次元いずれも可)
でもよい。1回の呼び出しで複数セルをまとめて計算する(ローカルメッシュ全体を
1回で処理する設計)。

**戻り値 `RiskResult`(dataclass)**

`x_m`/`y_m` がスカラーの場合、配列系フィールドは形状 `()` の0次元
`numpy.ndarray` になる(`float(...)` または `result.risk[()]` で素の値を
取り出せる)。`x_m`/`y_m` が配列の場合は同じ形状の配列になる。

| フィールド | 型 | 単位 | 対応する数式 |
|---|---|---|---|
| `wind_speed_mps` | ndarray | m/s | 3章の `S`(入力形状にブロードキャスト) |
| `downwind_distance_m` | ndarray | m | 3章の `s`(無風時は`r`) |
| `crosswind_distance_m` | ndarray | m | 3章の `c`(無風時は0) |
| `sigma_y_m` | ndarray | m | 5.5章の `sigma_y(s)` |
| `downwind_decay` | ndarray | 無次元(0-1) | 5.6章の `downwind_decay` |
| `crosswind_spread` | ndarray | 無次元(0-1) | 5.6章の `crosswind_spread` |
| `emission_factor` | `float`(スカラー) | 無次元 | 5.1章の `E_base` |
| `wind_activation` | `float`(スカラー) | 無次元(0〜wind_max_factor) | 5.2章の `wind_activation` |
| `rain_factor` | `float`(スカラー) | 無次元(0-1) | 5.3章の降水係数 |
| `mitigation_factor` | `float`(スカラー) | 無次元(0-1) | 5.4章の散水低減係数 |
| `raw_risk` | ndarray | 無次元 | 6章の `raw_risk`(クリップ前) |
| `risk` | ndarray | 無次元(0-100) | 6章の `risk`(クリップ後、**画面表示に使う値**) |
| `is_calm` | `bool`(スカラー) | - | 4章の無風判定結果(True=等方分布ブランチ使用) |
| `is_upwind` | ndarray(bool) | - | セルごとの風上判定(`s < 0`。無風時は全て`False`) |

`category`(表示区分文字列)は `compute_risk()` の戻り値には含まれない。
`categories.classify(risk, thresholds)` または `categories.classify_array(...)`
に `risk` を渡して別途求める(7章、`thresholds`は`config.thresholds`相当)。

**決定性**: 同一入力に対して常に同一出力を返す(乱数・時刻依存・外部I/Oなし)。

### 10.2 `rain_factor(hourly_precip_mm, breakpoints) -> float`

5.3章の降水係数のみを単独で計算したい場合の下位レベル関数。

| 引数 | 型 | 意味 |
|---|---|---|
| `hourly_precip_mm` | `float`(NaN可、0として扱う) | 時間降水量[mm/h] |
| `breakpoints` | `list[tuple[float, float]]` | `[(max_mm_h, factor), ...]` を `max_mm_h` 昇順で指定 |

戻り値: `float`。`hourly_precip_mm` が最初に `max_mm_h` を下回った要素の
`factor`。全て超える場合は最後の要素の `factor`。

**注意**: `compute_risk()` に渡す `model_cfg.rain_factor_breakpoints` は
`RainFactorBreakpoint`(pydanticモデル、`.max_mm_h`/`.factor`属性を持つ)の
リストであり、`compute_risk()` 内部で `[(bp.max_mm_h, bp.factor) for bp in
model_cfg.rain_factor_breakpoints]` のようにタプルのリストへ変換してから
`rain_factor()` を呼んでいる。`rain_factor()` を直接呼ぶ場合は、この変換を
呼出側で行うか、単純に `[(0.1, 1.0), (1.0, 0.7), (3.0, 0.4), (float("inf"), 0.15)]`
のようなタプルのリストを直接渡してよい(pydanticは不要)。

### 10.3 `model_cfg` に要求されるインターフェース

`compute_risk()` は型としては `dust_forecast.config.ModelConfig` を想定して
いるが、実際にアクセスするのは以下の属性・メソッドのみである。別システムに
組み込む際、pydanticを導入したくない場合は、以下を満たす単純なオブジェクト
(`types.SimpleNamespace` 等)や自前のクラスを渡してもよい。

| 属性/メソッド | 型 | 説明 |
|---|---|---|
| `.wind_start_mps` | `float` | 5.2章 |
| `.wind_full_mps` | `float` | 5.2章(`wind_start_mps`より大きいこと) |
| `.wind_max_factor` | `float` | 5.2章 |
| `.sigma0_m` | `float` | 5.5章 |
| `.spread_rate` | `float` | 5.5章 |
| `.decay_base_m` | `float` | 5.5章(0より大きいこと) |
| `.decay_per_ms` | `float` | 5.5章 |
| `.upwind_background` | `float` | 3章(既定0.0) |
| `.calm_threshold_mps` | `float` | 4章(既定0.3) |
| `.eps` | `float` | ゼロ除算回避用の微小値(既定1e-6) |
| `.e_base.for_intensity(intensity: str) -> float` | メソッド | 5.1章。`intensity`(`"small"`/`"medium"`/`"large"`)に対応する`E_base`を返す |
| `.mitigation_factor.for_watering(watering: str) -> float` | メソッド | 5.4章。`watering`に対応する係数を返す |
| `.rain_factor_breakpoints` | `list[obj]`(各要素が`.max_mm_h`・`.factor`属性を持つ) | 5.3章 |

`dust_forecast.config.ModelConfig`/`EmissionBase`/`MitigationFactor`/
`RainFactorBreakpoint` をそのまま使うのが最も簡単(pydantic+PyYAML+pathlibの
みに依存し、GRIB/UI関連の依存は無い)。設定ファイルの完全なスキーマは
`config/schema.md` を参照。
