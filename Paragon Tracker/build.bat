@echo off
REM Gera dist\Diablo4ParagonTracker.exe (rode no Windows, com Python instalado)
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --icon=tracker.ico --name Tracker main.py
copy /Y "D4 LoH Paragon XP Current S13.xlsx" dist\
echo.
echo Pronto: dist\Diablo4ParagonTracker.exe  (Deixe a planilha .xlsx na mesma pasta do .exe/ Let the table on the same folder as the .exe)
pause
