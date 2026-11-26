"""A permissive *fake* tkinter, used only by tests/test_ui_smoke.py.

Real Tk windows can't be opened in CI or by coding agents, so this stand-in accepts any widget call,
remembers options (``widget._opts``), stores text in Text/StringVar, and records Treeview rows.
It lets the smoke test build the whole app and click through the main flows to catch
AttributeErrors, wrong arguments and broken wiring. It does NOT check how anything looks - always
try UI changes in the real app too. Extend it when a new Tk method is used (add it to ``Misc``).
"""
import itertools
_ids = itertools.count()
class TclError(Exception): pass
class EventType: pass

class Misc:
    _root_ref = None
    def __init__(self, master=None, *a, **kw):
        self.master = master
        self.children_list = []
        self._name = f"w{next(_ids)}"
        self._opts = dict(kw)
        if master is not None and hasattr(master, "children_list"):
            master.children_list.append(self)
        self._grid = False
    def __str__(self):
        return (str(self.master) if self.master is not None else "") + "." + self._name
    # geometry
    def grid(self, *a, **k): self._grid = True
    def grid_remove(self): self._grid = False
    def pack(self, *a, **k): pass
    def pack_forget(self): pass
    def place(self, *a, **k): pass
    def pack_propagate(self, *a): pass
    def columnconfigure(self, *a, **k): pass
    def rowconfigure(self, *a, **k): pass
    # config
    def configure(self, *a, **k): self._opts.update(k)
    config = configure
    def cget(self, k): return self._opts.get(k, "normal" if k == "state" else "")
    def __setitem__(self, k, v): self._opts[k] = v
    def __getitem__(self, k): return self._opts.get(k)
    # events
    def bind(self, *a, **k): pass
    def bind_all(self, *a, **k): pass
    def unbind_all(self, *a, **k): pass
    def after(self, ms, fn=None, *a): return "after#1"
    def after_idle(self, fn, *a): fn(*a)
    def winfo_children(self): return list(self.children_list)
    def winfo_containing(self, x, y): return None
    def winfo_ismapped(self): return True
    def winfo_screenwidth(self): return 1600
    def winfo_screenheight(self): return 1000
    def winfo_toplevel(self): return self
    def winfo_exists(self): return True
    def destroy(self):
        if self.master is not None and self in getattr(self.master, "children_list", []):
            self.master.children_list.remove(self)
    def focus_set(self): pass
    def clipboard_clear(self): pass
    def clipboard_append(self, s): pass
    def option_add(self, *a): pass
    def title(self, *a): pass
    def geometry(self, *a): pass
    def mainloop(self): pass
    def transient(self, *a): pass
    def update_idletasks(self): pass
    def nametowidget(self, name): return _registry.get(name)
    def tk_splitlist(self, s): return s.split()
    def drop_target_register(self, *a): pass
    def dnd_bind(self, *a): pass

_registry = {}
class Tk(Misc):
    def __init__(self, *a, **k):
        super().__init__(None)
        self._name = ""
    def splitlist(self, s): return s.split()
    def __str__(self): return "."
class Toplevel(Misc): pass
class Frame(Misc): pass
class Label(Misc): pass
class Button(Misc): pass
class Radiobutton(Misc): pass
class Canvas(Misc):
    def create_window(self, *a, **k): return 1
    def itemconfigure(self, *a, **k): pass
    def bbox(self, *a): return (0, 0, 10, 10)
    def yview(self, *a): return (0.0, 1.0)
    def yview_scroll(self, *a): pass
class Text(Misc):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._text = ""
    def get(self, a, b=None): return self._text
    def insert(self, idx, s): self._text += s
    def delete(self, a, b=None): self._text = ""
    def see(self, *a): pass
    def yview(self, *a): return (0.0, 1.0)
class Listbox(Text):
    def curselection(self): return (0,)
    def selection_set(self, *a): pass
class PhotoImage:
    def __init__(self, *a, **k): pass
    def width(self): return 10
    def height(self): return 10
    def subsample(self, *a): return self

class Variable:
    def __init__(self, master=None, value=None, name=None):
        self._v = value if value is not None else self._default
        self._traces = []
    def get(self): return self._v
    def set(self, v):
        self._v = v
        for cb in self._traces: cb("", "", "write")
    def trace_add(self, mode, cb): self._traces.append(cb)
class StringVar(Variable):
    _default = ""
    def get(self): return str(self._v)
class BooleanVar(Variable):
    _default = False
    def get(self): return bool(self._v)
class IntVar(Variable): _default = 0

# ---- additions for theme/menu tests
import os as _os
_MAC = _os.environ.get("FAKE_AQUA") == "1"
_CALLS = []
class _TkInterp:
    def call(self, *args):
        _CALLS.append(args)
        if args[:2] == ("tk", "windowingsystem"):
            return "aqua" if _MAC else "x11"
        if args and args[0] == "::tk::unsupported::MacWindowStyle":
            if not _MAC:
                raise TclError("invalid command name")
            return "1" if args[1] == "isdark" else ""
        return ""
    def splitlist(self, s): return s.split()
_interp = _TkInterp()
Misc.tk = property(lambda self: _interp)
def _winfo_rgb(self, color):
    if color.startswith("system") and not _MAC:
        raise TclError(f'unknown color name "{color}"')
    if color == "systemSelectedTextColor":
        raise TclError("pretend this Tk lacks it")
    return (0, 0, 0)
Misc.winfo_rgb = _winfo_rgb
Misc.createcommand = lambda self, name, fn: _CALLS.append(("createcommand", name))
Misc.focus_get = lambda self: None
Misc.event_generate = lambda self, *a, **k: None
Misc.minsize = lambda self, *a: None
class Menu(Misc):
    def __init__(self, master=None, name=None, **kw):
        super().__init__(master, **kw); self.items = []; self.menu_name = name
    def add_command(self, **kw): self.items.append(("command", kw.get("label"), kw.get("accelerator")))
    def add_cascade(self, **kw): self.items.append(("cascade", kw.get("label") or getattr(kw.get("menu"), "menu_name", None), kw.get("menu")))
    def add_separator(self): self.items.append(("sep", None, None))
Misc.protocol = lambda self, *a: None
Misc.withdraw = lambda self: None
