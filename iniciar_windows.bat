@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo AMIGOS DE AMIGOS - SISTEMA FINANCEIRO
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Erro ao instalar os requisitos. Confirma a instalacao do Python.
  pause
  exit /b 1
)
python -m streamlit run app.py
pause
