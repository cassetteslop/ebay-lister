"""Main application window.

:class:`App` is the composition root: it loads settings, opens the template store and database,
creates the eBay client and services, builds one tab per feature, and offers shared helpers that
every tab uses through ``self.app``:

* ``app.settings``                      - live settings dict (``app.save_settings()`` writes it)
* ``app.templates``                     - :class:`~ebay_lister.services.templates.TemplateStore`
* ``app.ebay``                          - eBay API client
* ``app.db``                            - the Items Database
* ``app.listing_service``               - lists one item on eBay
* ``app.listing_queue``                 - items saved with "Add to queue"
* ``app.ebay_options``                  - business policies / locations loaded from eBay (or None)
* ``app.run_bg(fn, on_ok, on_err)``     - run slow work off the UI thread
* ``app.log(msg)`` / ``app.log_bg(msg)``- write to the activity log (UI thread / any thread)
* ``app.toast(msg)``                    - status bar message (also logged)
"""

import os
import sys
import tkinter as tk
import traceback
from tkinter import ttk

from ebay_lister.api.ebay import EbayClient
from ebay_lister.config import APP_DIR, APP_NAME, DB_FILE, DEFAULT_SETTINGS, LOG_FILE, SETTINGS_FILE, TEMPLATES_FILE
from ebay_lister.services.database import ItemsDB
from ebay_lister.services.listing import ListingService
from ebay_lister.services.listing_queue import ListingQueue
from ebay_lister.services.templates import TemplateStore
from ebay_lister.storage import load_json, save_json
from ebay_lister.ui.compat import HAS_DND, HAS_PIL, TkinterDnD
from ebay_lister.ui.menus import MenuBar
from ebay_lister.ui.tabs.items import ItemsTab
from ebay_lister.ui.tabs.links import HelpfulLinksTab
from ebay_lister.ui.tabs.list_item import ListItemTab
from ebay_lister.ui.tabs.settings import SettingsTab
from ebay_lister.ui.tabs.templates import TemplatesTab
from ebay_lister.ui.tasks import TaskRunner
from ebay_lister.ui.theme import apply_theme


class App:
    """The Ebay Lister desktop application."""

    TITLE = APP_NAME + " - templates, queue and bulk listing for eBay"

    def __init__(self):
        self.settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)

        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title(self.TITLE)
        self.root.geometry("1180x900")
        self.root.minsize(980, 640)
        # the theme must be applied before any widget is created: widgets read colours from theme.P
        self.theme = apply_theme(self.root, self.settings.get("appearance", "dark"))
        self.root.report_callback_exception = self._report_ui_error

        # ---- services
        self.templates = TemplateStore(TEMPLATES_FILE)
        self.ebay = EbayClient(self.settings, self.save_settings)
        self.db = ItemsDB(DB_FILE)
        self.listing_service = ListingService(self.ebay, self.settings, self.db)
        self.listing_queue = ListingQueue(self.db)
        self.ebay_options = None
        self._log_targets = []
        self.tasks = TaskRunner(self.root, self.log)

        # ---- tabs
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=(8 if self.theme == "aqua" else 0), pady=(6 if self.theme == "aqua" else 0))
        self.notebook = nb
        self.list_tab = ListItemTab(nb, self)
        self.items_tab = ItemsTab(nb, self)
        self.templates_tab = TemplatesTab(nb, self)
        self.links_tab = HelpfulLinksTab(nb, self)
        self.settings_tab = SettingsTab(nb, self)
        self.tabs = [(self.list_tab, "List Item"), (self.items_tab, "Items Database"),
                     (self.templates_tab, "Templates"), (self.links_tab, "Helpful Links"),
                     (self.settings_tab, "Settings")]
        pad = "" if self.theme == "aqua" else "  "  # native macOS tabs size themselves
        for tab, label in self.tabs:
            nb.add(tab, text=f"{pad}{label}{pad}")
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.menubar = MenuBar(self)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.statusbar = ttk.Label(self.root, text="", anchor="w", padding=(8, 3))
        self.statusbar.pack(fill="x")

        if not self.settings.get("ebay_client_id"):
            self.log("Welcome! Add your eBay keys on the Settings tab - until then, Create adds items to the queue.")
        if not HAS_PIL:
            self.log("Tip: pip install pillow  → JPEG thumbnails and large photo previews.")
        if not HAS_DND:
            self.log("Tip: pip install tkinterdnd2  → drag & drop photos from your file manager.")

    # ---- shared helpers used by the tabs
    def save_settings(self):
        """Persist ``self.settings`` (also called by the eBay client when tokens refresh)."""
        save_json(SETTINGS_FILE, self.settings)

    def register_log(self, widget_owner):
        """Tabs with an activity log register here; ``widget_owner.log(msg)`` is called for every message."""
        self._log_targets.append(widget_owner)

    def log(self, msg):
        for target in self._log_targets:
            target.log(msg)

    def log_bg(self, msg):
        self.tasks.log_from_thread(msg)

    def toast(self, msg):
        self.statusbar.configure(text=msg)
        self.log(msg)

    def run_bg(self, fn, on_ok=None, on_err=None):
        self.tasks.run(fn, on_ok, on_err)

    def refresh_submit_labels(self):
        """Things that change what Create does (eBay connection, publish setting, queue size)."""
        self.list_tab.update_submit_label()

    def _on_tab_changed(self, _event):
        current = self.notebook.nametowidget(self.notebook.select())
        if hasattr(current, "on_shown"):
            current.on_shown()

    def quit(self):
        """Window closed: offer to save unsaved template edits."""
        tab = self.templates_tab
        if tab.is_dirty():
            from tkinter import messagebox
            answer = messagebox.askyesnocancel(APP_NAME, f"Save your changes to the template '{tab.current['name']}'?")
            if answer is None or (answer and not tab.save(quiet=True)):
                return
        self.root.destroy()

    def _report_ui_error(self, exc_type, exc, tb):
        """Unexpected errors inside button handlers etc.: keep the traceback and tell the user."""
        traceback.print_exception(exc_type, exc, tb)
        from tkinter import messagebox
        messagebox.showerror(APP_NAME, f"Something went wrong: {exc}\n\nDetails were written to {LOG_FILE}"
                             if is_frozen() else f"Something went wrong: {exc}")

    def run(self):
        self.root.mainloop()


def is_frozen():
    """True when running from a packaged app (PyInstaller sets ``sys.frozen``)."""
    return bool(getattr(sys, "frozen", False))


def _redirect_output_to_log():
    """A packaged app has no console, so send print()/tracebacks to the log file in the data folder."""
    os.makedirs(APP_DIR, exist_ok=True)
    log = open(LOG_FILE, "a", buffering=1, encoding="utf-8")  # noqa: SIM115 - kept open for the app's lifetime
    sys.stdout = sys.stderr = log


def _windows_setup():
    """Sharp text on high-DPI Windows screens and a proper taskbar icon/grouping."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001 - older Windows: just slightly blurry
        pass
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EbayLister.App")
    except Exception:  # noqa: BLE001
        pass


def main():
    """Start the app."""
    if is_frozen():
        _redirect_output_to_log()
    _windows_setup()
    App().run()
