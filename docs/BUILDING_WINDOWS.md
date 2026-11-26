# Building the Windows app

The app is packaged with [PyInstaller](https://pyinstaller.org) as a **one-folder** app: `dist\Ebay Lister\Ebay Lister.exe` plus its support files. That starts faster and trips antivirus false positives less than a single-file exe. Python, Tk, Pillow and the tkdnd drag-and-drop library are all included, so the PC doesn't need Python.

## GitHub Actions (automatic)

[`.github/workflows/build-windows.yml`](../.github/workflows/build-windows.yml) runs on a `windows-latest` runner:

| Trigger | Result |
|---|---|
| push to `main`, pull request, **Actions › Build Windows app › Run workflow** | build artifact **Ebay-Lister-windows** (kept 30 days) |
| push a tag `v*` (e.g. `git tag v1.0.0 && git push origin v1.0.0`) | the above, plus a **GitHub Release** with `Ebay-Lister-<version>-windows.zip` |

Steps:
1. Install Python 3.12, then `requirements-build.txt` (Pillow, tkinterdnd2, PyInstaller).
2. Run the tests (`python -m unittest discover -s tests -t .`).
3. Run `python run.py --self-test` from source.
4. Make an icon from `packaging/windows/icon.png`, if there is one.
5. Build with `packaging/windows/ebay_lister.spec`.
6. **Self-test the built exe:** run `"Ebay Lister.exe" --self-test report.txt`. It imports every module and builds the window hidden, using a throw-away data folder. The build fails unless the report ends with `SELF-TEST OK`, which catches anything PyInstaller missed.
7. Upload the artifact; on tags, zip it and publish the Release.

The version comes from `ebay_lister/__init__.py` (`__version__`). Bump it before tagging, and keep `pyproject.toml` in step.

## Building locally (on Windows)

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-build.txt
python -m unittest discover -s tests -t .
python packaging\windows\make_ico.py                # optional, needs packaging\windows\icon.png
python -m PyInstaller --noconfirm --clean packaging\windows\ebay_lister.spec
start "" "dist\Ebay Lister\Ebay Lister.exe"
```

Check a build without touching your data:

```powershell
Start-Process "dist\Ebay Lister\Ebay Lister.exe" -ArgumentList "--self-test", "$PWD\selftest.txt" -Wait
type selftest.txt
```

## Icon
Put a square PNG (256×256 or larger) at `packaging/windows/icon.png` and commit it. Both the workflow and the local steps turn it into `ebay_lister.ico` for the exe. Without it, the exe uses PyInstaller's default icon.

## Running the app
* Unzip the whole folder anywhere, for example `C:\Apps\Ebay Lister\`, and run `Ebay Lister.exe`. Pin it to Start or the taskbar if you like. Don't move the exe out of its folder.
* **"Windows protected your PC"** (SmartScreen) appears because the exe isn't code-signed. Click **More info → Run anyway**. If Defender quarantines it (a known false positive with PyInstaller apps), restore it and add an exclusion, or sign the build (see below).
* **Data:** your data is kept in `%APPDATA%\Ebay Lister\`, so replacing the app folder with a new build keeps everything. For a portable setup, set the `EBAY_LISTER_HOME` environment variable to a folder next to the app.
* **Errors:** a windowed exe has no console, so errors go to `%APPDATA%\Ebay Lister\app.log`. Use **Help › Open Error Log**.

## Code signing (optional)
To remove the SmartScreen warning, sign `Ebay Lister.exe` with a code-signing certificate, for example an OV/EV certificate or Azure Trusted Signing. Add a step after the build, such as `signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p $env:CERT_PASSWORD "dist\Ebay Lister\Ebay Lister.exe"`, and keep the certificate and password in repository secrets.

## Troubleshooting
| Problem | Fix |
|---|---|
| CI: "The packaged app failed its self-test" | Read the report printed in the log. A `ModuleNotFoundError` usually means a module that's only imported dynamically; add it to `hiddenimports` in the spec. |
| CI: the self-test fails at `window:` with a Tk/display error | GitHub's Windows runners normally have a desktop session. If a runner image ever lacks one, set `KEEP_GOING_ON_TK_ERRORS = True` in `ebay_lister/selftest.py`; the import check still runs. |
| Drag & drop from Explorer doesn't work | Check the build log for `note: tkinterdnd2 not bundled`, and that `requirements-build.txt` installed it. |
| Blurry text | The app asks Windows for DPI awareness at start-up. Check *Properties › Compatibility › Change high DPI settings* isn't overriding it. |
