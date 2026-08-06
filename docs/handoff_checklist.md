# 引渡しチェックリスト (仕様書12章 受入条件)

実ファイル `data/input/Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin`
を用いて確認した結果。

| # | 受入条件 | 状態 | 備考 |
|---|---|---|---|
| 1 | `inspect-grib` が実ファイルを読み、インベントリCSVを出力する | ✅ | `outputs/grib_inventory.csv`、298レコード |
| 2 | 2023-03-15 09:00〜16:00 JSTの気象値を抽出する | ✅ | `test_run_pipeline_extracts_8_target_hours_09_16_jst` |
| 3 | 8時刻分のメッシュ計算を実施する | ✅ | 同上 |
| 4 | 各時刻について、設定から算出したnx×ny セルの詳細CSVを出力する | ✅ | `outputs/cells/*.csv`、100行/時刻(既定設定) |
| 5 | 時刻別PNGを8枚出力する | ✅ | `outputs/maps/*.png` |
| 6 | 一覧表付き総合ダッシュボードPNGを1枚出力する | ✅ | `outputs/dashboard.png` |
| 7 | Streamlitで時刻を切り替えて表示できる | ✅ | 手動ブラウザ確認済み。計算実行、時刻切り替え、メッシュ設定変更、CSV/JSON/PNGダウンロード、現場位置概略図の表示を一通り目視確認した |
| 8 | 計算式・係数・中間値を画面または出力ファイルで確認できる | ✅ | CSV/JSON、Streamlit画面の「計算式・係数」セクション |
| 9 | `pytest` が成功する | ✅ | 77件全件成功(実GRIB統合テスト含む) |
| 10 | READMEの手順だけで別PCに再構築できる | ✅ | `README.md` にwgrib2導入・環境構築手順を記載 |
| 11 | 絶対パスや個人名がコードに残っていない | ✅ | `paths.py`へ集約。grep確認済み(下記) |
| 12 | `wgrib2` の所在を設定またはPATHから解決できる | ✅ | `resolve_wgrib2_exe()`(設定→環境変数→PATH→既定探索) |
| 13 | 20m/200mと10m/200mの設定変更がコード修正なしで動く | ✅ | `config/sample.yaml` と `config/sample_10m.yaml`、テスト済み |
| 14 | 参考コードの流用範囲・著作権表示・独自実装箇所が確認できる | ✅ | `docs/provenance.md`, `LICENSE_NOTICE.md` |
| 15 | 入力GRIB2本体がGit管理対象外になっている | ✅ | `.gitignore` の `data/input/*.bin` |
| 16 | `model.py`(粉じん拡散リスク計算ロジック)が、GRIB2読込・Streamlit UIに一切依存せず、風向風速・降水量の取得元を問わず独立して呼び出せることを実行時に検証済み | ✅ | `xarray`/`cfgrib`/`eccodes`/`pygrib`/`streamlit`のimportを強制ブロックした状態で`compute_risk()`が正常動作することを確認した。将来的に社内の別システムへ計算ロジックのみを移植することを想定した検証であり、詳細は`docs/model_spec.md`の0章・10章を参照。`location_map.py`(現場位置の簡易概略図)についても同様の独立性検証(GRIB/UI非依存の静的import検査)を行っている |

## Streamlit画面の追加機能(社内フィードバック反映)

- 作業現場位置のオフセット既定値を `source_offset_x_m`/`source_offset_y_m` ともに
  `0.0`(表示範囲中央)へ変更(`config/sample.yaml`, `config/sample_10m.yaml`)。
- 時刻選択UIの初期表示を、対象期間の最初の時刻(2023-03-15 09:00 JST)に変更。
- 現場緯度経度が日本列島のどのあたりかを示す簡易概略図をサイドバーに追加
  (`location_map.py`、オンライン地図・外部地理データ不使用、オフライン動作)。

## 情シスへの引渡し時の注意

- `wgrib2.exe` を使う場合(`reader_backend: wgrib2_netcdf`)は別途導入が必要。
  既定の `reader_backend: cfgrib` は `pip install -e .` のみで動作する。
- 大容量の入力GRIB2ファイルはGit管理対象外。別途配布・配置手順を社内で
  合意すること。
- 本モデルは相対リスクのテスト版であり、法令・環境基準の判定には使用しない
  (`docs/limitations.md`)。
- Streamlitの対話操作(計算実行、時刻切り替え、メッシュ設定変更、CSV/JSON/PNG
  ダウンロード、現場位置概略図の表示)は手動ブラウザ確認済み(項目7参照)。
  ただしChrome拡張等を用いた自動化E2Eテストまでは整備していない。設定値を
  変更した場合は、引渡し前に改めて手動確認することを推奨する。
