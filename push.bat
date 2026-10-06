@echo off
cd /d "%~dp0"
git remote | findstr /i "origin" >nul
if not errorlevel 1 goto :push
echo First-time setup:
echo  1. Open https://github.com in your browser, sign in, and create a new EMPTY repository
echo     (suggested name: onimai-summon-system ; Visibility: Private is recommended).
echo     Do NOT tick "Add a README" or any auto-init option.
echo  2. Copy its URL, for example: https://github.com/USERNAME/onimai-summon-system.git
echo  3. Paste it below and press Enter.
echo.
set /p REPOURL=Paste repository URL: 
if "%REPOURL%"=="" goto :fail
git remote add origin %REPOURL%
:push
git push -u origin main
echo.
echo Done. If a browser window popped up, sign in to GitHub once and it will be remembered.
pause
exit /b
:fail
echo Empty URL. Run this file again.
pause
