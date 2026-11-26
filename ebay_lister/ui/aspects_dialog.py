"""Item specifics picker: eBay's suggested item specifics for a category, with their allowed values.

Used by the Templates tab (the template's item specifics, where values can be ``{VARIABLES}``) and
the List Item tab (one item's specifics). eBay's list comes from the Taxonomy API
(:meth:`~ebay_lister.api.ebay.EbayClient.item_aspects`), which only needs the eBay keys in Settings,
not a connected account. Lists are cached per category for the session.

Required specifics are marked *, recommended ones are shown first; *Show all* adds the rest.
Clicking *Apply* merges the chosen values into the text (see :func:`~ebay_lister.core.text.merge_aspects`):
changed lines are updated in place, new ones appended, and clearing a value removes its line.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from ebay_lister.config import APP_NAME
from ebay_lister.core.text import aspect_lines, merge_aspects
from ebay_lister.ui.theme import P, style_window
from ebay_lister.ui.widgets import ScrollFrame

_cache = {}           # category id -> aspects list
MAX_VALUES = 300      # values offered per drop-down (some aspects have thousands)


def suggest_aspects(parent, app, category_id, current_text, on_apply, note=""):
    """Fetch eBay's item specifics for ``category_id`` (in the background) and open the picker.
    ``on_apply(new_text)`` receives the merged item specifics text."""
    category_id = str(category_id or "").strip()
    if not category_id:
        messagebox.showinfo(APP_NAME, "Choose an eBay category first (Templates tab › Category › Suggest…). "
                                      "Item specifics depend on the category.")
        return
    if category_id in _cache:
        AspectsDialog(parent, category_id, _cache[category_id], current_text, on_apply, note)
        return
    app.toast(f"Loading item specifics for category {category_id} from eBay…")

    def loaded(aspects):
        _cache[category_id] = aspects
        AspectsDialog(parent, category_id, aspects, current_text, on_apply, note)

    app.run_bg(lambda: app.ebay.item_aspects(category_id), on_ok=loaded,
               on_err=lambda e: messagebox.showerror(APP_NAME, f"Couldn't load item specifics from eBay:\n\n{e}\n\n"
                                                               "Check your eBay keys on the Settings tab."))


def ranked(aspects, current_names=()):
    """Required first, then recommended, then the rest; flags which are shown before *Show all*."""
    have = {n.lower() for n in current_names}
    order = sorted(aspects, key=lambda a: (not a.get("required"), not a.get("recommended")))
    return [(a, bool(a.get("required") or a.get("recommended") or a["name"].lower() in have)) for a in order]


class AspectsDialog:
    def __init__(self, parent, category_id, aspects, current_text, on_apply, note=""):
        self.on_apply = on_apply
        self.current_text = current_text
        self.current = {k.lower(): v for k, v in aspect_lines(current_text).items()}
        self.rows = ranked(aspects, self.current)
        self.vars = {}      # aspect name -> StringVar
        self.win = win = tk.Toplevel(parent)
        style_window(win)
        win.title(f"Item specifics - category {category_id}")
        win.transient(parent.winfo_toplevel())
        win.geometry("760x620")

        top = ttk.Frame(win, padding=(14, 12, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Pick or type a value for each item specific. * = required by eBay. "
                            "Leave a box empty to leave it out.", foreground=P.muted, wraplength=700,
                  justify="left").pack(anchor="w")
        if note:
            ttk.Label(top, text=note, foreground=P.muted, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
        self.show_all = tk.BooleanVar(value=False)
        n_more = sum(1 for _, shown in self.rows if not shown)
        if n_more:
            ttk.Checkbutton(top, text=f"Show all ({n_more} more)", variable=self.show_all,
                            command=self._fill).pack(anchor="w", pady=(6, 0))

        self.scroll = ScrollFrame(win)
        self.scroll.pack(fill="both", expand=True)
        self.scroll.body.columnconfigure(1, weight=1)

        bf = ttk.Frame(win, padding=12)
        bf.pack(fill="x")
        ttk.Button(bf, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(bf, text="Apply", command=self.apply, default="active").pack(side="right", padx=6)
        win.bind("<Escape>", lambda e: win.destroy())
        self._fill()

    def _fill(self):
        body = self.scroll.body
        for w in body.winfo_children():
            w.destroy()
        r = 0
        for aspect, shown in self.rows:
            if not (shown or self.show_all.get()):
                continue
            name = aspect["name"]
            var = self.vars.setdefault(name, tk.StringVar(value=self.current.get(name.lower(), "")))
            label = name + (" *" if aspect.get("required") else "")
            ttk.Label(body, text=label, foreground=P.fg if aspect.get("required") else P.muted).grid(
                row=r, column=0, sticky="w", padx=(0, 10), pady=2)
            values = aspect.get("values", [])[:MAX_VALUES]
            # values eBay doesn't allow typing are still typeable here, so {VARIABLES} work in templates
            ttk.Combobox(body, textvariable=var, values=values, width=44).grid(row=r, column=1, sticky="w", pady=2)
            hint = []
            if aspect.get("multiple"):
                hint.append("several allowed: a | b")
            if not aspect.get("free_text", True):
                hint.append("pick from the list")
            if hint:
                ttk.Label(body, text=", ".join(hint), foreground=P.muted).grid(row=r, column=2, sticky="w", padx=8)
            r += 1
        if r == 0:
            ttk.Label(body, text="eBay has no suggested item specifics for this category.",
                      foreground=P.muted).grid(row=0, column=0, sticky="w")

    def changes(self):
        """{name: value} for every value that differs from the current text."""
        return {name: var.get().strip() for name, var in self.vars.items()
                if var.get().strip() != self.current.get(name.lower(), "")}

    def apply(self):
        self.on_apply(merge_aspects(self.current_text, self.changes()))
        self.win.destroy()
