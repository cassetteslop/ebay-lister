"""Validation rules for templates and listings.

Every function returns a list of human-readable error strings (empty list = valid); none raise.

Template checks come in three parts:

* **content** - name, title, description and variables (the text patterns).
* **settings** - quantity and package size.
* **account** - category, business policies and ship-from location, which need an eBay connection
  to fill in. Skipped when a listing is only added to the queue (``account=False``), and checked
  at batch time.
"""

import re

from ebay_lister.config import MAX_CONDITION_DESCRIPTION, MAX_PHOTOS, MAX_PRICE, MAX_SKU_LEN, MAX_TITLE_LEN, MIN_PRICE
from ebay_lister.core import variables as V
from ebay_lister.core.text import parse_price

FIELD_LABELS = {"title": "title", "description": "description", "condition_description": "condition description",
                "aspects": "item specifics"}


def _num(value, name, errs, minimum=0.0, integer=False, allow_zero=True):
    try:
        x = int(value) if integer else float(value)
    except (TypeError, ValueError):
        errs.append(f"{name} must be a {'whole ' if integer else ''}number.")
        return None
    if x < minimum or (not allow_zero and x == 0):
        errs.append(f"{name} must be {'greater than' if not allow_zero else 'at least'} {minimum}.")
        return None
    return x


def validate_variables(variables):
    """Variable definitions: valid, unique names."""
    errs, seen = [], set()
    for v in variables:
        name = v.get("name", "")
        if not V.is_valid_name(name):
            errs.append(f"Variable '{name}': use letters, digits and _ only, starting with a letter (e.g. MODEL).")
        if name in seen:
            errs.append(f"Variable '{name}' is defined twice.")
        seen.add(name)
    return errs


def validate_title(title):
    errs = []
    if not title.strip():
        errs.append("Title is required.")
    if len(title) > MAX_TITLE_LEN:
        errs.append(f"Title is {len(title)} characters (eBay's maximum is {MAX_TITLE_LEN}).")
    return errs


def validate_template_content(tpl):
    """Checks that don't need an eBay connection."""
    errs = []
    if not str(tpl.get("name", "")).strip():
        errs.append("Template name is required.")
    if not tpl.get("title", "").strip():
        errs.append("Template title is empty.")
    if not tpl.get("description", "").strip():
        errs.append("Template description is empty.")
    errs += validate_variables(tpl.get("variables", []))
    for field, name in V.undefined(tpl):
        errs.append(f"The {FIELD_LABELS[field]} uses {{{name}}} but there's no variable named {name}.")
    return errs + validate_template_settings(tpl)


def validate_template_settings(tpl):
    """Quantity and package size (needed to list, no eBay connection needed to fill in)."""
    errs = []
    q = _num(tpl.get("quantity"), "Quantity", errs, 1, integer=True)
    if q is not None and q > 999:
        errs.append("Quantity must be 999 or less.")
    lb = _num(tpl.get("weight_lb"), "Weight (lbs)", errs, 0)
    oz = _num(tpl.get("weight_oz"), "Weight (oz)", errs, 0)
    if lb is not None and oz is not None and lb * 16 + oz <= 0:
        errs.append("Package weight must be greater than 0.")
    for k in ("length", "width", "height"):
        _num(tpl.get(k), f"Package {k}", errs, 0, allow_zero=False)
    return errs


def validate_template_account(tpl):
    """Settings that come from your eBay account (filled in by 'Load policies & locations')."""
    errs = []
    if not str(tpl.get("category_id") or "").isdigit():
        errs.append("eBay category ID must be a number (use Suggest… on the Templates tab).")
    for key, label in (("fulfillment_policy_id", "shipping policy"), ("payment_policy_id", "payment policy"),
                       ("return_policy_id", "return policy")):
        if not tpl.get(key):
            errs.append(f"No {label} chosen - load policies from eBay on the Templates tab.")
    if not tpl.get("location_key"):
        errs.append("No ship-from location chosen - pick or create one on the Templates tab.")
    return errs


def validate_template(tpl, account=True):
    return validate_template_content(tpl) + (validate_template_account(tpl) if account else [])


def validate_listing(tpl, rendered, values, price, photos, sku, account=True, check_values=True):
    """Everything needed before listing (or queueing) one item.

    ``rendered``: :func:`~ebay_lister.core.variables.render_listing` output; ``values``: the variable
    values typed on the List Item tab; ``account=False`` skips eBay-account checks (queueing);
    ``check_values=False`` skips the required-variable check (queued items: their text is already
    filled in, and the template's variables may have changed since)."""
    errs = []
    for name in V.required(tpl) if check_values else []:
        if not str(values.get(name, "")).strip():
            errs.append(f"Fill in {name} (it's used in the title).")
    errs += validate_title(rendered["title"])
    if not rendered["description"].strip():
        errs.append("Description is empty.")
    for field in V.RENDERED_FIELDS:
        left = [n for n in V.placeholders(rendered.get(field, ""))]
        if left:
            errs.append(f"The {FIELD_LABELS[field]} still contains " + ", ".join("{" + n + "}" for n in left) + ".")
    if len(rendered.get("condition_description", "")) > MAX_CONDITION_DESCRIPTION:
        errs.append(f"Condition description is over {MAX_CONDITION_DESCRIPTION} characters.")
    try:
        p = parse_price(price)
        if p < MIN_PRICE or p > MAX_PRICE:
            errs.append(f"Price must be between ${MIN_PRICE:.2f} and ${MAX_PRICE:,.0f}.")
    except ValueError:
        errs.append("Price is required (e.g. 89.99).")
    if not photos:
        errs.append("Add at least one photo.")
    if len(photos) > MAX_PHOTOS:
        errs.append(f"eBay allows at most {MAX_PHOTOS} photos.")
    if sku and not re.match(r"^[A-Za-z0-9._\-/ ]+$", sku):
        errs.append("SKU may only contain letters, numbers, spaces and . _ - /")
    if sku and len(sku) > MAX_SKU_LEN:
        errs.append(f"SKU is {len(sku)} characters (eBay's maximum is {MAX_SKU_LEN}).")
    # template problems, de-duplicated (only the account part for queued items: their text is final)
    template_errs = (validate_template(tpl, account=account) if check_values
                     else validate_template_settings(tpl) + validate_template_account(tpl))
    for e in template_errs:
        if e not in errs:
            errs.append(e)
    return errs
