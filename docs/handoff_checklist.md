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
| 7 | Streamlitで時刻を切り替えて表示できる | 🟡 | サーバ起動・例外無しレンダリングまで確認。ブラウザでの実操作確認は`docs/limitations.md`参照 |
| 8 | 計算式・係数・中間値を画面または出力ファイルで確認できる | ✅ | CSV/JSON、Streamlit画面の「計算式・係数」セクション |
| 9 | `pytest` が成功する | ✅ | 71件全件成功(実GRIB統合テスト含む) |
| 10 | READMEの手順だけで別PCに再構築できる | ✅ | `README.md` にwgrib2導入・環境構築手順を記載 |
| 11 | 絶対パスや個人名がコードに残っていない | ✅ | `paths.py`へ集約。grep確認済み(下記) |
| 12 | `wgrib2` の所在を設定またはPATHから解決できる | ✅ | `resolve_wgrib2_exe()`(設定→環境変数→PATH→既定探索) |
| 13 | 20m/200mと10m/200mの設定変更がコード修正なしで動く | ✅ | `config/sample.yaml` と `config/sample_10m.yaml`、テスト済み |
| 14 | 参考コードの流用範囲・著作権表示・独自実装箇所が確認できる | ✅ | `docs/provenance.md`, `LICENSE_NOTICE.md` |
| 15 | 入力GRIB2本体がGit管理対象外になっている | ✅ | `.gitignore` の `data/input/*.bin` |

## 情シスへの引渡し時の注意

- `wgrib2.exe` を使う場合(`reader_backend: wgrib2_netcdf`)は別途導入が必要。
  既定の `reader_backend: cfgrib` は `pip install -e .` のみで動作する。
- 大容量の入力GRIB2ファイルはGit管理対象外。別途配布・配置手順を社内で
  合意すること。
- 本モデルは相対リスクのテスト版であり、法令・環境基準の判定には使用しない
  (`docs/limitations.md`)。
- Streamlitの対話操作(ボタン押下後の画面遷移)は、Chrome拡張等を用いた
  自動化テストまでは実施していない。引渡し前に手動でのブラウザ確認を推奨する。
