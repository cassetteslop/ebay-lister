"""Headless UI smoke test (run by tests/test_ui_smoke.py with the fake tkinter on sys.path).

Builds the real App and drives the main flows: template switching, variables and preview,
queueing, template duplicate / variable rename / save / rename / delete / new, bulk listing,
list-right-away and the Items Database. Exits non-zero on the first failed check.
"""

import os
import sys
import tempfile

os.environ["EBAY_LISTER_HOME"] = tempfile.mkdtemp(prefix="ebay-lister-smoke-")

import tkinter as tk  # noqa: E402 - the fake, because of PYTHONPATH
import tkinter.messagebox as mb  # noqa: E402
import tkinter.simpledialog as sd  # noqa: E402

from ebay_lister.ui.app import App  # noqa: E402
from ebay_lister.ui.aspects_dialog import AspectsDialog  # noqa: E402
from ebay_lister.ui.widgets import text_get, text_set  # noqa: E402
from tests.test_core import WALKMAN  # noqa: E402
from tests.test_services import FakeEbay  # noqa: E402


def check(cond, what):
    if not cond:
        print("FAILED:", what)
        sys.exit(1)


photos = []
for name in ("a.jpg", "b.jpg"):
    path = os.path.join(os.environ["EBAY_LISTER_HOME"], name)
    with open(path, "wb") as f:
        f.write(b"x")
    photos.append(path)

app = App()


def run_bg(fn, ok=None, err=None):  # run "background" work synchronously
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001
        if err:
            err(exc)
        raise
    if ok:
        ok(result)


app.run_bg, app.log_bg = run_bg, app.log
lt, tt, it = app.list_tab, app.templates_tab, app.items_tab
check([label for _, label in app.tabs] == ["List Item", "Items Database", "Templates", "Helpful Links", "Settings"],
      "tab names")
check(app.templates.names() == ["Patch", "Pokemon card", "Blank template"], "starter templates")
check(lt.template["name"] == "Patch" and "THEME" in lt.vars_frame._widgets, "first starter selected")
check(it.log_text is not None and it.scroll is not None, "Items Database has an activity log and scrolls")
app.log("hello from the log")
check("hello from the log" in it.log_text._text and "hello from the log" in lt.log_text._text, "log on both tabs")
walk = app.templates.save(dict(WALKMAN))                  # the flows below use this test template
tt._changed_templates(select_id=walk["id"])
check(lt.template["name"] == "Sony Walkman", "List Item switched to the new template")
check(lt.submit_btn._opts["text"] == "＋ Add to queue", "queues while eBay isn't connected")
help_menu = next(m for kind, label, m in app.menubar.menubar.items if kind == "cascade" and label == "Help")
check(help_menu.items[0][1] == "User Guide", "Help menu starts with the User Guide")

# variables -> preview -> queue
lt.vars_frame._widgets["MODEL"].set("WM-F2078")
lt.vars_frame._widgets["CONDITION_NOTES"].insert("end", "New belt.")
lt.update_preview()
title = lt.fields.text["title"]                         # editable by default
check("WM-F2078" in title.get(), "title follows the variables")
title.set("Sony Walkman WM-F2078 hand-written title")
lt.vars_frame._widgets["MODEL"].set("WM-F2079")
lt.update_preview()
check(title.get() == "Sony Walkman WM-F2078 hand-written title" and lt.fields.edited("title"), "hand edits are kept")
lt.fields.reset_text("title")
check("WM-F2079" in title.get() and not lt.fields.edited("title"), "Reset restores the template title")
check(isinstance(lt.fields.text["description"], tk.Text) and lt.fields.text["description"].cget("state") == "disabled",
      "description shown read-only by default")
lt.fields.settings["package"]["weight_oz"].set("20")
check(lt.fields.overrides() == {"weight_oz": 20}, f"package override: {lt.fields.overrides()}")
lt.price.set("89.99")
lt.photos.paths = list(photos)
check(lt._errors() == [], f"no errors before queueing: {lt._errors()}")
lt.submit()
check(app.listing_queue.count() == 1 and lt.vars_frame.values()["MODEL"] == "", "queued and form cleared")
check(len(it.queued_list.tree._rows) == 1, "queued section shows the item")
queued = app.listing_queue.data(app.listing_queue.pending()[0])
check(queued["overrides"] == {"weight_oz": 20} and "WM-F2079" in queued["rendered"]["title"], "queued with overrides")
check(lt.fields.overrides() == {}, "form cleared back to the template's package")

# item specifics picker merges eBay's suggestions into the text
applied = []
dlg = AspectsDialog(app.root, "15053", [{"name": "Brand", "required": True, "values": ["Sony", "Aiwa"]},
                                        {"name": "Color", "recommended": True, "values": []},
                                        {"name": "Rare", "values": []}], "Brand: Sony\nModel: {MODEL}", applied.append)
check(set(dlg.vars) == {"Brand", "Color"}, "required + recommended shown first")
dlg.vars["Brand"].set("Aiwa")
dlg.vars["Color"].set("Silver")
dlg.apply()
check(applied == ["Brand: Aiwa\nModel: {MODEL}\nColor: Silver"], f"aspects merged: {applied}")

# a template can make more fields editable on the List Item form
tt.select(walk["id"])
tt.list_fields["description"].set_value("edit")
tt.list_fields["package"].set_value("show")
check(tt.save(), "save field settings")
check(app.templates.get(walk["id"])["list_fields"]["description"] == "edit", "field settings saved")
lt.select_template(walk["id"])
check(lt.fields.text["description"].cget("state") == "normal" and "package" not in lt.fields.settings,
      "List Item form follows the template's field settings")

# switching templates rebuilds the variable boxes
blank = app.templates.by_name("Blank template")
lt.template_choice.set_value(blank["id"])
lt._template_selected()
check(list(lt.vars_frame._widgets) == ["BRAND", "ITEM", "CONDITION_NOTES"], "blank template variables")

# templates: duplicate, rename a variable, save, rename, delete, new
walk = app.templates.by_name("Sony Walkman")
tt.select(walk["id"])
sd.askstring = lambda *a, **k: "Sony Discman"
tt.duplicate()
check(tt.current["name"] == "Sony Discman", "duplicate")
check("Sony Discman" in [label for label, _ in lt.template_choice.options], "List Item drop-down updated")
tt.variables._saved({"name": "DISC_MODEL", "default": "", "multiline": False}, "MODEL")
check("{DISC_MODEL}" in tt.v["title"].get() and "{DISC_MODEL}" in text_get(tt.texts["aspects"]),
      "variable rename updates placeholders")
text_set(tt.texts["aspects"], text_get(tt.texts["aspects"]) + "\nColor: {COLOR}")
tt.variables.variables.append({"name": "COLOR", "default": "Black", "multiline": False})
check(tt.is_dirty(), "edits make the template dirty")
check(tt.save(), "save")
saved = app.templates.by_name("Sony Discman")
check([v["name"] for v in saved["variables"]] == ["DISC_MODEL", "CONDITION_NOTES", "COLOR"], "saved variables")
sd.askstring = lambda *a, **k: "Discman"
tt.rename()
check("Discman" in app.templates.names(), "rename")
mb.askyesno = lambda *a, **k: True
tt.delete()
check("Discman" not in app.templates.names(), "delete")
sd.askstring = lambda *a, **k: "Vinyl Records"
tt.new()
check(tt.current["name"] == "Vinyl Records" and tt.current["variables"] == [], "new template from defaults")

# connect eBay, finish the Walkman template, bulk-list, then list right away
fake = FakeEbay()
app.settings["ebay_refresh_token"] = "x"
app.ebay = app.listing_service.ebay = fake
walk = app.templates.by_name("Sony Walkman")
walk.update(fulfillment_policy_id="F", payment_policy_id="P", return_policy_id="R", location_key="L")
app.templates.save(walk)
it.list_queued()
check(app.listing_queue.count() == 0 and len(it.active_list.tree._rows) == 1, "bulk list")
lt.template_choice.set_value(walk["id"])
lt._template_selected()
lt.mode.mode.set("now")
lt.mode._changed()
check(lt.submit_btn._opts["text"] == "🚀 List on eBay", "list-now button")
lt.vars_frame._widgets["MODEL"].set("WM-10")
lt.price.set("120")
lt.photos.paths = [photos[0]]
mb.askyesno = lambda *a, **k: "browser" not in a[1]
lt.submit()
check(app.db.all()[0]["status"] == "active", "listed right away")
errors = [m for kind, m in mb.LOG if kind == "error"]
check(not errors, f"no error dialogs: {errors}")
print("UI SMOKE OK")
