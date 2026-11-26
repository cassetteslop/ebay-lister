"""Sales sync: pulls listing status and sales from eBay into the Items Database.

Only items that aren't marked sold (and aren't still queued) are checked, and fields you edited
by hand (a profit you typed in, an item you marked sold yourself) are never overwritten.

* ``getOffer`` gives each listing's status and listing id.
* The Fulfillment API ``getOrders`` gives sales: price + shipping, date and eBay's real marketplace
  fee (split across items for multi-item orders). Needs the ``sell.fulfillment.readonly`` scope.
"""

import time
from dataclasses import dataclass, field
from typing import List

from ebay_lister.api.http import ApiError
from ebay_lister.core.fees import calc_profit


@dataclass
class SyncReport:
    """What a sync found. Shown to the user when it finishes."""
    checked: int = 0
    sold: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class SalesSync:
    """One sync run over the Items Database. Use :meth:`run` from a background thread."""

    def __init__(self, db, ebay):
        self.db = db
        self.ebay = ebay
        self.report = SyncReport()

    def run(self, log=print) -> SyncReport:
        self.report = SyncReport()
        items = [i for i in self.db.all() if not i["sold"] and not i.get("queue")
                 and (i.get("offer_id") or i.get("listing_id"))]
        if not items:
            return self.report
        if not self.ebay.connected():
            self.report.errors.append("eBay isn't connected - connect it on the Settings tab.")
            return self.report
        log(f"[Sync] Checking {len(items)} eBay listing(s)…")
        for item in items:
            if item.get("offer_id"):
                self._status(item)
        try:
            self._sales(items)
        except ApiError as exc:
            text = str(exc).lower()
            if "http 403" in text or "insufficient" in text or "scope" in text:
                self.report.errors.append("Permission to read orders is missing - reconnect eBay on the Settings tab.")
            else:
                self.report.errors.append(f"eBay orders: {exc}")
        return self.report

    # ---- helpers
    def _update(self, item, **fields):
        self.db.update(item["id"], **fields)
        item.update(fields)

    def _mark_sold(self, item, price, date, fees):
        upd = {"sold": 1, "sold_on": "eBay", "sold_price": round(price, 2), "sold_date": date, "fees": fees}
        if item.get("profit") is None:  # never overwrite a profit you typed in
            upd["profit"] = calc_profit(price, fees, item.get("cost"))
        self._update(item, **upd)
        self.report.sold.append(f"{item['title'][:50]} - sold for ${price:.2f}")

    def _status(self, item):
        try:
            offer = self.ebay.get_offer(item["offer_id"])
        except ApiError as exc:
            if "HTTP 404" in str(exc):
                self._update(item, status="deleted")
            else:
                self.report.errors.append(f"Offer {item['offer_id']}: {exc}")
            return
        listing = offer.get("listing") or {}
        upd = {"status": (listing.get("listingStatus") or offer.get("status") or "").lower() or None,
               "last_synced": time.time()}
        if upd["status"] == "published":
            upd["status"] = "active"
        if listing.get("listingId"):
            upd["listing_id"] = str(listing["listingId"])
            upd["listing_url"] = self.ebay.listing_url(listing["listingId"])
        self._update(item, **upd)
        self.report.checked += 1

    def _sales(self, items):
        since = min(i["created_at"] for i in items) - 86400
        by_listing = {i["listing_id"]: i for i in items if i.get("listing_id")}
        by_sku = {i["sku"]: i for i in items if i.get("sku")}
        for order in self.ebay.orders_since(since):
            if (order.get("cancelStatus") or {}).get("cancelState") == "CANCELED":
                continue
            lines = order.get("lineItems", [])
            order_fee = float((order.get("totalMarketplaceFee") or {}).get("value") or 0)
            line_sum = sum(float((li.get("lineItemCost") or {}).get("value") or 0) for li in lines) or 1
            for li in lines:
                item = by_listing.get(str(li.get("legacyItemId"))) or by_sku.get(li.get("sku"))
                if not item or item["sold"]:
                    continue
                cost = float((li.get("lineItemCost") or {}).get("value") or 0)
                ship = float(((li.get("deliveryCost") or {}).get("shippingCost") or {}).get("value") or 0)
                fee = round(order_fee * cost / line_sum, 2) if order_fee else None  # split multi-item orders
                self._mark_sold(item, cost + ship, (order.get("creationDate") or "")[:10], fee)
