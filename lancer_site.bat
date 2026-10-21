@echo off
rem Met a jour les donnees puis ouvre le site Hémicycle sur http://localhost:8000
cd /d "%~dp0"
python pipeline\fetch.py || goto :err
python -X utf8 pipeline\build.py || goto :err
start "" http://localhost:8000
python -m http.server 8000 --directory site
goto :eof
:err
echo.
echo La mise a jour des donnees a echoue.
pause
