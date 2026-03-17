@echo off
title Kraft Finans Markedsportal
echo ================================================
echo  KRAFT FINANS - Markedsportal
echo ================================================
echo  Starter server pa http://localhost:5001
echo  Del pa lokalnett: http://[din-ip]:5001
echo  Trykk CTRL+C for a stoppe
echo ================================================
echo.

cd /d "%~dp0"

if not exist ".env" (
    echo ADVARSEL: .env fil ikke funnet. Kopier .env.example til .env og fyll inn verdier.
    copy .env.example .env
    echo.
)

python -m pip install -r requirements.txt -q
python app.py
pause
