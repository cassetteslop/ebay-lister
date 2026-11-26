"""Menu bar and keyboard shortcuts.

On macOS this builds a native menu bar: the **Ebay Lister** app menu (About, Settings… ⌘,,
Hide/Quit are added by macOS), File, Edit, View, Window and Help. Elsewhere the same menus sit at
the top of the window and use Ctrl instead of ⌘.

Shortcuts:

=========  ==========================================
⌘1 – ⌘5    switch tabs (List Item … Settings)
⌘N         new item (clears the List Item form)
⌘R         sync sales with eBay
⌘L         list all queued items
⌘S         save the template being edited (Templates tab)
⌘,         Settings (macOS app menu)
=========  ==========================================
"""

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox

import ebay_lister
from ebay_lister.config import APP_DIR, APP_NAME
from ebay_lister.ui.theme import is_mac, platform_modifier


class MenuBar:
    """Creates the menus and binds the shortcuts for one :class:`~ebay_lister.ui.app.App`."""

    def __init__(self, app):
        self.app = app
        self.root = root = app.root
        self.mac = is_mac(root)
        self.mod = platform_modifier()
        self.accel = "Command-" if self.mac else "Ctrl+"
        menubar = tk.Menu(root)

        # ---- app menu (macOS) - the name "apple" makes Tk use the application menu
        if self.mac:
            appmenu = tk.Menu(menubar, name="apple", tearoff=False)
            appmenu.add_command(label=f"About {APP_NAME}", command=self.about)
            appmenu.add_separator()
            menubar.add_cascade(menu=appmenu)
            root.createcommand("tk::mac::ShowPreferences", lambda: self.show_tab(app.settings_tab))
            root.createcommand("tk::mac::ShowHelp", self.open_guide)

        # ---- File
        file_menu = tk.Menu(menubar, tearoff=False)
        self._item(file_menu, "New Item", "n", self.new_item)
        self._item(file_menu, "New Template…", None, lambda: (self.show_tab(app.templates_tab), app.templates_tab.new()))
        file_menu.add_separator()
        self._item(file_menu, "Save Template", "s", lambda: app.templates_tab.save())
        self._item(file_menu, "Sync Sales with eBay", "r", self.sync)
        self._item(file_menu, "List All Queued Items…", "l", self.list_queued)
        self._item(file_menu, "Export Items to CSV…", None, lambda: app.items_tab.export_csv())
        file_menu.add_separator()
        self._item(file_menu, "Open Data Folder", None, lambda: reveal(APP_DIR))
        if not self.mac:  # macOS puts Quit in the app menu
            file_menu.add_separator()
            self._item(file_menu, "Quit", "q", root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        # ---- Edit (sends the standard virtual events to the focused widget)
        edit_menu = tk.Menu(menubar, tearoff=False)
        for label, event, key in (("Undo", "<<Undo>>", "z"), ("Redo", "<<Redo>>", None), (None, None, None),
                                  ("Cut", "<<Cut>>", "x"), ("Copy", "<<Copy>>", "c"), ("Paste", "<<Paste>>", "v"),
                                  ("Select All", "<<SelectAll>>", "a")):
            if label is None:
                edit_menu.add_separator()
                continue
            edit_menu.add_command(label=label, accelerator=self._accel(key) if key else "",
                                  command=lambda e=event: self._send(e))
        if not self.mac:
            self._item(edit_menu, "Settings", None, lambda: self.show_tab(app.settings_tab))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # ---- View: one entry per tab, ⌘1…⌘6
        view_menu = tk.Menu(menubar, tearoff=False)
        for n, (tab, label) in enumerate(app.tabs, 1):
            self._item(view_menu, label, str(n) if n <= 9 else None, lambda t=tab: self.show_tab(t))
        menubar.add_cascade(label="View", menu=view_menu)

        # ---- Window (macOS fills in the standard items) and Help
        if self.mac:
            menubar.add_cascade(menu=tk.Menu(menubar, name="window", tearoff=False), label="Window")
        help_menu = tk.Menu(menubar, name="help", tearoff=False)
        self._item(help_menu, "User Guide", None, self.open_guide)
        self._item(help_menu, "Helpful Links", None, lambda: self.show_tab(app.links_tab))
        self._item(help_menu, "Open Error Log", None, self.open_log)
        self._item(help_menu, "eBay API Documentation", None,
                   lambda: webbrowser.open("https://developer.ebay.com/develop/apis"))
        if not self.mac:
            help_menu.add_separator()
            self._item(help_menu, f"About {APP_NAME}", None, self.about)
        menubar.add_cascade(label="Help", menu=help_menu)

        root.configure(menu=menubar)
        self.menubar = menubar

    # ---- helpers
    def _accel(self, key):
        return f"{self.accel}{key.upper()}"  # Tk shows "Command-N" as ⌘N on macOS

    def _item(self, menu, label, key, command):
        """Add a menu item and, if ``key`` is given, bind ⌘/Ctrl+key to it."""
        menu.add_command(label=label, command=command, accelerator=self._accel(key) if key else "")
        if key:
            self.root.bind_all(f"<{self.mod}-{key}>", lambda e: (command(), "break")[1])
            if key.isalpha():
                self.root.bind_all(f"<{self.mod}-{key.upper()}>", lambda e: (command(), "break")[1])

    def _send(self, event):
        widget = self.root.focus_get()
        if widget is not None:
            widget.event_generate(event)

    # ---- actions
    def show_tab(self, tab):
        self.app.notebook.select(tab)

    def new_item(self):
        self.show_tab(self.app.list_tab)
        self.app.list_tab.clear(confirm=True)

    def sync(self):
        self.show_tab(self.app.items_tab)
        self.app.items_tab.sync()

    def list_queued(self):
        self.show_tab(self.app.items_tab)
        self.app.items_tab.list_queued()

    def about(self):
        messagebox.showinfo(f"About {APP_NAME}",
                            f"{APP_NAME} {ebay_lister.__version__}\n\n"
                            "eBay listings from reusable templates - queue them, then bulk-list.\n\n"
                            f"Your data: {APP_DIR}")

    def open_log(self):
        from ebay_lister.config import LOG_FILE
        if os.path.exists(LOG_FILE):
            reveal(LOG_FILE, select=True)
        else:
            messagebox.showinfo(APP_NAME, "No errors have been logged.")

    def open_guide(self):
        from ebay_lister.config import guide_path
        path = guide_path()
        if path:
            reveal(path, open_file=True)
        else:
            self.show_tab(self.app.links_tab)


def reveal(path, select=False, open_file=False):
    """Show a folder/file in Finder (Explorer / file manager elsewhere)."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path] if select and not open_file else ["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606 - Windows only
        else:
            subprocess.Popen(["xdg-open", path if not select else os.path.dirname(path)])
    except OSError as exc:
        messagebox.showerror(APP_NAME, f"Couldn't open {path}: {exc}")
