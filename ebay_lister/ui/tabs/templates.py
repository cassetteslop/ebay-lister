"""Templates tab: create, duplicate, rename, delete and edit listing templates.

Top bar: pick a template, then **New…** (from the defaults), **Duplicate…** (a copy of the current
one - "create a new template based on an existing one"), **Rename…**, **Delete**, **Save** and
**Revert**. Switching templates with unsaved edits asks whether to save them.

Sections of a template:

* **Variables** - the text boxes that appear on the List Item tab. Use ``{NAME}`` in the title,
  description, condition notes and item specifics. *Insert {NAME}* types the placeholder at the
  cursor of the last text field you clicked; renaming a variable updates its placeholders.
* **Listing text** - title, description, condition notes, item specifics.
* **eBay listing** - category (with Suggest…), condition, default price, quantity, Best Offer.
* **Package** - weight and dimensions.
* **Standard photos** - up to three photos added to every listing at a set position.
* **Business policies & location** - loaded from your eBay account.
"""

import copy
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from ebay_lister.config import APP_NAME, CONDITIONS, MAX_PHOTOS, MAX_TITLE_LEN, PHOTO_EXTS
from ebay_lister.core import variables as V
from ebay_lister.core.matching import best_match
from ebay_lister.core.validation import validate_template, validate_template_account, validate_template_content
from ebay_lister.services.templates import TemplateError, normalize
from ebay_lister.ui.tabs.base import BaseTab
from ebay_lister.ui.theme import P, style_window
from ebay_lister.ui.widgets import Choice, FormGrid, TextLabel, category_dialog, load_image, make_text, text_get, text_set

FIXED_PHOTO_SLOTS = 3
POLICY_KEYS = (("fulfillment", "fulfillment_policy_id", "fulfillment_policy_name", "Shipping policy"),
               ("payment", "payment_policy_id", "payment_policy_name", "Payment policy"),
               ("return", "return_policy_id", "return_policy_name", "Return policy"),
               ("location", "location_key", "location_name", "Ship-from location"))
NUMERIC = ("quantity", "weight_lb", "weight_oz", "length", "width", "height")


class VariableDialog:
    """Add / edit one variable: name, default value, single- or multi-line."""

    def __init__(self, parent, variable, taken_names, on_save):
        self.on_save, self.taken = on_save, {n for n in taken_names}
        self.original = variable.get("name", "")
        self.win = win = tk.Toplevel(parent)
        style_window(win)
        win.title("Edit variable" if self.original else "Add variable")
        win.transient(parent.winfo_toplevel())
        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)
        self.name = tk.StringVar(value=variable.get("name", ""))
        self.default = tk.StringVar(value=variable.get("default", ""))
        self.multiline = tk.BooleanVar(value=bool(variable.get("multiline")))
        ttk.Label(body, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        entry = ttk.Entry(body, textvariable=self.name, width=32)
        entry.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(body, text="Letters, digits and _ (e.g. MODEL, CONDITION_NOTES). Use it as {NAME}.",
                  foreground=P.muted).grid(row=1, column=1, sticky="w")
        ttk.Label(body, text="Default value").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(body, textvariable=self.default, width=48).grid(row=2, column=1, sticky="w", pady=4)
        ttk.Checkbutton(body, text="Multi-line text box (for longer notes)", variable=self.multiline).grid(
            row=3, column=1, sticky="w", pady=4)
        bf = ttk.Frame(body)
        bf.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bf, text="Cancel", command=win.destroy).pack(side="left", padx=(0, 6))
        ttk.Button(bf, text="Save", command=self.save, default="active").pack(side="left")
        win.bind("<Return>", lambda e: self.save())
        win.bind("<Escape>", lambda e: win.destroy())
        entry.focus_set()

    def save(self):
        name = self.name.get().strip()
        if not V.is_valid_name(name):
            messagebox.showwarning(APP_NAME, "Variable names use letters, digits and _ only, and start with a letter "
                                             "(e.g. MODEL).", parent=self.win)
            return
        if name != self.original and name in self.taken:
            messagebox.showwarning(APP_NAME, f"There's already a variable called {name}.", parent=self.win)
            return
        self.win.destroy()
        self.on_save({"name": name, "default": self.default.get(), "multiline": self.multiline.get()}, self.original)


class VariablesEditor(ttk.Frame):
    """Table of a template's variables with Add / Edit / Remove / ▲ ▼ / Insert {NAME}."""

    def __init__(self, master, tab):
        super().__init__(master)
        self.tab = tab
        self.variables = []
        tf = ttk.Frame(self)
        tf.pack(fill="x")
        self.tree = ttk.Treeview(tf, columns=("name", "default", "type", "used"), show="headings", height=5,
                                 selectmode="browse")
        for key, label, width in (("name", "Variable", 170), ("default", "Default", 200), ("type", "Text box", 90),
                                  ("used", "Used in", 260)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(side="left", fill="x", expand=True)
        self.tree.bind("<Double-Button-1>", lambda e: self.edit())
        bf = ttk.Frame(self)
        bf.pack(anchor="w", pady=(6, 0))
        for text, cmd in (("Add…", self.add), ("Edit…", self.edit), ("Remove", self.remove), ("▲", lambda: self.move(-1)),
                          ("▼", lambda: self.move(1)), ("Insert {NAME} at cursor", self.insert)):
            ttk.Button(bf, text=text, command=cmd).pack(side="left", padx=(0, 6))

    def set(self, variables):
        self.variables = copy.deepcopy(variables)
        self.refresh()

    def refresh(self, keep=None):
        used = self.tab.usage()
        self.tree.delete(*self.tree.get_children())
        for i, v in enumerate(self.variables):
            where = ", ".join(used.get(v["name"], [])) or "not used yet"
            self.tree.insert("", "end", iid=str(i), values=(v["name"], v.get("default", ""),
                                                            "multi-line" if v.get("multiline") else "single line", where))
        if keep is not None and 0 <= keep < len(self.variables):
            self.tree.selection_set(str(keep))

    def _selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add(self):
        VariableDialog(self, {}, [v["name"] for v in self.variables], self._saved)

    def edit(self):
        i = self._selected()
        if i is not None:
            VariableDialog(self, self.variables[i], [v["name"] for v in self.variables], self._saved)

    def _saved(self, var, original):
        if original:
            i = next(n for n, v in enumerate(self.variables) if v["name"] == original)
            self.variables[i] = var
            if var["name"] != original:
                self.tab.rename_placeholders(original, var["name"])
        else:
            self.variables.append(var)
            i = len(self.variables) - 1
        self.refresh(keep=i)

    def remove(self):
        i = self._selected()
        if i is None:
            return
        name = self.variables[i]["name"]
        where = self.tab.usage().get(name)
        if where and not messagebox.askyesno(APP_NAME, f"{{{name}}} is still used in the {', '.join(where)}.\n\n"
                                                       "Remove the variable anyway? (The {" + name + "} text stays "
                                                       "and will be flagged until you remove it.)"):
            return
        del self.variables[i]
        self.refresh()

    def move(self, delta):
        i = self._selected()
        if i is None or not 0 <= i + delta < len(self.variables):
            return
        self.variables.insert(i + delta, self.variables.pop(i))
        self.refresh(keep=i + delta)

    def insert(self):
        i = self._selected()
        if i is None:
            messagebox.showinfo(APP_NAME, "Select a variable first, then click in the title, description, condition "
                                          "notes or item specifics where it should go.")
            return
        self.tab.insert_text("{" + self.variables[i]["name"] + "}")


class TemplatesTab(BaseTab):
    """Manage and edit templates."""

    def __init__(self, master, app):
        super().__init__(master, app)
        self.store = app.templates
        self.current = None           # the stored template being edited
        self._last_text = None        # last focused text field (for Insert {NAME})
        b = self.body
        b.columnconfigure(2, weight=1)
        self.form = form = FormGrid(b)
        add, section = form.row, form.section
        self.v = {}

        # ---- template management bar
        bar = form.full(ttk.Frame(b), sticky="w")
        ttk.Label(bar, text="Template").pack(side="left", padx=(0, 6))
        self.picker = Choice(bar, width=34)
        self.picker.cb.pack(side="left")
        self.picker.cb.bind("<<ComboboxSelected>>", lambda e: self._picked())
        for text, cmd in (("New…", self.new), ("Duplicate…", self.duplicate), ("Rename…", self.rename),
                          ("Delete", self.delete)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(6, 0))
        bar2 = form.full(ttk.Frame(b), sticky="w", pady=(8, 0))
        ttk.Button(bar2, text="Save template", command=self.save).pack(side="left")
        ttk.Button(bar2, text="Revert", command=self.revert).pack(side="left", padx=6)
        ttk.Button(bar2, text="Validate", command=self.validate).pack(side="left")
        self.status = TextLabel(bar2, text="", fg=P.muted)
        self.status.pack(side="left", padx=12)

        # ---- variables
        section("Variables", "text boxes on the List Item tab · use them as {NAME}")
        self.variables = VariablesEditor(b, self)
        form.full(self.variables)
        form.full(ttk.Label(b, text="Variables used in the title are required on the List Item tab. Write {{ or }} "
                                    "for a literal brace.", foreground=P.muted), sticky="w")

        # ---- listing text
        section("Listing text")
        self.v["title"] = tk.StringVar()
        tf = ttk.Frame(b)
        title_entry = ttk.Entry(tf, textvariable=self.v["title"], width=80)
        title_entry.pack(anchor="w", fill="x")
        title_entry.bind("<FocusIn>", lambda e: self._focus(title_entry))
        self.title_hint = TextLabel(tf, text="")
        self.title_hint.pack(anchor="w")
        self.v["title"].trace_add("write", lambda *a: self._text_changed())
        add("Title", tf, f"eBay allows {MAX_TITLE_LEN} characters after the variables are filled in.", sticky="we")
        self.texts = {}
        for key, label, height, hint in (
                ("description", "Description", 9, "Plain text; blank lines become paragraphs on eBay."),
                ("condition_description", "Condition notes", 3, "eBay's condition description (not shown for New)."),
                ("aspects", "Item specifics", 6, "One per line as 'Name: value'; several values with |. "
                                                 "Lines whose value ends up empty are skipped.")):
            frame, box = make_text(b, height=height)
            box.bind("<FocusIn>", lambda e, w=box: self._focus(w))
            box.bind("<KeyRelease>", lambda e: self._text_changed())
            self.texts[key] = box
            add(label, frame, hint, sticky="we")

        # ---- eBay listing
        section("eBay listing")
        cf = ttk.Frame(b)
        self.v["category_id"] = tk.StringVar()
        self.v["category_name"] = tk.StringVar()
        ttk.Entry(cf, textvariable=self.v["category_id"], width=10).pack(side="left")
        ttk.Entry(cf, textvariable=self.v["category_name"], width=42, state="readonly").pack(side="left", padx=4)
        ttk.Button(cf, text="Suggest…", command=self.choose_category).pack(side="left")
        add("Category", cf, "eBay category ID. Suggest… searches eBay (needs your eBay keys in Settings).")
        self.condition = Choice(b, CONDITIONS, width=30)
        add("Condition", self.condition.cb, "Allowed conditions depend on the category.")
        self.v["default_price"] = tk.StringVar()
        add("Default price", ttk.Entry(b, textvariable=self.v["default_price"], width=12),
            "Pre-filled on the List Item tab (optional).")
        self.v["quantity"] = tk.StringVar()
        add("Quantity", ttk.Spinbox(b, from_=1, to=999, textvariable=self.v["quantity"], width=8))
        self.best_offer = tk.BooleanVar()
        add("Best Offer", ttk.Checkbutton(b, text="Allow buyers to send offers", variable=self.best_offer))

        # ---- package
        section("Package")
        wf = ttk.Frame(b)
        for k, lab in (("weight_lb", "lbs"), ("weight_oz", "oz")):
            self.v[k] = tk.StringVar()
            ttk.Spinbox(wf, from_=0, to=999, textvariable=self.v[k], width=6).pack(side="left")
            ttk.Label(wf, text=lab).pack(side="left", padx=(2, 10))
        add("Weight", wf)
        df = ttk.Frame(b)
        for k in ("length", "width", "height"):
            self.v[k] = tk.StringVar()
            ttk.Label(df, text=k.capitalize()).pack(side="left")
            ttk.Spinbox(df, from_=0, to=999, increment=0.5, textvariable=self.v[k], width=6).pack(side="left",
                                                                                                padx=(2, 10))
        ttk.Label(df, text="inches").pack(side="left")
        add("Dimensions", df)

        # ---- standard photos
        section("Standard photos", "added to every listing from this template")
        self.fixed = []
        for slot in range(FIXED_PHOTO_SLOTS):
            f = ttk.Frame(b)
            path, pos = tk.StringVar(), tk.StringVar()
            thumb = tk.Label(f, bg=P.preview_bg, fg=P.muted, cursor="hand2")
            thumb.pack(side="left")
            thumb.bind("<Button-1>", lambda e, s=slot: self.choose_fixed(s))
            ttk.Entry(f, textvariable=path, width=40, state="readonly").pack(side="left", padx=6)
            ttk.Button(f, text="Choose…", command=lambda s=slot: self.choose_fixed(s)).pack(side="left")
            ttk.Button(f, text="Remove", command=lambda s=slot: self.clear_fixed(s)).pack(side="left", padx=4)
            ttk.Label(f, text="Position").pack(side="left", padx=(12, 2))
            ttk.Spinbox(f, from_=1, to=MAX_PHOTOS, textvariable=pos, width=4).pack(side="left")
            self.fixed.append({"path": path, "pos": pos, "thumb": thumb, "img": None})
            add(f"Photo {slot + 1}", f, f"Shown at this position (1-{MAX_PHOTOS}); at the end if a listing has fewer "
                                        "photos. The file is copied into the app's folder." if slot == 0 else "")

        # ---- policies & location
        section("Business policies & location", "from your eBay account")
        lb = ttk.Frame(b)
        ttk.Button(lb, text="⟳ Load policies & locations from eBay", command=self.load_from_ebay).pack(side="left")
        ttk.Label(lb, text="Loaded once, then available for every template.", foreground=P.muted).pack(side="left",
                                                                                                    padx=10)
        form.full(lb, sticky="w")
        self.policy = {}
        for kind, _, _, label in POLICY_KEYS:
            self.policy[kind] = Choice(b)
            add(label, self.policy[kind].cb)
        zf = ttk.Frame(b)
        self.zip = tk.StringVar()
        ttk.Label(zf, text="ZIP").pack(side="left")
        ttk.Entry(zf, textvariable=self.zip, width=10).pack(side="left", padx=4)
        ttk.Button(zf, text="Create location", command=self.create_location).pack(side="left")
        add("No location yet?", zf, "Creates a ship-from location named 'Ebay Lister' (key 'ebay-lister').")

        self._refresh_picker()
        last = app.settings.get("last_template_id")
        self.load(self.store.get(last) or self.store.first())

    # ---- loading / collecting
    def load(self, template):
        """Show ``template`` in the editor."""
        t = normalize(template)
        self.current = t
        for key in ("title", "category_id", "category_name", "default_price"):
            self.v[key].set(str(t.get(key) or ""))
        for key in NUMERIC:
            self.v[key].set(str(t.get(key)))
        for key, box in self.texts.items():
            text_set(box, t.get(key, ""))
        self.condition.set_value(t["condition"])
        self.best_offer.set(bool(t["best_offer"]))
        fps = list(t["fixed_photos"]) + [{"path": "", "position": ""}] * FIXED_PHOTO_SLOTS
        for slot, f in enumerate(self.fixed):
            f["path"].set(fps[slot].get("path", ""))
            f["pos"].set(str(fps[slot].get("position") or (MAX_PHOTOS - FIXED_PHOTO_SLOTS + 1 + slot)))
            self._fixed_thumb(slot)
        self._apply_policy_options(t)
        self.variables.set(t["variables"])
        self.picker.set_value(t["id"])
        self._text_changed()
        self._set_status("")

    def collect(self):
        """The template as currently shown in the editor (not saved yet)."""
        t = copy.deepcopy(self.current)
        for key in ("title", "category_id", "category_name", "default_price"):
            t[key] = self.v[key].get().strip()
        for key in NUMERIC:
            raw = self.v[key].get().strip()
            try:
                num = float(raw)
                t[key] = int(num) if num.is_integer() else num
            except ValueError:
                t[key] = raw  # validation reports it
        for key, box in self.texts.items():
            t[key] = text_get(box)
        t["condition"] = self.condition.value() or t["condition"]
        t["best_offer"] = self.best_offer.get()
        t["variables"] = copy.deepcopy(self.variables.variables)
        fixed = []
        for slot, f in enumerate(self.fixed):
            if f["path"].get():
                try:
                    pos = min(MAX_PHOTOS, max(1, int(float(f["pos"].get()))))
                except ValueError:
                    pos = MAX_PHOTOS
                fixed.append({"path": f["path"].get(), "position": pos})
        t["fixed_photos"] = fixed
        for kind, id_key, name_key, _ in POLICY_KEYS:
            choice = self.policy[kind]
            value = choice.value()
            if value is not None:
                t[id_key], t[name_key] = value, choice.var.get()
        return t

    def is_dirty(self):
        return self.current is not None and normalize(self.collect()) != normalize(self.current)

    def _set_status(self, text, bad=False):
        self.status.configure(text=text, fg=P.bad if bad else P.muted)

    # ---- text helpers
    def usage(self):
        """{variable name: [fields it's used in]} from what's in the editor right now."""
        out = {}
        texts = {"title": self.v["title"].get(), **{k: text_get(b) for k, b in self.texts.items()}}
        labels = {"title": "title", "description": "description", "condition_description": "condition notes",
                  "aspects": "item specifics"}
        for field, text in texts.items():
            for name in V.placeholders(text):
                out.setdefault(name, []).append(labels[field])
        return out

    def _text_changed(self):
        title = self.v["title"].get()
        names = set(V.variable_names({"variables": self.variables.variables}))
        unknown = [n for n in V.placeholders(title) if n not in names]
        sample = V.render(title, {n: "x" * 6 for n in names})
        msg = f"~{len(sample)}/{MAX_TITLE_LEN} characters with 6-letter values"
        if unknown:
            msg = "⚠ no variable named " + ", ".join(unknown) + " · " + msg
        self.title_hint.configure(text=msg, fg=P.bad if unknown or len(sample) > MAX_TITLE_LEN else P.muted)
        if hasattr(self, "variables") and self.variables.tree.get_children() is not None:
            self.variables.refresh(keep=self.variables._selected())

    def _focus(self, widget):
        self._last_text = widget

    def insert_text(self, text):
        w = self._last_text
        if w is None:
            messagebox.showinfo(APP_NAME, "Click in the title, description, condition notes or item specifics first.")
            return
        w.insert("insert", text)
        w.focus_set()
        self._text_changed()

    def rename_placeholders(self, old, new):
        """A variable was renamed: update {OLD} -> {NEW} everywhere in the text."""
        pattern = re.compile(r"(?<!\{)\{" + re.escape(old) + r"\}(?!\})")
        self.v["title"].set(pattern.sub("{" + new + "}", self.v["title"].get()))
        for box in self.texts.values():
            text_set(box, pattern.sub("{" + new + "}", text_get(box)))
        self.app.toast(f"Renamed {{{old}}} to {{{new}}} in the text.")

    # ---- template management
    def _refresh_picker(self):
        self.picker.set_options([(t["name"], t["id"]) for t in self.store.all()])
        if self.current:
            self.picker.set_value(self.current["id"])

    def _confirm_leave(self):
        """Unsaved edits? Ask to save. Returns False if the user cancelled."""
        if not self.is_dirty():
            return True
        answer = messagebox.askyesnocancel(APP_NAME, f"Save your changes to '{self.current['name']}' first?")
        if answer is None:
            return False
        return self.save(quiet=True) if answer else True

    def select(self, template_id):
        """Show another template (asks about unsaved changes)."""
        if self.current and template_id == self.current["id"]:
            return
        if not self._confirm_leave():
            self.picker.set_value(self.current["id"])
            return
        t = self.store.get(template_id)
        if t:
            self.load(t)

    def _picked(self):
        self.select(self.picker.value())

    def _changed_templates(self, select_id=None):
        self._refresh_picker()
        self.app.list_tab.templates_changed(select_id=select_id)

    def new(self):
        if not self._confirm_leave():
            return
        name = simpledialog.askstring(APP_NAME, "Name for the new template:", initialvalue=self.store.unique_name(
            "New template"), parent=self)
        if not name:
            return
        try:
            t = self.store.create(name)
        except TemplateError as e:
            messagebox.showwarning(APP_NAME, str(e))
            return
        self.load(t)
        self._changed_templates()
        self.app.toast(f"Created template '{t['name']}'.")

    def duplicate(self):
        if not self._confirm_leave():
            return
        name = simpledialog.askstring(APP_NAME, f"Name for the copy of '{self.current['name']}':",
                                      initialvalue=self.store.unique_name(self.current["name"]), parent=self)
        if not name:
            return
        try:
            t = self.store.create(name, base_id=self.current["id"])
        except TemplateError as e:
            messagebox.showwarning(APP_NAME, str(e))
            return
        self.load(t)
        self._changed_templates()
        self.app.toast(f"Created '{t['name']}' from '{self.store.get(self.current['id'])['name']}'.")

    def rename(self):
        name = simpledialog.askstring(APP_NAME, "New name:", initialvalue=self.current["name"], parent=self)
        if not name or name.strip() == self.current["name"]:
            return
        try:
            saved = self.store.rename(self.current["id"], name)
        except TemplateError as e:
            messagebox.showwarning(APP_NAME, str(e))
            return
        self.current["name"] = saved["name"]
        self._changed_templates()
        self.app.toast(f"Renamed to '{saved['name']}'.")

    def delete(self):
        if not messagebox.askyesno(APP_NAME, f"Delete the template '{self.current['name']}'?\n\nItems already listed "
                                             "or queued with it are not affected."):
            return
        try:
            self.store.delete(self.current["id"])
        except TemplateError as e:
            messagebox.showwarning(APP_NAME, str(e))
            return
        self.current = None
        self.load(self.store.first())
        self._changed_templates()

    def save(self, quiet=False):
        """Save the editor's template. Returns True on success."""
        t = self.collect()
        problems = validate_template_content(t)
        try:
            saved = self.store.save(t)
        except TemplateError as e:
            messagebox.showwarning(APP_NAME, str(e))
            return False
        self.current = saved
        self._changed_templates(select_id=None)
        n = len(problems) + len(validate_template_account(saved))
        self._set_status(f"Saved. {n} thing(s) to fix - click Validate." if n else "Saved ✔", bad=bool(n))
        if not quiet:
            self.app.toast(f"Template '{saved['name']}' saved.")
        return True

    def revert(self):
        stored = self.store.get(self.current["id"])
        if stored:
            self.load(stored)
            self._set_status("Reverted to the saved version.")

    def validate(self):
        errs = validate_template(self.collect())
        if errs:
            messagebox.showwarning(APP_NAME, "Template issues:\n\n• " + "\n• ".join(errs) +
                                   "\n\n(Policies and location aren't needed to add items to the queue.)")
        else:
            messagebox.showinfo(APP_NAME, "Template looks good ✔")

    def on_shown(self):
        self._refresh_picker()

    # ---- standard photos
    def _fixed_thumb(self, slot):
        f = self.fixed[slot]
        p = f["path"].get()
        img = load_image(p, 64, 64)[0] if p and os.path.isfile(p) else None
        f["img"] = img
        if img:
            f["thumb"].configure(image=img, text="", width=64, height=64)
        else:
            f["thumb"].configure(image="", text="missing" if p else "none", width=8, height=4,
                                 fg=P.bad if p else P.muted)

    def choose_fixed(self, slot):
        src = filedialog.askopenfilename(title=f"Standard photo {slot + 1}",
                                         filetypes=[("Images", "*.jpg *.jpeg *.png *.gif *.JPG *.JPEG *.PNG"),
                                                    ("All", "*.*")])
        if not src:
            return
        if not src.lower().endswith(PHOTO_EXTS):
            messagebox.showwarning(APP_NAME, "Use a JPG, PNG or GIF photo.")
            return
        try:
            self.fixed[slot]["path"].set(self.store.copy_photo_in(src, self.current["id"]))
        except OSError as e:
            messagebox.showerror(APP_NAME, f"Couldn't copy the photo: {e}")
            return
        self._fixed_thumb(slot)
        self._set_status("Photo added - Save template to keep it.")

    def clear_fixed(self, slot):
        self.fixed[slot]["path"].set("")
        self._fixed_thumb(slot)
        self._set_status("Photo removed - Save template to keep the change.")

    # ---- eBay account data
    def _apply_policy_options(self, t):
        """Fill the policy/location drop-downs from the loaded eBay options (or show the saved choice)."""
        options = getattr(self.app, "ebay_options", None)
        for kind, id_key, name_key, _ in POLICY_KEYS:
            choice = self.policy[kind]
            if options and options.get(kind) is not None:
                opts = options[kind]
                choice.set_options(opts)
                if t.get(id_key) and choice.set_value(t[id_key]):
                    continue
                labels = [label for label, _ in opts]
                match = best_match(t.get(name_key) or "", labels) or (labels[0] if labels else None)
                choice.var.set(match or "")
            elif t.get(id_key):
                choice.set_options([(t.get(name_key) or str(t[id_key]), t[id_key])])
                choice.set_value(t[id_key])
            else:
                choice.set_options([])
                choice.var.set(f"{t.get(name_key) or '—'}  (load from eBay)")

    def load_from_ebay(self):
        c = self.app.ebay

        def work():
            return {"fulfillment": c.policies("fulfillment"), "payment": c.policies("payment"),
                    "return": c.policies("return"), "locations": c.locations()}

        self.app.log("Loading business policies and locations from eBay…")
        self.app.run_bg(work, on_ok=self._loaded, on_err=lambda e: messagebox.showerror(APP_NAME, str(e)))

    def _loaded(self, d):
        locations = []
        for loc in d["locations"]:
            addr = (loc.get("location") or {}).get("address") or {}
            label = f"{loc.get('name') or loc['merchantLocationKey']} - {addr.get('city', '')} {addr.get('postalCode', '')}"
            locations.append((label.strip(), loc["merchantLocationKey"]))
        self.app.ebay_options = {
            "fulfillment": [(p["name"], p["fulfillmentPolicyId"]) for p in d["fulfillment"]],
            "payment": [(p["name"], p["paymentPolicyId"]) for p in d["payment"]],
            "return": [(p["name"], p["returnPolicyId"]) for p in d["return"]],
            "location": locations,
        }
        self._apply_policy_options(self.collect())
        missing = [label for kind, _, _, label in POLICY_KEYS if not self.app.ebay_options[kind]]
        if missing:
            messagebox.showwarning(APP_NAME, "Nothing found for: " + ", ".join(missing) + ".\n\nCreate business "
                                   "policies in eBay Seller Hub › Account › Business policies, and a location below.")
        self._set_status("Loaded from eBay - review the choices and Save template.")

    def create_location(self):
        z = self.zip.get().strip()
        if not re.match(r"^\d{5}(-\d{4})?$", z):
            messagebox.showwarning(APP_NAME, "Enter a US ZIP code first.")
            return
        self.app.run_bg(lambda: self.app.ebay.create_location("ebay-lister", z, APP_NAME),
                        on_ok=lambda _: (self.app.toast("eBay location created."), self.load_from_ebay()),
                        on_err=lambda e: messagebox.showerror(APP_NAME, str(e)))

    def _set_category(self, node):
        self.v["category_id"].set(str(node["id"]))
        self.v["category_name"].set(node["path"])

    def choose_category(self):
        query = V.render(self.v["title"].get(), {})
        query = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", " ", query).strip()[:60] or self.current["name"]

        def search(q, fill):
            self.app.run_bg(lambda: self.app.ebay.suggest_categories(q), on_ok=fill,
                            on_err=lambda e: messagebox.showerror(APP_NAME, str(e)))

        self.app.run_bg(lambda: self.app.ebay.suggest_categories(query),
                        on_ok=lambda nodes: category_dialog(self, "Choose eBay category", nodes, query,
                                                            self._set_category, local_filter=False, search_fn=search),
                        on_err=lambda e: messagebox.showerror(APP_NAME, str(e)))
