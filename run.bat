@echo off
echo ============================================
echo  Assemblée Nationale — Téléchargement data
echo ============================================
call "%~dp0venv\Scripts\activate.bat"

echo.
echo [1/3] Téléchargement des députés...
python "%~dp0fetch_deputes.py"

echo.
echo [2/3] Téléchargement des scrutins...
python "%~dp0fetch_scrutins.py"

echo.
echo [3/4] Téléchargement des dossiers législatifs...
python "%~dp0fetch_dossiers.py"

echo.
echo [4/4] Classification par thème...
python "%~dp0classify_themes.py"

echo.
echo ============================================
echo  Données prêtes — Lancement de l'application
echo ============================================
echo.
python "%~dp0dash_app.py"

pause
