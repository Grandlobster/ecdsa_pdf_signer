#!/usr/bin/env bash
# Builds a single-file program for the operating system you run this on
# (Linux or macOS). On Windows, use build_exe.bat instead.
set -e
cd "$(dirname "$0")"

python3 -m venv .build_venv
source .build_venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt pyinstaller

python -m PyInstaller --noconfirm --clean --onefile --windowed --name Signet \
  --paths backend --paths gui \
  --collect-all pyhanko --collect-all pyhanko_certvalidator --collect-all asn1crypto \
  --hidden-import tzlocal --hidden-import uritools \
  main.py

./dist/Signet --self-test
echo "Done: $(pwd)/dist/Signet"
