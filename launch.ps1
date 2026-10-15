$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) { py -3 -m venv .venv }
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
& '.venv\Scripts\python.exe' -m streamlit run app.py
