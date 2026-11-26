"""List Item tab: one eBay listing built from a chosen template.

Pick a template from the drop-down, add photos, fill in the template's variables (one text box per
variable) plus SKU and price, check the live preview, and click Create - which adds the item to the
queue (default) or lists it right away (see :class:`~ebay_lister.ui.listing_runner.ListingModeSelector`).
"""

import tkinter as tk
from tkinter import messagebox, ttk

from ebay_lister.config import APP_NAME, MAX_TITLE_LEN
from ebay_lister.core import variables as V
from ebay_lister.core.text import make_sku
from ebay_lister.core.validation import validate_listing, validate_title
from ebay_lister.services.listing import ListingJob
from ebay_lister.ui.listing_runner import ListingModeSelector, run_listing_job
from ebay_lister.ui.photo_strip import PhotoStrip
from ebay_lister.ui.tabs.base import BaseTab
from ebay_lister.ui.theme import P
from ebay_lister.ui.widgets import Choice, FormGrid, TextLabel, make_text, text_get, text_set


class VariableInputs(ttk.Frame):
    """One text box per template variable. Values typed for a name are kept when switching templates."""

    def __init__(self, master, on_change):
        super().__init__(master)
        self.on_change = on_change
        self.columnconfigure(1, weight=1)
        self._widgets = {}      # name -> StringVar | Text
        self._memory = {}       # name -> last value typed (survives template switches)

    def build(self, template):
        self._remember()
        for w in self.winfo_children():
            w.destroy()
        self._widgets = {}
        variables = template.get("variables", [])
        required = set(V.required(template))
        if not variables:
            ttk.Label(self, text="This template has no variables - add some on the Templates tab, then use "
                                 "{NAME} in its title and description.", foreground=P.muted).grid(sticky="w")
            return
        for r, var in enumerate(variables):
            name = var["name"]
            label = f"{name}{' *' if name in required else ''}"
            ttk.Label(self, text=label).grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=3)
            value = self._memory.get(name, var.get("default", ""))
            if var.get("multiline"):
                frame, box = make_text(self, height=4, width=70)
                text_set(box, value)
                box.bind("<KeyRelease>", lambda e: self.on_change())
                frame.grid(row=r, column=1, sticky="we", pady=3)
                self._widgets[name] = box
            else:
                sv = tk.StringVar(value=value)
                sv.trace_add("write", lambda *a: self.on_change())
                ttk.Entry(self, textvariable=sv, width=48).grid(row=r, column=1, sticky="w", pady=3)
                self._widgets[name] = sv
        ttk.Label(self, text="* used in the title, so it must be filled in.", foreground=P.muted).grid(
            row=len(variables), column=1, sticky="w")

    def values(self):
        out = {}
        for name, w in self._widgets.items():
            out[name] = w.get() if isinstance(w, tk.StringVar) else text_get(w)
        return out

    def reset(self, template):
        """Back to the template's defaults (used by Clear form)."""
        self._memory = {}
        self._widgets = {}
        self.build(template)

    def _remember(self):
        self._memory.update(self.values())


class ListItemTab(BaseTab):
    """Create one eBay listing (or queue it) from a template."""

    def __init__(self, master, app):
        super().__init__(master, app)
        b = self.body
        b.columnconfigure(1, weight=1)
        self.form = form = FormGrid(b)
        hdr, row = form.section, form.row
        self.template = None

        # ---- template picker
        hdr("Template")
        tf = ttk.Frame(b)
        self.template_choice = Choice(tf, width=40)
        self.template_choice.cb.pack(side="left")
        self.template_choice.cb.bind("<<ComboboxSelected>>", lambda e: self._template_selected())
        ttk.Button(tf, text="Edit template…", command=self._edit_template).pack(side="left", padx=6)
        self.template_info = ttk.Label(tf, text="", foreground=P.muted)
        self.template_info.pack(side="left", padx=8)
        row("Use template", tf)

        # ---- photos (template's standard photos are pinned at their positions)
        hdr("Photos")
        self.photos = PhotoStrip(b, app.log)
        form.full(self.photos)

        # ---- item details
        hdr("This item")
        skf = ttk.Frame(b)
        self.sku = tk.StringVar()
        ttk.Entry(skf, textvariable=self.sku, width=34).pack(side="left")
        ttk.Button(skf, text="Generate", command=lambda: self.sku.set(make_sku(self.rendered()["title"]))).pack(
            side="left", padx=4)
        ttk.Label(skf, text="eBay needs a SKU - one is generated if you leave it blank.",
                  foreground=P.muted).pack(side="left", padx=8)
        row("SKU", skf)
        self.price = tk.StringVar()
        row("Price (USD)", ttk.Entry(b, textvariable=self.price, width=12))
        self.vars_frame = VariableInputs(b, on_change=self.update_preview)
        row("Variables", self.vars_frame, sticky="we")

        # ---- preview
        hdr("Preview", "what will be listed")
        self.title_preview = tk.Label(b, text="", anchor="w", justify="left", bg=P.readonly_bg, fg=P.fg, relief="flat",
                                      bd=0, highlightthickness=1, highlightbackground=P.border, padx=8, pady=4,
                                      wraplength=900, font=("TkDefaultFont", 11, "bold"))
        row("Title", self.title_preview, sticky="we")
        self.title_count = TextLabel(b, text="")
        form.full(self.title_count, column=1, columnspan=1, sticky="w")
        self.previews = {}
        for key, label, height in (("description", "Description", 9), ("condition_description", "Condition notes", 3),
                                   ("aspects", "Item specifics", 4)):
            frame, box = make_text(b, height=height, readonly=True)
            self.previews[key] = box
            row(label, frame, sticky="we")

        # ---- create
        hdr("List it")
        self.mode = ListingModeSelector(b, app, on_change=self.update_submit_label)
        row("When I click Create", self.mode)
        bf = form.full(ttk.Frame(b), sticky="w", pady=10)
        ttk.Button(bf, text="Validate", command=self.validate).pack(side="left")
        self.submit_btn = ttk.Button(bf, text="", command=self.submit)
        self.submit_btn.pack(side="left", padx=6)
        ttk.Button(bf, text="Clear form", command=lambda: self.clear(confirm=True)).pack(side="left")

        hdr("Activity log")
        self.add_log(form)

        self.templates_changed(select_id=app.settings.get("last_template_id"))
        self.update_submit_label()

    # ---- templates
    def templates_changed(self, select_id=None):
        """Refresh the drop-down after templates were added/renamed/deleted/edited."""
        store = self.app.templates
        options = [(t["name"], t["id"]) for t in store.all()]
        self.template_choice.set_options(options)
        wanted = select_id or (self.template["id"] if self.template else None)
        if not wanted or not store.get(wanted):
            wanted = options[0][1]
        self.template_choice.set_value(wanted)
        self._load_template(store.get(wanted))

    def select_template(self, template_id):
        if self.app.templates.get(template_id):
            self.template_choice.set_value(template_id)
            self._template_selected()

    def _template_selected(self):
        t = self.app.templates.get(self.template_choice.value())
        if t:
            self._load_template(t)
            self.app.settings["last_template_id"] = t["id"]
            self.app.save_settings()

    def _load_template(self, template):
        old_default = (self.template or {}).get("default_price", "")
        self.template = template
        if not self.price.get().strip() or self.price.get() == old_default:
            self.price.set(template.get("default_price", ""))
        self.photos.skipped_slots = set()
        self.photos.set_pinned(template.get("fixed_photos"))
        self.vars_frame.build(template)
        n = len(template.get("variables", []))
        self.template_info.configure(text=f"{n} variable{'s' if n != 1 else ''} · "
                                          f"category {template.get('category_name') or template.get('category_id') or '—'}")
        self.update_preview()

    def _edit_template(self):
        if self.template:
            self.app.templates_tab.select(self.template["id"])
            self.app.notebook.select(self.app.templates_tab)

    # ---- rendering / preview
    def values(self):
        return self.vars_frame.values()

    def rendered(self):
        return V.render_listing(self.template or {}, self.values())

    def update_preview(self):
        if not self.template:
            return
        r = self.rendered()
        self.title_preview.configure(text=r["title"] or " ")
        errs = validate_title(r["title"])
        left = V.placeholders(r["title"])
        if left:
            errs.insert(0, "unknown variable " + ", ".join("{" + n + "}" for n in left))
        self.title_count.configure(text=f"{len(r['title'])}/{MAX_TITLE_LEN} characters"
                                        + (f"   ⚠ {errs[0]}" if errs else "   ✔"), fg=P.bad if errs else P.ok)
        for key, box in self.previews.items():
            text_set(box, r.get(key, ""))

    def update_submit_label(self):
        self.mode.refresh()
        self.submit_btn.configure(text=self.mode.button_text())

    def on_shown(self):
        self.update_submit_label()

    # ---- validate / submit
    def _errors(self):
        errs = validate_listing(self.template, self.rendered(), self.values(), self.price.get(), self.photos.ordered(),
                                self.sku.get().strip(), account=not self.mode.queue())
        errs += [f"Template photo not found: {p} (fix it on the Templates tab, or ✕ it for this listing)"
                 for p in self.photos.missing_pins()]
        return errs

    def validate(self):
        errs = self._errors()
        if errs:
            messagebox.showwarning(APP_NAME, "Fix these before listing:\n\n• " + "\n• ".join(errs))
        else:
            messagebox.showinfo(APP_NAME, "Listing is valid ✔")

    def submit(self):
        if not self.sku.get().strip():
            self.sku.set(make_sku(self.rendered()["title"]))
        errs = self._errors()
        if errs:
            messagebox.showwarning(APP_NAME, "Fix these before listing:\n\n• " + "\n• ".join(errs))
            return
        job = ListingJob(template=dict(self.template), rendered=self.rendered(), price=self.price.get().strip(),
                         photos=self.photos.ordered(), sku=self.sku.get().strip(), values=self.values())
        queue = self.mode.queue()

        def after():
            if queue:
                self.clear()  # ready for the next item straight away
            self.update_submit_label()

        run_listing_job(self.app, self.submit_btn, job, queue=queue, on_success=after)

    def clear(self, confirm=False):
        if confirm and not messagebox.askyesno(APP_NAME, "Clear the form for a new item?"):
            return
        self.sku.set("")
        self.price.set(self.template.get("default_price", "") if self.template else "")
        self.photos.clear()
        if self.template:
            self.vars_frame.reset(self.template)
        self.update_preview()
