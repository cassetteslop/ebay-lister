# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: builds dist/Ebay Lister/Ebay Lister.exe (Windows, one-folder app).

Used by .github/workflows/build-windows.yml. To build by hand on Windows (from the project root):

    py -m pip install -r requirements-build.txt
    py packaging\\windows\\make_ico.py          (optional: icon.png -> ebay_lister.ico)
    py -m PyInstaller --noconfirm --clean packaging\\windows\\ebay_lister.spec

One-folder (not one-file) on purpose: it starts faster and trips antivirus false positives less.
"""
import os
import re
import shutil
import subprocess
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821 - SPECPATH is set by PyInstaller
HERE = os.path.join(ROOT, "packaging", "windows")
APP_NAME = "Ebay Lister"

with open(os.path.join(ROOT, "ebay_lister", "__init__.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)

# tkinterdnd2 ships the native tkdnd library as package data; collect_all copies it into the build.
datas, binaries, hiddenimports = [], [], []
for pkg in ("tkinterdnd2",):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # not installed: the app still works, without drag & drop from Explorer
        print(f"note: {pkg} not bundled ({exc})")

icon = os.path.join(HERE, "ebay_lister.ico")
icon = icon if os.path.exists(icon) else None

# The user guide PDF (docs/USER_GUIDE.md, rendered fresh for every build). Bundled as docs/<name> so
# Help > User Guide can open it; must match ebay_lister.config.GUIDE_PDF.
GUIDE = os.path.join(ROOT, "build", "guide", f"{APP_NAME} User Guide.pdf")
subprocess.run([sys.executable, os.path.join(ROOT, "packaging", "make_guide.py"), GUIDE], check=True)
datas.append((GUIDE, "docs"))

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    # every app module is imported lazily somewhere; list the package so nothing is missed
    hiddenimports=hiddenimports + ["PIL._tkinter_finder", "ebay_lister.selftest"],
    excludes=["tests", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,          # windowed app: no console window (errors go to %APPDATA%\Ebay Lister\app.log)
    icon=icon,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

# Also put the guide next to "Ebay Lister.exe" so people see it as soon as they unzip the download.
shutil.copy2(GUIDE, os.path.join(DISTPATH, APP_NAME))  # noqa: F821 - DISTPATH is set by PyInstaller
