# Building a Mac app

This turns the project into **Ebay Lister.app**, a normal Mac app you can keep in Applications and open from the Dock. It runs without Python installed. The build uses [PyInstaller](https://pyinstaller.org), which copies Python, Tk, Pillow and the drag-and-drop library into the app.

## Quick start

```bash
cd ebay-lister
packaging/macos/build_mac.sh
open "dist/Ebay Lister.app"
```

You get:

* `dist/Ebay Lister.app`: the app, with the User Guide PDF inside (Help › User Guide)
* `dist/Ebay-Lister-1.0.0.dmg`: a disk image that installs by dragging the app onto Applications; the User Guide PDF sits next to the app

The guide is `docs/USER_GUIDE.md`, rendered to PDF by `packaging/make_guide.py` during every build (it needs `reportlab`, which is in `requirements-build.txt`).

## Automatic build after every commit

Turn it on once:

```bash
packaging/macos/enable_autobuild.sh
```

From then on, every `git commit` starts a build of that commit in the background. When the build passes its self-test, it replaces **/Applications/Ebay Lister.app** and you get a notification. If it fails, you get a notification too. The log is `build/autobuild/autobuild.log`.

* It builds a clean copy of the commit, not your working folder, so uncommitted edits never end up in the app. If commits come in while a build is running, it builds again afterwards with the newest one.
* Build and install without committing: `packaging/macos/autobuild.sh` (the last commit) or `packaging/macos/autobuild.sh --working-tree` (the folder as it is now).
* Skip it for one commit: `EBAY_LISTER_NO_AUTOBUILD=1 git commit ...`. Turn it off: `packaging/macos/enable_autobuild.sh --off`.
* The hook lives in `.githooks/post-commit`; the enable script points `core.hooksPath` at that folder and remembers which Python to build with (`git config ebaylister.python`).

The script creates its own build environment (`.venv-build`), installs PyInstaller, Pillow and tkinterdnd2 into it, runs the tests, then builds. Running it again rebuilds from scratch.

## 1. Use the right Python

Build with **Python from python.org** (3.11 or newer): <https://www.python.org/downloads/macos/>.

* It ships a modern Tk (8.6.13+), and that Tk is what goes into the app.
* Don't use Apple's `/usr/bin/python3`. Its old Tk has drawing bugs and missing features.
* Homebrew Python works if you also run `brew install python-tk`. Homebrew can install Tk 9, which is newer and less tested with tkinterdnd2, so python.org is the safer choice.

To choose which Python the script uses:

```bash
PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 packaging/macos/build_mac.sh
```

The script prints the Python and Tk versions it found and stops if they're too old.

## 2. Apple Silicon vs Intel

By default the app is built for the Mac you build on: arm64 on M-series Macs, x86_64 on Intel.

* **For your own Mac:** nothing to do.
* **For both kinds:** use the *universal2* python.org installer and run `TARGET_ARCH=universal2 packaging/macos/build_mac.sh`. Every bundled library (Pillow, tkinterdnd2) must also be universal; if PyInstaller complains, build separately on each kind of Mac instead.

## 3. App icon (optional)

Save a square PNG, 1024×1024 is best, as `packaging/macos/icon.png`. The build script turns it into `EbayLister.icns` with macOS's `sips` and `iconutil` tools. Without one, the app uses the generic icon.

## 4. Opening an unsigned app

An app you build yourself is not signed by Apple, so the first time you open it macOS says it "can't be opened" or that the developer can't be verified. This is normal.

* **macOS 15 (Sequoia) and later:** try to open the app once. Then go to **System Settings › Privacy & Security**, scroll down to the message about Ebay Lister, and click **Open Anyway**.
* **macOS 14 and earlier:** right-click (or Control-click) the app › **Open** › **Open**.
* **Or, in Terminal:** `xattr -dr com.apple.quarantine "/Applications/Ebay Lister.app"`

You only need to do this once. It's only an issue when the app is copied or downloaded from somewhere else; an app you built on the same Mac usually opens straight away.

## 5. Signing and notarizing (only for sharing with other people)

To give the app to others without the warning above, you need an **Apple Developer account** ($99/year).

1. In Xcode › Settings › Accounts (or at developer.apple.com), create a **Developer ID Application** certificate.
2. Find its exact name: `security find-identity -v -p codesigning`
3. Save notarization credentials once:
   ```bash
   xcrun notarytool store-credentials ebay-lister-notary \
       --apple-id you@example.com --team-id TEAMID --password <app-specific-password>
   ```
   Create an app-specific password at <https://account.apple.com> › Sign-In and Security.
4. Build, sign and notarize:
   ```bash
   CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
   NOTARY_PROFILE=ebay-lister-notary \
   packaging/macos/build_mac.sh
   ```

PyInstaller signs the app with the "hardened runtime" Apple requires, using `packaging/macos/entitlements.plist`. That file contains two exceptions Python apps need to load their bundled libraries. The script then signs the .dmg, sends it to Apple for notarization, and attaches ("staples") the approval to it.

## How the packaged app behaves

* **Your data:** still in `~/.ebay_lister/` (settings, templates, Items Database, photo copies), so the app and `python run.py` share the same data. Copying in a new version of the app never touches your data.
* **Error log:** a double-clicked app has no Terminal, so errors are written to `~/.ebay_lister/app.log`. If something goes wrong, the error message tells you where the log is.
* **Appearance:** the app is dark by default, whatever macOS is set to. Change it in Settings › Appearance (Dark / Light / Match macOS). The spec sets `NSRequiresAquaSystemAppearance` to false so Dark Aqua is allowed.
* **Updating:** build again and replace the app in Applications.

## Files

```
packaging/macos/
├── build_mac.sh          one-command build: environment, tests, icon, app, (sign), dmg, (notarize)
├── autobuild.sh          build the latest commit and install it in /Applications (used by the git hook)
├── enable_autobuild.sh   turn the after-every-commit build on or off
├── EbayLister.spec    PyInstaller recipe: name, icon, bundle id, Info.plist, bundled tkdnd
├── entitlements.plist    hardened-runtime exceptions (used only when signing)
├── make_icns.sh          icon.png -> EbayLister.icns
└── icon.png              (optional, you provide it)
```

## Troubleshooting

| Problem | Fix |
|---|---|
| App opens and closes immediately | Check `~/.ebay_lister/app.log`. Or run `"dist/Ebay Lister.app/Contents/MacOS/Ebay Lister"` in Terminal to see the error. |
| "Tk 8.6+ is required" | Install Python from python.org and pass it with `PYTHON=...` |
| Drag & drop from Finder doesn't work in the app | Make sure `tkinterdnd2` installed during the build (the script installs it). Look for `note: tkinterdnd2 not bundled` in the build output. |
| Blurry text | Rebuild. `NSHighResolutionCapable` is already set in the spec; it only takes effect in a freshly built app. |
| "damaged and can't be opened" | It's the quarantine flag on an unsigned app. Run the `xattr` command in section 4. |
| Want a quick build without the .dmg | `MAKE_DMG=0 packaging/macos/build_mac.sh` |

## Alternative: py2app

[py2app](https://py2app.readthedocs.io) is a Mac-only alternative to PyInstaller. I chose PyInstaller here because its Tkinter, Pillow and tkinterdnd2 support is more mature and the same spec style also works for Windows and Linux builds. If you prefer py2app: `pip install py2app`, create a `setup.py` with `app=["run.py"]`, `options={"py2app": {"packages": ["ebay_lister", "tkinterdnd2", "PIL"]}}`, and run `python setup.py py2app`.
