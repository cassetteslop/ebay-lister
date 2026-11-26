"""Tests for the services layer (templates, listing, queue, sync, database) with a fake eBay client."""

import json
import os
import tempfile
import time
import unittest

from ebay_lister.api.http import ApiError
from ebay_lister.core import variables as V
from ebay_lister.services.database import ItemsDB
from ebay_lister.services.listing import ListingJob, ListingService
from ebay_lister.services.listing_queue import BatchLister, ListingQueue
from ebay_lister.services.sync import SalesSync
from ebay_lister.services.templates import TemplateError, TemplateStore
from tests.test_core import walkman_template


class FakeEbay:
    """Stands in for EbayClient: records what was sent, returns canned answers."""

    def __init__(self, connected=True, fail=None):
        self._connected, self.fail = connected, fail
        self.images, self.offers = [], []

    def connected(self):
        return self._connected

    def upload_image(self, path):
        self.images.append(path)
        return "https://i.ebayimg.com/" + os.path.basename(path)

    def put_inventory_item(self, sku, item):
        self.item = item

    def create_or_update_offer(self, offer):
        if self.fail:
            raise ApiError(self.fail)
        self.offers.append(offer)
        return "22"

    def publish(self, offer_id):
        return "922"

    def listing_url(self, listing_id):
        return f"https://www.ebay.com/itm/{listing_id}"

    def get_offer(self, offer_id):
        if offer_id == "404":
            raise ApiError("eBay HTTP 404 (GET /offer/404): not found")
        return {"status": "PUBLISHED", "listing": {"listingId": "922", "listingStatus": "ACTIVE"}}

    def orders_since(self, since_ts):
        return [{"creationDate": "2026-11-18T10:00:00.000Z", "totalMarketplaceFee": {"value": "12.40"},
                 "lineItems": [{"legacyItemId": "922", "sku": "B", "lineItemCost": {"value": "95.00"},
                                "deliveryCost": {"shippingCost": {"value": "0.0"}}}]}]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = ItemsDB(os.path.join(self.tmp, "items.db"))
        self.addCleanup(self.db.close)
        self.templates = TemplateStore(os.path.join(self.tmp, "templates.json"),
                                       photo_dir=os.path.join(self.tmp, "template_photos"))
        self.settings = {"publish_immediately": True, "ebay_env": "production"}
        self.photos = []
        for name in ("front.jpg", "back.jpg"):
            path = os.path.join(self.tmp, name)
            with open(path, "wb") as f:
                f.write(b"\xff\xd8fake-jpeg")
            self.photos.append(path)

    def job(self, template=None, **values):
        t = template or walkman_template()
        values = values or {"MODEL": "WM-2", "CONDITION_NOTES": "Great"}
        return ListingJob(template=t, rendered=V.render_listing(t, values), price="89.99", photos=list(self.photos),
                          sku="SKU-A", values=values)


class TemplateStoreTests(Base):
    def test_starters_and_persistence(self):
        self.assertEqual(self.templates.names(), ["Sony Walkman", "Blank template"])
        reopened = TemplateStore(self.templates.path, photo_dir=self.templates.photo_dir)
        self.assertEqual([t["id"] for t in reopened.all()], [t["id"] for t in self.templates.all()])

    def test_create_duplicate_rename_delete(self):
        base = self.templates.by_name("Sony Walkman")
        copy = self.templates.create(self.templates.unique_name(base["name"]), base_id=base["id"])
        self.assertEqual(copy["name"], "Sony Walkman (copy)")
        self.assertEqual(copy["title"], base["title"])
        self.assertNotEqual(copy["id"], base["id"])
        self.assertEqual(self.templates.unique_name("Sony Walkman"), "Sony Walkman (copy 2)")
        with self.assertRaises(TemplateError):
            self.templates.create("sony walkman")                   # names are unique, case-insensitive
        self.templates.rename(copy["id"], "Discman")
        self.assertIsNotNone(self.templates.by_name("Discman"))
        blank = self.templates.create("Fresh")
        self.assertEqual(blank["variables"], [])
        for t in self.templates.all()[1:]:
            self.templates.delete(t["id"])
        with self.assertRaises(TemplateError):
            self.templates.delete(self.templates.first()["id"])     # the last one stays

    def test_duplicate_copies_standard_photos(self):
        base = self.templates.first()
        base["fixed_photos"] = [{"path": self.templates.copy_photo_in(self.photos[0], base["id"]), "position": 2}]
        self.templates.save(base)
        copy = self.templates.create("Copy", base_id=base["id"])
        self.assertNotEqual(copy["fixed_photos"][0]["path"], base["fixed_photos"][0]["path"])
        self.templates.delete(base["id"])                            # deletes only the original's photo
        self.assertTrue(os.path.isfile(copy["fixed_photos"][0]["path"]))

    def test_old_files_get_new_keys(self):
        t = self.templates.first()
        t.pop("best_offer")
        saved = self.templates.save(t)
        self.assertIn("best_offer", saved)


class ListingTests(Base):
    def test_list_now_and_record(self):
        ebay = FakeEbay()
        svc = ListingService(ebay, self.settings, self.db)
        job = self.job()
        result = svc.run(job, log=lambda m: None)
        self.assertTrue(result.ok and result.published)
        self.assertEqual(ebay.images, self.photos)
        row = self.db.get(svc.record(job, result))
        self.assertEqual((row["status"], row["listing_id"], row["template_name"]), ("active", "922", "Sony Walkman"))
        self.assertEqual(json.loads(row["variables"])["MODEL"], "WM-2")
        self.assertTrue(ItemsDB.is_active(row))

    def test_unpublished_and_failure(self):
        self.settings["publish_immediately"] = False
        svc = ListingService(FakeEbay(), self.settings, self.db)
        row = self.db.get(svc.record(self.job(), svc.run(self.job(), log=lambda m: None)))
        self.assertEqual(row["status"], "unpublished")
        bad = ListingService(FakeEbay(fail="eBay HTTP 400: Brand required"), self.settings, self.db)
        result = bad.run(self.job(), log=lambda m: None)
        self.assertFalse(result.ok)
        self.assertIsNone(bad.record(self.job(), result))


class QueueTests(Base):
    def queue_one(self, template=None, **values):
        svc = ListingService(FakeEbay(connected=False), self.settings, self.db)
        job = self.job(template, **values)
        item_id = svc.record(job, queued=True)
        ListingQueue(self.db, os.path.join(self.tmp, "queued")).add(item_id, job)
        return item_id

    def lister(self, ebay=None):
        queue = ListingQueue(self.db, os.path.join(self.tmp, "queued"))
        return queue, BatchLister(queue, ListingService(ebay or FakeEbay(), self.settings, self.db), self.templates)

    def test_queue_and_batch(self):
        tpl = self.templates.first()
        tpl.update(fulfillment_policy_id="F", payment_policy_id="P", return_policy_id="R", location_key="L")
        self.templates.save(tpl)
        item_id = self.queue_one(template=self.templates.first())
        row = self.db.get(item_id)
        self.assertEqual(row["status"], "queued")
        data = ListingQueue.data(row)
        os.remove(self.photos[0])                                    # originals can go away
        self.assertTrue(all(os.path.isfile(p) for p in data["photos"]))
        queue, lister = self.lister()
        queue.update(item_id, title="Edited title", price="99")
        ebay = FakeEbay()
        queue, lister = self.lister(ebay)
        report = lister.run(log=lambda m: None)
        self.assertEqual(len(report.listed), 1)
        row = self.db.get(item_id)
        self.assertEqual((row["status"], row["listing_id"], row["queue"]), ("active", "922", None))
        self.assertEqual(ebay.item["product"]["title"], "Edited title")
        self.assertEqual(ebay.offers[0]["pricingSummary"]["price"]["value"], "99.00")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "queued", f"item_{item_id}")))

    def test_batch_uses_template_as_it_is_now(self):
        tpl = self.templates.first()
        item_id = self.queue_one(template=tpl)                       # queued before policies were set
        queue, lister = self.lister()
        self.assertIn("policy", lister.run(log=lambda m: None).failed[0])
        tpl.update(fulfillment_policy_id="NEW", payment_policy_id="P", return_policy_id="R", location_key="L")
        self.templates.save(tpl)
        ebay = FakeEbay()
        queue, lister = self.lister(ebay)
        lister.run(log=lambda m: None)
        self.assertEqual(ebay.offers[0]["listingPolicies"]["fulfillmentPolicyId"], "NEW")
        self.assertIsNone(self.db.get(item_id)["queue_error"])

    def test_deleted_template_falls_back_to_snapshot(self):
        tpl = self.templates.create("Temp", base_id=self.templates.first()["id"])
        tpl.update(fulfillment_policy_id="F", payment_policy_id="P", return_policy_id="R", location_key="L")
        tpl = self.templates.save(tpl)
        item_id = self.queue_one(template=tpl)
        self.templates.delete(tpl["id"])
        queue, lister = self.lister()
        self.assertEqual(len(lister.run(log=lambda m: None).listed), 1)
        self.assertEqual(self.db.get(item_id)["status"], "active")

    def test_failures_stay_queued_and_sold_items_are_skipped(self):
        a = self.queue_one(template=walkman_template())
        b = self.queue_one(template=walkman_template())
        self.db.update(b, sold=1, sold_on="Other")
        queue, lister = self.lister(FakeEbay(fail="eBay HTTP 400: Brand required"))
        report = lister.run(log=lambda m: None)
        self.assertEqual((len(report.failed), len(report.skipped)), (1, 1))
        self.assertIn("Brand required", self.db.get(a)["queue_error"])
        self.assertIsNone(self.db.get(b)["queue"])

    def test_list_selected_and_remove(self):
        a = self.queue_one(template=walkman_template())
        b = self.queue_one(template=walkman_template())
        queue, lister = self.lister()
        lister.run(log=lambda m: None, item_ids=[b])
        self.assertTrue(self.db.get(a)["queue"])
        self.assertIsNone(self.db.get(b)["queue"])
        queue.remove(a)
        self.assertEqual((self.db.get(a)["queue"], self.db.get(a)["status"]), (None, None))


class SyncTests(Base):
    def test_sync(self):
        a = self.db.add(title="Item B", sku="B", offer_id="22", status="active", cost=20.0, created_at=time.time())
        gone = self.db.add(title="Gone", offer_id="404", status="active")
        manual = self.db.add(title="Manual", offer_id="23", status="active", profit=50.0, sku="C")
        report = SalesSync(self.db, FakeEbay()).run(log=lambda m: None)
        a = self.db.get(a)
        self.assertEqual((a["sold"], a["sold_price"], a["fees"], a["profit"]), (1, 95.0, 12.4, 62.6))
        self.assertEqual(self.db.get(gone)["status"], "deleted")
        self.assertEqual(self.db.get(manual)["profit"], 50.0)
        self.assertEqual(len(report.sold), 1)

    def test_not_connected(self):
        self.db.add(title="X", offer_id="22", status="active")
        report = SalesSync(self.db, FakeEbay(connected=False)).run(log=lambda m: None)
        self.assertTrue(report.errors)


class DatabaseTests(Base):
    def test_crud_and_migration(self):
        i = self.db.add(title="T", price=10.0, bogus="ignored")
        self.db.update(i, sold=1, sold_on="Other")
        self.assertEqual(self.db.get(i)["sold_on"], "Other")
        ItemsDB(os.path.join(self.tmp, "items.db")).close()        # re-opening runs the migration again
        self.db.delete(i)
        self.assertIsNone(self.db.get(i))

    def test_no_etsy_columns(self):
        from ebay_lister.services.database import ITEM_FIELDS
        self.assertFalse([c for c in ITEM_FIELDS if "etsy" in c])


if __name__ == "__main__":
    unittest.main()
