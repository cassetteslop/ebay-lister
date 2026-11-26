# CLAUDE.md

Notes for Claude Code (and other coding assistants) working in this repository.

## What this is
**Ebay Lister**: a Python 3.9+ / Tkinter desktop app for creating eBay listings from named, reusable templates with user-defined `{VARIABLES}`. Listings are queued by default and bulk-listed later. A local SQLite "Items Database" tracks listings and sales. Windows builds come from GitHub Actions (PyInstaller). It was derived from an earlier Etsy + eBay "Walkman Lister" app; Etsy support was removed on purpose, so don't reintroduce Etsy code or Etsy columns.

## Commands
```bash
python -m unittest discover -s tests -t .     # all tests (unit + headless UI smoke); no display needed
ruff check .                                  # lint (config in pyproject.toml; tests/fake_tk is excluded)
python run.py                                 # run the app (needs a display)
python run.py --self-test                     # import everything + build the window hidden, temp data dir
```
Set `EBAY_LISTER_HOME=/some/tmp/dir` when running anything that might touch real user data.

Windows build (CI): `.github/workflows/build-windows.yml` → `packaging/windows/ebay_lister.spec`. It builds, then runs the exe with `--self-test`. See `docs/BUILDING_WINDOWS.md`.

## Layout and layering
`config.py`/`storage.py` → `core/` (pure) → `api/` (eBay HTTP) → `services/` (templates, listing, queue, db, sync) → `ui/` (Tkinter).
Lower layers never import higher ones, and **nothing outside `ui/` imports tkinter**. Details are in `docs/ARCHITECTURE.md`.

Key objects:
- `core/variables.py`: `{NAME}` rendering. `render_listing(template, values)` returns the rendered title / description / condition_description / aspects.
- `services/templates.py`: `TemplateStore` (`templates.json`, ids are stable, names unique case-insensitively, at least one template always exists). Templates are plain dicts; **`config.TEMPLATE_DEFAULTS` defines every key**.
- `services/listing.py`: `ListingJob`, `ListingService.run()` (never raises; returns `ListingResult`), `record()`.
- `services/listing_queue.py`: `ListingQueue` + `BatchLister`. Queued items store **rendered** text plus photo copies; at batch time they use the template's *current* account settings (fallback: the stored snapshot).
- `services/database.py`: `ItemsDB`; the schema is `ITEM_FIELDS`, and new columns are auto-migrated.
- `ui/app.py`: `App` is the composition root; tabs reach shared services via `self.app`.

## Conventions
- Validation functions return `list[str]` of user-facing errors and never raise. Template checks are split into **content** (text and variables), **settings** (quantity, package) and **account** (category, policies, location). Account checks are skipped when queueing (`account=False`), and batch validation skips the variable checks (`check_values=False`).
- Network work only runs through `app.run_bg(fn, on_ok, on_err)`; callbacks run on the Tk thread. Never touch widgets from a worker thread; use `app.log_bg` for logging from threads.
- Colours: never hard-code hex values in UI code. Use roles on the palette `ui.theme.P` (`P.fg`, `P.muted`, `P.card_bg`...) and add new roles to both `DARK` and `LIGHT`. Prefer `ttk` widgets, or `ui.widgets.TextLabel` for text, so macOS draws native controls.
- Forms use `ui.widgets.FormGrid` (`row(label, widget, hint)`, `section(...)`, `full(widget)`).
- Keep user-facing text plain and friendly. The README and docs are written for a non-developer seller.
- Line length 135; imports sorted (ruff `I`).

## Testing
- `tests/test_core.py`, `tests/test_services.py`: pure logic and services with `FakeEbay` (in `test_services.py`).
- `tests/test_ui_smoke.py` runs `tests/ui_smoke.py` in a subprocess with **`tests/fake_tk`**, a permissive fake tkinter, first on `PYTHONPATH`. It builds the real `App` and drives the main flows. It catches wiring errors and AttributeErrors, but **not** visual problems. If you use a new Tk method, add a no-op or simple version to `tests/fake_tk/tkinter`. When you add a UI flow, add a few `check(...)` lines to `tests/ui_smoke.py`.
- Add or adjust tests with every behaviour change; all tests must pass before committing.

## Gotchas
- eBay limits live in `config.py`: 80-character titles, 24 photos, 50-character SKUs, 1000-character condition descriptions.
- `fixed_photos` and queued photos are **copies** inside the data folder. `TemplateStore.remove_photo_copy` only deletes files inside its own photo folder, never user originals.
- In PyInstaller builds, modules that are only imported dynamically need `hiddenimports` in `packaging/windows/ebay_lister.spec`. The CI self-test fails the build if something is missing.
- Windowed builds have `sys.stdout is None`. `ui.app.main()` redirects output to `app.log` when frozen; `selftest.py` writes to a file.
- `EbayClient` keeps tokens in the shared settings dict and calls `save_settings()` on refresh.
- The version lives in `ebay_lister/__init__.py` (`__version__`) and `pyproject.toml`; bump both before tagging `v*`.
