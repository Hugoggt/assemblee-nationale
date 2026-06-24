@echo off
call "%~dp0venv\Scripts\activate.bat"
streamlit run "%~dp0app.py"
