@echo off
rem Met a jour les donnees, genere les pages puis ouvre le site sur http://localhost:8000
cd /d "%~dp0"
python pipeline\fetch.py || goto :err
python -X utf8 pipeline\build.py || goto :err
python -X utf8 pipeline\textes.py
python -X utf8 pipeline\budget.py
python -X utf8 pipeline\europe.py
python -X utf8 pipeline\prerender.py || goto :err
start "" http://localhost:8000
python pipeline\serve.py 8000
goto :eof
:err
echo.
echo La mise a jour du site a echoue.
pause
