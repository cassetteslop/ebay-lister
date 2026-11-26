#!/usr/bin/env bash
# Build "Ebay Lister.app" from the latest commit and install it in /Applications.
#
# Run automatically after every commit by .githooks/post-commit (turn that on once with
# packaging/macos/enable_autobuild.sh), or by hand at any time:
#
#   packaging/macos/autobuild.sh                  # build the latest commit and install it
#   packaging/macos/autobuild.sh --working-tree   # build the folder as it is now (uncommitted edits too)
#
# It builds a clean copy of the committed code (not your working folder, so half-finished edits
# never end up in the app), replaces /Applications/Ebay Lister.app, and shows a notification.
# The log is build/autobuild/autobuild.log. Your data in ~/.ebay_lister is never touched.
#
# Environment variables (all optional):
#   PYTHON          Python to build with (default: git config ebaylister.python, else python3)
#   INSTALL_DIR     where to install           (default: /Applications)
#   EBAY_LISTER_NO_AUTOBUILD=1   makes the post-commit hook skip the build
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$ROOT/build/autobuild"
LOG="$WORK/autobuild.log"
LOCK="$WORK/lock"
INSTALL_DIR="${INSTALL_DIR:-/Applications}"
APP_NAME="Ebay Lister"
mkdir -p "$WORK"

notify() {  # notify "message" ["sound"]
  osascript -e "display notification \"$1\" with title \"$APP_NAME build\"${2:+ sound name \"$2\"}" >/dev/null 2>&1 || true
}

# One build at a time. If commits come in quickly, a build that starts after the lock is free
# always builds the newest HEAD, so a build that's skipped here isn't lost.
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid")" 2>/dev/null; then
    touch "$LOCK/again"          # the running build will go round once more when it finishes
    echo "A build is already running; it will rebuild afterwards."
    exit 0
  fi
  rm -rf "$LOCK" && mkdir "$LOCK"  # stale lock from a crashed build
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

WORKING_TREE=0
[ "${1:-}" = "--working-tree" ] && WORKING_TREE=1

PY="${PYTHON:-$(git -C "$ROOT" config --get ebaylister.python || command -v python3)}"

build_once() {
  local commit src
  commit="$(git -C "$ROOT" rev-parse --short HEAD)"
  if [ "$WORKING_TREE" = "1" ]; then
    src="$ROOT"
    commit="$commit+working-tree"
  else
    # a clean copy of the commit (plus the untracked, optional icon)
    src="$WORK/src"
    rm -rf "$src" && mkdir -p "$src"
    git -C "$ROOT" archive HEAD | tar -x -C "$src" || return 1
    [ -f "$ROOT/packaging/macos/icon.png" ] && cp "$ROOT/packaging/macos/icon.png" "$src/packaging/macos/"
  fi
  echo "==> $(date '+%Y-%m-%d %H:%M:%S')  building $commit with $PY"

  # reuse the project's build environment so each build only takes a minute or two
  PYTHON="$PY" VENV="$ROOT/.venv-build" MAKE_DMG=0 bash "$src/packaging/macos/build_mac.sh" || return 1

  local built="$src/dist/$APP_NAME.app" target="$INSTALL_DIR/$APP_NAME.app"
  [ -d "$built" ] || { echo "Build output missing: $built"; return 1; }

  echo "==> Self-test"
  "$built/Contents/MacOS/$APP_NAME" --self-test "$WORK/selftest.txt" >/dev/null 2>&1
  if ! grep -q "SELF-TEST OK" "$WORK/selftest.txt" 2>/dev/null; then
    cat "$WORK/selftest.txt" 2>/dev/null
    echo "The built app failed its self-test; not installing it."
    return 1
  fi

  echo "==> Installing to $target"
  # copy next to the old app first, then swap, so a failed copy never leaves you without an app
  rm -rf "$target.new"
  ditto "$built" "$target.new" || return 1
  rm -rf "$target" && mv "$target.new" "$target" || return 1
  echo "Installed $commit"
  notify "Installed build $commit in $INSTALL_DIR." "Glass"
}

{
  while :; do
    rm -f "$LOCK/again"
    if ! build_once; then
      echo "BUILD FAILED - see above"
      notify "Build failed - see build/autobuild/autobuild.log" "Basso"
      exit 1
    fi
    [ -f "$LOCK/again" ] && [ "$WORKING_TREE" = "0" ] || break   # another commit arrived meanwhile: go again
  done
} >>"$LOG" 2>&1
