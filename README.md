# dust-dispersion-demo — 粉じん飛散リスク テスト版

気象庁GSM GPV(GRIB2)の予測値を読み込み、工事現場周辺の可変ローカルメッシュ
(既定20m×20m、200m×200m = 10×10セル)ごとに「相対的な粉じん飛散リスク」
(0-100の説明可能なスコア)を時刻別に計算・色分け表示するテスト版です。

**本モデルは粉じん濃度[μg/m³]を厳密に予測するものではありません。**
気象条件と工事条件から算出する、説明可能な「相対飛散リスクモデル」です。
法令・環境基準の判定には使用しないでください(詳細は `docs/limitations.md`)。

## 1. 前提条件 (Windows)

- Python 3.11 (Windows 10/11)
- 既存のconda環境がある場合はそれを使用可能。新規作成する場合は
  [`environment.yml`](environment.yml) または [`requirements.txt`](requirements.txt) を使用
- GRIB Readerは既定で **cfgrib**(pip配布のecCodesバイナリ同梱版)を使用するため、
  追加の外部実行ファイルは不要です
- 代替Readerとして `wgrib2.exe` を使う場合のみ、別途導入が必要です(3章参照)

## 2. セットアップ

### 2.1 既存のconda環境を使う場合(推奨)

```powershell
conda activate <既存の環境名>
cd dust-dispersion-demo
pip install -e .
```

### 2.2 新規に環境を作る場合

```powershell
conda env create -f environment.yml
conda activate dust-forecast
cd dust-dispersion-demo
pip install -e .
```

または pip のみ:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## 3. wgrib2 について(任意)

既定のGRIB Reader(`reader_backend: cfgrib`)は `wgrib2.exe` を必要としません。
`config/*.yaml` の `grib.reader_backend` を `wgrib2_netcdf` に変更した場合のみ、
以下が必要です。

- 検証済みバージョン: wgrib2 v3.1.1 (Wesley Ebisuzaki他)
- 入手: [NOAA/NCEP wgrib2 配布ページ](https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/) 等からWindows版バイナリを取得
- 配置後、以下いずれかの方法で場所を指定する(優先順):
  1. `config/*.yaml` の `grib.wgrib2_exe` にフルパスを記載
  2. 環境変数 `DUST_FORECAST_WGRIB2` にフルパスを設定
  3. `wgrib2`/`wgrib2.exe` を PATH に追加
  4. 上記が無い場合、既定の探索候補ディレクトリ(例: `C:\wgrib2\`)を自動探索

パスをコード中にハードコードすることはありません
(`src/dust_forecast/readers/wgrib2_netcdf.py` の `resolve_wgrib2_exe()`)。

## 4. データ配置

入力GRIB2ファイルを `data/input/` に配置してください
(大容量のため `.gitignore` によりGit管理対象外です)。

```
data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin
```

## 5. 使い方

### 5.1 GRIB2インベントリの確認

```powershell
python -m dust_forecast.cli inspect-grib --input data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin
```

`outputs/grib_inventory.csv` にレコード一覧(discipline/parameterCategory/
parameterNumber等を含む)が出力されます。

### 5.2 リスクマップ・CSV/JSON生成

```powershell
python -m dust_forecast.cli generate `
  --input data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin `
  --config config/sample.yaml
```

以下が `outputs/` 配下に生成されます。

- `maps/map_<validTimeUTC>.png` — 時刻別リスクマップ(8枚)
- `dashboard.png` — 総合ダッシュボード(選択時刻のマップ+時刻別一覧表)
- `cells/cells_<validTimeUTC>.csv` — 時刻ごとの全セル中間計算値
- `summary/summary_<validTimeUTC>.json` — 時刻ごとの計算根拠サマリ

Windowsでは `run_generate.bat <GRIB2ファイル> [設定YAML]` からも実行できます。

### 5.3 Streamlit画面

```powershell
streamlit run app.py
```

または `run_app.bat`。サイドバーで現場・グリッド・工事条件を設定し、
「計算実行」を押すとマップ・時刻別一覧・CSV/JSON/PNGダウンロードが表示されます。

### 5.4 テスト

```powershell
pytest
```

`data/input/*.bin` が存在する環境では、実GRIB2ファイルを使った統合テスト
(`tests/test_integration_sample_grib.py`)も自動的に実行されます。
存在しない環境では自動的にスキップされます。

## 6. 設定ファイル

`config/sample.yaml`(20m×20mメッシュ)と `config/sample_10m.yaml`
(10m×10mメッシュ)を用意しています。スキーマの詳細は
[`config/schema.md`](config/schema.md) を参照してください。

範囲・メッシュ間隔・格子数はすべて設定ファイルから実行時に算出されるため、
コード修正は不要です。

## 7. フォルダ構成

```
dust-dispersion-demo/
├─ app.py                  # Streamlit画面
├─ config/                 # 設定ファイル(YAML)とスキーマ文書
├─ data/
│  ├─ input/                # GRIB2入力(.binはGit管理対象外)
│  └─ background/           # 背景画像(任意)
├─ reference/               # 設計参考コード(docs/provenance.md参照)
├─ src/dust_forecast/        # 本体パッケージ
├─ tests/                    # pytestテスト
├─ docs/                     # 設計文書・仕様メモ
└─ outputs/                  # 生成物(Git管理対象外)
```

詳細な設計は [`docs/architecture.md`](docs/architecture.md)、計算式は
[`docs/model_spec.md`](docs/model_spec.md) を参照してください。

## 8. ドキュメント一覧

| ファイル | 内容 |
|---|---|
| `docs/architecture.md` | モジュール構成・データフロー・設計判断 |
| `docs/model_spec.md` | 相対飛散リスクモデルの計算式 |
| `docs/grib_spec.md` | GRIB2の要素識別・時刻の扱い |
| `docs/data_dictionary.md` | CSV/JSON出力の列・キー定義 |
| `docs/provenance.md` | 参考コードの評価・流用範囲・Reader方式比較 |
| `docs/limitations.md` | モデルの制約事項 |
| `docs/handoff_checklist.md` | 受入条件チェックリスト |
| `LICENSE_NOTICE.md` | サードパーティ著作権表示 |
| `CLAUDE.md` | 開発時の設計原則・禁止事項・テスト手順 |

## 9. 既知の制約

GSMの気象格子(約10km)はローカルメッシュ(10-20m)より大幅に粗いため、
現場地点で補間した風・降水量をローカルメッシュ全体に一様に与える方式です。
建物風の回り込み・乱流は未考慮です。詳細は `docs/limitations.md` を参照。
