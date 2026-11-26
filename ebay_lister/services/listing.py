"""Listing service: sends one item to eBay and records it in the Items Database.

No UI code here, so it can be used and tested on its own::

    rendered = render_listing(template, {"MODEL": "WM-2", "CONDITION_NOTES": "New belt"})
    job = ListingJob(template=template, rendered=rendered, values={...}, price="89.99",
                     photos=["1.jpg", "2.jpg"], sku="WM2-261125203015")
    result = service.run(job, log=print)     # network calls - run it off the UI thread
    service.record(job, result)              # save to the Items Database

eBay flow: Media API image upload × N -> createOrReplaceInventoryItem -> createOffer/updateOffer
-> publishOffer (unless "publish immediately" is off in Settings).
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ebay_lister.core.payloads import build_inventory_item, build_offer
from ebay_lister.core.text import parse_price


@dataclass
class ListingJob:
    """Everything needed to list one item. Built by the List Item tab (or rebuilt from the queue)."""
    template: dict                 # category, condition, package, policies, location...
    rendered: Dict[str, str]       # title / description / condition_description / aspects with variables filled
    price: str
    photos: List[str]
    sku: str
    values: Dict[str, str] = field(default_factory=dict)   # the variable values (kept for the record)

    @property
    def title(self):
        return self.rendered.get("title", "")


@dataclass
class ListingResult:
    """Outcome of one listing attempt."""
    ok: bool
    message: str = ""                 # listing id / "offer 123" on success, error text on failure
    url: Optional[str] = None
    listing_id: Optional[str] = None
    offer_id: Optional[str] = None
    published: bool = False


class ListingService:
    """Creates eBay listings. One job at a time per client."""

    def __init__(self, ebay, settings, db=None):
        self.ebay = ebay
        self.settings = settings
        self.db = db

    @property
    def publish(self):
        return bool(self.settings.get("publish_immediately", True))

    def run(self, job: ListingJob, log=print) -> ListingResult:
        """Upload photos, save the inventory item and offer, and publish. Never raises: failures
        are returned as ``ListingResult(ok=False, message=...)``."""
        try:
            return self._list(job, log)
        except Exception as exc:  # noqa: BLE001 - every failure is reported to the user
            log(f"[eBay] ✖ {exc}")
            return ListingResult(ok=False, message=str(exc))

    def _list(self, job, log):
        tpl = job.template
        image_urls = []
        for i, path in enumerate(job.photos, 1):
            log(f"[eBay] Uploading photo {i}/{len(job.photos)}: {os.path.basename(path)}")
            image_urls.append(self.ebay.upload_image(path))
        log(f"[eBay] Saving inventory item {job.sku}")
        self.ebay.put_inventory_item(job.sku, build_inventory_item(tpl, job.rendered, image_urls))
        offer_id = str(self.ebay.create_or_update_offer(build_offer(tpl, job.sku, job.rendered, job.price)))
        log(f"[eBay] Offer {offer_id} saved")
        result = ListingResult(ok=True, message=f"offer {offer_id}", offer_id=offer_id)
        if self.publish:
            log("[eBay] Publishing…")
            listing_id = str(self.ebay.publish(offer_id))
            result.listing_id, result.message, result.published = listing_id, listing_id, True
            result.url = self.ebay.listing_url(listing_id)
        return result

    # ---- database
    def result_fields(self, result: ListingResult):
        """Items Database columns for a successful listing."""
        fields = {"offer_id": result.offer_id, "status": "active" if result.published else "unpublished",
                  "environment": self.settings.get("ebay_env")}
        if result.listing_id:
            fields.update(listing_id=result.listing_id, listing_url=result.url)
        return fields

    def record(self, job: ListingJob, result: Optional[ListingResult] = None, queued=False):
        """Add the item to the Items Database. ``queued=True``: it was added to the queue instead of listed.
        Returns the row id, or None if it was neither listed nor queued."""
        if self.db is None or not (queued or (result and result.ok)):
            return None
        rec = {"template_id": job.template.get("id"), "template_name": job.template.get("name"),
               "title": job.title, "sku": job.sku, "photo": job.photos[0] if job.photos else "",
               "variables": json.dumps(job.values)}
        try:
            rec["price"] = parse_price(job.price)
        except ValueError:
            pass
        if queued:
            rec["status"] = "queued"
        else:
            rec.update(self.result_fields(result))
        return self.db.add(**rec)
