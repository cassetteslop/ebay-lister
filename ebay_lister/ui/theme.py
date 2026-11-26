"""Appearance: native macOS styling with a dark (or light) palette, and a matching custom theme elsewhere.

How it works
------------
* **macOS** - uses Tk's native ``aqua`` theme, so buttons, checkboxes, pop-up menus, tabs, scroll
  bars and tables are real macOS controls. The window is switched to *Dark Aqua* (or Light, or
  "match macOS"), and classic Tk widgets (text boxes, previews, labels) use macOS **semantic
  colours** such as ``systemTextColor`` / ``systemWindowBackgroundColor``, so they match the
  native controls exactly and follow the accent colour you chose in System Settings.
* **Windows / Linux** - uses ttk's ``clam`` theme recoloured with the same dark/light palette.

Colours are not hard-coded in the UI modules: they read roles from the shared palette :data:`P`
(``P.bg``, ``P.fg``, ``P.muted``, ``P.accent``...). :func:`apply_theme` fills ``P`` in, so it must run
before any widget is created (``App.__init__`` does this first).

The appearance is a setting (``settings["appearance"]``: ``"dark"`` | ``"light"`` | ``"system"``);
changing it takes effect after restarting the app.
"""

import sys
from tkinter import TclError, ttk

APPEARANCES = [("Dark", "dark"), ("Light", "light"), ("Match macOS / system", "system")]

# ---- palettes (hex fallbacks; on macOS some roles are replaced by semantic system colours)
DARK = {
    "bg": "#1e1e1e",            # window background
    "fg": "#e8e8e8",            # body text
    "field_bg": "#2a2a2a",      # text boxes / entries
    "readonly_bg": "#252527",   # previews and read-only fields
    "muted": "#9a9a9f",         # hints, secondary text
    "ok": "#4cc26a",            # ✔ green
    "bad": "#ff6b5e",           # ⚠ red
    "warn": "#f0a43a",          # in-progress amber
    "select_bg": "#2f5694",     # selected text / rows
    "select_fg": "#ffffff",
    "accent": "#0a84ff",        # focus rings, selected photo
    "link": "#4da3ff",
    "border": "#3a3a3c",        # hairlines around boxes
    "header_bg": "#2c2c2e",     # table headings / tabs (non-mac)
    "button_bg": "#3a3a3c",     # buttons (non-mac)
    "button_active": "#48484a",
    "card_bg": "#262628",       # drop zone, grouped boxes
    "cell_bg": "#2a2a2c",       # photo thumbnail cell
    "cell_border": "#3a3a3c",
    "pinned_bg": "#33301f",     # template photo cell
    "pinned_border": "#c9a227",
    "drop_hover": "#1f3a5f",    # photo drag target
    "preview_bg": "#232325",    # large photo preview / thumbnails
    "log_bg": "#141414",        # activity log
    "log_fg": "#d6d6d6",
    "sold_row": "#1f3527",      # Items Database rows
    "warn_row": "#46321a",
    "viewer_bg": "#0d0d0d",     # full-size photo viewer
    "viewer_fg": "#e6e6e6",
    "viewer_muted": "#a8a8a8",
}
LIGHT = {
    "bg": "#ffffff", "fg": "#111111", "field_bg": "#ffffff", "readonly_bg": "#eef0f3", "muted": "#666666",
    "ok": "#1a7f37", "bad": "#b42318", "warn": "#a15c00", "select_bg": "#b3d4ff", "select_fg": "#111111",
    "accent": "#2f6fed", "link": "#1f5fbf", "border": "#c8c8c8", "header_bg": "#e9e9e9",
    "button_bg": "#e9e9e9", "button_active": "#dcdcdc", "card_bg": "#f4f1ea", "cell_bg": "#ffffff",
    "cell_border": "#d9d9d9", "pinned_bg": "#fffbea", "pinned_border": "#d4a017", "drop_hover": "#cfe3ff",
    "preview_bg": "#f2f2f2", "log_bg": "#161616", "log_fg": "#e6e6e6", "sold_row": "#eaf6ec",
    "warn_row": "#fff1e6", "viewer_bg": "#111111", "viewer_fg": "#eeeeee", "viewer_muted": "#cccccc",
}
# macOS semantic colours (Tk 8.6.10+). Each is only used if this Tk knows it - see _resolve_mac_colours.
MAC_SEMANTIC = {
    "bg": "systemWindowBackgroundColor",
    "fg": "systemTextColor",
    "field_bg": "systemTextBackgroundColor",
    "select_bg": "systemSelectedTextBackgroundColor",
    "select_fg": "systemSelectedTextColor",
    "accent": "systemControlAccentColor",
    "link": "systemLinkColor",
    "border": "systemSeparatorColor",
    "muted": "systemPlaceholderTextColor",
}


class Palette:
    """Attribute bag of colour roles (``P.bg``, ``P.fg``...). Filled in by :func:`apply_theme`."""

    def __init__(self, values):
        self.update(values)
        self.dark = False
        self.native_mac = False

    def update(self, values):
        self.__dict__.update(values)


P = Palette(dict(LIGHT, pane=LIGHT["bg"]))  # replaced in place by apply_theme() before the UI is built


def is_mac(root):
    return root.tk.call("tk", "windowingsystem") == "aqua"


def _mac_window_appearance(win, appearance):
    """Force Dark/Light Aqua on one window (Tk 8.6.10+). 'system' leaves macOS in charge."""
    value = {"dark": "darkaqua", "light": "aqua", "system": "auto"}[appearance]
    try:
        win.tk.call("::tk::unsupported::MacWindowStyle", "appearance", win, value)
    except TclError:
        pass  # older Tk: follows the system appearance


def _mac_is_dark(root):
    try:
        return bool(int(root.tk.call("::tk::unsupported::MacWindowStyle", "isdark", root)))
    except (TclError, ValueError):
        return False


def _resolve_mac_colours(root, base):
    """Swap hex roles for semantic macOS colours that this Tk understands."""
    colours = dict(base)
    for role, name in MAC_SEMANTIC.items():
        try:
            root.winfo_rgb(name)  # raises TclError for unknown colour names
            colours[role] = name
        except TclError:
            pass
    return colours


def style_window(win):
    """Apply the current appearance to a new Toplevel window (dialogs, photo viewer)."""
    if P.native_mac:
        _mac_window_appearance(win, getattr(P, "appearance", "dark"))
    try:
        win.configure(bg=P.bg)
    except TclError:
        pass


def apply_theme(root, appearance="dark"):
    """Style the whole app. Call once, right after creating the Tk root and before building widgets.

    Returns the ttk theme name used ("aqua" on macOS, otherwise "clam").
    """
    appearance = appearance if appearance in ("dark", "light", "system") else "dark"
    mac = is_mac(root)
    if mac:
        _mac_window_appearance(root, appearance)
        root.update_idletasks()
        dark = _mac_is_dark(root) if appearance == "system" else appearance == "dark"
        colours = _resolve_mac_colours(root, DARK if dark else LIGHT)
    else:
        dark = appearance != "light"  # "system" = dark elsewhere (no reliable OS query)
        colours = dict(DARK if dark else LIGHT)
    # "pane": background inside notebook tabs. Native macOS tab panes are drawn one shade off the
    # window colour (Tk 8.6.11+ names it systemWindowBackgroundColor1); elsewhere it equals bg.
    colours["pane"] = colours["bg"]
    if mac:
        try:
            root.winfo_rgb("systemWindowBackgroundColor1")
            colours["pane"] = "systemWindowBackgroundColor1"
        except TclError:
            pass
    P.update(colours)
    P.dark, P.native_mac, P.appearance = dark, mac, appearance

    # classic Tk widgets read their defaults from the option database
    for pattern, value in (
            ("*Background", P.bg), ("*Foreground", P.fg), ("*highlightBackground", P.bg),
            ("*Text.Background", P.field_bg), ("*Text.Foreground", P.fg), ("*Text.insertBackground", P.fg),
            ("*Entry.insertBackground", P.fg), ("*Listbox.Background", P.field_bg), ("*Listbox.Foreground", P.fg),
            ("*selectBackground", P.select_bg), ("*selectForeground", P.select_fg),
            ("*TCombobox*Listbox.background", P.field_bg), ("*TCombobox*Listbox.foreground", P.fg),
            ("*TCombobox*Listbox.selectBackground", P.select_bg),
            ("*TCombobox*Listbox.selectForeground", P.select_fg)):
        root.option_add(pattern, value)
    root.configure(bg=P.bg)

    style = ttk.Style(root)
    if mac:
        style.theme_use("aqua")
        _style_aqua(style)
        return "aqua"
    style.theme_use("clam")
    _style_clam(style)
    return "clam"


def _style_aqua(style):
    """Native controls: only text colours, headings and table metrics are adjusted."""
    style.configure("TLabel", foreground=P.fg)
    style.configure("Muted.TLabel", foreground=P.muted)
    style.configure("Heading.TLabel", font=("TkDefaultFont", 17, "bold"))
    style.configure("Section.TLabel", font=("TkDefaultFont", 13, "bold"))
    style.configure("Treeview", rowheight=24)
    style.configure("Big.TRadiobutton", font=("TkDefaultFont", 13))


def _style_clam(style):
    """Recolour the cross-platform clam theme to match the palette."""
    style.configure(".", background=P.bg, foreground=P.fg, fieldbackground=P.field_bg, bordercolor=P.border,
                    lightcolor=P.bg, darkcolor=P.bg, troughcolor=P.card_bg, arrowcolor=P.fg,
                    selectbackground=P.select_bg, selectforeground=P.select_fg, insertcolor=P.fg,
                    focuscolor=P.accent)
    style.configure("TLabel", background=P.bg, foreground=P.fg)
    style.configure("Muted.TLabel", foreground=P.muted)
    style.configure("Heading.TLabel", font=("TkDefaultFont", 15, "bold"))
    style.configure("Section.TLabel", font=("TkDefaultFont", 12, "bold"))
    style.configure("TFrame", background=P.bg)
    style.configure("TLabelframe", background=P.bg, bordercolor=P.border)
    style.configure("TLabelframe.Label", background=P.bg, foreground=P.fg, font=("TkDefaultFont", 11, "bold"))
    style.configure("TButton", background=P.button_bg, foreground=P.fg, bordercolor=P.border, padding=(10, 4))
    style.map("TButton", background=[("pressed", P.select_bg), ("active", P.button_active)],
              foreground=[("disabled", P.muted)])
    for widget in ("TCheckbutton", "TRadiobutton"):
        style.configure(widget, background=P.bg, foreground=P.fg, indicatorbackground=P.field_bg)
        style.map(widget, background=[("active", P.bg)], indicatorbackground=[("selected", P.accent)])
    style.configure("Big.TRadiobutton", font=("TkDefaultFont", 11))
    for widget in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(widget, foreground=P.fg, fieldbackground=P.field_bg, insertcolor=P.fg, insertwidth=2,
                        bordercolor=P.border, arrowcolor=P.fg, background=P.button_bg)
    style.map("TCombobox", fieldbackground=[("readonly", P.field_bg)], foreground=[("readonly", P.fg)],
              selectbackground=[("readonly", P.field_bg)], selectforeground=[("readonly", P.fg)])
    style.map("TEntry", fieldbackground=[("readonly", P.readonly_bg)], foreground=[("readonly", P.fg)])
    style.configure("TNotebook", background=P.bg, bordercolor=P.border, tabmargins=(6, 6, 6, 0))
    style.configure("TNotebook.Tab", background=P.header_bg, foreground=P.muted, padding=(12, 5), bordercolor=P.border)
    style.map("TNotebook.Tab", background=[("selected", P.bg)], foreground=[("selected", P.fg)])
    style.configure("Treeview", background=P.field_bg, fieldbackground=P.field_bg, foreground=P.fg, rowheight=24,
                    bordercolor=P.border)
    style.configure("Treeview.Heading", background=P.header_bg, foreground=P.fg, font=("TkDefaultFont", 10, "bold"))
    style.map("Treeview", background=[("selected", P.select_bg)], foreground=[("selected", P.select_fg)])
    style.map("Treeview.Heading", background=[("active", P.button_active)])
    style.configure("TScrollbar", background=P.button_bg, troughcolor=P.bg, bordercolor=P.bg, arrowcolor=P.muted)
    style.configure("TPanedwindow", background=P.bg)
    style.configure("TSeparator", background=P.border)


def platform_modifier():
    """'Command' on macOS, 'Control' elsewhere (for key bindings and menu accelerators)."""
    return "Command" if sys.platform == "darwin" else "Control"
