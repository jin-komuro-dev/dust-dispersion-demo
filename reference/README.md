# reference/ フォルダについて

このフォルダは設計参考資料であり、本体コード(`src/dust_forecast/`)から
importされることはない。流用範囲・ライセンス表示・独自実装への置き換えの
詳細は `../docs/provenance.md` と `../LICENSE_NOTICE.md` を参照。

- `wxbcgribx.py` — wgrib2呼び出し・GRIB2読込の参考実装(MIT License)
- `wxparams.py` — 風向風速・気象パラメータ計算の参考実装(ライセンス条文なし、著作権表示のみ)
- `examples/GSM_new_deployment_20250415.py` — 上記2ファイルを実際に使っていた
  本番運用スクリプトの例。`getgpv`/`UV_to_SpdDir`/`Deg_to_Dir16` の実際の
  呼び出し方の確認用途。ハードコードされたドライブパス(`E:/...`)等は
  本プロジェクトでは踏襲していない。
