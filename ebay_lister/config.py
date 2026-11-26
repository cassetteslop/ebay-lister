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
    ("Used - very good", "USED_VERY_GOOD"),
    ("Used - good", "USED_GOOD"),
    ("Used - acceptable", "USED_ACCEPTABLE"),
    ("Seller refurbished", "SELLER_REFURBISHED"),
    ("Certified refurbished", "CERTIFIED_REFURBISHED"),
    ("For parts or not working", "FOR_PARTS_OR_NOT_WORKING"),
    ("New", "NEW"),
    ("New other (open box)", "NEW_OTHER"),
    ("Like new", "LIKE_NEW"),
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
    "fulfillment_policy_id": None, "fulfillment_policy_name": "USPS Ground Advantage free shipping",
    "payment_policy_id": None, "payment_policy_name": "eBay Payments",
    "return_policy_id": None, "return_policy_name": "30 days returns",
    "location_key": None, "location_name": "",
    "fixed_photos": [],           # [{"path": ..., "position": 1-24}] added to every listing
    "variables": [],              # [{"name": "MODEL", "default": "", "multiline": False}]
}

STARTER_TEMPLATES = [
    dict(TEMPLATE_DEFAULTS,
         name="Sony Walkman",
         title="Sony Walkman {MODEL} Portable Cassette Player Vintage Tested Working",
         description=("Sony Walkman {MODEL}\n\n{CONDITION_NOTES}\n\n"
                      "Every Walkman is cleaned, tested and inspected before it ships.\n\n"
                      "What's included:\n- Sony Walkman {MODEL}\n\n"
                      "Ships fast and well packed. Message me with any questions!"),
         condition_description="{CONDITION_NOTES}",
         category_id="15053", category_name="Personal Cassette Players",
         aspects=("Brand: Sony\nModel: {MODEL}\nProduct Line: Walkman\nType: Portable Cassette Player\n"
                  "Playable Media Format: Cassette Tape\nMPN: Does Not Apply"),
         weight_lb=0, weight_oz=15, length=8, width=6, height=4,
         variables=[{"name": "MODEL", "default": "", "multiline": False},
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
