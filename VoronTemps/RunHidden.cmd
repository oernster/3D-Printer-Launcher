@echo off
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden ^
  -File "C:\Users\Oliver\bin\run_venv_hidden.ps1" ^
  -ProjectDir "C:\Users\Oliver\Development\VoronTemps" ^
  -ScriptName "app.py" ^
  -LogName "app.log" ^
  >> "C:\Users\Oliver\Development\VoronTemps\launcher.log" 2>&1
