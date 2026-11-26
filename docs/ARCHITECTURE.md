# Architecture

Ebay Lister is split into layers. Each layer may use the layers above it in this list, never the ones below:

```
config.py / storage.py      constants and JSON files            (no app imports)
core/                       pure functions                      (config only)
api/                        eBay HTTP client                    (core, config)
services/                   templates, listing, queue, db, sync (api, core, config)
ui/                         Tkinter                             (everything above)
```

`core/`, `api/` and `services/` never import Tkinter, so they can be unit-tested, or used from a script, without a window.

## Modules

### `ebay_lister/config.py`
Fixed values:
* the data folder (`default_data_dir()`: `EBAY_LISTER_HOME`, then `%APPDATA%\Ebay Lister`, then `~/.ebay_lister`);
* eBay hosts and scopes, and eBay limits (80-character titles, 24 photos, 50-character SKUs, prices);
* `CONDITIONS` and `EBAY_ENVS`, and `DEFAULT_SETTINGS`;
* **`TEMPLATE_DEFAULTS`**, the reference for every template key;
* `STARTER_TEMPLATES` and `HELPFUL_LINKS`.

### `core/`: pure logic
| Module | Contents |
|---|---|
| `variables.py` | `{NAME}` placeholders: `render`, `placeholders`, `is_valid_name`, `required` (variables used in the title), `undefined`, and `render_listing(template, values)`, which returns the rendered title, description, condition description and item specifics |
| `text.py` | item-specific parsing (`Name: a \| b`), SKUs, prices, text → HTML |
| `validation.py` | Rules that return lists of error strings. Template checks come in three groups: **content** (name, text, variables), **settings** (quantity, package) and **account** (category, policies, location; skipped when queueing). `validate_listing(...)` is what the List Item tab and the batch call. |
| `payloads.py` | `build_inventory_item`, `build_offer`: the exact eBay JSON bodies |
| `matching.py` | `best_match()` maps saved policy names onto the policies eBay returns |
| `fees.py` | `calc_profit` |

### `api/`
* `http.py`: `http_call()` (urllib), `ApiError`, multipart encoding.
* `ebay.py`: `EbayClient`.
  * **Sign-in:** OAuth with a RuName and automatic token refresh (plus an application token for the category API).
  * **Account:** business policies, locations, category suggestions and item aspects.
  * **Listing:** Media API image upload, inventory item, offer (create or update), publish.
  * **Sales:** `getOffer`, orders.

### `services/`
| Module | Contents |
|---|---|
| `templates.py` | `TemplateStore`: named templates in `templates.json`, identified by `id` (stable across renames). It does create (from defaults or `base_id`), save, rename, delete (never the last one), and `unique_name` ("X (copy)", "X (copy 2)"). Duplicates get their own standard-photo copies. `normalize()` fills keys missing from older files. |
| `listing.py` | `ListingJob` (template + rendered text + price + photos + SKU + variable values), `ListingResult`, and `ListingService.run(job, log)` (never raises). `record(job, result, queued=False)` adds the row to the Items Database. |
| `listing_queue.py` | `ListingQueue` saves a job on its database row (`queue` JSON: rendered text, values, price, SKU, photo copies in `queued_photos/item_<id>/`, `template_id` plus a snapshot). `BatchLister(queue, service, templates).run(log, item_ids)` lists queued items using each template **as it is now**, falling back to the snapshot. It returns a `BatchReport` (listed / skipped / failed). |
| `database.py` | `ItemsDB`, a thread-safe SQLite wrapper. The schema is `ITEM_FIELDS`; missing columns are added on start-up. `status` is `queued` / `unpublished` / `active` / `out_of_stock` / `ended` / `deleted`. `is_active`, `is_queued`. |
| `sync.py` | `SalesSync(db, ebay).run(log)` returns a `SyncReport` (status updates and sales from orders). |

### `ui/`
| Module | Contents |
|---|---|
| `app.py` | `App`, the composition root: settings, `TemplateStore`, `EbayClient`, `ItemsDB`, services, tabs, menus. Shared helpers (`run_bg`, `log`, `toast`, `refresh_submit_labels`). `main()` redirects output to `app.log` when frozen and sets up Windows DPI awareness. |
| `tasks.py` | `TaskRunner`: runs work in a thread and delivers results on the Tk thread through a queue. Widgets are never touched from a thread. |
| `theme.py` | Palette `P` plus `apply_theme(root, appearance)`. Native `aqua` on macOS (Dark/Light Aqua, semantic colours); a recoloured `clam` theme elsewhere. |
| `menus.py` | `MenuBar`: native macOS menu bar; File / Edit / View / Help elsewhere; ⌘/Ctrl shortcuts |
| `widgets.py` | `FormGrid` (label · widget · hint rows), `ScrollFrame`, `Choice` (readonly combobox over `(label, value)`), `TextLabel`, text-box helpers, `load_image`, `category_dialog` |
| `photo_strip.py` | `PhotoStrip`: drop/browse, reorder, large preview, pinned standard photos (`set_pinned`, `ordered()`) |
| `listing_runner.py` | `ListingModeSelector` (queue / list now; always queue while eBay isn't connected) and `run_listing_job(app, button, job, queue)` |
| `compat.py` | Optional Pillow / tkinterdnd2 imports and `HAS_PIL` / `HAS_DND` |
| `tabs/base.py` | `BaseTab`: `self.app`, scrollable `self.body`, `add_log()`, `on_shown()` |
| `tabs/list_item.py` | `ListItemTab` and `VariableInputs` (one entry per variable; values survive template switches) |
| `tabs/templates.py` | `TemplatesTab` (template management bar, editor, eBay policies), `VariablesEditor`, `VariableDialog` |
| `tabs/items.py` | `ItemsTab`, `ItemList` (one section), `QueuedListingEditor` |
| `tabs/links.py`, `tabs/settings.py` | Helpful Links (built from `HELPFUL_LINKS`), Settings |

`selftest.py` (`--self-test`) imports every module and builds the window hidden, using a temporary data folder. The Windows CI build runs it against the packaged `.exe`.

## Data flow: listing an item

```
List Item tab
  values typed in VariableInputs ─► core.variables.render_listing(template, values) ─► preview
  Create ─► core.validation.validate_listing(... account=not queue)
         ─► ListingJob(template, rendered, price, photos, sku, values)
              ├─ queue ─► ListingService.record(queued=True) + ListingQueue.add   (instant, no uploads)
              └─ now ──► app.run_bg(ListingService.run) ─► record(result)         (background thread)
Items Database › List queued ─► BatchLister.run ─► for each item: job_for(item, TemplateStore) ─► ListingService.run
```

## Common changes

| I want to… | Change |
|---|---|
| Add a template field | Add the key to `TEMPLATE_DEFAULTS` (old files get it automatically through `normalize`). Add it to the editor in `tabs/templates.py` (`load` / `collect`), to `core/payloads.py` if it's sent to eBay, and to `core/validation.py` if it needs a rule. |
| Make another template field support `{VARIABLES}` | Add it to `RENDERED_FIELDS` in `core/variables.py` and to `FIELD_LABELS` in `core/validation.py`, then use `rendered[...]` in the payload |
| Add a Helpful Link | Add a `(title, url, description)` tuple to `HELPFUL_LINKS` |
| Add a column to the Items Database | Add it to `ITEM_FIELDS` (migrated automatically), then show it in `tabs/items.py` |
| Change the starter templates | `STARTER_TEMPLATES` (only used when `templates.json` doesn't exist yet) |
| Add a tab | Subclass `BaseTab`, lay it out with `FormGrid`, then create it and add it to `self.tabs` in `ui/app.py` |
| Allow more standard photos | `FIXED_PHOTO_SLOTS` in `tabs/templates.py` |

## Conventions
* Never hard-code colours in UI code: use palette roles (`P.muted`, `P.card_bg`...). Prefer `ttk` widgets or `TextLabel`.
* Network calls only happen inside `app.run_bg(...)`; callbacks run on the Tk thread.
* Validation functions return error lists and never raise. Services return result objects instead of raising for expected failures.
* Templates are plain dicts; `TEMPLATE_DEFAULTS` is the reference for keys. The store hands out copies, and changes only go through `TemplateStore.save/create/rename/delete`.
