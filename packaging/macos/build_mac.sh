#!/usr/bin/env bash
# Build "Ebay Lister.app" (and a .dmg) on macOS.
#
#   packaging/macos/build_mac.sh
#
# Environment variables (all optional):
#   PYTHON             Python to build with      (default: python3 - use the python.org installer, see docs)
#   CODESIGN_IDENTITY  "Developer ID Application: Your Name (TEAMID)" to sign; unsigned if empty
#   NOTARY_PROFILE     keychain profile from `xcrun notarytool store-credentials` to notarize the .dmg
#   TARGET_ARCH        arm64 | x86_64 | universal2 (default: same as your Python)
#   MAKE_DMG           1 (default) to also build dist/Ebay-Lister-<version>.dmg, 0 to skip
#   BUNDLE_ID          bundle identifier         (default: com.ebaylister.app)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
APP="dist/Ebay Lister.app"

[ "$(uname)" = "Darwin" ] || { echo "This script must run on macOS."; exit 1; }

echo "==> Checking Python and Tk"
"$PY" - <<'PYCHECK'
import sys, tkinter
tk_version = tkinter.Tcl().eval("info patchlevel")
print(f"Python {sys.version.split()[0]}  |  Tk {tk_version}")
if sys.version_info < (3, 9):
    sys.exit("Python 3.9+ is required.")
if tuple(int(x) for x in tk_version.split(".")[:2]) < (8, 6):
    sys.exit("Tk 8.6+ is required - install Python from python.org (it bundles a modern Tk).")
PYCHECK

echo "==> Creating build environment (.venv-build)"
"$PY" -m venv .venv-build
# shellcheck disable=SC1091
source .venv-build/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install "pyinstaller>=6.0" pillow tkinterdnd2

echo "==> Running tests"
python -m unittest discover -s tests -t . -q

echo "==> Icon"
bash packaging/macos/make_icns.sh

echo "==> Building app"
VERSION="$(python -c 'import ebay_lister; print(ebay_lister.__version__)')"
pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/macos/EbayLister.spec

if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  echo "==> Verifying signature"
  codesign --verify --deep --strict --verbose=2 "$APP"
fi

if [ "${MAKE_DMG:-1}" = "1" ]; then
  echo "==> Building disk image"
  DMG="dist/Ebay-Lister-$VERSION.dmg"
  STAGE="$(mktemp -d)"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"      # drag-to-install shortcut
  hdiutil create -volname "Ebay Lister" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
  rm -rf "$STAGE"
  if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    codesign --sign "$CODESIGN_IDENTITY" --timestamp "$DMG"
  fi
  if [ -n "${NOTARY_PROFILE:-}" ]; then
    echo "==> Notarizing (this can take a few minutes)"
    xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
    xcrun stapler staple "$DMG"
  fi
  echo "Disk image: $DMG"
fi

echo
echo "Done: $APP"
echo "Try it:  open \"$APP\""
