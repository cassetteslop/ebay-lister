"""Ebay Lister - create eBay listings from reusable templates, queue them, and bulk-list them.

Package layout (see docs/ARCHITECTURE.md for details)::

    ebay_lister/
        config.py      constants, defaults, starter templates, helpful links
        storage.py     JSON settings persistence
        core/          pure logic: variables, text, validation, payload builders, matching, fees
        api/           eBay HTTP client
        services/      templates, listing service, listing queue, items database, sales sync
        ui/            Tkinter app, widgets and one module per tab

Run with ``python -m ebay_lister`` or ``python run.py``.
"""

__version__ = "1.0.0"
