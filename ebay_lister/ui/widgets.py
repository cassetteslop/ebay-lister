"""Reusable Tk widgets and helpers used by every tab.
"""

import tkinter as tk
from tkinter import ttk

from ebay_lister.ui.compat import HAS_PIL, Image, ImageOps, ImageTk
from ebay_lister.ui.theme import P, style_window


class ScrollFrame(ttk.Frame):
    """Scrollable page; the mouse wheel / trackpad scrolls it anywhere over its contents."""
    _instances = []
    _bound = False
    STEP = 20  # pixels per scroll unit

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=P.pane, yscrollincrement=self.STEP)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, padding=12)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self._acc = 0.0
        ScrollFrame._instances.append(self)
        if not ScrollFrame._bound:
            ScrollFrame._bound = True
            for seq, kind in (("<MouseWheel>", "wheel"), ("<Button-4>", "up"), ("<Button-5>", "down"),
                              ("<TouchpadScroll>", "touchpad")):
                try:
                    self.bind_all(seq, lambda e, k=kind: ScrollFrame._dispatch(e, k), add="+")
                except tk.TclError:
                    pass  # <TouchpadScroll> only exists on Tk 8.7+/9

    @staticmethod
    def _dispatch(e, kind):
        w = e.widget
        if not isinstance(w, tk.Misc):
            return
        # let text boxes / lists / tables scroll themselves when they actually have more content
        if isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview)):
            try:
                if tuple(round(x, 3) for x in w.yview()) != (0.0, 1.0):
                    return
            except tk.TclError:
                return
        name = str(w)
        for sf in ScrollFrame._instances:
            if sf.winfo_ismapped() and (name == str(sf) or name.startswith(str(sf) + ".")):
                sf._scroll(e, kind)
                return

    def _scroll(self, e, kind):
        if self.canvas.yview() == (0.0, 1.0):
            return
        if kind == "up":
            self.canvas.yview_scroll(-3, "units")
            return
        if kind == "down":
            self.canvas.yview_scroll(3, "units")
            return
        if kind == "touchpad":
            low = e.delta & 0xFFFF
            dy = low if low < 0x8000 else low - 0x10000
            self._acc -= dy
        else:
            d = e.delta
            if abs(d) >= 120:            # Windows / Tk 9 wheel: multiples of 120
                self._acc -= d / 120 * 3 * self.STEP
            else:                        # macOS Tk 8.6: small deltas
                self._acc -= d * self.STEP
        n = int(self._acc / self.STEP)
        if n:
            self.canvas.yview_scroll(n, "units")
            self._acc -= n * self.STEP


class TextLabel(ttk.Label):
    """Native (ttk) label that also accepts classic Tk's ``fg=`` / ``bg=`` options.

    ``fg`` becomes ``foreground``; ``bg`` is ignored because native labels take their container's
    background - which keeps them seamless inside macOS tabs and group boxes in dark mode.
    """

    @staticmethod
    def _native(kw):
        if "fg" in kw:
            kw["foreground"] = kw.pop("fg")
        kw.pop("bg", None)
        return kw

    def __init__(self, master=None, **kw):
        super().__init__(master, **self._native(kw))

    def configure(self, cnf=None, **kw):
        return super().configure(cnf, **self._native(kw))

    config = configure


class Choice:
    """Readonly combobox over (label, value) pairs."""

    def __init__(self, parent, options=(), width=48):
        self.var = tk.StringVar()
        self.cb = ttk.Combobox(parent, textvariable=self.var, width=width, state="readonly")
        self.options = []
        self.set_options(options)

    def set_options(self, opts):
        self.options = list(opts)
        self.cb["values"] = [l for l, _ in self.options]

    def value(self):
        for l, v in self.options:
            if l == self.var.get():
                return v
        return None

    def set_value(self, v):
        for l, vv in self.options:
            if vv == v:
                self.var.set(l)
                return True
        return False


def make_text(parent, height=6, width=70, readonly=False, **kw):
    """Text box with a scrollbar and the app's colours. Returns ``(frame, text_widget)``.
    ``readonly=True`` makes it a grey, non-editable preview."""
    frm = ttk.Frame(parent)
    opts = dict(height=height, width=width, wrap="word", undo=True, font=("TkDefaultFont", 11),
                fg=P.fg, bg=P.readonly_bg if readonly else P.field_bg, insertbackground=P.fg, insertwidth=2,
                selectbackground=P.select_bg, selectforeground=P.select_fg, relief="flat", bd=0,
                highlightthickness=1, highlightcolor=P.accent, highlightbackground=P.border,  # macOS-style focus ring
                padx=8, pady=6)
    opts.update(kw)
    t = tk.Text(frm, **opts)
    if readonly:
        t.configure(state="disabled", cursor="arrow")
    sb = ttk.Scrollbar(frm, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frm, t


def text_get(t):
    """Contents of a Text widget without the trailing newline Tk adds."""
    return t.get("1.0", "end-1c")


def text_set(t, s):
    """Replace a Text widget's contents (works on read-only ones too)."""
    st = t.cget("state")
    t.configure(state="normal")
    t.delete("1.0", "end")
    t.insert("1.0", s)
    t.configure(state=st)


def load_image(path, max_w, max_h):
    """PhotoImage scaled to fit (max_w, max_h); None if unsupported."""
    try:
        if HAS_PIL:
            im = Image.open(path)
            im = ImageOps.exif_transpose(im)
            im.thumbnail((max_w, max_h))
            return ImageTk.PhotoImage(im), im.size
        if path.lower().endswith((".png", ".gif")):
            im = tk.PhotoImage(file=path)
            f = max(1, -(-max(im.width() / max_w, im.height() / max_h) // 1))
            im = im.subsample(int(f), int(f))
            return im, (im.width(), im.height())
    except Exception:
        pass
    return None, None


def category_dialog(parent, title, nodes, query, on_pick, local_filter=True, search_fn=None):
    """Searchable category picker. nodes: [{'id','name','path'}]."""
    win = tk.Toplevel(parent)
    style_window(win)
    win.title(title)
    win.geometry("760x500")
    win.transient(parent.winfo_toplevel())
    q = tk.StringVar(value=query)
    top = ttk.Frame(win)
    top.pack(fill="x", padx=10, pady=8)
    e = ttk.Entry(top, textvariable=q, width=60)
    e.pack(side="left", fill="x", expand=True)
    lb = tk.Listbox(win, activestyle="dotbox", fg=P.fg, bg=P.field_bg, selectbackground=P.select_bg,
                    selectforeground=P.fg, font=("TkDefaultFont", 11))
    lb.pack(fill="both", expand=True, padx=10)
    shown = []

    def fill(items):
        shown[:] = items
        lb.delete(0, "end")
        for n in items:
            lb.insert("end", f"{n['path']}   (#{n['id']})")
        if items:
            lb.selection_set(0)

    def filt(*_):
        terms = q.get().lower().replace("&", " ").split()
        fill([n for n in nodes if all(tm in n["path"].lower() for tm in terms)])

    def pick(*_):
        sel = lb.curselection()
        if sel:
            on_pick(shown[sel[0]])
            win.destroy()

    if local_filter:
        q.trace_add("write", filt)
        filt()
        if not shown:
            q.set("audio")
    else:
        ttk.Button(top, text="Search", command=lambda: search_fn(q.get(), fill)).pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: search_fn(q.get(), fill))
        fill(nodes)
    lb.bind("<Double-Button-1>", pick)
    ttk.Button(win, text="Use selected category", command=pick).pack(pady=8)
    e.focus_set()
    e.icursor("end")


class FormGrid:
    """Builds the 3-column form layout used by every tab: ``label | widget | hint``.

    It keeps the current grid row, so tabs just call :meth:`row` / :meth:`section` in order.
    Rows can be tagged with a *group* (e.g. ``"advanced"``) and later shown or hidden together
    with :meth:`show_groups`.

    Example::

        form = FormGrid(body)
        form.section("Package")
        form.row("Weight", weight_frame, "Pounds and ounces.")
        form.group = "ebay"          # following rows belong to the eBay group
        form.row("Condition", condition_combo)
        form.group = None
    """

    def __init__(self, parent, start_row=0, hint_wrap=320):
        self.parent = parent
        self.r = start_row          # next free grid row
        self.hint_wrap = hint_wrap
        self.group = None           # current group name, or None
        self.groups = {}            # group name -> [widgets]

    def _track(self, *widgets):
        if self.group:
            self.groups.setdefault(self.group, []).extend(w for w in widgets if w is not None)

    def section(self, title, note="", pady=(14, 4)):
        """Bold section heading (with optional muted note) spanning all columns."""
        frame = ttk.Frame(self.parent)
        frame.grid(row=self.r, column=0, columnspan=3, sticky="w", pady=pady)
        ttk.Label(frame, text=title, style="Section.TLabel").pack(side="left")
        if note:
            ttk.Label(frame, text="   " + note, foreground=P.muted).pack(side="left")
        self._track(frame)
        self.r += 1
        return frame

    def row(self, label, widget, hint="", sticky="w"):
        """``label | widget | hint`` on one row. Returns the hint label (or None) so it can be updated."""
        lab = ttk.Label(self.parent, text=label)
        lab.grid(row=self.r, column=0, sticky="nw", padx=(0, 10), pady=4)
        widget.grid(row=self.r, column=1, sticky=sticky, pady=4)
        hint_label = None
        if hint:
            hint_label = ttk.Label(self.parent, text=hint, foreground=P.muted, wraplength=self.hint_wrap,
                                   justify="left")
            hint_label.grid(row=self.r, column=2, sticky="nw", padx=10, pady=4)
        self._track(lab, widget, hint_label)
        self.r += 1
        return hint_label

    def full(self, widget, column=0, columnspan=3, sticky="we", **grid):
        """Place ``widget`` across the columns on its own row."""
        widget.grid(row=self.r, column=column, columnspan=columnspan, sticky=sticky, **grid)
        self._track(widget)
        self.r += 1
        return widget

    def show_groups(self, visible):
        """``visible``: {group name: bool}. Hidden widgets keep their grid settings for re-showing."""
        for name, widgets in self.groups.items():
            for w in widgets:
                if visible.get(name, True):
                    w.grid()
                else:
                    w.grid_remove()
