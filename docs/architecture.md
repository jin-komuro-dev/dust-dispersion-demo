# アーキテクチャ設計

## 1. 設計原則

- **ロジックと画面の分離**: 計算ロジック(`src/dust_forecast/*.py`)はCLI/Streamlitのどちらからも同じ関数を呼び出す。画面固有のコードは `app.py` と `cli.py` のみに置く。
- **設定駆動**: グリッド仕様・モデル係数・しきい値は `config/*.yaml` で完全に外部化する。コードへ数値を埋め込まない。
- **Reader Adapterパターン**: GRIB2読込方式(cfgrib/wgrib2/pygrib)を切り替えても、計算・画面側のコードは変更不要。
- **追跡可能性**: 各時刻・各セルの中間計算値をCSV/JSONへ出力し、画面表示の色がどの入力・計算根拠から得られたか追跡できるようにする。
- **例外は独自例外に変換**: 外部ツール(wgrib2, eccodes)由来の例外は `GribReaderError` 系に変換して上位へ伝える。`sys.exit()` はライブラリ内部で使わない。

## 2. モジュール構成と責務

```
src/dust_forecast/
├─ paths.py            # 全パス定数の唯一の定義箇所(Path(__file__)基準)
├─ config.py            # YAML設定のpydanticスキーマと読込
├─ logging_config.py    # 共通ロガー設定、長大出力のファイル退避
├─ grib_reader.py        # Reader Adapterの選択・GRIB読込の高レベルAPI
├─ readers/
│  ├─ base.py            # Reader共通インターフェース、FieldSpec、標準要素定義
│  ├─ cfgrib_reader.py    # 標準Reader (cfgrib/ecCodes)
│  ├─ wgrib2_netcdf.py   # 代替Reader (wgrib2 -netcdf -> xarray)
│  └─ pygrib_reader.py    # プレースホルダ(Windows未対応の理由を明示して例外送出)
├─ interpolation.py     # 現場地点への空間補間(双線形/最近傍)
├─ wind.py               # 風向風速、飛散方向、16方位変換(スカラー/配列両対応)
├─ precipitation.py      # 積算降水量からの時間降水量差分
├─ grid.py                # 可変ローカルメッシュ生成、pyproj局所座標系
├─ model.py               # 相対飛散リスクモデル(物理量計算とは独立)
├─ categories.py          # しきい値による4段階色分け
├─ weather.py             # 簡易天気判定(第9節)
├─ reports.py              # CSV/JSON出力(追跡可能性)
├─ plotting.py             # Matplotlib時刻別図・ダッシュボード図
└─ cli.py                  # inspect-grib / generate コマンド
app.py                      # Streamlit画面(ロジックはimportのみ)
```

## 3. データフロー

```
GRIB2ファイル
  → GribReader.inventory()        -> outputs/grib_inventory.csv
  → GribReader.read(fields)       -> xr.Dataset (u10,v10,t2m,r2,tcc,apcp; UTC)
  → interpolation.interpolate_point_series() -> 現場地点の時系列 (bilinear/nearest)
  → precipitation.hourly_from_accumulated()   -> 時間降水量
  → wind.uv_to_speed_dir() / wind_from_deg() / downwind_to_deg()
  → grid.build_grid(config.grid)              -> セル中心のローカル座標(x,y)・緯度経度
  → model.compute_risk(cell, wind, precip, construction, model_config)
       -> raw_risk, risk, 中間値一式
  → categories.classify(risk, thresholds)     -> 表示区分
  → reports.write_cell_csv() / write_time_json()
  → plotting.plot_time_map() / plot_dashboard()
  → (Streamlit) app.py がこれらの関数を呼び出して画面表示
```

## 4. GRIB Reader Adapter

`readers/base.py` の `BaseGribReader` が共通インターフェース:

```python
class BaseGribReader(abc.ABC):
    def read(self, input_path, fields=(...)) -> xr.Dataset: ...
    def inventory(self, input_path) -> pd.DataFrame: ...
```

`grib_reader.py` はconfigの `grib.reader_backend` に応じて実装クラスを選択するファクトリを提供する。
呼出側(cli.py, app.py, model計算パイプライン)は `BaseGribReader` のインターフェースのみに依存し、
具象クラスを直接importしない。

要素の識別は `readers/base.py` の `STANDARD_FIELDS`(discipline/parameterCategory/parameterNumberの
組)に一元化されており、name/shortNameのみに依存しない(Phase 0で確認した通り、JMA GSMの
積算降水量・全雲量はecCodesの既定テーブルでshortNameが`unknown`になるため必須の設計)。

## 5. 可変グリッド設計

`grid.py` は `config.grid` から以下を実行時に算出する(コード埋め込み禁止)。

- `nx = round(width_m / cell_size_x_m)`, `ny = round(height_m / cell_size_y_m)`
- `edge_policy` (`error`/`trim`/`pad`) に応じて、割り切れない場合の実効範囲を決定
- 発生源位置は `source_position_mode` (`offset_m`/`latlon`/`rowcol`) に応じて解決
- 現場中心のAzimuthal Equidistant局所座標系(`pyproj.Proj`)でセル中心のx,y[m]を生成し、
  緯度経度は逆変換で求める
- `rotation_deg` によりグリッド軸を回転できる(正方形・北基準を前提にしない)
- 総セル数が `max_cells` を超える場合は `GridConfigError` を送出する

## 6. モデルの位置づけ

`model.py` は物理濃度シミュレーションではなく、说明可能な相対リスクモデル(0-100の無次元スコア)を
計算する。全ての係数は `config.model` から注入し、コード中に定数を埋め込まない。
計算式の詳細は `docs/model_spec.md` を参照。

`model.py` はGRIB2読込(xarray/cfgrib/wgrib2/eccodes)にもStreamlit UIにも
依存しない純粋関数として独立している(依存は `config.py` と `wind.py` のみ)。
`precipitation.py` はxarrayに依存するため、model.pyからはimportしない
(降水係数`rain_factor()`はmodel.py側に置いている)。この独立性は
`tests/test_model.py::test_model_module_has_no_grib_or_ui_imports` で
静的に回帰検証している。他システムへ計算ロジックのみを切り出す場合の
完全なAPI定義は `docs/model_spec.md` 第10章を参照。

## 7. 主要な設計判断 (ADR的記録)

| 判断 | 理由 |
|---|---|
| 標準ReaderにCfgribReaderを採用 | Phase 0比較の結果、外部exe不要・サブプロセス不要で情シス引渡しに有利なため(`docs/provenance.md`参照) |
| wgrib2/cfgribの一時ファイルをoutputs/_tmp(プロジェクト配下ASCIIパス)に置く | 日本語ユーザー名を含む既定TEMPディレクトリではnetCDF4-pythonがファイルを開けないことを実機で確認したため |
| 全パス定数をpaths.pyへ集約 | パスのハードコード・コピペを禁止する方針(ユーザー指示)に基づく |
| 時刻ごとの色スケールを固定 | 仕様書要求により、時刻間でリスクの絶対値を比較できるようにするため(時刻ごとの最大値再正規化を禁止) |
| grid.pyでnx/nyを実行時算出 | 20m/200m、10m/200m等の設定変更をコード修正無しで反映するため |

## 8. 背景描画の拡張ポイント(現状: 未実装)

現時点では `plotting.py` に背景描画ロジックは存在しない。`plot_time_map()` /
`plot_dashboard()` はどちらも `_draw_risk_map(ax, grid, risk_2d, ...)` を呼び、
このリスクセル(`ax.pcolormesh(...)`)を白紙のaxesへ直接描画しているのみで、
仕様書8.1節が挙げた「固定乱数の道路・建物背景」「ユーザーアップロード背景」の
いずれも実装していない(オフライン動作という制約を満たすため、当面は
背景なしとした)。

将来、情シス側が実際の航空写真やCAD図面へ差し替える場合、変更が必要な箇所は
以下の1箇所に閉じている想定である。

- **フック位置**: `_draw_risk_map()` 冒頭、`ax.pcolormesh(...)` を呼ぶ**前**に
  `_draw_background(ax, grid, background_config)` のような関数を追加し、
  `ax.imshow(image, extent=(-half_w, half_w, -half_h, half_h), zorder=0)` で
  背景を敷く。座標系はセル中心と同じ現場ローカル東西南北[m](`grid.center_x_m`/
  `center_y_m` と同じAEQD局所座標)なので、画像側がこの範囲に対して
  ジオリファレンス済み(切り出し・回転済み)であれば他のモジュール
  (grid.py/model.py等)は変更不要。
- **リスクセルの重ね方**: 背景の上にリスクセルを重ねて見せるには
  `pcolormesh(..., alpha=0.6)` 等での半透明化、または区分ごとの塗り潰しを
  枠線・ハッチングのみにするデザイン変更が必要になる可能性がある。
- **設定の追加**: `config.py` に `background: {mode: none|random|image,
  image_path, ...}` 相当のセクションを追加し、`AppConfig` へ組み込む想定。
- **既知の注意点**: `grid.rotation_deg != 0` の場合、`pcolormesh`側は
  `_rotate_cw()` でセル自体を回転させているが、`imshow`のextent指定は
  軸並行の矩形にしか対応しないため、回転グリッドと組み合わせる場合は
  画像側を事前に同じ角度だけ回転させておく必要がある。
