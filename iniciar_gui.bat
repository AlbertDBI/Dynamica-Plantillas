@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run scripts/gui.py --server.runOnSave false
pause
