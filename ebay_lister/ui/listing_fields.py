"""The template-controlled part of the List Item form: title, description, item specifics, package...

Each template says, per field (``template["list_fields"]``, see ``config.LIST_FIELDS``), whether
the List Item tab hides it, shows it read-only, or lets you edit it for the one item:

* **Text fields** (title, description, condition notes, item specifics) start as the template's text
  with the variables filled in, and keep following the variables as you type them - until you change
  the text yourself. From then on your version is kept; *Reset* goes back to the template's.
* **Settings** (condition, card condition, package, quantity, Best Offer) start with the template's
  values. Changed values become the item's ``overrides`` (see :class:`~ebay_lister.services.listing.ListingJob`),
  which are applied on top of the template when it's listed, also from the queue.
"""

import tkinter as tk
from tkinter import ttk

from ebay_lister.config import CARD_CONDITIONS, CONDITIONS, LIST_FIELDS, MAX_TITLE_LEN, PACKAGE_KEYS
from ebay_lister.services.templates import normalize
from ebay_lister.ui.aspects_dialog import suggest_aspects
from ebay_lister.ui.theme import P
from ebay_lister.ui.widgets import Choice, TextLabel, make_text, text_get, text_set

TEXT_FIELDS = {"title": 0, "description": 8, "condition_description": 3, "aspects": 6}  # key -> box height
LABELS = dict(LIST_FIELDS)


def _label(options, value):
    return next((lab for lab, v in options if v == value), value or "—")


def _number(raw):
    """'3' -> 3, '2.5' -> 2.5; anything else is returned as typed so validation can report it."""
    try:
        num = float(str(raw).strip())
        return int(num) if num.is_integer() else num
    except ValueError:
        return str(raw).strip()


def package_text(t):
    return (f"{t.get('weight_lb') or 0} lb {t.get('weight_oz') or 0} oz  ·  "
            f"{t.get('length') or 0} × {t.get('width') or 0} × {t.get('height') or 0} in")


class ListingFields(ttk.Frame):
    """Builds itself from a template's ``list_fields``; see the module docstring."""

    def __init__(self, master, app, on_change):
        super().__init__(master)
        self.app = app
        self.on_change = on_change
        self.columnconfigure(1, weight=1)
        self.template = None
        self.modes = {}
        self.text = {}          # key -> StringVar (title) | Text widget (edit) | read-only Text/label (show)
        self._auto = {}         # key -> the template text last put in an editable box
        self.settings = {}      # key -> widget state for condition / card_condition / package / quantity / best_offer
        self.title_status = None

    # ---- building
    def build(self, template):
        self.template = normalize(template)
        self.modes = dict(self.template["list_fields"])
        for w in self.winfo_children():
            w.destroy()
        self.text, self._auto, self.settings, self.title_status = {}, {}, {}, None
        r = 0
        for key, label in LIST_FIELDS:
            mode = self.modes.get(key, "hidden")
            if mode == "hidden":
                continue
            lab = ttk.Label(self, text=label)
            lab.grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=4)
            if key in TEXT_FIELDS:
                widget = self._text_field(key, mode)
            else:
                widget = self._setting_field(key, mode)
            widget.grid(row=r, column=1, sticky="we" if key in TEXT_FIELDS else "w", pady=4)
            r += 1
            if key == "title":
                self.title_status = TextLabel(self, text="")
                self.title_status.grid(row=r, column=1, sticky="w")
                r += 1
        if r == 0:
            ttk.Label(self, text="This template doesn't show any listing fields here (Templates tab › List Item form).",
                      foreground=P.muted).grid(row=0, column=0, columnspan=2, sticky="w")

    def _text_field(self, key, mode):
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        if key == "title":
            if mode == "edit":
                var = tk.StringVar()
                var.trace_add("write", lambda *a: self.on_change())
                ttk.Entry(frame, textvariable=var, font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, sticky="we")
                self.text[key] = var
            else:
                lbl = tk.Label(frame, text="", anchor="w", justify="left", bg=P.readonly_bg, fg=P.fg, relief="flat",
                               bd=0, highlightthickness=1, highlightbackground=P.border, padx=8, pady=4,
                               wraplength=900, font=("TkDefaultFont", 11, "bold"))
                lbl.grid(row=0, column=0, sticky="we")
                self.text[key] = lbl
        else:
            box_frame, box = make_text(frame, height=TEXT_FIELDS[key], readonly=(mode == "show"))
            box_frame.grid(row=0, column=0, sticky="we")
            if mode == "edit":
                box.bind("<KeyRelease>", lambda e: self.on_change())
            self.text[key] = box
        if mode == "edit":
            bf = ttk.Frame(frame)
            bf.grid(row=1, column=0, sticky="w", pady=(2, 0))
            ttk.Button(bf, text="Reset", command=lambda k=key: self.reset_text(k)).pack(side="left")
            if key == "aspects":
                ttk.Button(bf, text="Suggest from eBay…", command=self.suggest_aspects).pack(side="left", padx=6)
            ttk.Label(bf, text="Reset goes back to the template's text with your variables filled in.",
                      foreground=P.muted).pack(side="left", padx=6)
        return frame

    def _setting_field(self, key, mode):
        t = self.template
        frame = ttk.Frame(self)
        if mode == "show":
            if key == "condition":
                text = _label(CONDITIONS, t["condition"])
            elif key == "card_condition":
                text = _label(CARD_CONDITIONS, t.get("card_condition") or "")
            elif key == "package":
                text = package_text(t)
            elif key == "quantity":
                text = str(t["quantity"])
            else:
                text = "Allowed" if t["best_offer"] else "Off"
            TextLabel(frame, text=text).pack(side="left")
            return frame
        if key in ("condition", "card_condition"):
            choice = Choice(frame, CONDITIONS if key == "condition" else CARD_CONDITIONS, width=34)
            choice.set_value(t.get(key) or "")
            choice.cb.pack(side="left")
            self.settings[key] = choice
        elif key == "package":
            vars_ = {}
            for k, lab, step in (("weight_lb", "lb", 1), ("weight_oz", "oz", 1), ("length", "L", 0.5),
                                 ("width", "W", 0.5), ("height", "H", 0.5)):
                vars_[k] = tk.StringVar(value=str(t.get(k) or 0))
                if k == "length":
                    ttk.Label(frame, text="  Box").pack(side="left", padx=(6, 4))
                if k.startswith("weight"):
                    ttk.Spinbox(frame, from_=0, to=999, increment=step, textvariable=vars_[k], width=5).pack(side="left")
                    ttk.Label(frame, text=lab).pack(side="left", padx=(2, 8))
                else:
                    ttk.Label(frame, text=lab).pack(side="left", padx=(0, 2))
                    ttk.Spinbox(frame, from_=0, to=999, increment=step, textvariable=vars_[k], width=5).pack(
                        side="left", padx=(0, 6))
            ttk.Label(frame, text="inches", foreground=P.muted).pack(side="left")
            self.settings[key] = vars_
        elif key == "quantity":
            var = tk.StringVar(value=str(t["quantity"]))
            ttk.Spinbox(frame, from_=1, to=999, textvariable=var, width=6).pack(side="left")
            self.settings[key] = var
        else:
            var = tk.BooleanVar(value=bool(t["best_offer"]))
            ttk.Checkbutton(frame, text="Allow buyers to send offers", variable=var).pack(side="left")
            self.settings[key] = var
        return frame

    # ---- text
    def _get(self, key):
        w = self.text[key]
        if isinstance(w, tk.StringVar):
            return w.get()
        if isinstance(w, tk.Text):
            return text_get(w)
        return w.cget("text")

    def _set(self, key, value):
        w = self.text[key]
        if isinstance(w, tk.StringVar):
            w.set(value)
        elif isinstance(w, tk.Text):
            text_set(w, value)
        else:
            w.configure(text=value or " ")

    def refresh(self, rendered):
        """New template text (variables changed): update shown fields, and editable ones not changed by hand."""
        for key, w in self.text.items():
            new = rendered.get(key, "")
            if self.modes[key] == "show":
                self._set(key, new)
                continue
            current = self._get(key)
            if key not in self._auto or current == self._auto[key]:  # still the template's text
                self._auto[key] = new
                if current != new:
                    self._set(key, new)

    def reset_text(self, key):
        self._auto.pop(key, None)
        self.on_change()  # -> refresh() puts the template's text back

    def edited(self, key):
        """True if the user changed this text field by hand."""
        return self.modes.get(key) == "edit" and key in self._auto and self._get(key) != self._auto[key]

    def final(self, rendered):
        """``rendered`` with this item's hand edits applied."""
        out = dict(rendered)
        for key in self.text:
            if self.modes[key] == "edit":
                out[key] = self._get(key).strip() if key == "title" else self._get(key)
        return out

    def set_title_status(self, text, ok):
        if self.title_status is not None:
            self.title_status.configure(text=text, fg=P.ok if ok else P.bad)

    def suggest_aspects(self):
        def applied(text):
            self._set("aspects", text)
            self.on_change()

        suggest_aspects(self, self.app, self.template.get("category_id"), self._get("aspects"), applied)

    # ---- settings
    def overrides(self):
        """Settings changed from the template's, as {template key: value}."""
        t, out = self.template, {}
        for key, w in self.settings.items():
            if key in ("condition", "card_condition"):
                value = w.value()
                if value is not None and value != (t.get(key) or ""):
                    out[key] = value
            elif key == "package":
                for k in PACKAGE_KEYS:
                    value = _number(w[k].get())
                    if value != _number(t.get(k) or 0):
                        out[k] = value
            elif key == "quantity":
                value = _number(w.get())
                if value != _number(t["quantity"]):
                    out[key] = value
            else:
                if bool(w.get()) != bool(t["best_offer"]):
                    out[key] = bool(w.get())
        return out

    def title_limit_text(self, title, errs):
        return f"{len(title)}/{MAX_TITLE_LEN} characters" + (f"   ⚠ {errs[0]}" if errs else "   ✔")
