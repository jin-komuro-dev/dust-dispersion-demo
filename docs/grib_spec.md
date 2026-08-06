# GRIB2仕様メモ (気象庁GSM GPV)

対象ファイル形式: `Z__C_RJTD_YYYYMMDDHHMMSS_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD****-****_grib2.bin`

## 格子仕様(実ファイルで確認済み)

- 緯度: 20.0〜50.0度、0.1度刻み(301点、北から南へ降順)
- 経度: 120.0〜150.0度、0.125度刻み(241点、西から東へ昇順)
- 総格子点数: 301 x 241 = 72,541点
- 予報時間: FT0〜FT24、1時間間隔(検証用サンプルファイルの場合)
- グリッド種別: 正距円筒図法(regular_ll)

## 要素識別 (仕様書5.1節、`readers/base.py` の `STANDARD_FIELDS`)

`shortName` だけに依存すると、積算降水量・全雲量は `unknown` としてデコード
されるため(下表、Phase 0で実機確認済み)、`discipline` /
`parameterCategory` / `parameterNumber` を必ず使う。

| 要素 | discipline | parameterCategory | parameterNumber | typeOfLevel | level | shortName(cfgrib) |
|---|---|---|---|---|---|---|
| 10m U風 | 0 | 2 | 2 | heightAboveGround | 10 | `u10` |
| 10m V風 | 0 | 2 | 3 | heightAboveGround | 10 | `v10` |
| 2m気温 | 0 | 0 | 0 | heightAboveGround | 2 | `t2m` (単位K) |
| 2m相対湿度 | 0 | 1 | 1 | heightAboveGround | 2 | `r2` (単位%) |
| 全雲量 | 0 | 6 | 1 | surface | - | `unknown` (要discipline等での特定) |
| 積算降水量 | 0 | 1 | 8 | surface | - | `unknown` (要discipline等での特定) |

## 時刻の扱い

- 初期時刻(reference time)はUTC。GRIB2ファイル名にも `YYYYMMDDHHMMSS` で含まれる。
- 積算降水量(APCP)は `stepRange` が `"0-N hour acc fcst"` の形式であり、
  **初期時刻からの積算値**である。時間降水量は隣接する積算値の差分で求める
  (`precipitation.hourly_from_accumulated`、仕様書5.4節)。
- forecast hour 0(初期時刻そのもの)にはAPCPフィールドが存在しない
  (積算量が定義上0であるため)。`hourly_from_accumulated` はこれを検知し、
  0として補完してから差分を取る。
- UTC→JST変換は `+9時間`。表示対象期間は既定で2023-03-15 09:00〜16:00 JST
  (初期時刻2023-03-14 12:00 UTCからFT12〜FT19相当)。

## Reader Adapterごとの差異

| 項目 | CfgribReader(標準) | Wgrib2NetcdfReader(代替) |
|---|---|---|
| 時刻の次元名 | `step` (timedelta) + `valid_time`座標 | `time` (絶対時刻) |
| 緯度の並び | 降順(50→20) | 昇順(20→50、wgrib2の`-netcdf`規約) |
| 未知要素の扱い | `shortName="unknown"`、`filter_by_keys`で特定 | wgrib2の`-varX`で discipline/parmcat/parmnum を取得 |
| 中間ファイル | 無し(直接xarrayへロード) | NetCDF一時ファイル(`outputs/_tmp`使用) |

`interpolation.py` は緯度経度の昇順・降順を都度確認するため、
どちらのReaderでも同じ結果になる。

## 既知の制約

- GSMの気象格子間隔は約10km(0.1度×0.125度)であり、ローカルメッシュ
  (10-20m)より2桁以上粗い。現場地点で補間した風・降水量をローカルメッシュ
  全体に一様に適用する(仕様書4.1節)。
- 積算降水量の極小値(例: 0.0004mm)は浮動小数点誤差や空間補間により
  隣接時刻間でわずかに減少することがある。`hourly_from_accumulated` は
  これを検知して警告ログを出し、0へ切り詰める。
