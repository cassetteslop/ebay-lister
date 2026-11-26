"""The queue / list-now choice and running one listing (used by the List Item tab).

* :class:`ListingModeSelector` - "When I click Create": **Add to queue** (default: instant, nothing
  uploaded; bulk-list later from the Items Database) or **List right away**.
* :func:`run_listing_job` - confirm, list in the background (or queue), record the item in the
  Items Database and show a summary.

While eBay isn't connected (e.g. your developer account is waiting for approval) Create always adds
to the queue, whatever the choice.
"""

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from ebay_lister.config import APP_NAME
from ebay_lister.core.text import parse_price
from ebay_lister.services.listing import ListingJob
from ebay_lister.ui.theme import P

MODES = (("Add to queue - save now, bulk-list later from the Items Database (no uploads now)", "queue"),
         ("List right away - upload photos and create the eBay listing now", "now"))


class ListingModeSelector(ttk.Frame):
    """Radio buttons for queue vs. list now. The choice is saved in the settings."""

    def __init__(self, master, app, on_change=None):
        super().__init__(master)
        self.app = app
        self.on_change = on_change
        self.mode = tk.StringVar(value=app.settings.get("listing_mode", "queue"))
        for label, value in MODES:
            ttk.Radiobutton(self, text=label, value=value, variable=self.mode, command=self._changed).pack(anchor="w")
        self.note = ttk.Label(self, text="", foreground=P.muted, wraplength=720, justify="left")
        self.note.pack(anchor="w", pady=(2, 0))

    def _changed(self):
        self.app.settings["listing_mode"] = self.mode.get()
        self.app.save_settings()
        if self.on_change:
            self.on_change()

    def queue(self):
        """True if Create should add to the queue (chosen, or eBay not connected)."""
        return self.mode.get() == "queue" or not self.app.ebay.connected()

    def refresh(self):
        """Update the explanation under the radio buttons."""
        n = self.app.listing_queue.count() if hasattr(self.app, "listing_queue") else 0
        if not self.app.ebay.connected():
            text = ("eBay isn't connected yet, so Create adds the item to the queue. Connect eBay on the Settings "
                    "tab, then bulk-list from the Items Database.")
        elif self.mode.get() == "queue":
            text = "Create saves the item instantly; bulk-list from Items Database › List all queued / List selected."
        else:
            text = "Photos are uploaded and the eBay listing created when you click Create."
        self.note.configure(text=(f"{n} item(s) in the queue. " if n else "") + text)

    def button_text(self):
        if self.queue():
            return "＋ Add to queue"
        return "🚀 List on eBay" if self.app.settings.get("publish_immediately", True) else "🚀 Create unpublished offer"


def confirm_text(job: ListingJob, publish):
    return (f"{job.title[:70]}\n{len(job.photos)} photos · SKU {job.sku} · ${parse_price(job.price):.2f}\n\n"
            f"{'Publish this listing on eBay now' if publish else 'Create an unpublished eBay offer now'}?")


def run_listing_job(app, button, job: ListingJob, queue=False, on_success=None):
    """List ``job`` now (in the background) or add it to the queue, record it, and report.

    ``button`` is disabled while the job runs; ``on_success`` runs if it was listed or queued."""
    service = app.listing_service

    if queue:  # instant and reversible - no confirmation, no uploads
        try:
            item_id = service.record(job, queued=True)
            app.listing_queue.add(item_id, job)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Couldn't add the item to the queue: {exc}")
            return
        app.items_tab.reload()
        app.toast(f"＋ Added to the queue: {job.title[:60]} ({app.listing_queue.count()} queued)")
        if on_success:
            on_success()
        return

    if not messagebox.askyesno(APP_NAME, confirm_text(job, service.publish)):
        return
    button.configure(state="disabled")

    def done(result):
        button.configure(state="normal")
        if not result.ok:
            messagebox.showerror(APP_NAME, f"eBay listing failed:\n\n{result.message}")
            return
        try:
            service.record(job, result)
            app.items_tab.reload()
        except Exception as exc:  # noqa: BLE001
            app.log(f"⚠ Listed, but couldn't save the item to the Items Database: {exc}")
        if on_success:
            on_success()
        state = "published" if result.published else "unpublished offer"
        if result.url:
            app.log(f"✔ eBay: {result.url}")
            if messagebox.askyesno(APP_NAME, f"✔ eBay: {result.message} ({state})\n\nOpen the listing in your browser?"):
                webbrowser.open(result.url)
        else:
            messagebox.showinfo(APP_NAME, f"✔ eBay: {result.message} ({state})")

    def failed(exc):
        button.configure(state="normal")
        messagebox.showerror(APP_NAME, str(exc))

    app.run_bg(lambda: service.run(job, app.log_bg), done, failed)
