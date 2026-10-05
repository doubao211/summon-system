@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter ""Name='python.exe'"" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo All stopped.
pause

