@echo off
rem CLIバッチ処理(generate)を実行するバッチファイル。
rem 事前に環境(conda activate dust-forecast 等)を有効化してから実行してください。
rem 使用方法: run_generate.bat <GRIB2ファイルパス> [設定YAMLパス]
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo 使用方法: run_generate.bat ^<GRIB2ファイルパス^> [設定YAMLパス]
    echo 例: run_generate.bat data\input\Z__C_RJTD_20230314120000_GSM_GPV_Rjp_Gll0p1deg_Lsurf_FD0000-0100_grib2.bin config\sample.yaml
    exit /b 1
)

set INPUT=%~1
set CONFIG=%~2
if "%CONFIG%"=="" set CONFIG=config\sample.yaml

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python が見つかりません。事前に環境を有効化してください。
    echo   例: conda activate dust-forecast
    exit /b 1
)

python -m dust_forecast.cli generate --input "%INPUT%" --config "%CONFIG%"
endlocal
