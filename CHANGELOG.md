# Changelog

## 0.1.0 (テスト版初版)

- GSM GPV(GRIB2)読込のReader Adapter実装(cfgrib標準、wgrib2_netcdf代替、pygrib未対応プレースホルダ)
- 風向・風速・飛散方向・16方位変換(スカラー/配列両対応)
- 積算降水量からの時間降水量差分
- 設定駆動の可変ローカルメッシュ生成(pyproj方位等距離図法)
- 説明可能な相対飛散リスクモデル(0-100)
- 4段階色分け・簡易天気判定
- 時刻別リスクマップ・総合ダッシュボードPNG出力
- 中間計算値のCSV/JSON出力(追跡可能性)
- CLI(`inspect-grib`, `generate`)とStreamlit画面
- pytest単体テスト・実GRIB統合テスト一式(71件)
