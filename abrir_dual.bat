@echo off
REM abrir_dual.bat
REM Abre a interface dual: CQ-Editor 3D + Viewer 2D de footprint lado a lado
REM Pressione F5 no editor para gerar e atualizar ambas as vistas simultaneamente.

echo Iniciando Interface Dual - CQ-Editor + Footprint 2D...
echo.
"%~dp0.venv\Scripts\python.exe" -Xfrozen_modules=off "%~dp0gui\interface_dual.py" %*
