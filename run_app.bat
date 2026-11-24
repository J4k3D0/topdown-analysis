@echo off
title VNStock Quant App
cd /d "%~dp0"
echo ========================================================
echo   DANG KHOI CHAY HE THONG QUANT TOP-DOWN (VNSTOCK)
echo ========================================================
echo.
python -m streamlit run app.py
pause
