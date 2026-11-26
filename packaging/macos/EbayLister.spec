# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: builds "dist/Ebay Lister.app" (macOS).

Normally run through packaging/macos/build_mac.sh, which installs the tools first.
To run it directly from the project root:

    pyinstaller --noconfirm --clean packaging/macos/EbayLister.spec

Optional environment variables:
    BUNDLE_ID          bundle identifier            (default: com.ebaylister.app)
    TARGET_ARCH        arm64 | x86_64 | universal2  (default: the Python you build with)
    CODESIGN_IDENTITY  "Developer ID Application: Your Name (TEAMID)"  (default: unsigned)
"""
import os
import re
import subprocess
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821 - SPECPATH is set by PyInstaller
HERE = os.path.join(ROOT, "packaging", "macos")
APP_NAME = "Ebay Lister"

with open(os.path.join(ROOT, "ebay_lister", "__init__.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)

# tkinterdnd2 ships the native tkdnd library as package data; collect_all copies it into the app.
datas, binaries, hiddenimports = [], [], []
for pkg in ("tkinterdnd2",):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # not installed: the app still works, without drag & drop from Finder
        print(f"note: {pkg} not bundled ({exc})")

icon = os.path.join(HERE, "EbayLister.icns")
icon = icon if os.path.exists(icon) else None
entitlements = os.path.join(HERE, "entitlements.plist")

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
    hiddenimports=hiddenimports + ["PIL._tkinter_finder"],
    excludes=["tests", "pytest", "unittest.mock"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,               # no Terminal window
    argv_emulation=False,
    target_arch=os.environ.get("TARGET_ARCH") or None,
    codesign_identity=os.environ.get("CODESIGN_IDENTITY") or None,
    entitlements_file=entitlements if os.environ.get("CODESIGN_IDENTITY") else None,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=icon,
    bundle_identifier=os.environ.get("BUNDLE_ID", "com.ebaylister.app"),
    version=VERSION,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,       # sharp text on Retina screens
        "LSMinimumSystemVersion": "11.0",
        "NSRequiresAquaSystemAppearance": False,  # allow Dark Aqua (the app picks dark/light itself)
        "NSHumanReadableCopyright": "Ebay Lister",
    },
)
