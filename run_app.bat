@echo off
rem Streamlit画面を起動するバッチファイル。
rem 事前に環境(conda activate dust-forecast 等)を有効化してから実行してください。
setlocal
cd /d "%~dp0"

where streamlit >nul 2>nul
if errorlevel 1 (
    echo [ERROR] streamlit が見つかりません。事前に環境を有効化してください。
    echo   例: conda activate dust-forecast
    exit /b 1
)

streamlit run app.py
endlocal
