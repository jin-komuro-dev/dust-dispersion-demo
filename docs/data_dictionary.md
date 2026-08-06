# データ辞書 (CSV/JSON出力)

## セルCSV (`outputs/cells/cells_<validTimeUTC>.csv`)

1時刻・1セルにつき1行。`reports.CELL_CSV_COLUMNS` が正。

| 列名 | 型 | 説明 |
|---|---|---|
| `valid_time_utc` | str (ISO8601) | 予報時刻(UTC) |
| `valid_time_jst` | str (ISO8601) | 予報時刻(JST) |
| `row` | int | セルの行番号(0始まり、0が北端) |
| `column` | int | セルの列番号(0始まり、0が西端) |
| `center_x_m` | float | セル中心の東向き座標[m](現場中心が原点) |
| `center_y_m` | float | セル中心の北向き座標[m] |
| `latitude`, `longitude` | float | セル中心の緯度経度 |
| `source_x_m`, `source_y_m` | float | 発生源(作業現場)の東向き・北向き座標[m] |
| `grid_width_m`, `grid_height_m` | float | 実効表示範囲[m](edge_policy適用後) |
| `cell_size_x_m`, `cell_size_y_m` | float | セルサイズ[m] |
| `nx`, `ny` | int | 格子数(東西・南北) |
| `u10_mps`, `v10_mps` | float | 現場地点へ補間した10m風のU/V成分[m/s] |
| `wind_speed_mps` | float | 風速[m/s] |
| `wind_from_deg` | float | 気象学的風向(吹いてくる方向)[度] |
| `downwind_to_deg` | float | 飛散注意方向(吹いていく方向)[度] |
| `hourly_precip_mm` | float | 時間降水量[mm/h](積算値の差分) |
| `emission_factor` | float | 工事強度別の基準発生係数 `E_base` |
| `wind_activation` | float | 風活性化係数 |
| `rain_factor` | float | 降水係数 |
| `mitigation_factor` | float | 散水低減係数 |
| `downwind_distance_m` | float | 風下距離 `s`[m](発生源基準) |
| `crosswind_distance_m` | float | 横風距離 `c`[m] |
| `sigma_y_m` | float | 横風方向広がり `sigma_y(s)`[m] |
| `downwind_decay` | float | 風下減衰係数(0-1) |
| `crosswind_spread` | float | 横風広がり係数(0-1) |
| `raw_risk` | float | クリップ前のリスク値 |
| `risk` | float | クリップ後のリスク値(0-100) |
| `category` | str | 表示区分(少ない/やや多い/多い/非常に多い) |

## 時刻サマリJSON (`outputs/summary/summary_<validTimeUTC>.json`)

| キー | 説明 |
|---|---|
| `input_filename` | 入力GRIB2ファイル名 |
| `init_time_utc` | 初期時刻(UTC) |
| `valid_time_utc`, `valid_time_jst` | 予報時刻 |
| `site` | 現場名・緯度・経度 |
| `grid` | 実効幅・高さ・セル間隔・nx/ny・回転角・edge_policy・発生源位置 |
| `interpolation_method` | 実際に使用した補間方式(`bilinear`/`nearest`、フォールバック後の値) |
| `used_grib_fields` | 読み込んだGRIB要素名の一覧 |
| `construction` | 工事強度・稼働時間・散水レベル |
| `model_coefficients` | `config.model` の全係数(そのままJSON化) |
| `formula_version` | 計算式バージョン |
| `thresholds` | 色分けしきい値 |
| `max_risk` | その時刻の最大リスク値 |
| `max_risk_cell` | 最大リスクのセル位置(row, column) |
| `warnings` | グリッド構築時などの警告メッセージ一覧 |

## GRIBインベントリCSV (`outputs/grib_inventory.csv`)

`readers/base.py` の `INVENTORY_COLUMNS` に従う: `record_index`, `name`,
`shortName`, `discipline`, `parameterCategory`, `parameterNumber`,
`typeOfLevel`, `level`, `forecastTime`, `stepRange`, `validDate`, `units`,
`gridType`, `Ni`, `Nj`。
