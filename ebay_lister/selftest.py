"""``--self-test``: check that a packaged build contains everything, without touching real data.

Used by the GitHub Actions Windows build (and handy after building on any machine)::

    "Ebay Lister.exe" --self-test report.txt      # packaged app (windowed: no console, so write a file)
    python run.py --self-test                      # from source: prints the report

It imports every module, checks the optional packages, then builds the whole app window hidden,
using a throw-away data folder, and closes it. The last line of the report is ``SELF-TEST OK`` or
``SELF-TEST FAILED``; the exit code is 0 or 1.

This module must not import ``ebay_lister.config`` at the top: the data folder is redirected to a
temporary directory *before* config is imported.
"""

import importlib
import os
import pkgutil
import sys
import tempfile
import traceback

KEEP_GOING_ON_TK_ERRORS = False  # True would let a build pass on machines without a display


def _report(lines, path):
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    elif sys.stdout is not None:
        sys.stdout.write(text)


def run(path=None):
    lines, ok = [], True
    os.environ["EBAY_LISTER_HOME"] = tempfile.mkdtemp(prefix="ebay-lister-selftest-")
    lines.append(f"Python {sys.version.split()[0]} on {sys.platform}; frozen={bool(getattr(sys, 'frozen', False))}")
    try:
        import ebay_lister
        lines.append(f"Ebay Lister {ebay_lister.__version__}")
        for mod in pkgutil.walk_packages(ebay_lister.__path__, "ebay_lister."):
            if mod.name.endswith(".__main__"):
                continue
            importlib.import_module(mod.name)
        lines.append("imports: ok")
    except Exception:  # noqa: BLE001
        ok = False
        lines.append("imports: FAILED\n" + traceback.format_exc())
    if ok:
        from ebay_lister.ui.compat import HAS_DND, HAS_PIL
        lines.append(f"pillow: {'yes' if HAS_PIL else 'NO'}; tkinterdnd2: {'yes' if HAS_DND else 'NO'}")
        try:
            from ebay_lister.ui.app import App
            app = App()
            app.root.withdraw()
            app.root.update_idletasks()
            lines.append(f"window: ok ({len(app.tabs)} tabs, theme {app.theme}, "
                         f"{len(app.templates.names())} starter templates)")
            app.db.close()
            app.root.destroy()
        except Exception:  # noqa: BLE001
            ok = KEEP_GOING_ON_TK_ERRORS
            lines.append("window: FAILED\n" + traceback.format_exc())
    lines.append("SELF-TEST OK" if ok else "SELF-TEST FAILED")
    _report(lines, path)
    return 0 if ok else 1


def main(argv):
    """``argv``: sys.argv. The argument after ``--self-test`` (if any) is the report file."""
    i = argv.index("--self-test")
    path = argv[i + 1] if len(argv) > i + 1 else None
    return run(path)
