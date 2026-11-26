"""Headless UI smoke test (run by tests/test_ui_smoke.py with the fake tkinter on sys.path).

Builds the real App and drives the main flows: template switching, variables and preview,
queueing, template duplicate / variable rename / save / rename / delete / new, bulk listing,
list-right-away and the Items Database. Exits non-zero on the first failed check.
"""

import os
import sys
import tempfile

os.environ["EBAY_LISTER_HOME"] = tempfile.mkdtemp(prefix="ebay-lister-smoke-")

import tkinter.messagebox as mb  # noqa: E402 - the fake, because of PYTHONPATH
import tkinter.simpledialog as sd  # noqa: E402

from ebay_lister.ui.app import App  # noqa: E402
from ebay_lister.ui.widgets import text_get, text_set  # noqa: E402
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
check(app.templates.names() == ["Sony Walkman", "Blank template"], "starter templates")
check(lt.submit_btn._opts["text"] == "＋ Add to queue", "queues while eBay isn't connected")

# variables -> preview -> queue
lt.vars_frame._widgets["MODEL"].set("WM-F2078")
lt.vars_frame._widgets["CONDITION_NOTES"].insert("end", "New belt.")
lt.update_preview()
check("WM-F2078" in lt.title_preview._opts["text"], "title preview uses the variable")
lt.price.set("89.99")
lt.photos.paths = list(photos)
check(lt._errors() == [], f"no errors before queueing: {lt._errors()}")
lt.submit()
check(app.listing_queue.count() == 1 and lt.vars_frame.values()["MODEL"] == "", "queued and form cleared")
check(len(it.queued_list.tree._rows) == 1, "queued section shows the item")

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
