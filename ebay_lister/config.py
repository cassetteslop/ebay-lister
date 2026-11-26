"""App-wide constants and defaults.

Everything that is a fixed value lives here: where data is stored, eBay API endpoints and OAuth
scopes, eBay field limits, drop-down option lists, default settings, the starter templates and the
Helpful Links list. Change values here rather than in the UI code.
"""

import os
import sys

APP_NAME = "Ebay Lister"
APP_ID = "ebay-lister"  # used for the PyInstaller executable name


def default_data_dir():
    """Where settings, templates, the database and photo copies live.

    * ``EBAY_LISTER_HOME`` environment variable, if set (handy for testing or a portable install)
    * Windows: ``%APPDATA%\\Ebay Lister``
    * macOS / Linux: ``~/.ebay_lister``
    """
    if os.environ.get("EBAY_LISTER_HOME"):
        return os.environ["EBAY_LISTER_HOME"]
    if sys.platform.startswith("win") and os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], APP_NAME)
    return os.path.join(os.path.expanduser("~"), ".ebay_lister")


APP_DIR = default_data_dir()
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
TEMPLATES_FILE = os.path.join(APP_DIR, "templates.json")
DB_FILE = os.path.join(APP_DIR, "items.db")
TEMPLATE_PHOTO_DIR = os.path.join(APP_DIR, "template_photos")   # copies of templates' standard photos
QUEUED_PHOTO_DIR = os.path.join(APP_DIR, "queued_photos")       # photo copies for queued listings
LOG_FILE = os.path.join(APP_DIR, "app.log")                     # errors from the packaged app

# The user guide: docs/USER_GUIDE.md, rendered to this PDF by packaging/make_guide.py and bundled
# with the built apps (inside the app as docs/<name>, and next to the app in the download).
GUIDE_PDF = f"{APP_NAME} User Guide.pdf"


def guide_path():
    """The user guide to open from Help › User Guide, or None if there isn't one.

    Packaged app: the bundled PDF. From source: the PDF from the last build, else the Markdown source.
    """
    if getattr(sys, "frozen", False):
        candidates = [os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "docs", GUIDE_PDF)]
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [os.path.join(root, "build", "guide", GUIDE_PDF), os.path.join(root, "docs", "USER_GUIDE.md")]
    return next((p for p in candidates if os.path.exists(p)), None)

# --------------------------------------------------------------------------
# eBay API
# --------------------------------------------------------------------------
EBAY_HOSTS = {
    "production": {"api": "https://api.ebay.com", "auth": "https://auth.ebay.com", "media": "https://apim.ebay.com"},
    "sandbox": {"api": "https://api.sandbox.ebay.com", "auth": "https://auth.sandbox.ebay.com",
                "media": "https://apim.sandbox.ebay.com"},
}
EBAY_SCOPES = " ".join([
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",  # read orders for the Items Database
])
EBAY_MARKETPLACE = "EBAY_US"

# --------------------------------------------------------------------------
# eBay limits
# --------------------------------------------------------------------------
MAX_PHOTOS = 24          # eBay allows up to 24 photos per listing
MAX_TITLE_LEN = 80
MAX_SKU_LEN = 50
MAX_CONDITION_DESCRIPTION = 1000
MIN_PRICE, MAX_PRICE = 0.99, 1_000_000
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".gif")

# --------------------------------------------------------------------------
# Drop-down options
# --------------------------------------------------------------------------
CONDITIONS = [
    ("Used", "USED_EXCELLENT"),
    ("Used - very good  (trading cards: Ungraded)", "USED_VERY_GOOD"),
    ("Used - good", "USED_GOOD"),
    ("Used - acceptable", "USED_ACCEPTABLE"),
    ("Seller refurbished", "SELLER_REFURBISHED"),
    ("Certified refurbished", "CERTIFIED_REFURBISHED"),
    ("For parts or not working", "FOR_PARTS_OR_NOT_WORKING"),
    ("New", "NEW"),
    ("New other (open box)", "NEW_OTHER"),
    ("Like new  (trading cards: Graded)", "LIKE_NEW"),
]
# Ungraded trading cards (category 183454, CCG Individual Cards, e.g. Pokemon) need a "Card Condition"
# condition descriptor (name 40001). eBay's values for CCG cards - sports / non-sport cards use other IDs:
# https://developer.ebay.com/api-docs/user-guides/static/mip-user-guide/mip-enum-condition-descriptor-ids-for-trading-cards.html
CARD_CONDITION_DESCRIPTOR = "40001"
CARD_CONDITIONS = [
    ("(not a trading card)", ""),
    ("Near Mint or Better", "400010"),
    ("Lightly Played (Excellent)", "400015"),
    ("Moderately Played (Very Good)", "400016"),
    ("Heavily Played (Poor)", "400017"),
]
EBAY_ENVS = [("Production (real listings)", "production"), ("Sandbox (testing)", "sandbox")]

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "ebay_env": "production", "ebay_client_id": "", "ebay_client_secret": "", "ebay_runame": "",
    "ebay_access_token": "", "ebay_refresh_token": "", "ebay_token_expires_at": 0,
    "ebay_refresh_expires_at": 0,
    "publish_immediately": True,   # False = create unpublished offers
    "listing_mode": "queue",       # "queue" (Add to queue) | "now" (List right away)
    "appearance": "dark",          # "dark" | "light" | "system" (applied at start-up)
    "last_template_id": None,      # template selected on the List Item tab
}

# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
# Fields a template can put on the List Item form, in form order: (key, label).
# Each template chooses a mode per field (``list_fields``): "hidden", "show" (read-only, as filled in
# from the template) or "edit" (pre-filled from the template, and can be changed for this one item).
LIST_FIELDS = [
    ("title", "Title"),
    ("description", "Description"),
    ("condition_description", "Condition notes"),
    ("aspects", "Item specifics"),
    ("condition", "Condition"),
    ("card_condition", "Card condition"),
    ("package", "Package weight & size"),
    ("quantity", "Quantity"),
    ("best_offer", "Best Offer"),
]
LIST_FIELD_MODES = [("Hidden", "hidden"), ("Show", "show"), ("Edit", "edit")]
DEFAULT_LIST_FIELDS = {"title": "edit", "description": "show", "condition_description": "show", "aspects": "edit",
                       "condition": "hidden", "card_condition": "hidden", "package": "edit", "quantity": "hidden",
                       "best_offer": "hidden"}
# Template settings a single listing can override (List Item fields in "edit" mode); "package" covers 5 keys.
PACKAGE_KEYS = ("weight_lb", "weight_oz", "length", "width", "height")
OVERRIDABLE = ("condition", "card_condition", "quantity", "best_offer") + PACKAGE_KEYS

# Every template has these keys. Account-specific IDs (policies, location) are filled in by
# "Load policies & locations from eBay" on the Templates tab.
TEMPLATE_DEFAULTS = {
    "id": None,
    "name": "New template",
    "title": "",
    "description": "",
    "condition": "USED_EXCELLENT",
    "condition_description": "",
    "category_id": "",
    "category_name": "",
    "aspects": "",                # item specifics, one "Name: value | value2" per line
    "default_price": "",
    "quantity": 1,
    "weight_lb": 0, "weight_oz": 0,
    "length": 0, "width": 0, "height": 0,   # inches
    "best_offer": False,
    "card_condition": "",         # CARD_CONDITIONS value; trading cards only
    "fulfillment_policy_id": None, "fulfillment_policy_name": "USPS Ground Advantage free shipping",
    "payment_policy_id": None, "payment_policy_name": "eBay Payments",
    "return_policy_id": None, "return_policy_name": "30 days returns",
    "location_key": None, "location_name": "",
    "fixed_photos": [],           # [{"path": ..., "position": 1-24}] added to every listing
    "variables": [],              # [{"name": "MODEL", "default": "", "multiline": False}]
    "list_fields": dict(DEFAULT_LIST_FIELDS),   # what the List Item form shows (see LIST_FIELDS)
}

STARTER_TEMPLATES = [
    dict(TEMPLATE_DEFAULTS,
         name="Patch",
         title="{THEME} {TYPE} Patch {SIZE} {BACKING}",
         description=("{THEME} {TYPE} patch\n\n"
                      "Size: {SIZE}\nBacking: {BACKING}\nColors: {COLORS}\n\n{NOTES}\n\n"
                      "Ships flat in a rigid mailer the next business day. Message me with any questions!"),
         condition="NEW",
         aspects=("Type: {TYPE}\nTheme: {THEME}\nAttachment: {BACKING}\nSize: {SIZE}\nColor: {COLORS}\n"
                  "Material: {MATERIAL}\nBrand: Unbranded"),
         default_price="6.99",
         weight_lb=0, weight_oz=2, length=7, width=5, height=1,
         variables=[{"name": "THEME", "default": "", "multiline": False},
                    {"name": "TYPE", "default": "Embroidered", "multiline": False},
                    {"name": "SIZE", "default": "", "multiline": False},
                    {"name": "BACKING", "default": "Iron-On", "multiline": False},
                    {"name": "COLORS", "default": "", "multiline": False},
                    {"name": "MATERIAL", "default": "Embroidered Fabric", "multiline": False},
                    {"name": "NOTES", "default": "", "multiline": True}]),
    dict(TEMPLATE_DEFAULTS,
         name="Pokemon card",
         title="Pokemon {CARD_NAME} {CARD_NUMBER} {SET} {RARITY} TCG Card",
         description=("Pokemon TCG - {CARD_NAME} {CARD_NUMBER}\nSet: {SET}\nRarity: {RARITY}\nFinish: {FINISH}\n\n"
                      "Ungraded. {CONDITION_NOTES}\n\n"
                      "The card in the photos is the card you'll receive. Ships in a penny sleeve and toploader."),
         condition="USED_VERY_GOOD", card_condition="400010",
         condition_description="{CONDITION_NOTES}",
         category_id="183454", category_name="CCG Individual Cards",
         aspects=("Game: Pokemon TCG\nCard Name: {CARD_NAME}\nCharacter: {CARD_NAME}\nSet: {SET}\n"
                  "Card Number: {CARD_NUMBER}\nRarity: {RARITY}\nFinish: {FINISH}\nLanguage: {LANGUAGE}\n"
                  "Graded: No\nManufacturer: The Pokemon Company"),
         default_price="1.99",
         weight_lb=0, weight_oz=1, length=6, width=4, height=1,
         list_fields=dict(DEFAULT_LIST_FIELDS, card_condition="edit"),
         variables=[{"name": "CARD_NAME", "default": "", "multiline": False},
                    {"name": "CARD_NUMBER", "default": "", "multiline": False},
                    {"name": "SET", "default": "", "multiline": False},
                    {"name": "RARITY", "default": "", "multiline": False},
                    {"name": "FINISH", "default": "Regular", "multiline": False},
                    {"name": "LANGUAGE", "default": "English", "multiline": False},
                    {"name": "CONDITION_NOTES", "default": "", "multiline": True}]),
    dict(TEMPLATE_DEFAULTS,
         name="Blank template",
         title="{BRAND} {ITEM}",
         description="{BRAND} {ITEM}\n\n{CONDITION_NOTES}",
         condition_description="{CONDITION_NOTES}",
         aspects="Brand: {BRAND}",
         weight_lb=1, length=10, width=8, height=4,
         variables=[{"name": "BRAND", "default": "", "multiline": False},
                    {"name": "ITEM", "default": "", "multiline": False},
                    {"name": "CONDITION_NOTES", "default": "", "multiline": True}]),
]

# --------------------------------------------------------------------------
# Helpful Links tab: (section, [(title, url, description), ...]). Add your own here.
# --------------------------------------------------------------------------
HELPFUL_LINKS = [
    ("Orders", [
        ("eBay - All orders", "https://www.ebay.com/sh/ord/?filter=status:ALL_ORDERS",
         "Seller Hub orders: awaiting shipment, paid, shipped, cancellations and returns."),
    ]),
    ("Time away", [
        ("eBay - Time away", "https://www.ebay.com/vac/timeaway",
         "Schedule time away: pause your listings or extend handling time while you're unavailable."),
    ]),
    ("Listings", [
        ("eBay - Active listings", "https://www.ebay.com/sh/lst/active",
         "Seller Hub listings: active, unsold, drafts and scheduled."),
    ]),
    ("Developer (API keys used by this app)", [
        ("eBay - Application keys", "https://developer.ebay.com/my/keys",
         "App ID, Cert ID and User Tokens (RuName) for production and sandbox."),
    ]),
]
