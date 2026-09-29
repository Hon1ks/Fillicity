@echo off
REM Build the portable Fillicity.exe on Windows.
REM Run this from the project root, in a Python 3.11+ environment.

python -m venv .venv
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
pyinstaller Fillicity.spec

echo.
echo Done. Portable app is in dist\Fillicity\Fillicity.exe
