"""Entry point: ``python -m ebay_lister`` (add ``--self-test`` to check the installation)."""

import sys

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from ebay_lister.selftest import main as self_test
        sys.exit(self_test(sys.argv))
    from ebay_lister.ui.app import main
    main()
