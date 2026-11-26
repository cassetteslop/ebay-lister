"""Base class shared by all notebook tabs."""

import time
from tkinter import ttk

from ebay_lister.ui.theme import P
from ebay_lister.ui.widgets import ScrollFrame, make_text


class BaseTab(ttk.Frame):
    """A notebook tab with access to the :class:`~ebay_lister.ui.app.App`.

    * ``self.app``  - the application (settings, template, clients, db, run_bg, log...)
    * ``self.body`` - where to put widgets: a scrollable frame when ``scroll=True``
    * :meth:`add_log` creates an activity log that receives every ``app.log()`` message
    * :meth:`on_shown` is called each time the user switches to the tab
    """

    def __init__(self, master, app, scroll=True, padding=0):
        super().__init__(master, padding=padding)
        self.app = app
        self.log_text = None
        if scroll:
            self.scroll = ScrollFrame(self)
            self.scroll.pack(fill="both", expand=True)
            self.body = self.scroll.body
        else:
            self.scroll = None
            self.body = self

    def on_shown(self):
        """Hook: called when the tab becomes visible. Override if needed."""

    # ---- activity log
    def add_log(self, form, height=8):
        """Add a dark activity-log box as the next full-width row of ``form`` and register it with the app."""
        frame, self.log_text = make_text(form.parent, height=height, readonly=True, bg=P.log_bg, fg=P.log_fg,
                                         insertbackground=P.log_fg)
        form.full(frame)
        self.app.register_log(self)
        return frame

    def log(self, msg):
        if self.log_text is None:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", time.strftime("[%H:%M:%S] ") + msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
