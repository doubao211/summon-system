@echo off
cd /d "%~dp0"
python init.py
start "" pythonw "%~dp0workbench.py"
