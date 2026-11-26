"""Builders that turn a template + rendered listing into the exact eBay request bodies.

* :func:`build_inventory_item` -> Inventory API createOrReplaceInventoryItem (JSON)
* :func:`build_offer`          -> Inventory API createOffer / updateOffer (JSON)

``rendered`` is the output of :func:`ebay_lister.core.variables.render_listing`: the template's
title, description, condition description and item specifics with ``{VARIABLES}`` filled in.
"""

from ebay_lister.config import CARD_CONDITION_DESCRIPTOR, EBAY_MARKETPLACE, MAX_CONDITION_DESCRIPTION
from ebay_lister.core.text import parse_aspects, parse_price, text_to_html


def package_weight_oz(tpl):
    return round(float(tpl.get("weight_lb") or 0) * 16 + float(tpl.get("weight_oz") or 0), 2)


def build_inventory_item(tpl, rendered, image_urls):
    """Condition, package size, title, HTML description, item specifics and the uploaded image URLs."""
    item = {
        "availability": {"shipToLocationAvailability": {"quantity": int(tpl["quantity"])}},
        "condition": tpl["condition"],
        "packageWeightAndSize": {
            "dimensions": {"length": float(tpl["length"]), "width": float(tpl["width"]),
                           "height": float(tpl["height"]), "unit": "INCH"},
            "weight": {"value": package_weight_oz(tpl), "unit": "OUNCE"},
        },
        "product": {
            "title": rendered["title"].strip(),
            "description": text_to_html(rendered["description"]),
            "aspects": parse_aspects(rendered.get("aspects", "")),
            "imageUrls": list(image_urls),
        },
    }
    notes = (rendered.get("condition_description") or "").strip()
    if notes and tpl["condition"] != "NEW":  # eBay ignores condition descriptions on new items
        item["conditionDescription"] = notes[:MAX_CONDITION_DESCRIPTION]
    if tpl.get("card_condition"):  # ungraded trading cards: eBay requires the card's condition
        item["conditionDescriptors"] = [{"name": CARD_CONDITION_DESCRIPTOR, "values": [str(tpl["card_condition"])]}]
    return item


def build_offer(tpl, sku, rendered, price):
    """Buy It Now, Good 'Til Cancelled: price, category, business policies and ship-from location."""
    policies = {
        "fulfillmentPolicyId": str(tpl["fulfillment_policy_id"]),
        "paymentPolicyId": str(tpl["payment_policy_id"]),
        "returnPolicyId": str(tpl["return_policy_id"]),
    }
    if tpl.get("best_offer"):
        policies["bestOfferTerms"] = {"bestOfferEnabled": True}
    return {
        "sku": sku,
        "marketplaceId": EBAY_MARKETPLACE,
        "format": "FIXED_PRICE",
        "availableQuantity": int(tpl["quantity"]),
        "categoryId": str(tpl["category_id"]),
        "listingDescription": text_to_html(rendered["description"]),
        "listingDuration": "GTC",
        "listingPolicies": policies,
        "pricingSummary": {"price": {"value": f"{parse_price(price):.2f}", "currency": "USD"}},
        "merchantLocationKey": tpl["location_key"],
    }
