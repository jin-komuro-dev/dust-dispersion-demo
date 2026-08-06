# -*- coding: utf-8 -*-
"""
Python library wxbcgribX

＜著作権表示＞
The MIT License
Copyright 2022 気象ビジネス推進コンソーシアム 人材育成ワーキンググループ 気象×IT勉強会

＜利用条件＞
以下に定める条件に従い、本ソフトウェア（以下「ソフトウェア」）の複製を取得する
すべての人に対し、ソフトウェアを無制限に扱うことを無償で許可します。これには、
ソフトウェアの複製を使用、複写、変更、結合、掲載、頒布、サブライセンス、およ
び/または販売する権利、および ソフトウェアを提供する相手に同じことを許可する
権利も無制限に含まれます。
　ただし、上記の著作権表示および本許諾表示を、ソフトウェアのすべての複製また
は重要な部分に記載するものとします。
ソフトウェアは「現状のまま」で、明示であるか暗黙であるかを問わず、何らの保証も
なく提供されます。ここでいう保証とは、商品性、特定の目的への適合性、および権利非
侵害についての保証も含みますが、それに限定されるものではありません。 作者または
著作権者は、契約行為、不法行為、またはそれ以外であろうと、ソフトウェアに起因また
は関連し、あるいはソフトウェアの使用また はその他の扱いによって生じる一切の請求、
損害、その他の義務について何らの 責任も負わないものとします。

Version 20221217
"""
import subprocess
import tempfile
from pathlib import Path
import xarray as xr
import sys
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


global wgrib2
#wgrib2 = Path("~/work/grib2/wgrib2/wgrib2") # Macの場合
wgrib2 = Path("C:/Users/fctsm_000/wgrib2/wgrib2.exe")       # Windowsの場合

def wg2(src, opt=""):
    import sys
    import subprocess
    from pathlib import Path

    src_path = Path(src)
    parent = str(src_path.parent)
    name = src_path.name

    # 手動で成功した形：
    # pushd "\\server\share\日本語フォルダ" && wgrib2 "ファイル名" -var
    cmd = f'pushd "{parent}" && wgrib2 "{name}" {opt}'

    print("[DEBUG wg2 cmd]", cmd)

    try:
        rc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="cp932",
            errors="replace"
        )
    except FileNotFoundError:
        print("wgrib2 をインストールしてください。")
        sys.exit(1)

    if rc.returncode != 0:
        print("[wgrib2 stdout]")
        print(rc.stdout)
        print("[wgrib2 stderr]")
        print(rc.stderr)
        sys.exit(1)

    return rc

def wg2_old(src,opt=''):
    # wgrib2を実行する関数
    if not wgrib2.exists():
        print("wgrib2 をインストールしてください。")
        sys.exit(1)
    rc = subprocess.run(f'{wgrib2} {opt} {src}', 
                        shell=True, text=True, capture_output=True)
#    print(rc.returncode)
#    print(rc.stdout)
#    print(rc.stderr)
    return rc


def valid_path(path):
    """
    ファイルがあるか確認する関数
    """
    path = Path(path)
    if not path.exists():
        return False
    return True


def catchinf(src,opt):
    """
    ＜機能＞
    wgrib2の'-var'や'-ens'の戻り値の重要部分を受ける関数
    src: 対象とするGRIBファイルへのパス
    opt: wgrib2 に渡すオプション文字列
    戻り値：重要部分のリスト
    """
    ##インベントリに現れる気象要素を取り出す
    rc = wg2(src,opt)
    if rc.returncode != 0:
        return
    msgs = []
    for line in rc.stdout.splitlines():
        msg = line.split(":")
        msgs.append(msg)
    return [msg[2] for msg in msgs]


def getvarname(src):
    """
    ＜機能＞
    ファイルに格納されているる気象要素を取り出す関数
    src:   対象とするGRIBファイルへのパス
    戻り値：気象要素の識別子のリスト
    """
    inf = catchinf(src,opt="-var")
    var = sorted(set(inf))
    return var

def getensname(src):
    """
    ＜機能＞
    ファイルに格納されているるアンサンブルメンバー識別子をキレイに取り出す関数
    src:   対象とするGRIBファイルへのパス
    戻り値：アンサンブルメンバー識別子のリスト
    """
    inf = catchinf(src,opt="-ens")
    enss = sorted(set(inf))
    ensc = enss[-1] # コントロールを取り出す。ソートすれば'ctl'は一番最後
    ensn = enss[:-1] # コントロール以外のメンバーのリスト
    ef = [float(oo.replace('ENS=','')) for oo in ensn] # 数値化
    es = [oo if oo > 0 else -oo+0.5 for oo in ef] # マイナス○をプラス○よりちょっと大きい値に置換
    ei = [es.index(oo) for oo in sorted(es)] # もしソートしたら自分は何番目になるかを計算
    ens = [ensc]+[ensn[oo] for oo in ei] # その順番にmemipを並べ替えて頭にコントロール追加
    return ens


def valid_var(grbpath, elements):
    """
    気象要素がGRIB2ファイルにあるか確認する関数
    """
    if not isinstance(elements,list):
        elements = [elements]
    if elements == []:
        print('気象要素を指定してください.')
        return False
    vars = getvarname(grbpath)
    for var in elements:
        if not(var in vars):
            print('指定したファイルに ' + var + ' は収録されていません。' )
            print(','.join(vars) + ' が収録されています。')
            return False
    return True


def matchopt(elements, ens=''):
    """
    気象要素・アンサンブルメンバーを指定するためのwgrib2のオプション文字列を作成する関数
    elementsはリストを想定
    ensは文字列を想定するが、リストで来たら最初の要素を取り出す
    """
    mopt = '-match "' + '|'.join(elements) + '"'
    if isinstance(ens,list):
        ens=ens[0]
    if ens != '':
        mopt = mopt + ' -match_fs "' + ens + ':"'
    return mopt


def from_grb(grbpath,matchopt,verbose):
    """
    gpvデータをGRIB2ファイルから取得する関数
    matchopt: データを選別するオプション文字列
    """
    #指定した気象要素のデータを取り出して一時ファイルに格納
    with tempfile.TemporaryDirectory() as td:
        dumppath = Path(td)/"extracting.nc" #作業ファイルの指定
        opt = f'{matchopt} -netcdf {dumppath}'
        rc = wg2(grbpath, opt)
        if verbose:
            print(rc.stdout)#.splitlines())
        #一時ファイルからデータセットをロード
        with xr.open_dataset(dumppath) as ds:
            ds.load()
        dumppath.unlink(missing_ok=True) #後片付け
    return ds


def from_nc(ncpath,verbose):
    """
    gpvデータをNetCDFファイルから取得する関数
    """
    if verbose:
        print("reading from", ncpath)
    with xr.open_dataset(ncpath) as ds:
        ds.load()
    return ds


def imima(coord, minmax):
    """
    -trimで使う-
    2要素のリストで与えられた緯度や経度の上限と下限端から、対応するインデックスの上限と下限を求める関数
    値とグリッドが一致すればそのグリッドの、一致しなかったら外側のグリッドのインデックスを返す
    coord: 座標変数（dataset.latitude または dataset.longitude）
    minmax: 座標の最小値と最大値のリスト
    戻り値：インデックスの最小値と最大値
    """
    imin = max(np.where(coord.data <= min(minmax))[0])
    imax = min(np.where(coord.data >= max(minmax))[0])
    return imin,imax


def trim(ds,lalomima):
    """
    self.dataに格納されているデータを、特定の領域部分だけにトリミングする関数
    緯度下限(南端)、緯度上限(北端)、経度下限(西端)、軽度上限(東端)の４つの
    数値をこの順でリストにして与える
    """
    lamima = lalomima[0:2]
    lomima = lalomima[2:4]
    ilami, ilama = imima(ds.latitude, lamima)
    ilomi, iloma = imima(ds.longitude, lomima)
    dss = ds.isel(latitude=slice(ilami,ilama+1),longitude=slice(ilomi,iloma+1))
    return dss


def getsingle(grbpath, elements, ncdir, to_netcdf, from_netcdf, lalomima, verbose):
    """
    ファイル１つ分のGPVデータを取得しxarrayのDataSetオブジェクトを返す関数
    ・to_netcdf=True ならNetCDFファイルに保存
    ・from_netcdf=True ならGRIB2でなくNetCDFファイル読む
    ・lalomima が指定されたらトリミング
    ・複数ファイルに対応
    ・アンサンブルプロダクトに対応
    """
    #Pathオブジェクトであることを保証
    grbpath = Path(grbpath)
    ncdir = Path(ncdir)
    #気象要素がリストであることを保証
    if not isinstance(elements,list):
        elements = [elements]
    #NetCDFファイルが保存されるディレクトリ確保
    if to_netcdf and not ncdir.exists():
        ncdir.mkdir(parents=True,exist_ok=True)
    ncpath = ncdir/(grbpath.stem+"."+"_".join(elements)+".nc") 

    #NetCDFファイルが保存される
    if to_netcdf==True and not ncdir.exists():
        ncdir.mkdir(parents=True,exist_ok=True)
    #データ取得
    if from_netcdf and ncpath.exists():#過去に作ったので良ければそれをロード
        ds = from_nc(ncpath,verbose)
    else:#ダメならGRIB2ファイルから
        #GRIBファイルの存在確認
        if not valid_path(grbpath):
            return 'invalid path'
        #指定した気象要素が収録されているか確認
        if not valid_var(grbpath, elements):
            return 'invalid grib var names'
        #アンサンブルメンバー名を取得(メンバーなければ[''])
        members = getensname(grbpath) #アンサンブルメンバー名(普通のGPVなら[''])
        #print(members[0])
        ds = from_grb(grbpath,matchopt(elements,members[0]),verbose)
        if members[0] != '': #アンサンブルプロダクトなら
            for member in members[1:] :
                if verbose:
                    print(member,end=', ')
                da = from_grb(grbpath,matchopt(elements,member),False)
                ds = xr.concat([ds,da],"member")
            if verbose:
                print()
            ds = ds.assign_coords({"member":members})  # メンバーの次元を座標に格上げ
            ds["member"].attrs = {"long_name":"ensemble member"}  # 属性情報を設定
        #指定されていたらNetCDFファイルに保存
        if to_netcdf:
            ds.to_netcdf(ncpath, format="NETCDF4")
    #lalomimaに領域が指定されていたらトリミング
    if lalomima!=None :
        ds = trim(ds,lalomima)
    return ds


def getgpv(grblist, elements, ncdir="./nc", to_netcdf=True, from_netcdf=True, lalomima=None, verbose=False):
    """
     ＜機能＞
    複数のGRIBファイルから指定した気象要素のデータを取り出しxarrayのDataSetオブジェクトを
    作成する関数。時刻はUTCのまま。
    grbpath:   対象とするGRIBファイルのリスト
    elements: GRIBファイルから取り出す気象要素を指定する引数。インベントリで使用されて
            いる文字列をリストで与える(['TMP','RH']など)。
    ncdir: 作成したDataDetオブジェクトをファイルとして保管する場所を指定する引数。
            このディレクトリは、GRIBファイルからデータを取り出す際に作る一時ファイル
            の置き場所としても使用される。何も指定しないと"./nc"が設定される。
    to_netcdf: 作成したDataDetオブジェクトをファイルとして保管するかどうかを指定する引数。
            Falseを与えると保管しない。何も指定しないと保管される。
    from_netcdf: 以前に保管したNetCDFファイルからDataDetオブジェクトを読み込むか、GRIB2
            ファイルから読み出すかを指定する引数。
            Falseを与えると読み込まずGRIB2ファイルから取り出す。何も指定しないと読み込む。
    lalomima:データの緯度経度範囲を限定するときは範囲を以下の4要素リストで与える。
                    [緯度の最大値,緯度の最小値,経度の最大値,経度の最小値]
            これを設定してもGRIB2から読みだされる領域が限定されることはない。故に、
            to_netcdf=Trueにより生成されるファイルのサイズは抑制されない。
    vorbose: デコード中のメンバー名と枚数を逐次表示するかどうかを指定する引数。       
            Trueを与えると表示する。何も指定しないと表示しない。
    Version 20221203
   """
    if not isinstance(grblist,list):
        grblist = [grblist]
    else:
        grblist.sort()
    ds = getsingle(grblist[0], elements, ncdir, to_netcdf, from_netcdf, lalomima, verbose)
    for grbpath in grblist[1:] :
        da = getsingle(grbpath, elements, ncdir, to_netcdf, from_netcdf, lalomima, verbose)
        if ds.time[-1] < da.time[0]:
            ds = xr.concat([ds,da],'time')
        else:
            ds = xr.concat([ds,da],list(ds.coords)[-1])
    return ds


def strft_range(start='202001010000', format='%Y%m%d%H%M', ita=1, **step):
    """
     ＜機能＞
    formatで指定した文字列のリストを作成する関数
    start に開始の日時をyyyymmddhhmm の文字列または、datetimeオブジェクトで指定し、
    itaに作成する個数を整数で指定し、
    刻む時間間隔を「hours=1」「minutes=30」などの形で指定する
    Version 20221215
   """
    # 文字列をdatetimeに変換．
    if isinstance(start, str):
        start = datetime.datetime.strptime(start, '%Y%m%d%H%M')
    # 間隔の設定．デフォルトは1時間
    step = datetime.timedelta(**(step or dict(hours=1)))
    date = start
    strft =[]
    for i in range(ita):
        strft.append(date.strftime(format))
        date += step
    return strft



def jst(xarr):
    """
     ＜機能＞
    DataArray または、Datasetオブジェクトから時刻を日本標準時で取り出す関数
    Version 20221115
   """
    return list(pd.Series(xarr.time).dt.tz_localize('UTC').dt.tz_convert('Asia/Tokyo'))


# 折れ線グラフを描画する関数
def tsj(darr, overlay=None,iscommony=True):
    """
     ＜機能＞
    折れ線グラフを描画する関数
    darray
    Version 20221115
   """
    fig, ax = plt.subplots(figsize=(15,5),ncols=1,nrows=1)
    # 主な折れ線の描画
    ax.set_xlabel(darr["time"].attrs["long_name"])
    ax.set_ylabel(darr.attrs["long_name"] + "  (" + darr.attrs["units"] + ")")
    ax.set_title("latitude = "+str(darr["latitude"].data)+", longitude = "+str(darr["longitude"].data))
    ax.plot(jst(darr.time), darr.T)
    # 重ねる折れ線の描画（DataArrayの場合）
    if type(overlay) is type(darr):
        if iscommony:
            ax.plot(jst(overlay.time), overlay,label=darr.attrs["long_name"],color='black', linewidth=3, marker="o")
            ax.legend(loc='lower right')
        else:
            ax2 = ax.twinx()
            ax2.set_ylabel(overlay.attrs["long_name"] + "  (" + overlay.attrs["units"] + ")")
            ax2.plot(jst(overlay.time), overlay,label=overlay.attrs["long_name"],color='black', linewidth=3, marker="o")
            ax2.legend(loc='lower right')
    # 重ねる折れ線の描画（[[y],[x],"label"]の場合）
    elif type(overlay) is list:
        if len(overlay)==2:
            overlay = overlay + ["overlay"]
        if iscommony:
            ax.plot(overlay[1], overlay[0],label=overlay[2], color='brown', linewidth=3, marker="o")
            ax.legend(loc='lower left')
        else:
            ax2 = ax.twinx()
            ax2.set_ylabel(overlay[2])
            ax2.plot(overlay[1], overlay[0],label=overlay[2], color='brown', linewidth=3, marker="o")
            ax2.legend(loc='lower right')
    plt.savefig('fig.png')
    plt.show()

    
########　以降は後方互換性のために存在　使用を推奨しない　########
def getgrvarname(src):
    """
    ＜機能＞
   ファイルに格納されているる気象要素を取り出す関数
    src:   対象とするGRIBファイルへのパス
    戻り値：気象要素の識別子のリスト
    """
    ##インベントリに現れる気象要素を取り出す
    rc = wg2(src,opt="-var")
    if rc.returncode != 0:
        return
    msgs = []
    for line in rc.stdout.splitlines():
        msg = line.split(":")
        msgs.append(msg)
    var = sorted(set([msg[2] for msg in msgs]))
    return var

def dt_range(start='202001010000', ita=3, **step):
    """
     ＜機能＞
    python標準のdatetimeオブジェクトのリストを作成する関数
    start に開始の日時をyyyymmddhhmm の文字列で指定し、
    itaに作成する個数を整数で指定し、
    刻む時間間隔を「hours=1」「minutes=30」などの形で指定する
    Version 20221115
   """
    # 文字列をdatetimeに変換．
    start = datetime.datetime.strptime(start, '%Y%m%d%H%M')
    # 間隔の設定．デフォルトは1時間
    step = datetime.timedelta(**(step or dict(hours=1)))
    # while文を回し，yieldでジェネレータを返す．
    date = start
    for i in range(ita):
        yield date
        date += step
