@echo off
rem Double-click on Windows. Needs Python 3 from python.org (tick "Add to PATH" when installing).
cd /d "%~dp0"
where py >nul 2>nul && (py -3 emosticker.py %* & goto :done)
where python >nul 2>nul && (python emosticker.py %* & goto :done)
echo Python 3 was not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
pause
:done
