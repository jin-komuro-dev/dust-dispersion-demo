# 参考コードの評価・流用範囲・ライセンス表記 (Provenance)

## 1. reference/wxbcgribx.py

出典: 気象ビジネス推進コンソーシアム 人材育成ワーキンググループ 気象×IT勉強会
ライセンス: MIT License (Copyright 2022)。ファイル冒頭に著作権表示・許諾表示あり。

### 参考にした設計・アイデア(コードの直接流用ではなく、設計参考資料として利用)

- `wgrib2 -match ... -netcdf` によるGRIB2要素抽出とxarrayへのロードという処理経路そのもの
- `-var` / `-ens` によるインベントリ取得の考え方
- 緯度経度範囲のトリミング(`imima`/`trim`)の考え方
- UTC→JST変換(`jst`)の考え方

### 直接流用しなかった/改善した点

`reference/wxbcgribx.py` の `wg2()` 関数は以下の問題があり、本プロジェクトの
`src/dust_forecast/readers/wgrib2_netcdf.py` では踏襲せず独自実装した。

| 問題 | wxbcgribx.pyの実装 | 本プロジェクトでの改善 |
|---|---|---|
| パスのハードコード | `wgrib2 = Path("C:/Users/fctsm_000/wgrib2/wgrib2.exe")` を既定値として保持 | 設定ファイル→環境変数`DUST_FORECAST_WGRIB2`→PATH→既定探索の順に解決する`resolve_wgrib2_exe()` |
| shell実行 | `f'pushd "{parent}" && wgrib2 "{name}" {opt}'` を `shell=True` で実行 | `subprocess.run(cmd_list, cwd=...)` を使用し、引数リストで渡す |
| 日本語/UNCパス対策 | 無し(pushdに依存) | 失敗時にローカル一時フォルダ(`outputs/_tmp`)へ入力ファイルをコピーして1回再試行 |
| 文字コード | `encoding="cp932"` 決め打ち | まずUTF-8で復号を試み、失敗時のみcp932にフォールバック |
| エラー処理 | `sys.exit(1)` をライブラリ内部から呼ぶ | `GribReaderError`系の独自例外を送出し、上位(CLI)で処理する |
| 一時ファイル | `tempfile.TemporaryDirectory()`使用(削除は自動だが日本語ユーザー名配下) | `outputs/_tmp`(ASCIIパス、プロジェクト配下)を使用し、`finally`で確実に削除。理由は下記2章 |
| ログ | `print()`のみ | `logging`モジュールでコマンド・戻り値・stderrを記録。長大な出力はファイルへ退避 |
| テスト容易性 | `subprocess.run`呼び出しが`wg2()`内に直書き | `_invoke_subprocess()`に分離し、単体テストでモック可能にした |

### ライセンス表示について

`wxbcgribx.py` のMITライセンス条文はコード実質流用ではなく設計参考としての利用に留めたが、
著作権表示・許諾表示は `LICENSE_NOTICE.md` に転記した。

## 2. reference/wxparams.py

出典: Yoshiki Kato (Weather Data Science)。ファイルにライセンス条文の明記は無く、
利用条件が不明であるため、**直接のコード流用は行わず、数式を独自に再実装**した。

### 参考にした関数と再実装の方針

| wxparams.pyの関数 | 参考にした内容 | 本プロジェクトでの再実装 |
|---|---|---|
| `UV_to_SpdDir` | `wspd = sqrt(u^2+v^2)`, `wdir = atan2(u,v)+180` という気象学的風向の定式化 | `src/dust_forecast/wind.py` の `uv_to_speed_dir()` で独自実装。仕様書のwind_from_deg式 `(atan2(-U,-V)+360)%360` を採用し、NumPy配列・スカラー双方に対応させた |
| `Deg_to_Dir16` | 360度を16方位へ変換する考え方(22.5度刻み、+11.25度オフセット) | `deg_to_dir16()` で独自実装。日本語名称・英字略号を返すよう拡張し、0m/sを「静穏」として特別扱いする分岐を追加した |

`wxparams.py`のコードをそのまま呼び出す形では利用していない。設計参考資料として使用した旨をここに記録する。

## 3. reference/examples/GSM_new_deployment_20250415.py

`wxbcgribx.py` / `wxparams.py` を実際に使っていた本番運用スクリプトの例として、
プロジェクト開始後に追加された。内容を確認した上で、以下の位置づけで扱う。

### 参考にした使用パターン(設計確認用途、コード流用なし)

- `wx.getgpv(grblist, elements, ncdir="./nc", to_netcdf=False, from_netcdf=False, verbose=False)` のように、
  `to_netcdf=False` を指定すればNetCDFファイルを作らずGRIB2から直接読み出せることを確認した
  (本プロジェクトのcfgrib標準Readerも同様に中間ファイルを作らない方針であり、方向性が一致することの裏付けとした)
- `wp.UV_to_SpdDir(df["UGRD..."], df["VGRD..."])` はpandas Seriesに対してもそのまま動作しており、
  NumPy配列だけでなくpandas Series/スカラーでも動く共通関数にすべきという仕様書の要求と整合することを確認した
- `wp.Deg_to_Dir16(...)` は方位名の配列を1つだけ返す実装(数値コード返却との切替は`numeric`引数)であることを確認した。
  本プロジェクトの `wind.deg_to_dir16()` は(日本語名称, 英字略号)のタプルを返す独自仕様とし、この点は流用せず変更した

### 踏襲しなかった箇所(このプロジェクトの方針に反するため)

| 箇所 | 元スクリプトの実装 | 本プロジェクトでの扱い |
|---|---|---|
| GRIB2格納先 | `grbdir = Path('E:/bin/gsm/20250414gsm/...')` を絶対パスでハードコード | `src/dust_forecast/paths.py` の `DATA_INPUT_DIR`(`Path(__file__)`基準)を使用し、CLIの`--input`で指定する |
| NetCDFキャッシュ先 | `ncdir="./nc"` を相対パスでハードコード(実行時のカレントディレクトリに依存) | 一時ファイルは `paths.ensure_temp_dir()`(`outputs/_tmp`、プロジェクト配下ASCIIパス)を使用する |
| 出力先 | `output_folder = f'E:/csv_files/{product}/test'` をEドライブへ直書き | `paths.ensure_outputs_dir()` (`outputs/`) 配下に統一する |
| 文字コード | CSV出力を `encoding='Shift_JIS'` 固定 | `utf-8-sig` を使用し、Windows(Excel等)でも文字化けしないことを確認した上で統一する |

これらのハードコードされたパス・個人/組織固有のドライブ構成は、
本プロジェクトの「パスをハードコードしない」という方針に反するため一切流用していない。

## 4. GRIB Reader方式の比較 (Phase 0)

実ファイル `data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin`
(Windows 11, Python 3.11.15, `C:\conda-envs\py311`)で3方式を検証した。

| 方式 | 検証結果 |
|---|---|
| `wgrib2 → NetCDF → xarray` | 動作した。`wgrib2.exe`(`C:\wgrib2\wgrib2.exe`, v3.1.1)は既にPATH上に導入済みで、298レコードのインベントリ取得・複数要素の`-netcdf`一括抽出ともに成功した。ただし外部exeへの依存、サブプロセス呼び出し、一時ファイル(NetCDF)が必要になる。**さらに、既定の一時ディレクトリ(`%TEMP%`、日本語ユーザー名を含む)へNetCDFを書き出すと、netCDF4-python(libnetcdf)がそのパスを開けず`FileNotFoundError`になることを実機で確認した。** そのため一時ファイルはプロジェクト配下のASCIIパス(`outputs/_tmp`)に置く実装とした。 |
| `pygrib` | `pip install pygrib` がビルド失敗(`eccodes.h`が見つからない)。pygribはecCodesの開発用ヘッダ・共有ライブラリに対してCソースをビルドする構成だが、conda-forgeにwin-64向けの`eccodes`/`cfgrib`パッケージが存在せず(`PackagesNotFoundError`)、Windows上でのビルド環境を用意できなかった。**本プロジェクトではWindows環境でpygribを採用しない。** |
| `cfgrib` (ecCodes) | `pip install cfgrib eccodes` で導入でき、pip配布のeccodesパッケージにWindows向けの共有ライブラリ本体が同梱されているため、追加のC言語ライブラリ導入無しに実ファイルを読み込めた。ただし、積算降水量(APCP)・全雲量(TCDC)はecCodesの既定パラメータテーブルに shortName の対応が無く `shortName="unknown"` としてデコードされることを確認した(`GRIB_paramId=0`)。`discipline`/`parameterCategory`/`parameterNumber`(それぞれAPCP: 0/1/8, TCDC: 0/6/1)による`filter_by_keys`で正しく要素を特定できることを確認済み。また、多メッセージ読込には`eccodes.codes_grib_multi_support_on()`が必要(cfgribは内部で自動的に有効化している)。 |

### 採用結果

標準Reader (`reader_backend: cfgrib`, 既定) は **CfgribReader** とした。理由:

1. 外部exe(wgrib2.exe)のインストール・PATH設定が不要で、`pip install`のみで情シスへの引渡しが容易
2. サブプロセス呼び出し・一時ファイルが無く、日本語パス問題が(入力ファイル自体のパスを除き)発生しない
3. 実行速度が速い(サブプロセス起動・NetCDF書き出しのオーバーヘッドが無い)

**Wgrib2NetcdfReader** は代替Adapterとして完全に実装し、`config/*.yaml`の`grib.reader_backend`を
`wgrib2_netcdf`に変更するだけで切り替えられる。`wgrib2.exe`が既に導入されている環境や、
cfgribの結果を独立に検証したい場合に利用する。

**PygribReader** はAdapter構造を保つためのプレースホルダとして実装し、呼び出すと
明確なエラーメッセージで`GribReaderError`を送出する。

## 5. 積算降水量・全雲量のGRIB2識別情報 (実機確認済み)

| 要素 | discipline | parameterCategory | parameterNumber | 備考 |
|---|---|---|---|---|
| 10m U風 | 0 | 2 | 2 | shortName=`u10`/`UGRD`で解決可能 |
| 10m V風 | 0 | 2 | 3 | shortName=`v10`/`VGRD`で解決可能 |
| 2m気温 | 0 | 0 | 0 | shortName=`t2m`/`TMP`で解決可能 |
| 2m相対湿度 | 0 | 1 | 1 | shortName=`r2`/`RH`で解決可能 |
| 全雲量 | 0 | 6 | 1 | **shortName=`unknown`。discipline/parameterCategory/parameterNumberでの特定が必須** |
| 積算降水量 | 0 | 1 | 8 | **shortName=`unknown`。同上** |

これはwgrib2の`-varX`出力(`var0_2_1_34_1_8`形式)でも独立に確認しており、
両ツールの結果が一致している。
