"""Listing queue: save listings now, bulk-list them on eBay later.

By default the List Item tab doesn't upload anything when you click Create. It saves the item to
the Items Database as **queued**, which is instant, and *List queued* in the Items Database sends
queued items in one batch. (Choose *List right away* on the List Item tab to skip the queue.)
Listing also queues automatically while eBay isn't connected, e.g. while your developer account is
waiting for approval.

What's stored per item (``queue`` column, JSON):

* ``rendered`` - the title, description, condition description and item specifics with the
  variables filled in, exactly as they'll be listed (editable with *Edit queued listing…*);
* ``values``, ``price``, ``sku``;
* ``photos`` - **copies** in ``queued_photos/item_<id>/``, so moving or deleting the originals
  doesn't matter;
* ``template_id`` plus a ``template`` snapshot;
* ``overrides`` - settings changed for this item on the List Item form (package size, condition...).

At batch time the item uses its template **as it is then** (category, condition, package size,
policies, location), so you can finish a template's eBay settings after queueing, with the item's
own ``overrides`` on top. The snapshot is only used if the template has since been deleted.

Batch rules (:class:`BatchLister`): nothing is attempted while eBay isn't connected; items that sold
in the meantime are skipped and taken out of the queue; failures stay queued with the error shown
(``queue_error``); successful items get their listing link, and their photo copies are deleted.
"""

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import List

from ebay_lister.config import QUEUED_PHOTO_DIR
from ebay_lister.core.text import parse_price
from ebay_lister.core.validation import validate_listing
from ebay_lister.services.listing import ListingJob

EDITABLE = ("title", "description", "condition_description", "aspects")


@dataclass
class BatchReport:
    """Outcome of one batch run (shown to the user)."""
    listed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)   # sold in the meantime
    failed: List[str] = field(default_factory=list)


class ListingQueue:
    """Stores queued listings on Items Database rows."""

    def __init__(self, db, photo_dir=QUEUED_PHOTO_DIR):
        self.db = db
        self.photo_dir = photo_dir

    # ---- adding / reading
    def add(self, item_id, job: ListingJob):
        """Queue ``job`` on database row ``item_id``. Photos are copied."""
        data = {"rendered": dict(job.rendered), "values": dict(job.values), "price": job.price, "sku": job.sku,
                "photos": self._copy_photos(item_id, job.photos), "template_id": job.template.get("id"),
                "template": job.template, "overrides": dict(job.overrides)}
        self.db.update(item_id, queue=json.dumps(data), queued_at=time.time(), queue_error=None, status="queued")

    @staticmethod
    def data(item):
        """The stored queue entry of an item (dict), or None."""
        raw = item.get("queue") if item else None
        return json.loads(raw) if raw else None

    def pending(self):
        """Queued items, oldest first."""
        items = [i for i in self.db.all() if i.get("queue")]
        return sorted(items, key=lambda i: i.get("queued_at") or i.get("created_at") or 0)

    def count(self):
        return len(self.pending())

    def update(self, item_id, price=None, **rendered_changes):
        """Edit a queued listing's text (title, description, condition_description, aspects) or price."""
        item = self.db.get(item_id)
        data = self.data(item)
        if data is None:
            raise KeyError(f"Item {item_id} is not queued.")
        data["rendered"].update({k: v for k, v in rendered_changes.items() if k in EDITABLE})
        upd = {"queue_error": None}
        if price is not None:
            data["price"] = price
            try:
                upd["price"] = parse_price(price)
            except ValueError:
                pass
        if "title" in rendered_changes:
            upd["title"] = rendered_changes["title"]
        upd["queue"] = json.dumps(data)
        self.db.update(item_id, **upd)

    def remove(self, item_id):
        """Take an item out of the queue (it stays in the database) and delete its photo copies."""
        item = self.db.get(item_id)
        if not item:
            return
        upd = {"queue": None, "queue_error": None, "queued_at": None}
        if item.get("status") == "queued":
            upd["status"] = None
        self.db.update(item_id, **upd)
        shutil.rmtree(self._folder(item_id), ignore_errors=True)

    def job_for(self, item, templates) -> ListingJob:
        """Rebuild the ListingJob: stored content + the item's template as it is now (``templates`` is
        a :class:`~ebay_lister.services.templates.TemplateStore`)."""
        data = self.data(item)
        template = (templates.get(data.get("template_id")) if templates else None) or data.get("template") or {}
        return ListingJob(template=template, rendered=data["rendered"], price=data.get("price", ""),
                          photos=data.get("photos", []), sku=data.get("sku", ""), values=data.get("values", {}),
                          overrides=data.get("overrides") or {})

    # ---- photos
    def _folder(self, item_id):
        return os.path.join(self.photo_dir, f"item_{item_id}")

    def _copy_photos(self, item_id, photos):
        folder = self._folder(item_id)
        os.makedirs(folder, exist_ok=True)
        copies = []
        for i, src in enumerate(photos, 1):
            dest = os.path.join(folder, f"{i:02d}_{os.path.basename(src)}")
            if os.path.abspath(src) == os.path.abspath(dest):
                copies.append(dest)
                continue
            try:
                shutil.copy2(src, dest)
                copies.append(dest)
            except OSError:
                copies.append(src)  # keep the original path; the batch reports it if it's gone
        return copies

    def delete_photo_copies(self, item_id):
        shutil.rmtree(self._folder(item_id), ignore_errors=True)


class BatchLister:
    """Lists queued items on eBay. Run :meth:`run` from a background thread."""

    def __init__(self, queue: ListingQueue, service, templates):
        self.queue = queue
        self.service = service        # ListingService (eBay client + publish setting)
        self.templates = templates    # TemplateStore

    @staticmethod
    def problems(job: ListingJob):
        """Everything that would make this item fail, checked before anything is uploaded."""
        errs = validate_listing(job.settings, job.rendered, job.values, job.price, job.photos, job.sku,
                                check_values=False)
        if not job.sku:
            errs.append("missing SKU")
        missing = [p for p in job.photos if not os.path.isfile(p)]
        if missing:
            errs.append(f"{len(missing)} photo file(s) missing")
        return errs

    def _items(self, item_ids):
        items = self.queue.pending()
        if item_ids is not None:
            wanted = set(item_ids)
            items = [i for i in items if i["id"] in wanted]
        return items

    def run(self, log=print, item_ids=None) -> BatchReport:
        report = BatchReport()
        items = self._items(item_ids)
        for n, item in enumerate(items, 1):
            name = (item.get("title") or item.get("sku") or f"item {item['id']}")[:60]
            if item.get("sold"):
                report.skipped.append(f"{name} - already sold on {item.get('sold_on') or 'another site'}")
                self.queue.remove(item["id"])
                continue
            job = self.queue.job_for(item, self.templates)
            problems = self.problems(job)
            if problems:
                self._fail(item, report, name, "; ".join(problems))
                continue
            log(f"[Batch] {n}/{len(items)}: {name}")
            result = self.service.run(job, log=log)
            if not result.ok:
                self._fail(item, report, name, result.message)
                continue
            self.queue.db.update(item["id"], queue=None, queue_error=None, queued_at=None,
                                 template_name=job.template.get("name"), **self.service.result_fields(result))
            self.queue.delete_photo_copies(item["id"])
            report.listed.append(f"{name} - {'listed' if result.published else 'offer created'} "
                                 f"({result.listing_id or result.offer_id})")
        return report

    def _fail(self, item, report, name, msg):
        self.queue.db.update(item["id"], queue_error=msg)
        report.failed.append(f"{name} - {msg}")
