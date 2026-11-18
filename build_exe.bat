@echo off
REM ---------------------------------------------------------------------
REM  Builds Signet.exe (a single file, no installer needed).
REM  Double-click this file on a Windows PC that has Python 3.10 or newer
REM  (64-bit, from python.org, with "Add python.exe to PATH" ticked).
REM  The finished program appears at:  dist\Signet.exe
REM ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Creating a private build environment...
python -m venv .build_venv
if errorlevel 1 goto failed
call .build_venv\Scripts\activate.bat

echo [2/4] Installing the required libraries (this can take a few minutes)...
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt pyinstaller
if errorlevel 1 goto failed

echo [3/4] Building Signet.exe (this can take a few minutes)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Signet ^
  --paths backend --paths gui ^
  --collect-all pyhanko --collect-all pyhanko_certvalidator --collect-all asn1crypto ^
  --hidden-import tzlocal --hidden-import uritools ^
  main.py
if errorlevel 1 goto failed

echo [4/4] Checking that the program can sign and verify...
dist\Signet.exe --self-test
echo.
echo Done. Your program is here:  %~dp0dist\Signet.exe
echo Keys and signed documents are stored in  Documents\ECDSA PDF Signer
pause
exit /b 0

:failed
echo.
echo The build failed. Please read the messages above.
pause
exit /b 1
