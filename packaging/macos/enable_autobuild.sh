#!/usr/bin/env bash
# Turn on (or off) the automatic Mac build after every commit.
#
#   packaging/macos/enable_autobuild.sh          # on: uses .githooks/post-commit
#   packaging/macos/enable_autobuild.sh --off    # off
#
# Also remembers which Python to build with (the python3 you run this with, or $PYTHON), because
# git hooks often run with a shorter PATH than your Terminal.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [ "${1:-}" = "--off" ]; then
  git config --unset core.hooksPath || true
  echo "Automatic builds are off."
  exit 0
fi
PY="${PYTHON:-$(command -v python3)}"
"$PY" -c "import tkinter" || { echo "$PY has no tkinter - pass PYTHON=/path/to/python3"; exit 1; }
chmod +x .githooks/post-commit packaging/macos/autobuild.sh packaging/macos/build_mac.sh
git config core.hooksPath .githooks
git config ebaylister.python "$PY"
echo "Automatic builds are on: each commit installs a fresh 'Ebay Lister.app' in /Applications."
echo "Building with: $PY"
echo "Build now without committing: packaging/macos/autobuild.sh"
