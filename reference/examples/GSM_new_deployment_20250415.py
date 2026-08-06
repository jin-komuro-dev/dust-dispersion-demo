#!/usr/bin/env python
# coding: utf-8

# In[3]:


import wxbcgribx as wx
from pathlib import Path
import pandas as pd
import math
import numpy as np
import wxparams as wp
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import reduce
import os
import json
import gc

# ファイルのパス
grbdir = Path('E:/bin/gsm/20250414gsm/202503_GSM_Asia_HiresGlobal/joho645_sample/Asia')

product = 'GSM'

frange_sets = [
    ["FD0000-0100", "FD0101-0200", "FD0201-0300", "FD0301-0400"],
    ["FD0401-0500", "FD0501-0512", "FD0513-0600", "FD0601-0700"],
    ["FD0701-0800", "FD0801-0900", "FD0901-1000", "FD1001-1100"]   
]

__________frange = ["FD0000-0100", "FD0101-0200", "FD0201-0300", "FD0301-0400", "FD0401-0500",
          "FD0501-0512", "FD0513-0600", "FD0601-0700", "FD0701-0800", "FD0801-0900", 
          "FD0901-1000", "FD1001-1100"]
_frange = ["FD0000-0100", "FD0101-0200", "FD0201-0300", "FD0301-0400", "FD0401-0500",
          "FD0501-0512"]
__frange = ["FD0513-0600", "FD0601-0700", "FD0701-0800", "FD0801-0900", "FD0901-1000", "FD1001-1100"]
___frange = ["FD0000-0100"]

elements = ['PRMSL', 'PRES', 'UGRD', 'VGRD', 'TMP', 'RH', 'TCDC', 'LCDC', 'MCDC', 'HCDC', 'APCP', 'DSWRF']
__elements = ['UGRD', 'VGRD']

__json_data = [{
    "code":"---",
    "observatory":"相模湾",
    "kana":"sagami_bay",
    "latitude":35.23026164169609,
    "longitude":139.38284983212495
},
             {
    "code":"---",
    "observatory":"東京湾",
    "kana":"tokyo_bay",
    "latitude":35.54039322851855,
    "longitude":139.91980661923452
             }]

json_data = [{
    "code":"---",
    "observatory":"東京湾",
    "kana":"tokyo_bay",
    "latitude":35.54039322851855,
    "longitude":139.91980661923452
             }]

# 日付と時間範囲の指定
start_date = datetime.strptime('20250114', '%Y%m%d')
end_date = datetime.strptime('20250114', '%Y%m%d')
hours = ['0000', '1200']
__hours = ['0000','0600','1200','1800']

#丸めるための関数
def round_decimal(x):
    return float(Decimal(x).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))

def extract_surface_data(ds, lat, lon, initial_UTC):
    # 任意の緯度経度の地上データを取得
    def sel_and_to_df(var):
        return ds[var].sel(latitude=lat, longitude=lon, method='nearest').to_dataframe()

    df_ugrd = sel_and_to_df('UGRD_10maboveground')
    df_vgrd = sel_and_to_df('VGRD_10maboveground')
    df_tmp  = sel_and_to_df('TMP_2maboveground')

    # マージ
    df_m = pd.merge(df_ugrd, df_vgrd, on=['time', 'latitude', 'longitude'])
    df_m = pd.merge(df_m, df_tmp, on=['time', 'latitude', 'longitude'])

    # 時刻の処理
    df_m['fct(UTC)'] = df_m.index
    df_m['initial(UTC)'] = initial_UTC
    df_m['fct(JST)'] = df_m['fct(UTC)'] + timedelta(hours=9)
    df_m['initial(JST)'] = df_m['initial(UTC)'] + timedelta(hours=9)
    df_m['FT'] = ((df_m['fct(UTC)'] - df_m['initial(UTC)']).dt.total_seconds() / 3600).astype(int)

    # 風速・風向の計算
    df_m["wspd_wx_surface"], df_m["wdir_wx_surface"] = wp.UV_to_SpdDir(
        df_m["UGRD_10maboveground"], df_m["VGRD_10maboveground"]
    )
    df_m["DIR16_surface"] = wp.Deg_to_Dir16(df_m["wdir_wx_surface"])

    # 気温を℃に変換
    df_m["tmp_surface"] = df_m["TMP_2maboveground"] - 273.15

    # 列の並び替え
    cols_to_move = ['initial(UTC)', 'fct(UTC)', 'initial(JST)', 'fct(JST)', 'FT']
    other_cols = [col for col in df_m.columns if col not in cols_to_move]
    df_m2 = df_m[cols_to_move + other_cols]

    # カラム名の変更
    df_m2 = df_m2.rename(columns={'wspd_wx_surface': 'WS_surface(m/s)'})

    # 丸め処理
    exclude_cols = ['latitude', 'longitude']
    for col in df_m2.columns:
        if col not in exclude_cols and np.issubdtype(df_m2[col].dtype, np.floating):
            df_m2[col] = df_m2[col].apply(lambda x: round_decimal(x))

    # 結果用の列を選択
    df_result = df_m2[['initial(UTC)', 'fct(UTC)', 'initial(JST)', 'fct(JST)', 'FT',
                       'latitude', 'longitude', 'DIR16_surface', 'WS_surface(m/s)', 'tmp_surface']]
    
    return df_result

data = {}
# 指定した日付範囲でループ
current_date = start_date
while current_date <= end_date:
    yyyymmdd = current_date.strftime('%Y%m%d')
    year = yyyymmdd[0:4]
    month = yyyymmdd[4:6]
    day = yyyymmdd[6:8]

    # 指定された時間でループ
    for hhtt in hours:
        for entry in json_data:
            kana = entry['kana']
            lat = entry['latitude']
            lon = entry['longitude']

            df_result_list = []
            
            for idx, frange in enumerate(frange_sets):
                print(f"\n=== {yyyymmdd} {hhtt} 第{idx+1}フェーズ 処理中 ===")
                # 対象の日と時間における全ファイルのパスを生成
                __grblist = [grbdir / product / year / f"Z__C_RJTD_{yyyymmdd}{hhtt}00_GSM_GPV_Ras_Gll0p1deg_Lsurf_{xx}_grib2.bin" for xx in frange]
                grblist = [grbdir / f"Z__C_RJTD_{yyyymmdd}{hhtt}00_GSM_GPV_Ras_Gll0p1deg_Lsurf_{xx}_grib2.bin" for xx in frange]
        
                # ファイル存在確認
                grblist_existing = [f for f in grblist if Path(f).exists()]
                if not grblist_existing:
                    print(f"ファイルが見つかりません: {grblist}")
                    continue  # 存在しない場合は次のループへ
        
                ds = wx.getgpv(grblist_existing, elements, ncdir="./nc", to_netcdf=False, from_netcdf=False, verbose=False)
        
                # 初期時刻を取得
                initial_ds = ds['time'].attrs['reference_date']
                # datetimeに変換
                initial_UTC = datetime.strptime(initial_ds, '%Y.%m.%d %H:%M:%S UTC')

                df_result = extract_surface_data(ds, lat, lon, initial_UTC)
                df_result_list.append(df_result)

                del ds
                
            gc.collect()

            if df_result_list:
                df_merged = pd.concat(df_result_list, ignore_index=True)
                df_merged = df_merged.sort_values("FT")  # 必要に応じて時系列順にソート
    
                output_folder = f'E:/csv_files/{product}/test'
                os.makedirs(output_folder, exist_ok=True)
                file_name = f'{product}_new_{kana}_{yyyymmdd}{hhtt}.csv'
                output_path = os.path.join(output_folder, file_name)
    
                df_merged.to_csv(output_path, index=False, date_format='%Y-%m-%d %H:%M:%S', encoding='Shift_JIS')
                print(f"✅ 保存完了: {output_path}")
        
    


    current_date += timedelta(days=1)

df_merged


# In[ ]:




