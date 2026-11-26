"""Settings tab: eBay credentials and connection, publishing, appearance.

eBay sign-in uses your app's RuName: you approve access in the browser, then paste the address
you land on back into the app. Switching between Production and Sandbox signs you out (tokens
differ per environment). Until eBay is connected, Create on the List Item tab adds items to the
queue.
"""

import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog, ttk

from ebay_lister.api.http import ApiError
from ebay_lister.config import APP_NAME, EBAY_ENVS, SETTINGS_FILE
from ebay_lister.ui.tabs.base import BaseTab
from ebay_lister.ui.theme import APPEARANCES, P
from ebay_lister.ui.widgets import Choice


class SettingsTab(BaseTab):
    """eBay credentials, connection status and app options."""

    def __init__(self, master, app):
        super().__init__(master, app)
        b = self.body
        s = app.settings
        self.vars = {k: tk.StringVar(value=s.get(k, "")) for k in ("ebay_client_id", "ebay_client_secret", "ebay_runame")}

        # ---- eBay
        ef = ttk.LabelFrame(b, text="  eBay  ", padding=12)
        ef.pack(fill="x", pady=(0, 12))
        ttk.Label(ef, text="From developer.ebay.com › Application Keys (App ID + Cert ID) and User Tokens › "
                           "'Get a Token from eBay via Your Application' (RuName).",
                  foreground=P.muted, wraplength=760, justify="left").grid(row=0, column=0, columnspan=3, sticky="w",
                                                                         pady=(0, 8))
        ttk.Label(ef, text="Environment").grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.env = Choice(ef, EBAY_ENVS, width=30)
        self.env.set_value(s.get("ebay_env", "production"))
        self.env.cb.grid(row=1, column=1, sticky="w", pady=3)
        r = 2
        for key, label, show in (("ebay_client_id", "App ID (Client ID)", ""),
                                 ("ebay_client_secret", "Cert ID (Client Secret)", "•"),
                                 ("ebay_runame", "RuName (redirect URL name)", "")):
            ttk.Label(ef, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
            ttk.Entry(ef, textvariable=self.vars[key], width=60, show=show).grid(row=r, column=1, sticky="w")
            r += 1
        self.publish = tk.BooleanVar(value=bool(s.get("publish_immediately", True)))
        ttk.Checkbutton(ef, text="Publish listings immediately (otherwise an unpublished offer is created, which "
                                 "doesn't show in Seller Hub)", variable=self.publish).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(10, 4))
        r += 1
        bb = ttk.Frame(ef)
        bb.grid(row=r, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(bb, text="Save settings", command=self.save).pack(side="left")
        ttk.Button(bb, text="Connect to eBay…", command=self.connect).pack(side="left", padx=6)
        ttk.Button(bb, text="Disconnect", command=self.disconnect).pack(side="left")
        r += 1
        self.status = ttk.Label(ef, text="", font=("TkDefaultFont", 10, "bold"))
        self.status.grid(row=r, column=0, columnspan=3, sticky="w")

        # ---- appearance
        af = ttk.LabelFrame(b, text="  Appearance  ", padding=12)
        af.pack(fill="x", pady=(0, 12))
        self.appearance = tk.StringVar(value=s.get("appearance", "dark"))
        for label, value in APPEARANCES:
            ttk.Radiobutton(af, text=label, value=value, variable=self.appearance,
                            command=self._appearance_changed).pack(side="left", padx=(0, 18))
        self.appearance_note = ttk.Label(af, text="", foreground=P.muted)
        self.appearance_note.pack(side="left", padx=8)

        ttk.Label(b, text=f"Settings are stored locally in {SETTINGS_FILE}", foreground=P.muted).pack(anchor="w")
        self.update_status()

    def save(self, quiet=False):
        for k, v in self.vars.items():
            self.app.settings[k] = v.get().strip()
        self.app.settings["publish_immediately"] = self.publish.get()
        self.app.settings["appearance"] = self.appearance.get()
        new_env = self.env.value() or "production"
        if new_env != self.app.settings.get("ebay_env"):
            self.app.settings["ebay_env"] = new_env
            self.disconnect(quiet=True)  # tokens are environment-specific
        self.app.save_settings()
        self.update_status()
        if not quiet:
            self.app.toast("Settings saved.")

    def _appearance_changed(self):
        """Saved immediately; the palette is built at start-up, so it applies after a restart."""
        self.app.settings["appearance"] = self.appearance.get()
        self.app.save_settings()
        self.appearance_note.configure(text=f"Saved - restart {APP_NAME} to apply.")

    def connect(self):
        self.save(quiet=True)
        try:
            url = self.app.ebay.auth_url()
        except ApiError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        webbrowser.open(url)
        pasted = simpledialog.askstring(
            "Connect to eBay",
            "1. Sign in to eBay in the browser window that just opened and click 'Agree'.\n"
            "2. eBay then sends you to your RuName's 'accept' page.\n"
            "3. Copy the FULL address from the browser's address bar (it contains code=...) and paste it here:",
            parent=self)
        if not pasted:
            return
        self.status.configure(text="Exchanging code with eBay…", foreground=P.warn)
        self.app.run_bg(lambda: self.app.ebay.exchange_code(pasted),
                        on_ok=lambda _: (self.update_status(), self.app.toast("Connected to eBay!"),
                                         self.app.templates_tab.load_from_ebay()),
                        on_err=lambda e: (self.update_status(), messagebox.showerror(APP_NAME, str(e))))

    def disconnect(self, quiet=False):
        for k in ("ebay_access_token", "ebay_refresh_token"):
            self.app.settings[k] = ""
        self.app.settings["ebay_token_expires_at"] = 0
        self.app.settings["ebay_refresh_expires_at"] = 0
        self.app.save_settings()
        if not quiet:
            self.update_status()

    def update_status(self):
        s = self.app.settings
        if s.get("ebay_refresh_token"):
            exp = s.get("ebay_refresh_expires_at") or 0
            until = f" · re-connect needed by {time.strftime('%b %d %Y', time.localtime(exp))}" if exp else ""
            self.status.configure(text=f"✔ Connected to eBay ({s.get('ebay_env')}){until}", foreground=P.ok)
        else:
            self.status.configure(text="✖ eBay not connected - Create adds items to the queue until you connect",
                                  foreground=P.bad)
        if hasattr(self.app, "list_tab"):  # connecting changes what Create does on List Item
            self.app.refresh_submit_labels()
