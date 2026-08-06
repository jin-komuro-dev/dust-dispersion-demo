# CLAUDE.md

このファイルは、Claude Code(および他の開発者)が本リポジトリで継続して
作業する際のガイドです。

## プロジェクト概要

気象庁GSM GPV(GRIB2)を読み込み、工事現場周辺の可変ローカルメッシュ
(既定20m x 20m, 200m x 200m = 10x10セル)ごとに「相対的な粉じん飛散リスク」
(0-100の説明可能なスコア。物理濃度[μg/m³]の厳密予測ではない)を時刻別に
計算・可視化するテスト版。詳細仕様は `claude_code_dust_forecast_prompt_v2.md`
を参照。

## 実行コマンド

```powershell
# 環境(既存condaを使う場合。新規作成は不要)
conda activate <既存のconda環境名>
pip install -e .

# GRIB2インベントリ確認
python -m dust_forecast.cli inspect-grib --input data/input/<file>.bin

# メッシュ計算・図・CSV/JSON出力
python -m dust_forecast.cli generate --input data/input/<file>.bin --config config/sample.yaml

# Streamlit画面
streamlit run app.py

# テスト
pytest
```

Windowsでは `run_app.bat` / `run_generate.bat` からも起動できる。

## 設計原則

- **ロジックと画面の分離**: 計算ロジックは `src/dust_forecast/*.py` に置き、
  `cli.py` の `run_pipeline()` をCLIとStreamlit(`app.py`)の両方から呼び出す。
  `app.py` に計算ロジックを書かない。
- **設定駆動**: グリッド仕様・モデル係数・しきい値は `config/*.yaml` から
  `pydantic` モデル(`config.py`)経由で読み込む。数値をコードへ埋め込まない。
- **パスは1箇所で定義する**: 全パス定数は `src/dust_forecast/paths.py` に
  集約し、`Path(__file__)` 基準で解決する。他のファイルでパス文字列を
  コピペ・再定義しない。
- **Reader Adapterパターン**: GRIB読込は `readers/base.py` の
  `BaseGribReader` インターフェースに従う。呼出側は `grib_reader.get_reader()`
  経由でのみ具象クラスを取得し、`CfgribReader`/`Wgrib2NetcdfReader` を
  直接importしない。
- **要素識別はGRIB2識別情報を優先**: JMA GSMの積算降水量・全雲量はecCodesの
  既定テーブルで `shortName` が `unknown` になる。`discipline` /
  `parameterCategory` / `parameterNumber` による識別(`readers/base.py` の
  `STANDARD_FIELDS`)を必ず使う。
- **例外は独自例外に変換する**: `readers/base.py` の `GribReaderError` 系
  例外を使う。ライブラリ内部で `sys.exit()` を呼ばない。
- **追跡可能性**: 各時刻・各セルの中間計算値は `reports.py` 経由でCSV/JSONに
  出力する。新しい計算項目を追加したら `reports.CELL_CSV_COLUMNS` と
  `docs/data_dictionary.md` も更新する。
- **時刻ごとの色スケール固定**: `plotting.py` は時刻の最大値で再正規化しない。
  `config.thresholds` の固定しきい値を使う。

## 禁止事項

- 絶対パス・個人のユーザー名・特定ドライブ(例: `C:/Users/xxx/...`,
  `E:/...`)をコードへハードコードしない。
- `wgrib2.exe` のパスをハードコードしない。設定 > 環境変数
  (`DUST_FORECAST_WGRIB2`) > PATH > 既定探索の順で解決する
  (`readers/wgrib2_netcdf.resolve_wgrib2_exe`)。
- `shell=True` や `pushd` に依存したサブプロセス呼び出しを追加しない。
  `subprocess.run(cmd_list, cwd=...)` を使う。
- GRIB2を読めない状態を「架空値への置換」で誤魔化して完了扱いにしない。
- 20m/200m、10m/200m等のメッシュ設定値をコードへ埋め込まない
  (`config/*.yaml` で完結させる)。
- ライブラリ内部での `sys.exit()` 呼び出し。
- `data/input/*.bin` (入力GRIB2本体)をGitへコミットしない
  (`.gitignore` 済み)。

## テスト手順

```powershell
pytest            # 単体テスト全件(外部ファイル不要)
pytest -v tests/test_integration_sample_grib.py  # 実GRIB統合テスト(data/input/*.binがある場合のみ実行される)
```

新しい計算ロジックを追加した場合は、対応する `tests/test_*.py` に
境界値・決定性(同じ入力→同じ出力)のテストを追加すること。

## 参考コードの扱い

`reference/` 配下のファイルはコード流用ではなく設計参考資料として扱う。
流用範囲・ライセンス表示は `docs/provenance.md` と `LICENSE_NOTICE.md` を
必ず更新すること(新しい参考ファイルを追加した場合も同様)。
