@echo off
title Generador de Presupuestos CGM
echo Iniciando Generador de Presupuestos CGM...
cd /d "%~dp0"
py -m streamlit run app.py
pause