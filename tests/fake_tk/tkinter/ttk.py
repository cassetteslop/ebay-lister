from tkinter import Misc, Text
class Frame(Misc): pass
class Label(Misc): pass
class LabelFrame(Misc): pass
class Button(Misc):
    def invoke(self):
        c = self._opts.get("command"); return c() if c else None
class Checkbutton(Button): pass
class Radiobutton(Button): pass
class Entry(Misc):
    def icursor(self, *a): pass
class Spinbox(Entry): pass
class Combobox(Entry): pass
class Scrollbar(Misc):
    def set(self, *a): pass
class Separator(Misc): pass
class PanedWindow(Misc):
    def add(self, *a, **k): pass
class Notebook(Misc):
    def add(self, w, **k):
        from tkinter import _registry
        _registry[str(w)] = w
        self._tabs = getattr(self, "_tabs", []) + [w]
    def select(self, w=None):
        if w is not None: self._sel = w; return None
        return str(getattr(self, "_sel", self._tabs[0]))
class Treeview(Misc):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._rows = {}; self._sel = ()
    def heading(self, *a, **k): pass
    def column(self, *a, **k): pass
    def tag_configure(self, *a, **k): pass
    def insert(self, parent, idx, iid=None, values=(), tags=()):
        self._rows[iid] = (values, tags); return iid
    def delete(self, *iids):
        for i in iids: self._rows.pop(i, None)
    def get_children(self, *a): return tuple(self._rows)
    def selection(self): return self._sel
    def selection_set(self, iid): self._sel = (iid,)
    def selection_remove(self, *a): self._sel = ()
    def exists(self, iid): return iid in self._rows
    def see(self, *a): pass
    def identify_row(self, y): return ""
    def identify_column(self, x): return "#1"
    def yview(self, *a): return (0.0, 1.0)
class Style:
    def __init__(self, *a): pass
    def theme_names(self): return ("clam",)
    def theme_use(self, *a): pass
    def configure(self, *a, **k): pass
    def map(self, *a, **k): pass
class Label(Misc):
    def __init__(self, master=None, **kw):
        bad = {"fg", "bg"} & set(kw)
        assert not bad, f"ttk.Label got classic options {bad}"
        super().__init__(master, **kw)
    def configure(self, cnf=None, **kw):
        bad = {"fg", "bg"} & set(kw)
        assert not bad, f"ttk.Label.configure got classic options {bad}"
        self._opts.update(kw)
    config = configure
class Style:
    used = None
    def __init__(self, *a): pass
    def theme_names(self): return ("clam", "aqua")
    def theme_use(self, name=None): Style.used = name
    def configure(self, *a, **k): pass
    def map(self, *a, **k): pass
