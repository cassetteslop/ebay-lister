"""Photo picker: drop/browse up to 20 photos, drag to reorder, large preview, and pinned
template photos that stay at a fixed position.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ebay_lister.config import MAX_PHOTOS, PHOTO_EXTS
from ebay_lister.ui.compat import DND_FILES, HAS_DND, HAS_PIL, Image
from ebay_lister.ui.theme import P, style_window
from ebay_lister.ui.widgets import TextLabel, load_image


class PhotoStrip(ttk.Frame):
    """Your photos + optional pinned template photos at fixed positions.

    self.paths  = this listing's own photos (reorderable)
    self.pinned = [(slot, position, path)] template photos, placed at `position` (1-based) or
                  at the end if the listing has fewer photos than that.
    ordered()   = the final photo order sent to eBay.
    """
    THUMB = 92
    COLS = 5
    PREVIEW = 400

    def __init__(self, master, log):
        super().__init__(master)
        self.log = log
        self.paths = []
        self.pinned = []
        self.skipped_slots = set()
        self.selected = None
        self._thumbs = {}
        self._preview_img = None
        self._drag_src = None
        self._press_xy = (0, 0)
        self._entries = []
        self.drop = tk.Label(self, text="", relief="flat", bd=0, height=2, cursor="hand2",
                             highlightthickness=1, highlightbackground=P.border,
                             bg=P.card_bg, fg=P.fg, font=("TkDefaultFont", 11))
        self.drop.pack(fill="x", pady=(0, 8))
        self.drop.bind("<Button-1>", lambda e: self.browse())
        if HAS_DND:
            for w in (self.drop, self):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)

        body = ttk.Frame(self)
        body.pack(fill="x")
        self.grid_frame = ttk.Frame(body)
        self.grid_frame.pack(side="left", anchor="n", fill="x", expand=True)

        pv = ttk.Frame(body)
        pv.pack(side="right", anchor="n", padx=(12, 0))
        self.pv_box = tk.Frame(pv, width=self.PREVIEW, height=self.PREVIEW, bg=P.preview_bg,
                               highlightthickness=1, highlightbackground=P.border)
        self.pv_box.pack_propagate(False)
        self.pv_box.pack()
        self.pv_label = tk.Label(self.pv_box, bg=P.preview_bg, fg=P.muted, cursor="hand2",
                                 text="Click a thumbnail to preview it here.\nDouble-click for full size.")
        self.pv_label.pack(fill="both", expand=True)
        self.pv_label.bind("<Button-1>", lambda e: self.open_full())
        self.pv_caption = TextLabel(pv, text="", fg=P.muted, bg=P.bg, wraplength=self.PREVIEW, justify="left")
        self.pv_caption.pack(anchor="w", pady=(4, 0))

        self.status = TextLabel(self, text="", fg=P.muted, bg=P.bg, anchor="w", justify="left")
        self.status.pack(anchor="w", pady=(6, 0), fill="x")
        self.refresh()

    # ---- model
    def active_pins(self):
        return sorted(((pos, slot, p) for slot, pos, p in self.pinned if slot not in self.skipped_slots),
                      key=lambda x: (x[0], x[1]))

    def capacity(self):
        return MAX_PHOTOS - len(self.active_pins())

    def entries(self):
        """[(path, pinned_slot_or_None, user_index_or_None)] in final order."""
        out = [(p, None, i) for i, p in enumerate(self.paths)]
        for pos, slot, p in self.active_pins():
            out.insert(min(max(pos, 1) - 1, len(out)), (p, slot, None))
        return out

    def ordered(self):
        return [p for p, _, _ in self.entries()]

    def set_pinned(self, fixed_photos):
        """fixed_photos: template list of {'path','position'}."""
        self.pinned = [(i, int(fp.get("position") or MAX_PHOTOS), fp["path"])
                       for i, fp in enumerate(fixed_photos or []) if fp.get("path")]
        pinned_paths = {p for _, _, p in self.pinned}
        self.paths = [p for p in self.paths if p not in pinned_paths]
        self.paths = self.paths[:self.capacity()]
        self.refresh()

    def missing_pins(self):
        return [p for _, _, p in self.active_pins() if not os.path.isfile(p)]

    # ---- adding / removing
    def browse(self):
        paths = filedialog.askopenfilenames(
            title="Choose photos", filetypes=[("Images", "*.jpg *.jpeg *.png *.gif *.JPG *.JPEG *.PNG"), ("All", "*.*")])
        if paths:
            self.add(paths)

    def _on_drop(self, event):
        self.add(self.tk.splitlist(event.data))

    def add(self, paths):
        skipped = 0
        pinned_paths = {p for _, _, p in self.pinned}
        for p in paths:
            p = p.strip("{}")
            if os.path.isdir(p):
                continue
            if not p.lower().endswith(PHOTO_EXTS):
                skipped += 1
                continue
            if p in self.paths or p in pinned_paths:
                continue
            if len(self.paths) >= self.capacity():
                self.log(f"Only {MAX_PHOTOS} photos allowed in total "
                         f"({len(self.active_pins())} come from the template) - extra files ignored.")
                break
            self.paths.append(p)
        if skipped:
            self.log(f"Skipped {skipped} file(s): use JPG, PNG or GIF.")
        if self.paths and self.selected not in self.ordered():
            self.selected = self.paths[0]
        self.refresh()

    def clear(self):
        self.paths = []
        self.skipped_slots = set()
        self.selected = None
        self._thumbs = {}
        self.refresh()

    def move_user(self, src_u, dst_u):
        if 0 <= dst_u < len(self.paths) and src_u != dst_u:
            self.paths.insert(dst_u, self.paths.pop(src_u))
        self.after_idle(self.refresh)

    def remove_entry(self, i):
        p, slot, u = self._entries[i]
        if slot is not None:
            self.skipped_slots.add(slot)
            self.log("Template photo removed for this listing only (Clear form brings it back).")
        else:
            self.paths.pop(u)
            self._thumbs.pop(p, None)
        if self.selected == p:
            rest = self.ordered()
            self.selected = rest[min(i, len(rest) - 1)] if rest else None
        self.after_idle(self.refresh)

    # ---- drawing
    def _thumb(self, path):
        if path not in self._thumbs:
            self._thumbs[path] = load_image(path, self.THUMB, self.THUMB)[0]
        return self._thumbs[path]

    def refresh(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self._entries = self.entries()
        cap = self.capacity()
        hint = (f"Drag & drop up to {cap} photos here, or click to browse" if HAS_DND else
                f"Click to add up to {cap} photos   (pip install tkinterdnd2 to drag & drop from your file manager)")
        self.drop.configure(text=hint)
        for i, (p, slot, u) in enumerate(self._entries):
            sel = p == self.selected
            pinned = slot is not None
            border = P.accent if sel else (P.pinned_border if pinned else P.cell_border)
            cell = tk.Frame(self.grid_frame, bd=0, bg=P.pinned_bg if pinned else P.cell_bg, padx=3, pady=3,
                            highlightthickness=3, highlightbackground=border)
            cell._photo_idx = i
            cell._pinned = pinned
            cell.grid(row=i // self.COLS, column=i % self.COLS, padx=3, pady=3, sticky="n")
            img = self._thumb(p) if os.path.isfile(p) else None
            cbg = cell.cget("bg")
            if img:
                lbl = tk.Label(cell, image=img, bg=cbg, cursor="hand2" if pinned else "fleur",
                               width=self.THUMB, height=self.THUMB)
            else:
                txt = "MISSING FILE\n" if not os.path.isfile(p) else ""
                lbl = tk.Label(cell, text=txt + os.path.basename(p)[:14] + "\n(no preview)", bg=P.preview_bg,
                               fg=P.bad if txt else P.fg, width=13, height=6)
            lbl._photo_idx = i
            lbl.pack()
            cap_txt = ("1 ★ Primary" if i == 0 else str(i + 1)) + ("  📌 template" if pinned else "")
            tk.Label(cell, text=cap_txt, bg=cbg, fg=P.fg, font=("TkDefaultFont", 9, "bold")).pack()
            btns = tk.Frame(cell, bg=cbg)
            btns.pack()
            if pinned:
                ttk.Button(btns, text="✕", width=2, command=lambda i=i: self.remove_entry(i)).pack(side="left")
            else:
                ttk.Button(btns, text="◀", width=2, command=lambda u=u: self.move_user(u, u - 1)).pack(side="left")
                ttk.Button(btns, text="✕", width=2, command=lambda i=i: self.remove_entry(i)).pack(side="left")
                ttk.Button(btns, text="▶", width=2, command=lambda u=u: self.move_user(u, u + 1)).pack(side="left")
            for w in (cell, lbl):
                w.bind("<ButtonPress-1>", lambda e, i=i: self._press(e, i))
                w.bind("<B1-Motion>", self._motion)
                w.bind("<ButtonRelease-1>", self._release)
                w.bind("<Double-Button-1>", lambda e, i=i: self.open_full(i))
        n = len(self._entries)
        pins = len(self.active_pins())
        msg = (f"{n}/{MAX_PHOTOS} photos · drag thumbnails (or use ◀ ▶) to reorder · the first photo is the primary image."
               if n else "No photos yet.")
        if pins:
            msg += (f"\n📌 {pins} template photo(s) stay at their set position (or at the end if there are fewer photos). "
                    "✕ on one skips it for this listing.")
        missing = self.missing_pins()
        if missing:
            msg += f"\n⚠ Template photo file not found: {', '.join(os.path.basename(m) for m in missing)}"
        self.status.configure(text=msg, fg=P.bad if missing else P.muted)
        self._show_preview()

    def _show_preview(self):
        order = self.ordered()
        p = self.selected if self.selected in order else None
        if not p:
            self._preview_img = None
            self.pv_label.configure(image="", text="Click a thumbnail to preview it here.\nDouble-click for full size.")
            self.pv_caption.configure(text="")
            return
        img, _ = load_image(p, self.PREVIEW - 8, self.PREVIEW - 8)
        self._preview_img = img
        if img:
            self.pv_label.configure(image=img, text="")
        else:
            self.pv_label.configure(image="", text="Preview needs Pillow for this file type\n(pip install pillow)")
        idx = order.index(p) + 1
        dims = ""
        if HAS_PIL:
            try:
                with Image.open(p) as im:
                    dims = f" · {im.width}×{im.height}px"
            except Exception:
                pass
        pin = "  📌 template photo" if any(p == pp for _, _, pp in self.pinned) else ""
        self.pv_caption.configure(text=f"Photo {idx}: {os.path.basename(p)}{dims}{pin}")

    def select(self, i):
        if 0 <= i < len(self._entries):
            self.selected = self._entries[i][0]
            for c in self.grid_frame.winfo_children():
                c.configure(highlightbackground=P.accent if c._photo_idx == i else
                            (P.pinned_border if c._pinned else P.cell_border))
            self._show_preview()

    def open_full(self, i=None):
        order = self.ordered()
        if not order:
            return
        idx = [order.index(self.selected) if self.selected in order else 0] if i is None else [i]
        win = tk.Toplevel(self)
        style_window(win)
        win.configure(bg=P.viewer_bg)
        sw, sh = int(self.winfo_screenwidth() * 0.85), int(self.winfo_screenheight() * 0.85)
        win.geometry(f"{sw}x{sh}")
        lbl = tk.Label(win, bg=P.viewer_bg, fg=P.viewer_fg)
        lbl.pack(fill="both", expand=True)
        cap = tk.Label(win, bg=P.viewer_bg, fg=P.viewer_muted, text="")
        cap.pack(fill="x", pady=4)
        holder = {}

        def show():
            p = order[idx[0]]
            img, _ = load_image(p, sw - 20, sh - 60)
            holder["img"] = img
            lbl.configure(image=img or "", text="" if img else "Install Pillow to view this file type.")
            win.title(f"Photo {idx[0] + 1}/{len(order)} - {os.path.basename(p)}")
            cap.configure(text=f"Photo {idx[0] + 1} of {len(order)}  ·  ← → to browse  ·  Esc to close")

        def step(d):
            idx[0] = (idx[0] + d) % len(order)
            show()

        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Left>", lambda e: step(-1))
        win.bind("<Right>", lambda e: step(1))
        lbl.bind("<Button-1>", lambda e: win.destroy())
        show()
        win.focus_set()

    # ---- drag to reorder (your photos only; template photos stay put)
    def _cell_at(self, x, y):
        w = self.winfo_containing(x, y)
        while w is not None and not hasattr(w, "_photo_idx"):
            w = w.master
        return w

    def _press(self, e, i):
        self._drag_src = i
        self._press_xy = (e.x_root, e.y_root)

    def _motion(self, e):
        if self._drag_src is None or self._entries[self._drag_src][1] is not None:
            return
        tgt = self._cell_at(e.x_root, e.y_root)
        tcell = tgt.master if (tgt is not None and not isinstance(tgt, tk.Frame)) else tgt
        for c in self.grid_frame.winfo_children():
            base = P.pinned_bg if c._pinned else P.cell_bg
            c.configure(bg=P.drop_hover if c is tcell else base)

    def _release(self, e):
        src, self._drag_src = self._drag_src, None
        if src is None:
            return
        for c in self.grid_frame.winfo_children():
            c.configure(bg=P.pinned_bg if c._pinned else P.cell_bg)
        moved = abs(e.x_root - self._press_xy[0]) + abs(e.y_root - self._press_xy[1]) > 6
        tgt = self._cell_at(e.x_root, e.y_root)
        src_entry = self._entries[src]
        if moved and tgt is not None and tgt._photo_idx != src and src_entry[1] is None:
            dst = tgt._photo_idx
            before = self._entries[:dst + 1] if dst > src else self._entries[:dst]
            k = sum(1 for _, slot, u in before if slot is None and u != src_entry[2])
            self.selected = src_entry[0]
            self.move_user(src_entry[2], k)
        else:
            self.select(src)
