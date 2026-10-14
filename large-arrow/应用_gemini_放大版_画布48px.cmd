@echo off
setlocal
set "PSModulePath="
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-updated.ps1" -Character gemini -Size 48
if errorlevel 1 pause
