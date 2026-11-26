#!/usr/bin/env python3
"""Launcher: ``python run.py`` (same as ``python -m ebay_lister``). Also the PyInstaller entry point.

``python run.py --self-test [report.txt]`` checks the installation/build without touching your data.
"""

import sys

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from ebay_lister.selftest import main as self_test
        sys.exit(self_test(sys.argv))
    from ebay_lister.ui.app import main
    main()
