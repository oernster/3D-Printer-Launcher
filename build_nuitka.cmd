@echo off
setlocal

REM Build the 3D Printer Launcher into a single-file Windows executable.
REM
REM This is a thin wrapper: build_nuitka.py holds the one definition of the
REM build, including the version metadata it reads from the VERSION file.
REM
REM Prerequisites (run once, from an activated venv in this repo):
REM   pip install -r requirements.txt
REM   pip install nuitka ordered-set zstandard

python "%~dp0build_nuitka.py" %*
