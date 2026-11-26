"""Unit tests for the pure logic in ebay_lister.core (no network, no Tk).

Run all tests with:  python -m unittest discover -s tests -t .
"""

import os
import tempfile
import unittest

from ebay_lister.config import STARTER_TEMPLATES, TEMPLATE_DEFAULTS
from ebay_lister.core import variables as V
from ebay_lister.core.fees import calc_profit
from ebay_lister.core.matching import best_match
from ebay_lister.core.payloads import build_inventory_item, build_offer
from ebay_lister.core.text import aspect_lines, make_sku, merge_aspects, parse_aspects, parse_price, text_to_html
from ebay_lister.core.validation import validate_listing, validate_template, validate_template_content, validate_variables

# A complete template used throughout the tests (it was the app's first starter template).
WALKMAN = dict(
    TEMPLATE_DEFAULTS,
    name="Sony Walkman",
    title="Sony Walkman {MODEL} Portable Cassette Player Vintage Tested Working",
    description=("Sony Walkman {MODEL}\n\n{CONDITION_NOTES}\n\nEvery Walkman is cleaned, tested and inspected.\n\n"
                 "Ships fast and well packed."),
    condition_description="{CONDITION_NOTES}",
    category_id="15053", category_name="Personal Cassette Players",
    aspects=("Brand: Sony\nModel: {MODEL}\nProduct Line: Walkman\nType: Portable Cassette Player\n"
             "Playable Media Format: Cassette Tape\nMPN: Does Not Apply"),
    weight_lb=0, weight_oz=15, length=8, width=6, height=4,
    variables=[{"name": "MODEL", "default": "", "multiline": False},
               {"name": "CONDITION_NOTES", "default": "", "multiline": True}])


def walkman_template(**overrides):
    """The Walkman test template with the eBay account settings filled in."""
    t = dict(WALKMAN)
    t.update(id="t_test", fulfillment_policy_id="F1", payment_policy_id="P1", return_policy_id="R1",
             location_key="home")
    t.update(overrides)
    return t


class VariableTests(unittest.TestCase):
    def test_render(self):
        self.assertEqual(V.render("Sony {MODEL} - {{boxed}}", {"MODEL": "WM-2"}), "Sony WM-2 - {boxed}")
        self.assertEqual(V.render("{UNKNOWN} stays", {}), "{UNKNOWN} stays")
        self.assertEqual(V.render("{A}{A}", {"A": " x "}), "xx")  # values are trimmed

    def test_placeholders_and_names(self):
        self.assertEqual(V.placeholders("{B} {A} {B} {{C}}"), ["B", "A"])
        self.assertTrue(V.is_valid_name("CONDITION_NOTES"))
        self.assertFalse(V.is_valid_name("2FAST"))
        self.assertFalse(V.is_valid_name("has space"))

    def test_template_helpers(self):
        t = walkman_template()
        self.assertEqual(V.required(t), ["MODEL"])                   # only title variables are required
        self.assertEqual(V.undefined(t), [])
        t2 = dict(t, description="{MODEL} {COLOR}")
        self.assertEqual(V.undefined(t2), [("description", "COLOR")])

    def test_render_listing(self):
        r = V.render_listing(walkman_template(), {"MODEL": "WM-F2078", "CONDITION_NOTES": "New belt."})
        self.assertIn("Sony Walkman WM-F2078", r["title"])
        self.assertIn("New belt.", r["description"])
        self.assertEqual(r["condition_description"], "New belt.")
        self.assertIn("Model: WM-F2078", r["aspects"])

    def test_empty_optional_values(self):
        r = V.render_listing(dict(walkman_template(), title="Sony {MODEL} {CONDITION_NOTES} Walkman"),
                             {"MODEL": "WM-2"})
        self.assertEqual(r["title"], "Sony WM-2 Walkman")          # no double space


class ValidationTests(unittest.TestCase):
    def test_variable_definitions(self):
        self.assertEqual(validate_variables([{"name": "A"}, {"name": "B"}]), [])
        self.assertTrue(validate_variables([{"name": "A"}, {"name": "A"}]))
        self.assertTrue(validate_variables([{"name": "bad name"}]))

    def test_starter_templates_are_ready_to_queue(self):
        self.assertEqual([t["name"] for t in STARTER_TEMPLATES], ["Patch", "Pokemon card", "Blank template"])
        for t in STARTER_TEMPLATES:
            self.assertEqual(validate_template_content(dict(TEMPLATE_DEFAULTS, **t)), [], t["name"])

    def test_templates(self):
        self.assertEqual(validate_template(walkman_template()), [])
        starter = dict(WALKMAN)
        self.assertEqual(validate_template_content(starter), [])      # ready to queue before eBay is connected
        self.assertTrue(validate_template(starter))                   # ...but not to list
        errs = validate_template_content(dict(starter, description="{NOPE}"))
        self.assertTrue(any("{NOPE}" in e for e in errs))

    def test_listing(self):
        t = walkman_template()
        values = {"MODEL": "WM-2", "CONDITION_NOTES": ""}
        r = V.render_listing(t, values)
        self.assertEqual(validate_listing(t, r, values, "89.99", ["a.jpg"], "SKU-1"), [])
        values = {"MODEL": ""}
        errs = validate_listing(t, V.render_listing(t, values), values, "", [], "bad sku!")
        self.assertIn("Fill in MODEL (it's used in the title).", errs)
        self.assertTrue(any("Price" in e for e in errs))
        self.assertTrue(any("photo" in e for e in errs))
        self.assertTrue(any("SKU" in e for e in errs))
        long_title = dict(t, title="x" * 81)
        self.assertTrue(validate_listing(long_title, V.render_listing(long_title, {}), {}, "5", ["a"], "S"))

    def test_account_checks_skipped_when_queueing(self):
        t = dict(WALKMAN)
        values = {"MODEL": "WM-2"}
        r = V.render_listing(t, values)
        self.assertTrue(validate_listing(t, r, values, "10", ["a"], "S"))
        self.assertEqual(validate_listing(t, r, values, "10", ["a"], "S", account=False), [])
        # a hand-edited title (check_values=False) can still be queued without eBay settings
        self.assertEqual(validate_listing(t, dict(r, title="My own title"), {}, "10", ["a"], "S", account=False,
                                          check_values=False), [])


class PayloadTests(unittest.TestCase):
    def test_card_condition_descriptor(self):
        t = walkman_template(condition="USED_VERY_GOOD", card_condition="400015")
        item = build_inventory_item(t, V.render_listing(t, {"MODEL": "x"}), [])
        self.assertEqual(item["conditionDescriptors"], [{"name": "40001", "values": ["400015"]}])
        self.assertNotIn("conditionDescriptors", build_inventory_item(walkman_template(), V.render_listing(t, {}), []))

    def test_inventory_item_and_offer(self):
        t = walkman_template()
        r = V.render_listing(t, {"MODEL": "WM-2", "CONDITION_NOTES": "Scuffs"})
        item = build_inventory_item(t, r, ["https://x/1.jpg"])
        self.assertEqual(item["product"]["aspects"]["Model"], ["WM-2"])
        self.assertEqual(item["conditionDescription"], "Scuffs")
        self.assertEqual(item["packageWeightAndSize"]["weight"], {"value": 15.0, "unit": "OUNCE"})
        offer = build_offer(t, "SKU-1", r, "95")
        self.assertEqual(offer["pricingSummary"]["price"]["value"], "95.00")
        self.assertEqual(offer["categoryId"], "15053")
        self.assertEqual(offer["listingPolicies"]["fulfillmentPolicyId"], "F1")
        self.assertNotIn("bestOfferTerms", offer["listingPolicies"])

    def test_no_condition_description_for_new(self):
        t = walkman_template(condition="NEW")
        item = build_inventory_item(t, V.render_listing(t, {"MODEL": "x", "CONDITION_NOTES": "n"}), [])
        self.assertNotIn("conditionDescription", item)


class TextAndMatchingTests(unittest.TestCase):
    def test_merge_aspects(self):
        text = "Brand: Sony\nModel: {MODEL}\nColor: Red"
        merged = merge_aspects(text, {"color": "Blue", "Model": "{MODEL}", "Brand": "", "Size": "Large"})
        self.assertEqual(merged, "Model: {MODEL}\nColor: Blue\nSize: Large")
        self.assertEqual(aspect_lines(merged), {"Model": "{MODEL}", "Color": "Blue", "Size": "Large"})
        self.assertEqual(merge_aspects("", {"Game": "Pokemon TCG"}), "Game: Pokemon TCG")

    def test_text(self):
        self.assertEqual(parse_aspects("Brand: Sony\nColor: \nFeatures: Radio | Tape\nnot a line"),
                         {"Brand": ["Sony"], "Features": ["Radio", "Tape"]})
        self.assertEqual(parse_price("$1,089.50"), 1089.5)
        self.assertTrue(make_sku("Sony Walkman WM-2").startswith("SONYWALKMANWM2-"))
        self.assertEqual(text_to_html("Hi\nthere\n\n<b>"), "<p>Hi<br>there</p><p>&lt;b&gt;</p>")

    def test_best_match_and_profit(self):
        self.assertEqual(best_match("30 days returns", ["No returns", "Returns Accepted, 30 Days"]),
                         "Returns Accepted, 30 Days")
        self.assertEqual(calc_profit(95, 12.4, 20), 62.6)
        self.assertIsNone(calc_profit(None, 1, 1))


if __name__ == "__main__":
    unittest.main()


class UserGuideTests(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_guide_source_found_from_source_checkout(self):
        from ebay_lister.config import guide_path
        path = guide_path()
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))

    def test_guide_uses_only_characters_the_pdf_fonts_have(self):
        with open(os.path.join(self.ROOT, "docs", "USER_GUIDE.md"), encoding="utf-8") as f:
            f.read().encode("cp1252")  # raises if a character would print as a box in the PDF

    def test_frozen_app_looks_inside_the_bundle(self):
        from unittest import mock

        from ebay_lister import config
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs"))
            pdf = os.path.join(tmp, "docs", config.GUIDE_PDF)
            with mock.patch.object(config.sys, "frozen", True, create=True), \
                    mock.patch.object(config.sys, "_MEIPASS", tmp, create=True):
                self.assertIsNone(config.guide_path())
                open(pdf, "wb").close()
                self.assertEqual(config.guide_path(), pdf)
