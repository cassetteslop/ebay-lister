"""Items Database tab: every item listed or queued through the app, with sales tracking.

Layout:

* toolbar - search, Sync with eBay, List all queued / List selected, Export CSV, running totals
* **Active listings** - unsold items that are live on eBay
* **Queued** - items saved with "Add to queue", waiting to be bulk-listed (select several with
  ⌘/Ctrl/Shift-click and use *List selected*, or *List all queued*)
* **Unpublished, sold & ended** - everything else
* **Selected item** - link to the eBay listing and the sale fields (sold, sold on, date, price,
  your cost, fees, profit, notes); *Remove from database* deletes only the local record.
"""

import csv
import json
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from ebay_lister.config import APP_NAME, MAX_TITLE_LEN
from ebay_lister.core.fees import calc_profit
from ebay_lister.core.validation import validate_title
from ebay_lister.services.database import ITEM_FIELDS, SOLD_ON, ItemsDB
from ebay_lister.services.listing_queue import BatchLister, ListingQueue
from ebay_lister.services.sync import SalesSync
from ebay_lister.ui.tabs.base import BaseTab
from ebay_lister.ui.theme import P, style_window
from ebay_lister.ui.widgets import TextLabel, load_image, make_text, text_get, text_set

STATUS_LABELS = {"queued": "queued", "unpublished": "unpublished", "active": "active", "out_of_stock": "sold out",
                 "ended": "ended", "deleted": "deleted"}


class ItemList(ttk.Frame):
    """A titled, sortable table of items (one section of the Items Database tab)."""

    COLS = (("listed", "Listed", 86), ("title", "Title", 320), ("template", "Template", 130), ("sku", "SKU", 140),
            ("price", "Price", 72), ("status", "eBay", 96), ("sold", "Sold", 46), ("sold_price", "Sold $", 72),
            ("profit", "Profit", 72))
    STATUS_COL = "#6"   # Treeview column id of the eBay status (double-click opens the listing)

    def __init__(self, master, title, height, on_select, on_open, on_sort, multi=False):
        super().__init__(master)
        self.title = title
        self.header = ttk.Label(self, text=title, style="Section.TLabel")
        self.header.pack(anchor="w", pady=(6, 2))
        tf = ttk.Frame(self)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=[c[0] for c in self.COLS], show="headings", height=height,
                                 selectmode="extended" if multi else "browse")
        for key, label, width in self.COLS:
            self.tree.heading(key, text=label, command=lambda k=key: on_sort(k))
            self.tree.column(key, width=width, anchor="w" if key in ("title", "sku", "template") else "center",
                             stretch=key == "title")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("sold", background=P.sold_row)
        self.tree.tag_configure("error", background=P.warn_row)
        self.tree.tag_configure("dim", foreground=P.muted)
        self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(self))
        self.tree.bind("<Double-Button-1>", lambda e: self._double_click(e, on_open))

    def fill(self, rows):
        """``rows``: iterable of (item_id, values tuple, tags tuple)."""
        self.tree.delete(*self.tree.get_children())
        n = 0
        for item_id, values, tags in rows:
            self.tree.insert("", "end", iid=str(item_id), values=values, tags=tags)
            n += 1
        self.header.configure(text=f"{self.title} ({n})")

    def selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def selected_ids(self):
        return [int(i) for i in self.tree.selection()]

    def select(self, item_id):
        if item_id is not None and self.tree.exists(str(item_id)):
            self.tree.selection_set(str(item_id))
            self.tree.see(str(item_id))
            return True
        return False

    def clear_selection(self):
        if self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())

    def _double_click(self, e, on_open):
        row = self.tree.identify_row(e.y)
        if row and self.tree.identify_column(e.x) == self.STATUS_COL:
            on_open(int(row))


class ItemsTab(BaseTab):
    """Browse, edit, bulk-list and sync the Items Database."""

    SORT_KEYS = {"listed": "created_at", "title": "title", "template": "template_name", "sku": "sku", "price": "price",
                 "status": "status", "sold": "sold", "sold_price": "sold_price", "profit": "profit"}

    def __init__(self, master, app):
        super().__init__(master, app, scroll=False, padding=10)
        self.current = None
        self._thumb = None
        self._sort = ("listed", True)

        # ---- toolbar
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search").pack(side="left")
        self.q = tk.StringVar()
        ttk.Entry(bar, textvariable=self.q, width=26).pack(side="left", padx=(4, 10))
        self.q.trace_add("write", lambda *a: self.reload())
        self.sync_btn = ttk.Button(bar, text="⟳ Sync with eBay", command=self.sync)
        self.sync_btn.pack(side="left", padx=(0, 10))
        self.batch_btn = ttk.Button(bar, text="", command=self.list_queued)
        self.batch_btn.pack(side="left", padx=(0, 6))
        self.batch_sel_btn = ttk.Button(bar, text="⬆ List selected", command=lambda: self.list_queued(selected=True))
        self.batch_sel_btn.pack(side="left", padx=(0, 10))
        ttk.Button(bar, text="Export CSV…", command=self.export_csv).pack(side="left")
        self.totals = TextLabel(bar, text="", font=("TkDefaultFont", 10, "bold"))
        self.totals.pack(side="right")

        # ---- sections, in a resizable split
        panes = ttk.PanedWindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, pady=(6, 0))
        self.active_list = ItemList(panes, "Active listings", 6, self._on_select, self._open_item, self.sort_by)
        self.queued_list = ItemList(panes, "Queued - ready to bulk list", 5, self._on_select, self._open_item,
                                    self.sort_by, multi=True)
        self.other_list = ItemList(panes, "Unpublished, sold & ended", 5, self._on_select, self._open_item,
                                   self.sort_by)
        for lst in (self.active_list, self.queued_list, self.other_list):
            panes.add(lst, weight=1)
        self.lists = (self.active_list, self.queued_list, self.other_list)
        ttk.Label(self, text="Tip: double-click the eBay cell to open a listing. Click a column heading to sort.",
                  foreground=P.muted).pack(anchor="w")

        # ---- selected item
        d = ttk.LabelFrame(self, text="  Selected item  ", padding=10)
        d.pack(fill="x", pady=(8, 0))
        self.thumb = tk.Label(d, bg=P.preview_bg, width=16, height=8, text="")
        self.thumb.grid(row=0, column=0, rowspan=6, sticky="nw", padx=(0, 14))
        self.d_title = TextLabel(d, text="Select an item above.", font=("TkDefaultFont", 11, "bold"),
                                 anchor="w", justify="left", wraplength=760)
        self.d_title.grid(row=0, column=1, columnspan=6, sticky="w")
        self.d_info = TextLabel(d, text="", fg=P.muted, anchor="w", justify="left", wraplength=760)
        self.d_info.grid(row=1, column=1, columnspan=6, sticky="w")
        lf = ttk.Frame(d)
        lf.grid(row=2, column=1, columnspan=6, sticky="w", pady=6)
        self.btn_open = ttk.Button(lf, text="Open on eBay", command=lambda: self._open_item(self.current))
        self.btn_queue = ttk.Button(lf, text="Edit queued listing…", command=self.edit_queued)
        self.btn_open.pack(side="left", padx=(0, 6))
        self.btn_queue.pack(side="left", padx=(0, 6))

        self.e = {k: tk.StringVar() for k in ("sold_on", "sold_date", "sold_price", "cost", "fees", "profit", "notes")}
        self.sold = tk.BooleanVar()
        ttk.Checkbutton(d, text="Sold", variable=self.sold, command=self._sold_toggled).grid(row=3, column=1, sticky="w")
        ttk.Label(d, text="Sold on").grid(row=3, column=2, sticky="e", padx=(10, 4))
        ttk.Combobox(d, textvariable=self.e["sold_on"], values=SOLD_ON, state="readonly", width=8).grid(
            row=3, column=3, sticky="w")
        ttk.Label(d, text="Sold date").grid(row=3, column=4, sticky="e", padx=(10, 4))
        ttk.Entry(d, textvariable=self.e["sold_date"], width=12).grid(row=3, column=5, sticky="w")
        mf = ttk.Frame(d)
        mf.grid(row=4, column=1, columnspan=6, sticky="w", pady=6)
        for key, label in (("sold_price", "Sold price $"), ("cost", "Your cost $"), ("fees", "Fees $"),
                           ("profit", "Profit $")):
            ttk.Label(mf, text=label).pack(side="left", padx=(0, 3))
            ttk.Entry(mf, textvariable=self.e[key], width=9).pack(side="left", padx=(0, 12))
        ttk.Button(mf, text="Calculate profit", command=self.calc).pack(side="left")
        nf = ttk.Frame(d)
        nf.grid(row=5, column=1, columnspan=6, sticky="we")
        ttk.Label(nf, text="Notes").pack(side="left", padx=(0, 4))
        ttk.Entry(nf, textvariable=self.e["notes"], width=70).pack(side="left")
        bf = ttk.Frame(d)
        bf.grid(row=6, column=1, columnspan=6, sticky="w", pady=(10, 0))
        self.save_btn = ttk.Button(bf, text="Save changes", command=self.save)
        self.save_btn.pack(side="left")
        self.del_btn = ttk.Button(bf, text="Remove from database", command=self.remove)
        self.del_btn.pack(side="left", padx=8)
        ttk.Label(bf, text="(removing only deletes the record here - it doesn't end the eBay listing)",
                  foreground=P.muted).pack(side="left")

        self.reload()
        self.show_selected()

    # ---- list
    @staticmethod
    def _fmt(v):
        return "" if v is None else f"${v:,.2f}"

    @staticmethod
    def status_text(it):
        if it.get("queue"):
            return "queued ⚠" if it.get("queue_error") else "queued"
        return STATUS_LABELS.get(it.get("status") or "", it.get("status") or "—")

    def _filtered_sorted(self):
        items = self.app.db.all()
        q = self.q.get().lower().strip()
        if q:
            items = [i for i in items if q in " ".join(str(i.get(k) or "") for k in
                                                         ("title", "sku", "template_name", "notes", "variables")).lower()]
        key, desc = self._sort
        k = self.SORT_KEYS[key]
        items.sort(key=lambda i: (i.get(k) is None, i.get(k) if not isinstance(i.get(k), str) else i[k].lower()),
                   reverse=desc)
        return items

    def _row(self, it):
        if it["sold"]:
            tags = ("sold",)
        elif it.get("queue_error"):
            tags = ("error",)
        elif it.get("status") in ("ended", "deleted", "unpublished"):
            tags = ("dim",)
        else:
            tags = ()
        values = (time.strftime("%Y-%m-%d", time.localtime(it["created_at"] or 0)), it["title"] or "",
                  it["template_name"] or "", it["sku"] or "", self._fmt(it["price"]), self.status_text(it),
                  "✔" if it["sold"] else "", self._fmt(it["sold_price"]), self._fmt(it["profit"]))
        return it["id"], values, tags

    def sort_by(self, key):
        self._sort = (key, not self._sort[1] if self._sort[0] == key else False)
        self.reload()

    def reload(self):
        """Re-read the database and refill every section (keeps the current selection)."""
        items = self._filtered_sorted()
        self.active_list.fill(self._row(i) for i in items if ItemsDB.is_active(i))
        self.queued_list.fill(self._row(i) for i in items if ItemsDB.is_queued(i))
        self.other_list.fill(self._row(i) for i in items if not ItemsDB.is_active(i) and not ItemsDB.is_queued(i))
        if self.current is not None and not any(lst.select(self.current) for lst in self.lists):
            self.current = None
        everything = self.app.db.all()
        sold = [i for i in everything if i["sold"]]
        active = sum(1 for i in everything if ItemsDB.is_active(i))
        queued = sum(1 for i in everything if ItemsDB.is_queued(i))
        revenue = sum(i["sold_price"] or 0 for i in sold)
        profit = sum(i["profit"] or 0 for i in sold)
        self.totals.configure(text=f"{len(everything)} items · {active} active · {queued} queued · {len(sold)} sold · "
                                   f"revenue ${revenue:,.2f} · profit ${profit:,.2f}")
        self.update_batch_button()

    def _on_select(self, source):
        item_id = source.selected_id()
        if item_id is None:  # selection cleared (e.g. by selecting in another section)
            self.update_batch_button()
            return
        for lst in self.lists:
            if lst is not source:
                lst.clear_selection()
        self.current = item_id
        self.show_selected()
        self.update_batch_button()

    def on_shown(self):
        self.reload()

    # ---- details
    def show_selected(self):
        """Fill the 'Selected item' panel from ``self.current``."""
        it = self.app.db.get(self.current) if self.current else None
        for w in (self.save_btn, self.del_btn):
            w.configure(state="normal" if it else "disabled")
        if not it:
            self.d_title.configure(text="Select an item above.")
            self.d_info.configure(text="")
            for v in self.e.values():
                v.set("")
            self.sold.set(False)
            for bt in (self.btn_open, self.btn_queue):
                bt.configure(state="disabled")
            self.thumb.configure(image="", text="", width=16, height=8)
            return
        self.d_title.configure(text=it["title"] or "(untitled)")
        bits = [f"listed {time.strftime('%b %d %Y', time.localtime(it['created_at'] or 0))}"]
        if it["template_name"]:
            bits.append(f"template '{it['template_name']}'")
        if it["sku"]:
            bits.append(f"SKU {it['sku']}")
        if it["price"] is not None:
            bits.append(f"price ${it['price']:.2f}")
        if it["listing_id"] or it["offer_id"]:
            bits.append(f"eBay #{it['listing_id'] or 'offer ' + str(it['offer_id'])} ({self.status_text(it)})")
        if it.get("queue"):
            bits.append("queued" + (f" - last batch error: {it['queue_error']}" if it.get("queue_error") else ""))
        values = json.loads(it["variables"]) if it.get("variables") else {}
        if values:
            bits.append(", ".join(f"{k}={v}" for k, v in values.items() if str(v).strip() and "\n" not in str(v))[:160])
        if it["last_synced"]:
            bits.append("synced " + time.strftime("%b %d %H:%M", time.localtime(it["last_synced"])))
        self.d_info.configure(text=" · ".join(b for b in bits if b))
        self.btn_open.configure(state="normal" if it["listing_url"] else "disabled")
        self.btn_queue.configure(state="normal" if it.get("queue") else "disabled")
        self.sold.set(bool(it["sold"]))
        for k in ("sold_on", "sold_date", "notes"):
            self.e[k].set(it[k] or "")
        for k in ("sold_price", "cost", "fees", "profit"):
            self.e[k].set("" if it[k] is None else f"{it[k]:.2f}")
        img = load_image(it["photo"], 120, 120)[0] if it["photo"] else None
        self._thumb = img
        if img:
            self.thumb.configure(image=img, text="", width=120, height=120)
        else:
            self.thumb.configure(image="", text="no photo", width=16, height=8)

    def _num(self, key):
        s = self.e[key].get().replace("$", "").replace(",", "").strip()
        return round(float(s), 2) if s else None

    def _sold_toggled(self):
        if self.sold.get():
            if not self.e["sold_date"].get().strip():
                self.e["sold_date"].set(time.strftime("%Y-%m-%d"))
            if not self.e["sold_on"].get():
                self.e["sold_on"].set("eBay")

    def calc(self):
        try:
            p = calc_profit(self._num("sold_price"), self._num("fees"), self._num("cost"))
        except ValueError:
            messagebox.showwarning(APP_NAME, "Sold price, cost and fees must be numbers.")
            return
        if p is None:
            messagebox.showinfo(APP_NAME, "Enter a sold price first (profit = sold price - fees - your cost).")
            return
        self.e["profit"].set(f"{p:.2f}")

    def save(self):
        if not self.current:
            return
        try:
            nums = {k: self._num(k) for k in ("sold_price", "cost", "fees", "profit")}
        except ValueError:
            messagebox.showwarning(APP_NAME, "Sold price, cost, fees and profit must be numbers (or blank).")
            return
        date = self.e["sold_date"].get().strip()
        if date and not (len(date) == 10 and date[4] == date[7] == "-"):
            messagebox.showwarning(APP_NAME, "Sold date should look like 2026-11-25.")
            return
        self.app.db.update(self.current, sold=1 if self.sold.get() else 0, sold_on=self.e["sold_on"].get() or None,
                           sold_date=date or None, notes=self.e["notes"].get().strip() or None, **nums)
        self.reload()
        self.show_selected()
        self.app.toast("Item saved.")

    def remove(self):
        if not self.current:
            return
        it = self.app.db.get(self.current)
        if not messagebox.askyesno(APP_NAME, f"Remove this item from the database?\n\n{it['title']}\n\n"
                                             "This does NOT end the listing on eBay."):
            return
        self.app.listing_queue.remove(self.current)  # also deletes queued photo copies
        self.app.db.delete(self.current)
        self.current = None
        self.reload()
        self.show_selected()

    def _open_item(self, item_id):
        it = self.app.db.get(item_id) if item_id else None
        if it and it.get("listing_url"):
            webbrowser.open(it["listing_url"])

    # ---- listing queue
    def update_batch_button(self):
        n = self.app.listing_queue.count()
        self.batch_btn.configure(text=f"⬆ List all queued ({n})", state="normal" if n else "disabled")
        sel = self.queued_list.selected_ids()
        self.batch_sel_btn.configure(text=f"⬆ List selected ({len(sel)})" if sel else "⬆ List selected",
                                     state="normal" if sel else "disabled")

    def edit_queued(self):
        it = self.app.db.get(self.current) if self.current else None
        if it and it.get("queue"):
            QueuedListingEditor(self, self.app, it)

    def list_queued(self, selected=False):
        """Bulk-list queued items (all, or the ones selected in the Queued section)."""
        app = self.app
        ids = self.queued_list.selected_ids() if selected else None
        total = len(ids) if ids else app.listing_queue.count()
        if (selected and not ids) or not total:
            return
        if not app.ebay.connected():
            messagebox.showinfo(APP_NAME, f"{total} item(s) are waiting in the queue.\n\nConnect eBay on the Settings "
                                          "tab first (your eBay developer account must be approved), then load your "
                                          "policies and location on the Templates tab.")
            return
        how = "Publish" if app.listing_service.publish else "Create unpublished offers for"
        if not messagebox.askyesno(APP_NAME, f"{how} {total} queued item(s) on eBay?\n\nPhotos are uploaded now, so "
                                             "this can take a while. Each item uses its template's current eBay "
                                             "settings. Items that sold in the meantime are skipped; failed items "
                                             "stay queued with the error."):
            return
        self.batch_btn.configure(state="disabled", text="Listing queued items…")
        self.batch_sel_btn.configure(state="disabled")
        lister = BatchLister(app.listing_queue, app.listing_service, app.templates)

        def done(rep):
            self.reload()
            self.show_selected()
            app.refresh_submit_labels()
            lines = [f"Listed: {len(rep.listed)}   Skipped: {len(rep.skipped)}   Failed: {len(rep.failed)}"]
            for title, entries in (("Listed", rep.listed), ("Failed (still queued - fix and run again)", rep.failed),
                                   ("Skipped (sold)", rep.skipped)):
                if entries:
                    shown = entries[:15] + ([f"… and {len(entries) - 15} more"] if len(entries) > 15 else [])
                    lines += ["", title + ":"] + ["• " + e for e in shown]
            (messagebox.showwarning if rep.failed else messagebox.showinfo)(APP_NAME, "\n".join(lines))

        def failed(exc):
            self.update_batch_button()
            messagebox.showerror(APP_NAME, str(exc))

        app.run_bg(lambda: lister.run(app.log_bg, item_ids=ids), done, failed)

    # ---- sync / export
    def sync(self):
        self.sync_btn.configure(state="disabled", text="Syncing…")

        def done(rep):
            self.sync_btn.configure(state="normal", text="⟳ Sync with eBay")
            self.reload()
            self.show_selected()
            lines = [f"Checked {rep.checked} listing(s)."]
            if rep.sold:
                lines += ["", "Newly sold:"] + ["• " + s for s in rep.sold]
            if rep.errors:
                lines += ["", "Problems:"] + ["• " + x for x in dict.fromkeys(rep.errors)]
            (messagebox.showwarning if rep.errors else messagebox.showinfo)(APP_NAME, "\n".join(lines))

        def err(e):
            self.sync_btn.configure(state="normal", text="⟳ Sync with eBay")
            messagebox.showerror(APP_NAME, str(e))

        sync = SalesSync(self.app.db, self.app.ebay)
        self.app.run_bg(lambda: sync.run(self.app.log_bg), done, err)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="ebay_lister_items.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        items = self.app.db.all()
        cols = ["id"] + [c for c in ITEM_FIELDS if c != "queue"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for it in items:
                row = dict(it)
                for k in ("created_at", "last_synced", "queued_at"):
                    if row.get(k):
                        row[k] = time.strftime("%Y-%m-%d %H:%M", time.localtime(row[k]))
                w.writerow([row.get(c, "") for c in cols])
        self.app.toast(f"Exported {len(items)} item(s) to {path}")


class QueuedListingEditor:
    """Window to edit a queued listing's text and price, or take it out of the queue."""

    def __init__(self, tab, app, item):
        self.tab, self.app, self.item_id = tab, app, item["id"]
        data = ListingQueue.data(item)
        rendered = data["rendered"]
        self.win = win = tk.Toplevel(tab)
        style_window(win)
        win.title("Queued listing")
        win.geometry("820x760")
        win.transient(tab.winfo_toplevel())
        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        self.r = 0

        ttk.Label(body, text=item.get("title") or "", style="Section.TLabel", wraplength=760).grid(
            row=self._next(), column=0, columnspan=2, sticky="w")
        ttk.Label(body, text=f"Template '{item.get('template_name') or '?'}' · SKU {data.get('sku') or '-'} · "
                             f"{len(data.get('photos') or [])} photos · queued "
                             + time.strftime("%b %d %Y", time.localtime(item.get("queued_at") or 0)),
                  foreground=P.muted).grid(row=self._next(), column=0, columnspan=2, sticky="w", pady=(0, 8))
        if item.get("queue_error"):
            TextLabel(body, text=f"Last batch error: {item['queue_error']}", fg=P.bad, wraplength=760,
                      justify="left").grid(row=self._next(), column=0, columnspan=2, sticky="w", pady=(0, 8))

        tf = ttk.Frame(body)
        self.title = tk.StringVar(value=rendered.get("title", ""))
        ttk.Entry(tf, textvariable=self.title, width=72).pack(fill="x")
        self.count = TextLabel(tf, text="")
        self.count.pack(anchor="w")
        self.title.trace_add("write", lambda *a: self._count())
        self._row(body, "Title", tf, "we")
        self.price = tk.StringVar(value=data.get("price") or "")
        self._row(body, "Price (USD)", ttk.Entry(body, textvariable=self.price, width=12))
        self.texts = {}
        for key, label, height in (("description", "Description", 9), ("condition_description", "Condition notes", 3),
                                   ("aspects", "Item specifics", 5)):
            frame, box = make_text(body, height=height)
            text_set(box, rendered.get(key, ""))
            self.texts[key] = box
            if key == "description":
                body.rowconfigure(self.r, weight=1)
            self._row(body, label, frame, "nsew" if key == "description" else "we")

        bf = ttk.Frame(body)
        bf.grid(row=self._next(), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bf, text="Remove from queue", command=self.unqueue).pack(side="left", padx=(0, 18))
        ttk.Button(bf, text="Cancel", command=win.destroy).pack(side="left", padx=(0, 6))
        ttk.Button(bf, text="Save", command=self.save, default="active").pack(side="left")
        self._count()

    def _next(self):
        self.r += 1
        return self.r - 1

    def _row(self, body, label, widget, sticky="w"):
        r = self._next()
        ttk.Label(body, text=label).grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=4)
        widget.grid(row=r, column=1, sticky=sticky, pady=4)

    def _count(self):
        t = self.title.get()
        errs = validate_title(t)
        self.count.configure(text=f"{len(t)}/{MAX_TITLE_LEN} characters" + (f"   ⚠ {errs[0]}" if errs else "   ✔"),
                             fg=P.bad if errs else P.ok)

    def save(self):
        errs = validate_title(self.title.get())
        try:
            price = f"{float(self.price.get().replace('$', '').replace(',', '').strip()):.2f}"
        except ValueError:
            errs.append("Price must be a number.")
        if errs:
            messagebox.showwarning(APP_NAME, "\n".join(errs), parent=self.win)
            return
        self.app.listing_queue.update(self.item_id, price=price, title=self.title.get().strip(),
                                      **{k: text_get(box) for k, box in self.texts.items()})
        self._close()
        self.app.toast("Queued listing saved.")

    def unqueue(self):
        if messagebox.askyesno(APP_NAME, "Remove this item from the queue? It stays in the Items Database; it just "
                                         "won't be listed.", parent=self.win):
            self.app.listing_queue.remove(self.item_id)
            self._close()

    def _close(self):
        self.win.destroy()
        self.tab.reload()
        self.tab.show_selected()
        self.app.refresh_submit_labels()
