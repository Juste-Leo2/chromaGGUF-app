@echo off
setlocal

:: =================================================================
:: ==            SILENT LAUNCHER FOR CHROMA-GGUF APP              ==
:: =================================================================
::
:: This batch file silently executes the PowerShell launcher.
:: The PowerShell window itself is hidden for a completely
:: seamless user experience.
::

:: -WindowStyle Hidden : This is the key. It runs the PowerShell
::   process without showing any window.
powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "%~dp0src\run.ps1"

endlocal