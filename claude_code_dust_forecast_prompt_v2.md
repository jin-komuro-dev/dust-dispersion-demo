# Claude Code 用プロンプト：GSMを用いた粉じん飛散予測テスト版（参考コード・可変メッシュ対応）

あなたは、Python・気象GRIB2・数値計算・可視化・Streamlitに詳しいシニアエンジニアとして行動してください。

## 1. 目的

工事現場から発生する粉じんについて、気象庁GSMの予測値を読み込み、工事現場周辺を設定可能なローカルメッシュに分割し、各メッシュの「相対的な粉じん飛散リスク」を時刻別に計算・色分け表示するテスト版を作成してください。初期設定は20mメッシュ・200m×200m（10×10格子）としますが、範囲・メッシュ間隔・縦横格子数をコード修正なしで変更できる設計にしてください。

最終的には社内の情報システム部門へコード一式を引き渡すため、単なるデモスクリプトではなく、以下を満たす構成にしてください。

- ロジックと画面を分離する
- 入出力仕様と計算根拠を文書化する
- 係数やしきい値を設定ファイルで変更できる
- 中間計算値をCSV/JSONに出力し、画面の色がどの入力・計算から得られたか追跡できる
- テストコードを用意する
- Windows上で再現できる手順をREADMEにまとめる
- パスをハードコードしない

このモデルは、現段階では粉じん濃度（μg/m³）を厳密に予測するものではありません。気象条件と工事条件から算出する、説明可能な「相対飛散リスクモデル」としてください。

## 2. 使用するテストデータ

入力GRIB2ファイル：

`Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin`

このファイルはリポジトリ直下、または `data/input/` に置かれている前提とします。まず実際のファイルを探索し、存在を確認してください。大容量入力データはGit管理対象外とし、`.gitignore` に追加してください。

事前確認したメタデータの目安は以下です。ただし、必ず実ファイルをプログラムで確認し、結果を `outputs/grib_inventory.csv` に出力してください。

- 初期時刻：2023-03-14 12:00 UTC（2023-03-14 21:00 JST）
- 格子：緯度20～50度、経度120～150度
- 格子間隔：緯度0.1度、経度0.125度
- 格子数：301 × 241 = 72,541点
- 予報時間：概ねFT0～FT24、1時間間隔
- 主な要素：
  - 海面更正気圧
  - 地上気圧
  - 10m U風・10m V風
  - 2m気温
  - 2m相対湿度
  - 下層・中層・上層・全雲量
  - 積算降水量
  - 下向き短波放射

粉じん計算で必須とする要素は、10m U風、10m V風、時間降水量です。気温・湿度・全雲量は画面表示用の補助値として使用可能です。

## 2.1 添付の参考コード

次の2ファイルもプロジェクト内の `reference/` に配置されている前提で、Phase 0で必ず内容を確認してください。

- `reference/wxbcgribx.py`
- `reference/wxparams.py`

### `wxbcgribx.py` の扱い

このファイルには、次の実装例があります。

- `wgrib2` の呼び出し
- `-var`、`-ens` などによるインベントリ取得
- `-match` による気象要素の抽出
- `-netcdf` による一時NetCDF化
- xarrayへのロード
- 緯度経度範囲のトリミング
- UTC時刻のJST変換

GRIB2展開方式を検討する際の重要な参考資料としてください。特に、気象庁GRIB2を `wgrib2 → NetCDF → xarray` の経路で読む方式を、実ファイルで必ず試験してください。

ただし、そのまま無条件に本番コードへコピーしないでください。以下を改善したラッパーまたはReaderクラスとして再設計してください。

- `wgrib2.exe` の絶対パスをハードコードしない
- 設定ファイル、環境変数、PATH、自動探索の順で実行ファイルを解決する
- `shell=True` と `pushd` への依存を可能な限り避け、`subprocess.run(..., cwd=...)` と引数リストを使用する
- 日本語パス・UNCパスで失敗する場合に備え、ローカル一時フォルダへコピーして再試行する処理を用意する
- 標準出力の文字コードはUTF-8だけで決め打ちせず、Windowsではcp932も考慮する
- ライブラリ内部で `sys.exit()` せず、独自例外を送出して上位で処理する
- 一時ファイルを例外時にも確実に削除する
- コマンド、戻り値、stderrをログに残す。ただし長大な出力はファイルへ退避する
- 単体テストでは `subprocess.run` をモックできる構造にする

`wxbcgribx.py` のMIT License表示は、コードを実質的に流用する場合、著作権表示と許諾表示を `LICENSE_NOTICE.md` 等へ残してください。参考にとどめて独自実装した場合も、設計参考資料として使用したことを `docs/provenance.md` に記録してください。

### `wxparams.py` の扱い

このファイルには、U/V成分から風速・風向を求める `UV_to_SpdDir`、風向を8方位・16方位へ変換する関数などがあります。風向・風速計算の参考にしてください。

ただし、次を確認してください。

- 気象学的風向（吹いてくる方向）と、粉じんの移流方向（吹いていく方向）を分離する
- NumPy配列だけでなくPythonのスカラー値でも正しく動く共通関数にする
- 0m/s時の風向を「静穏」等として扱えるようにする
- 方位境界値をpytestで検証する
- 直接流用する場合は著作権・利用条件を確認し、必要な表示を残す。利用条件が不明な部分は、数式を根拠に独自実装し、参考資料としてのみ扱う

### GRIB Readerの設計

GRIB読込処理は呼出側から分離し、共通インターフェースを持つAdapter構造にしてください。候補は以下です。

1. `Wgrib2NetcdfReader`：`wgrib2 -match ... -netcdf` とxarrayを使用
2. `PygribReader`：pygribを使用
3. `CfgribReader`：ecCodes/cfgribを使用

Phase 0で実ファイルを使って比較し、Windows環境で最も再現性が高い方式を標準Readerに採用してください。別方式へ切り替えても計算・画面側を変更しなくてよい構造にします。架空値への置換はReaderの代替にはしないでください。

## 3. 技術方針

### 3.1 実行環境

- Python 3.11
- Windows 10/11を主対象
- GRIB2読込はReader Adapterで分離し、`wgrib2 → NetCDF → xarray`、`pygrib`、`eccodes/cfgrib` を実ファイルで比較する
- 添付の `wxbcgribx.py` を参考に、Windowsで再現性が高い方式を標準Readerとして採用する
- 採用方式、必要な外部実行ファイル、バージョン、PATH設定をREADMEに明記する
- GRIB2を読めない状態で架空値に置き換えて完了扱いにしない
- 依存関係は `environment.yml` を優先し、可能であれば `requirements.txt` も用意する
- Claude Codeが継続して作業しやすいよう、リポジトリ直下に `CLAUDE.md` を作成し、実行コマンド、設計原則、禁止事項、テスト手順を記載する

推奨依存関係：

- numpy
- pandas
- scipy
- xarray
- netCDF4
- matplotlib
- pyproj
- streamlit
- pydantic または pydantic-settings
- PyYAML
- pytest
- Pillow
- pygrib
- cfgrib / eccodes（採用するReaderに応じて）

外部実行ファイルとして `wgrib2` を使用する場合は、対応バージョンと入手・配置・PATH設定をREADMEに記載してください。

Cartopyやオンライン地図は必須にしないでください。社内環境でも動かせるよう、標準画面はネット接続不要とします。

### 3.2 アプリ形式

以下の2通りを用意してください。

1. CLIバッチ処理
2. Streamlit画面

CLIの例：

```powershell
python -m dust_forecast.cli inspect-grib --input data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin

python -m dust_forecast.cli generate `
  --input data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin `
  --config config/sample.yaml

streamlit run app.py
```

## 4. テスト現場と可変メッシュ仕様

テスト用の架空現場を以下とします。すべて設定ファイルおよびStreamlit画面から変更可能にしてください。

- 現場名：テスト工事現場A
- 緯度：35.6812
- 経度：139.7671
- デフォルト表示範囲：200m × 200m
- デフォルトメッシュ間隔：20m × 20m
- デフォルト格子数：10 × 10
- 作業現場の初期位置：表示範囲中央よりやや西南側
- 工事強度：中
- 稼働時間：09:00～16:00 JST
- 散水：なし

「200mm四方」ではなく「200m四方」を想定します。もし設定値の単位が異なる場合に誤動作しないよう、設定キー名に `_m` を付け、画面にも単位を明示してください。

### 4.1 グリッド設定

範囲やメッシュ間隔は将来変更されるため、10m、20m、200m、正方形などをコードへ埋め込まないでください。少なくとも以下の設定を用意します。

```yaml
grid:
  width_m: 200.0
  height_m: 200.0
  cell_size_x_m: 20.0
  cell_size_y_m: 20.0
  rotation_deg: 0.0
  source_position_mode: offset_m
  source_offset_x_m: -20.0
  source_offset_y_m: -40.0
  edge_policy: error       # error / trim / pad
  max_cells: 10000
```

以下を満たしてください。

- `nx = width_m / cell_size_x_m`、`ny = height_m / cell_size_y_m` を実行時に算出する
- 正方形範囲、正方形セルを前提にしない
- 割り切れない場合の扱いを `edge_policy` で明示する
- `error` は設定エラー、`trim` は内側へ切り詰め、`pad` は外側へ拡張する
- 実際に使用した範囲、セル間隔、nx、ny、総セル数をログ・CSV・JSON・図へ記録する
- 総セル数が `max_cells` を超える場合は警告またはエラーとする
- 作業現場は中央固定にせず、緯度経度指定、中心からのオフセット指定、行列番号指定のいずれかに対応できる設計にする
- 画面サイズやフォントをセル数に応じて調整し、10×10、20×20、40×30程度でも表示が破綻しないようにする

最低限、次の設定を自動テストしてください。

- 200m×200m、20mセル → 10×10＝100セル
- 200m×200m、10mセル → 20×20＝400セル
- 500m×300m、25mセル → 20×12＝240セル
- 幅がセル間隔で割り切れない設定に対する各 `edge_policy` の挙動

今回のGSMは0.1度×0.125度格子であり、20mまたは10m解像度の気象予測ではありません。GSMの現場地点風を最近傍または双線形補間で取得し、その風をローカルメッシュ全体に一様に与える方式としてください。この制約を画面とREADMEに明記してください。

デフォルト表示期間は、入力ファイルで利用できる以下の時間帯とします。

- 2023-03-15 09:00～16:00 JST
- 初期時刻12UTCから見て、おおむねFT12～FT19

## 5. GRIB2読込要件

### 5.1 要素の特定

名称・shortNameだけに依存せず、必要に応じて以下のGRIB2識別情報をフォールバックとして使用してください。

- 10m U風：discipline=0, parameterCategory=2, parameterNumber=2, typeOfFirstFixedSurface=103, level=10
- 10m V風：discipline=0, parameterCategory=2, parameterNumber=3, typeOfFirstFixedSurface=103, level=10
- 2m気温：discipline=0, parameterCategory=0, parameterNumber=0, typeOfFirstFixedSurface=103, level=2
- 2m相対湿度：discipline=0, parameterCategory=1, parameterNumber=1, typeOfFirstFixedSurface=103, level=2
- 全雲量：discipline=0, parameterCategory=6, parameterNumber=1
- 積算降水量：discipline=0, parameterCategory=1, parameterNumber=8, 統計処理テンプレート

全フィールドについて、少なくとも次の情報をインベントリCSVに出力してください。

- record_index
- name
- shortName
- discipline
- parameterCategory
- parameterNumber
- typeOfLevel
- level
- forecastTime
- stepRange
- validDate
- units
- gridType
- Ni/Nj

### 5.2 現場地点への補間

- 緯度・経度配列の昇順・降順を確認する
- 双線形補間を基本とする
- 補間不能時は最近傍へフォールバックし、ログに残す
- 取得した元格子点または補間に使った4格子点を計算トレースへ出力する

### 5.3 風向・風速

Uは東向き正、Vは北向き正として扱います。

```text
風速 = sqrt(U^2 + V^2)
```

気象学的な「風向」は風が吹いてくる方向です。

```text
wind_from_deg = (degrees(atan2(-U, -V)) + 360) % 360
```

画面の「飛散注意方向」は粉じんが流れていく風下方向です。

```text
downwind_to_deg = (degrees(atan2(U, V)) + 360) % 360
```

風向と飛散方向を混同しないでください。16方位の日本語名称と英字略号を返す共通関数を作り、単体テストを作成してください。

### 5.4 時間降水量

入力は初期時刻からの積算降水量である可能性があります。`forecastTime` だけで判断せず、`validDate`、`stepRange`、`endStep` 等を確認してください。

時間降水量は原則として次の差分で求めます。

```text
hourly_precip(t) = max(accum_precip(t) - accum_precip(t-1), 0)
```

積算のリセットや欠損があれば警告ログを出し、処理方針をREADMEに記載してください。

## 6. 粉じん飛散リスク計算

### 6.1 座標系

現場を中心とするローカル平面直角座標を使用してください。

- x：東向き[m]
- y：北向き[m]
- 現場中心の局所Azimuthal Equidistant座標、または妥当なUTM座標を `pyproj` で構築
- 設定された `cell_size_x_m`、`cell_size_y_m` に従ってセル中心座標を生成
- 地図は北を上、東を右に描画

### 6.2 モデルの位置づけ

これは物理濃度を直接算出するGaussian Plumeの厳密実装ではなく、説明可能な相対リスクモデルです。ロジックを `src/dust_forecast/model.py` に独立させ、UIから分離してください。

各セル中心について、発生源からの相対座標を `(x, y)`、風ベクトルを `(U, V)`、風速を `S` とします。

```text
S = sqrt(U^2 + V^2)

s = (x*U + y*V) / max(S, eps)          # 風下距離
c = (-x*V + y*U) / max(S, eps)         # 横風方向距離
```

`s < 0` は基本的に風上側とし、低いバックグラウンド値または0とします。

以下を初期モデルとし、全係数をYAMLで変更可能にしてください。

```text
E_base:
  small  = 0.6
  medium = 1.0
  large  = 1.5

wind_activation = clip((S - wind_start) / (wind_full - wind_start), 0, wind_max_factor)

rain_factor:
  hourly_precip < 0.1 mm/h       -> 1.00
  0.1 <= precip < 1.0 mm/h       -> 0.70
  1.0 <= precip < 3.0 mm/h       -> 0.40
  precip >= 3.0 mm/h             -> 0.15

mitigation_factor:
  none    = 1.00
  normal  = 0.60
  strong  = 0.35

sigma_y(s) = sigma0 + spread_rate * max(s, 0)
L(S)       = decay_base + decay_per_ms * S

downwind_decay = exp(-max(s, 0) / L)
crosswind_spread = exp(-0.5 * (c / sigma_y)^2)

raw_risk = 100 * E_base * wind_activation * rain_factor \
           * mitigation_factor * downwind_decay * crosswind_spread

risk = clip(raw_risk, 0, 100)
```

推奨初期値：

```yaml
model:
  wind_start_mps: 0.5
  wind_full_mps: 4.0
  wind_max_factor: 1.2
  sigma0_m: 8.0
  spread_rate: 0.18
  decay_base_m: 35.0
  decay_per_ms: 18.0
  upwind_background: 0.0
```

無風または風速0.3m/s未満の場合、特定方向へ細長く伸ばさず、発生源周辺に弱い等方分布を与える分岐を実装してください。

### 6.3 色分け

初期しきい値は以下とし、YAMLから変更可能にしてください。

```yaml
thresholds:
  low_max: 25
  moderate_max: 50
  high_max: 75
```

表示区分：

- 0～25：少ない
- 25超～50：やや多い
- 50超～75：多い
- 75超～100：非常に多い

時刻ごとの最大値で再正規化しないでください。時刻間で比較できる固定スケールとします。

## 7. 追跡可能性・説明可能性

情シスへ計算根拠を示せるよう、各時刻・各セルについて以下をCSVに出力してください。

- valid_time_utc
- valid_time_jst
- row
- column
- center_x_m
- center_y_m
- latitude
- longitude
- source_x_m
- source_y_m
- grid_width_m
- grid_height_m
- cell_size_x_m
- cell_size_y_m
- nx
- ny
- u10_mps
- v10_mps
- wind_speed_mps
- wind_from_deg
- downwind_to_deg
- hourly_precip_mm
- emission_factor
- wind_activation
- rain_factor
- mitigation_factor
- downwind_distance_m
- crosswind_distance_m
- sigma_y_m
- downwind_decay
- crosswind_spread
- raw_risk
- risk
- category

また、時刻ごとに次をJSONへ出力してください。

- 入力ファイル名
- 初期時刻
- 予報時刻
- 現場座標
- グリッド幅・高さ・セル間隔・nx・ny・回転角
- 補間方式
- 使用したGRIBフィールド
- 使用係数
- 計算式のバージョン
- しきい値
- 最大リスク値
- 最大リスクのセル位置
- 警告事項

## 8. 可視化要件

### 8.1 時刻別マップ

Matplotlibで、時刻ごとにPNGを作成してください。

- 設定された幅・高さに追従
- 設定されたメッシュ間隔とnx×nyに追従
- 北が上、東が右
- 作業現場アイコンまたは明確な記号
- 風向矢印は「風が流れていく方向」を示す
- 4段階色分け
- 凡例
- スケールバー
- 初期時刻・予報時刻（UTC/JST）
- 風向、風速、時間降水量
- 工事強度、散水有無
- フッター：`気象データ出典：気象庁 GSM GPV` と `相対飛散リスクの試算値` を表示

背景は当初、オフラインで動く簡易平面図とします。

- 道路・建物を模した簡易背景を固定乱数で生成してもよい
- または、ユーザーが背景PNG/JPGをアップロードし、範囲に重ねられる機能を追加する
- オンライン地図は任意機能とし、必須にしない

### 8.2 総合ダッシュボード画像

説明資料用に、次の要素を1枚にまとめたPNGも出力してください。

- タイトル
- 選択時刻の飛散リスクマップ
- 凡例
- 時刻別一覧表（09～16時）
- 入力条件
- 計算モデルの注意書き

AI画像生成ではなく、実際のGRIB値と計算結果から決定的に再生成できるMatplotlib出力としてください。

### 8.3 Streamlit画面

画面に以下を用意してください。

- GRIB2ファイル選択
- 現場名
- 緯度・経度
- 表示範囲（幅・高さ）
- メッシュサイズ（x方向・y方向）
- グリッド回転角
- 作業現場位置
- 工事強度
- 稼働時間
- 散水レベル
- 対象時刻選択
- マップ表示
- 時刻別一覧
- 入力気象値
- 計算式・係数の表示
- 選択セルの中間計算値表示
- CSV/JSON/PNGのダウンロード
- 「本モデルは相対リスクであり、濃度予測ではない」という注意書き

## 9. 天気表示

画面上の天気は、GSMの時間降水量と全雲量から作る簡易判定とし、気象庁の正式な天気予報表現ではないことを表示してください。

例：

```text
時間降水量 >= 1.0 mm/h  -> 雨
0.1～1.0 mm/h            -> 弱い雨
降水なし・全雲量 >= 80%  -> くもり
全雲量 50～80%           -> 晴れ時々くもり
全雲量 < 50%             -> 晴れ
```

しきい値は設定ファイルへ出してください。

## 10. 推奨フォルダ構成

```text
dust-dispersion-demo/
├─ README.md
├─ LICENSE_NOTICE.md
├─ CHANGELOG.md
├─ environment.yml
├─ requirements.txt
├─ pyproject.toml
├─ .gitignore
├─ app.py
├─ run_app.bat
├─ run_generate.bat
├─ config/
│  ├─ sample.yaml
│  ├─ sample_10m.yaml
│  └─ schema.md
├─ reference/
│  ├─ wxbcgribx.py
│  ├─ wxparams.py
│  └─ README.md
├─ data/
│  ├─ input/
│  │  └─ .gitkeep
│  └─ background/
│     └─ .gitkeep
├─ src/
│  └─ dust_forecast/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ grib_reader.py
│     ├─ readers/
│     │  ├─ __init__.py
│     │  ├─ base.py
│     │  ├─ wgrib2_netcdf.py
│     │  ├─ pygrib_reader.py
│     │  └─ cfgrib_reader.py
│     ├─ interpolation.py
│     ├─ wind.py
│     ├─ precipitation.py
│     ├─ grid.py
│     ├─ model.py
│     ├─ categories.py
│     ├─ plotting.py
│     ├─ reports.py
│     └─ logging_config.py
├─ tests/
│  ├─ test_wind.py
│  ├─ test_precipitation.py
│  ├─ test_grid.py
│  ├─ test_model.py
│  ├─ test_categories.py
│  └─ test_integration_sample_grib.py
├─ docs/
│  ├─ architecture.md
│  ├─ model_spec.md
│  ├─ grib_spec.md
│  ├─ provenance.md
│  ├─ data_dictionary.md
│  ├─ handoff_checklist.md
│  └─ limitations.md
└─ outputs/
```

## 11. テスト要件

最低限、以下をテストしてください。

1. U=1, V=0のとき、風向は西、飛散方向は東になる
2. U=0, V=1のとき、風向は南、飛散方向は北になる
3. 発生源の風下側が風上側より高リスクになる
4. 横風距離が大きいほどリスクが低下する
5. 距離が遠いほどリスクが低下する
6. 降水量が増えるほどリスクが低下する
7. 散水ありでリスクが低下する
8. 同じ入力なら同じ出力になる
9. 色区分の境界値が正しい
10. 積算降水量から時間降水量を正しく差分化する
11. GRIBファイルが存在する場合、09～16時JSTの8時刻を抽出できる
12. 各時刻の出力セル数が、設定から算出した `nx × ny` と一致する
13. 20m/200m、10m/200m、25m/500m×300mの各設定でグリッドが正しく生成される
14. `wgrib2` Readerのコマンド組立て、エラー処理、一時ファイル削除をテストする
15. 風向・16方位変換がスカラーとNumPy配列の両方で正しく動く

外部ファイルを必要としない単体テストを中心にし、GRIB統合テストはサンプルファイルがある場合のみ実行してください。

## 12. 受入条件

以下を満たすまで作業を完了扱いにしないでください。

- `inspect-grib` が実ファイルを読み、インベントリCSVを出力する
- 2023-03-15 09:00～16:00 JSTの気象値を抽出する
- 8時刻分のメッシュ計算を実施する
- 各時刻について、設定から算出した `nx × ny` セルの詳細CSVを出力する
- 時刻別PNGを8枚出力する
- 一覧表付き総合ダッシュボードPNGを1枚出力する
- Streamlitで時刻を切り替えて表示できる
- 計算式・係数・中間値を画面または出力ファイルで確認できる
- `pytest` が成功する
- READMEの手順だけで別PCに再構築できる
- 絶対パスや個人名がコードに残っていない
- `wgrib2` の所在を設定またはPATHから解決できる
- 20m/200mと10m/200mの設定変更がコード修正なしで動く
- 参考コードの流用範囲・著作権表示・独自実装箇所が `docs/provenance.md` と `LICENSE_NOTICE.md` で確認できる
- 入力GRIB2本体がGit管理対象外になっている

## 13. 作業の進め方

次の順序で進めてください。

### Phase 0：確認

- 現在の作業ディレクトリとPython環境を確認
- 入力GRIB2の存在を確認
- 利用可能なGRIBライブラリと `wgrib2` 実行環境を確認
- `reference/wxbcgribx.py` と `reference/wxparams.py` を読み、利用可能部分・改善点・ライセンス上の扱いを `docs/provenance.md` に記録
- `wgrib2 → NetCDF → xarray`、pygrib、cfgribのうち利用可能な方式を実ファイルで比較
- ファイルのインベントリを取得
- 実際に取得できる要素名・時刻・単位を報告

### Phase 1：設計

- フォルダ構成を作る
- 設定スキーマを定義
- GRIB Reader Adapter、補間、可変グリッド、計算、表示のインターフェースを決める
- `docs/architecture.md` と `docs/model_spec.md` を先に作る

### Phase 2：コア実装

- GRIB読込
- 風向・風速
- 積算降水差分
- 設定駆動の可変ローカルメッシュ
- 相対リスク計算
- 中間値出力

### Phase 3：可視化・画面

- Matplotlib時刻別図
- 総合ダッシュボード図
- Streamlit画面

### Phase 4：検証・引渡し

- pytest
- 実ファイルによる統合試験
- 出力例の確認
- README、制約、引渡しチェックリストを完成

各Phaseの終了時に、実施内容、生成・変更ファイル、実行したコマンド、確認結果、未解決事項を簡潔に報告してください。計画だけで止まらず、実際にファイルを作成し、可能な範囲でコマンドを実行して結果を確認してください。エラーが発生した場合は、原因を調査して修正・再実行し、単なる回避やモック値への置換で完了扱いにしないでください。大きな設計判断はADRまたは `docs/architecture.md` に記録してください。

## 14. 重要な注意

- 粉じん濃度の厳密な法令・環境基準判定には使わない
- 10m・20m等のローカルメッシュは表示・局所拡散計算の解像度であり、GSMの気象解像度ではない
- 建物による風の回り込みや乱流は未考慮
- 発生量は工事種類・土質・含水率・車両走行等で変わるため、現段階は設定値
- 将来的には現地風向風速計、粉じん計、散水実績を用いて係数を校正する
- 出力図には必ず「テスト版」「相対リスク」「気象データ出典」を明記する

## 15. Claude Codeでの実行方針

この依頼はClaude Code上でエージェント的に実行してください。まずリポジトリを調査し、Phase 0の結果を短く提示した後、そのまま実装・実行・テストへ進んでください。

- 既存ファイルを読む前に上書きしない
- 変更前にGitの状態を確認する
- 小さな単位で実装し、各段階でテストする
- 実行不能なコマンドがある場合は、必要なインストール手順と検証コマンドを明示する
- ユーザーにしか判断できない業務仕様以外は、合理的な仮定を明記して先へ進む
- 最終報告では、起動方法、生成物、テスト結果、未実装事項、情シスへの引渡し時の注意をまとめる

作業を開始してください。最初にPhase 0を実施し、入力ファイルの実際のインベントリ、参考コードの評価、採用するGRIB読込方式、デフォルト20m/200m設定から算出される格子数を示してから実装へ進んでください。
