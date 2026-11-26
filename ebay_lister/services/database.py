"""Local SQLite database of every item listed (or queued) through the app: the Items Database tab.

The schema is :data:`ITEM_FIELDS`. Missing columns are added automatically on start-up, so
upgrading the app never loses data. Rows are plain dicts.

``status`` describes the eBay listing:

=============  ==============================================================
queued         saved with "Add to queue", not on eBay yet (see ``queue``)
unpublished    offer created but not published (Settings › publish unticked)
active         live on eBay
out_of_stock   eBay listing has no quantity left (usually: it sold)
ended          ended on eBay
deleted        the offer no longer exists on eBay
=============  ==============================================================
"""

import os
import sqlite3
import threading
import time

ITEM_FIELDS = {
    "created_at": "REAL",
    # what was listed
    "template_id": "TEXT", "template_name": "TEXT", "title": "TEXT", "sku": "TEXT", "price": "REAL",
    "photo": "TEXT",                      # first photo, for the thumbnail
    "variables": "TEXT",                  # JSON {name: value} typed on the List Item tab
    # eBay
    "listing_id": "TEXT", "offer_id": "TEXT", "listing_url": "TEXT", "status": "TEXT", "environment": "TEXT",
    # sale
    "sold": "INTEGER DEFAULT 0", "sold_on": "TEXT", "sold_date": "TEXT", "sold_price": "REAL",
    "cost": "REAL", "fees": "REAL", "profit": "REAL", "notes": "TEXT", "last_synced": "REAL",
    # listing queue (see services/listing_queue.py)
    "queue": "TEXT", "queue_error": "TEXT", "queued_at": "REAL",
}
SOLD_ON = ["eBay", "Other"]


class ItemsDB:
    """Thread-safe wrapper around the SQLite ``items`` table."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock, self.con:
            self.con.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            have = {r["name"] for r in self.con.execute("PRAGMA table_info(items)")}
            for col, typ in ITEM_FIELDS.items():
                if col not in have:  # forward migration
                    self.con.execute(f"ALTER TABLE items ADD COLUMN {col} {typ}")

    def add(self, **fields):
        """Insert a row (unknown keys are ignored). Returns its id."""
        fields = {k: v for k, v in fields.items() if k in ITEM_FIELDS}
        fields.setdefault("created_at", time.time())
        with self.lock, self.con:
            cur = self.con.execute(f"INSERT INTO items ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
                                   list(fields.values()))
            return cur.lastrowid

    def update(self, item_id, **fields):
        fields = {k: v for k, v in fields.items() if k in ITEM_FIELDS}
        if not fields:
            return
        with self.lock, self.con:
            self.con.execute(f"UPDATE items SET {','.join(k + '=?' for k in fields)} WHERE id=?",
                             list(fields.values()) + [item_id])

    def delete(self, item_id):
        with self.lock, self.con:
            self.con.execute("DELETE FROM items WHERE id=?", (item_id,))

    def get(self, item_id):
        with self.lock:
            row = self.con.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    def all(self):
        with self.lock:
            return [dict(r) for r in self.con.execute("SELECT * FROM items ORDER BY created_at DESC")]

    def close(self):
        """Close the connection (the app keeps it open for its whole lifetime)."""
        with self.lock:
            self.con.close()

    # ---- classification used by the Items Database sections
    @staticmethod
    def is_queued(item):
        return bool(item.get("queue"))

    @staticmethod
    def is_active(item):
        return not item.get("sold") and item.get("status") == "active"
