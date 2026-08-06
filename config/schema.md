# 設定ファイルスキーマ (config/*.yaml)

Pythonの実装は `src/dust_forecast/config.py` の pydantic モデル (`AppConfig`) が正。
本ドキュメントはその要約であり、詳細な検証ルールはコードを参照すること。

## site

| キー | 型 | 説明 |
|---|---|---|
| `name` | str | 現場名 |
| `latitude` | float | 現場緯度 [度] |
| `longitude` | float | 現場経度 [度] |

## grid

すべての長さは **メートル** (キー名に `_m` を付与し、単位を明示)。

| キー | 型 | 説明 |
|---|---|---|
| `width_m` | float>0 | 表示範囲の幅(東西) |
| `height_m` | float>0 | 表示範囲の高さ(南北) |
| `cell_size_x_m` | float>0 | セルサイズ(東西) |
| `cell_size_y_m` | float>0 | セルサイズ(南北) |
| `rotation_deg` | float | グリッド回転角(度、時計回り) |
| `source_position_mode` | `offset_m`/`latlon`/`rowcol` | 作業現場位置の指定方式 |
| `source_offset_x_m`, `source_offset_y_m` | float | `offset_m`モード時: 表示範囲中心からのオフセット(東・北が正) |
| `source_latitude`, `source_longitude` | float | `latlon`モード時: 作業現場の緯度経度 |
| `source_row`, `source_col` | int | `rowcol`モード時: セル行・列番号(0始まり) |
| `edge_policy` | `error`/`trim`/`pad` | `width_m`/`height_m` がセル間隔で割り切れない場合の扱い |
| `max_cells` | int>0 | 総セル数の上限。超過時は警告/エラー |

`nx = width_m / cell_size_x_m`、`ny = height_m / cell_size_y_m` は実行時に算出する(コード埋め込み禁止)。

## construction

| キー | 型 | 説明 |
|---|---|---|
| `intensity` | `small`/`medium`/`large` | 工事強度 |
| `work_start_jst`, `work_end_jst` | "HH:MM" | 稼働時間(JST) |
| `watering` | `none`/`normal`/`strong` | 散水レベル |

## grib

| キー | 型 | 説明 |
|---|---|---|
| `input_path` | str\|null | GRIB2ファイルパス。未指定時はCLI引数を使用 |
| `reader_backend` | `cfgrib`/`wgrib2_netcdf`/`pygrib` | GRIB Readerの実装選択 |
| `wgrib2_exe` | str\|null | `wgrib2.exe` の場所。未指定時は環境変数 `DUST_FORECAST_WGRIB2` → PATH → 既定探索の順で解決 |
| `target_start_jst`, `target_end_jst` | ISO8601 | 抽出対象期間(JST) |
| `interpolation` | `bilinear`/`nearest` | 現場地点への空間補間方式 |

## model

相対リスクモデルの係数。詳細な計算式は `docs/model_spec.md` を参照。

| キー | 説明 |
|---|---|
| `wind_start_mps`, `wind_full_mps`, `wind_max_factor` | 風活性化関数のパラメータ |
| `sigma0_m`, `spread_rate` | 横風方向広がり `sigma_y(s)` のパラメータ |
| `decay_base_m`, `decay_per_ms` | 風下減衰スケール `L(S)` のパラメータ |
| `upwind_background` | 風上側の背景値 |
| `calm_threshold_mps` | この風速未満は無風(等方分布)として扱う |
| `eps` | ゼロ除算回避用の微小値 |
| `e_base.{small,medium,large}` | 工事強度別の基準発生係数 |
| `rain_factor_breakpoints` | `[{max_mm_h, factor}, ...]` 降水量に対する係数の階段関数(昇順) |
| `mitigation_factor.{none,normal,strong}` | 散水レベル別の低減係数 |

## thresholds

| キー | 説明 |
|---|---|
| `low_max` | 「少ない」の上限(既定25) |
| `moderate_max` | 「やや多い」の上限(既定50) |
| `high_max` | 「多い」の上限(既定75)。これを超えると「非常に多い」 |

## weather_display

第9節の簡易天気判定のしきい値。気象庁の正式な天気予報ではないことを画面に明記する。

| キー | 説明 |
|---|---|
| `rain_mm_h` | これ以上で「雨」 |
| `light_rain_mm_h` | これ以上`rain_mm_h`未満で「弱い雨」 |
| `cloudy_cloud_pct` | 降水なし かつ 全雲量がこれ以上で「くもり」 |
| `partly_cloudy_cloud_pct` | 全雲量がこれ以上`cloudy_cloud_pct`未満で「晴れ時々くもり」。これ未満は「晴れ」 |

## output

| キー | 説明 |
|---|---|
| `formula_version` | 計算式バージョン文字列(JSON出力・トレーサビリティ用) |

## 検証済みの代表設定例

- `config/sample.yaml`: 200m×200m, 20m×20m -> 10×10=100セル
- `config/sample_10m.yaml`: 200m×200m, 10m×10m -> 20×20=400セル

(500m×300m, 25mセル -> 20×12=240セルの例は `tests/test_grid.py` で検証。)
