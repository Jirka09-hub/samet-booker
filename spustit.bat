@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
if not exist .venv\Scripts\python.exe (
  echo Pripravuji prostredi, poprve to chvili trva...
  %PY% -m venv .venv
  if errorlevel 1 goto nopython
)
.venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements.txt
.venv\Scripts\python.exe -m samet_booker
pause
goto :eof
:nopython
echo Nenasel jsem Python. Stahni ho z https://www.python.org/downloads/ (zaskrtni "Add python.exe to PATH") nebo pouzij SAMET-Booker.exe z Releases.
pause
