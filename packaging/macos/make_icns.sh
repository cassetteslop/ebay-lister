#!/usr/bin/env bash
# Make packaging/macos/EbayLister.icns from a square PNG (1024x1024 recommended).
# Usage: packaging/macos/make_icns.sh [path/to/icon.png]     (default: packaging/macos/icon.png)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-$HERE/icon.png}"
[ -f "$SRC" ] || { echo "No icon PNG at $SRC - skipping icon (the app will use the default icon)."; exit 0; }
SET="$(mktemp -d)/EbayLister.iconset"
mkdir -p "$SET"
for size in 16 32 128 256 512; do
  sips -z $size $size "$SRC" --out "$SET/icon_${size}x${size}.png" >/dev/null
  sips -z $((size * 2)) $((size * 2)) "$SRC" --out "$SET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$HERE/EbayLister.icns"
echo "Icon written to $HERE/EbayLister.icns"
