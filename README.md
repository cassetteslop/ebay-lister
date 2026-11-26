# Ebay Lister

A desktop app (Python + Tkinter) for creating **eBay** listings from reusable, named **templates** with your own **variables**. You can queue listings instantly and bulk-list them later, and it keeps a local database of everything you've listed, with sales tracking.

| Tab | What it's for |
|---|---|
| **List Item** | Pick a template, add photos, fill in the template's variables, SKU and price, check the live preview, and click Create. Create adds the item to the queue (default) or lists it right away. |
| **Items Database** | Everything listed or queued. Active listings are on top, then the **Queued** section (bulk-list all or just the ones you select), then unpublished, sold and ended items. Mark items sold, record prices, fees and profit, open listings, or sync sales from eBay. |
| **Templates** | Create, duplicate, rename and delete templates, and edit their variables, text, eBay settings, package size, standard photos and business policies. |
| **Helpful Links** | Shortcuts to your eBay orders, time away, active listings and developer keys. |
| **Settings** | eBay API keys, connect/disconnect, publish-or-unpublished, appearance (dark / light / match system). |

## Install and run

### Windows: download the built app
Every push to `main` builds the Windows app with GitHub Actions (see [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)).
1. Open the repository's **Actions** tab and click the latest **Build Windows app** run.
2. Under **Artifacts**, download **Ebay-Lister-windows**.
3. Unzip it anywhere and run **`Ebay Lister.exe`**. Keep the whole folder together.

Pushing a version tag (for example `git tag v1.0.0 && git push --tags`) also publishes a GitHub **Release** with the zip attached.

The app isn't code-signed, so Windows SmartScreen may say *"Windows protected your PC"*. Click **More info → Run anyway**. See [docs/BUILDING_WINDOWS.md](docs/BUILDING_WINDOWS.md) for building locally and for signing.

### From source (any OS)
You need **Python 3.9+ with Tkinter**. On Windows and with the python.org macOS installer it's included; with Homebrew, run `brew install python-tk`.
```bash
pip install -r requirements.txt     # optional: Pillow (photo previews) + tkinterdnd2 (drag & drop)
python run.py                       # or: python -m ebay_lister
python run.py --self-test           # checks the installation without touching your data
```

### Where your data lives
| OS | Folder |
|---|---|
| Windows | `%APPDATA%\Ebay Lister\` |
| macOS / Linux | `~/.ebay_lister/` |

Set the environment variable `EBAY_LISTER_HOME` to use another folder (for example a portable install on a USB stick). The folder contains:

* `settings.json`: eBay keys and sign-in tokens
* `templates.json`: your templates
* `items.db`: the Items Database (SQLite)
* `template_photos/`: copies of standard photos
* `queued_photos/`: photo copies for queued items
* `app.log`: errors from the packaged app

## Templates and variables

A **template** holds everything that's the same for a kind of item:

* title and description patterns, condition notes and item specifics;
* eBay category and condition, default price, quantity, Best Offer;
* package weight and size;
* up to three **standard photos** that appear in every listing at a set position;
* business policies and ship-from location.

You start with two templates, **Sony Walkman** and **Blank template**.

* **New…** creates a template from the defaults.
* **Duplicate…** creates a new template based on the current one, including its variables and standard photos.
* **Rename…** and **Delete** do what they say. Deleting a template doesn't affect items already listed or queued with it.
* If you switch away from a template with unsaved changes, the app asks whether to save them.

**Variables** are your own fields. Each one becomes a text box on the List Item tab, and its value replaces `{VARIABLE_NAME}` in the title, description, condition notes and item specifics:

```
Variables:   MODEL (single line), CONDITION_NOTES (multi-line)
Title:       Sony Walkman {MODEL} Portable Cassette Player Vintage Tested Working
Specifics:   Brand: Sony
             Model: {MODEL}
```

* **Names:** letters, digits and `_`, starting with a letter. Names are case-sensitive; UPPER_CASE is recommended. Each variable can have a default value.
* **Required:** variables used in the **title** must be filled in. Others can be left blank. An item-specifics line whose value ends up empty is skipped.
* **Insert {NAME} at cursor** types the placeholder where you last clicked. **Renaming** a variable updates every `{OLD}` to `{NEW}`.
* **Mistakes are flagged:** using `{SOMETHING}` without a matching variable shows up in the title hint and in **Validate**. Write `{{` or `}}` for a literal brace.

## Connecting eBay
1. At <https://developer.ebay.com/my/keys>, copy the **App ID** and **Cert ID**.
2. Under *User Tokens*, create a **RuName** (your app's redirect URL name).
3. In **Settings**, choose Production or Sandbox, enter the three values and click **Connect to eBay…**.
4. Approve access in the browser, then paste the **full address of the page you land on** back into the app.
5. On **Templates**, click **⟳ Load policies & locations from eBay**. If you have no ship-from location yet, create one from your ZIP code there. Then **Save template**.

Scopes requested: `sell.inventory`, `sell.account` and `sell.fulfillment.readonly` (the last one is for syncing orders).

**No API access yet?** You can still create items: until eBay is connected, Create adds them to the queue. Policies, location and category aren't needed to queue, only to list.

## The listing queue

**List Item › When I click Create** has two options:

* **Add to queue** (default): saves the item instantly, with copies of its photos, and clears the form for the next item. Nothing is uploaded.
* **List right away:** uploads photos and creates the eBay listing now.

**Bulk listing:** in the **Items Database**, use **⬆ List all queued** (also **File › List All Queued Items…**, Ctrl/⌘+L) or **⬆ List selected** (Ctrl/⌘/Shift-click to pick several).
* **Template settings:** each item uses **its template as it is at that moment** for category, condition, package, policies and location. You can finish a template after queueing. A copy saved with the item is used if the template has since been deleted.
* **Text:** the item's title and description are already filled in when it's queued. Change them with **Edit queued listing…**.
* **Skipped and failed items:** items that sold in the meantime are skipped. Failures stay queued with the error shown. Finished items get their eBay link, and their photo copies are deleted.

## How listing works
1. Photos are uploaded to eBay's picture service (Media API).
2. The **inventory item** is created: condition and condition description, item specifics, package size.
3. The **offer** is created or updated: Buy It Now, Good 'Til Cancelled, price, category, policies, location.
4. It's **published**, unless *Publish listings immediately* is off in Settings (then you get an unpublished offer).

## Items Database and sales sync
**⟳ Sync with eBay** checks unsold, listed items:
* it updates each item's status (active, sold out, ended, deleted);
* it reads your orders to fill in the sold price (item plus shipping), the date and eBay's actual fee;
* it fills in profit (sold price − fees − your cost) only if you haven't typed one yourself.

Use **Sold on: Other** for items you sold elsewhere.

## Development
```bash
python -m unittest discover -s tests -t .     # unit tests + headless UI smoke test (no display needed)
ruff check .                                  # lint
python run.py --self-test                     # imports + builds the window hidden, with a temp data folder
```
* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the code is organised, and common changes
* [docs/BUILDING_WINDOWS.md](docs/BUILDING_WINDOWS.md): the Windows build, locally and in GitHub Actions
* [docs/BUILDING_MAC.md](docs/BUILDING_MAC.md): building a Mac `.app`
* [CLAUDE.md](CLAUDE.md): notes for AI coding assistants (Claude Code)

```
ebay-lister/
├── run.py                        launcher + PyInstaller entry point
├── requirements.txt              optional runtime packages
├── requirements-build.txt        + PyInstaller
├── .github/workflows/            Windows build
├── packaging/windows/            PyInstaller spec, icon tool
├── packaging/macos/              Mac .app build
├── docs/
├── tests/                        unit tests, fake tkinter + UI smoke test
└── ebay_lister/
    ├── config.py                 constants, defaults, starter templates, helpful links
    ├── storage.py                JSON files
    ├── selftest.py               --self-test
    ├── core/                     variables, text, validation, payloads, matching, fees
    ├── api/                      eBay HTTP client
    ├── services/                 templates, listing, queue, database, sync
    └── ui/                       app window, theme, menus, widgets, photo strip, tabs/
```
