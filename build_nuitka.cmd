@echo off
setlocal

REM Build Oliver's App Launcher into a single-file Windows executable using Nuitka.
REM Prerequisites (run once, from an activated venv in this repo):
REM   pip install nuitka ordered-set zstandard
REM   pip install -r requirements.txt

REM Clean previous build artifacts
if exist dist (
  echo Removing existing dist directory...
  rmdir /S /Q dist
)

python -m nuitka ^
  --onefile ^
  --enable-plugin=pyside6 ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=filament.ico ^
  --follow-imports ^
  --output-dir=dist ^
  main.py

echo.
echo If the build succeeded, your single-file executable is in dist\main.exe

