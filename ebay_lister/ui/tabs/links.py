"""Helpful Links tab: one-click shortcuts to eBay seller pages.

The links come from :data:`ebay_lister.config.HELPFUL_LINKS`, so adding a link means adding
one line there - no UI code changes needed.
"""

import webbrowser
from tkinter import ttk

from ebay_lister.config import HELPFUL_LINKS
from ebay_lister.ui.tabs.base import BaseTab
from ebay_lister.ui.theme import P
from ebay_lister.ui.widgets import FormGrid, TextLabel


class LinkCard(ttk.Frame):
    """A clickable title, its description and URL, plus Open / Copy buttons."""

    def __init__(self, master, app, title, url, description):
        super().__init__(master, padding=(0, 4))
        self.app = app
        self.url = url
        link = TextLabel(self, text=title, fg=P.link, bg=P.bg, cursor="hand2", font=("TkDefaultFont", 11, "underline"))
        link.grid(row=0, column=0, sticky="w")
        link.bind("<Button-1>", lambda e: self.open())
        ttk.Button(self, text="Open", width=7, command=self.open).grid(row=0, column=1, padx=(12, 4))
        ttk.Button(self, text="Copy link", command=self.copy).grid(row=0, column=2)
        TextLabel(self, text=description, fg=P.fg, bg=P.bg, anchor="w", justify="left", wraplength=640).grid(
            row=1, column=0, columnspan=3, sticky="w")
        TextLabel(self, text=url, fg=P.muted, bg=P.bg, anchor="w", font=("TkDefaultFont", 9)).grid(
            row=2, column=0, columnspan=3, sticky="w")

    def open(self):
        webbrowser.open(self.url)

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.url)
        self.app.toast(f"Copied: {self.url}")


class HelpfulLinksTab(BaseTab):
    """Shortcuts to orders, vacation/away settings and listing managers on both marketplaces."""

    def __init__(self, master, app):
        super().__init__(master, app)
        form = FormGrid(self.body)
        form.full(ttk.Label(self.body, text="Links open in your default browser (you may need to sign in).",
                            foreground=P.muted), sticky="w")
        for section, links in HELPFUL_LINKS:
            form.section(section, pady=(16, 2))
            for title, url, description in links:
                form.full(LinkCard(self.body, app, title, url, description), sticky="w")
