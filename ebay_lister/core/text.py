"""Pure text helpers: item-specific parsing, SKUs, prices and HTML descriptions.

Nothing in this module touches the network or the UI, so it is easy to unit-test.
Template variables (``{NAME}``) live in :mod:`ebay_lister.core.variables`.
"""

import html
import re
import time


def parse_aspects(text):
    """Item specifics: 'Name: value | value2' per line -> {'Name': ['value', 'value2']}.

    Lines without a colon, or without a value (e.g. an empty variable), are skipped."""
    out = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        vals = [x.strip() for x in v.split("|") if x.strip()]
        if k.strip() and vals:
            out[k.strip()] = vals
    return out


def aspect_lines(text):
    """Item specifics text -> {'Name': 'raw value text'} (values unparsed, so {VARIABLES} survive)."""
    out = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip():
                out[k.strip()] = v.strip()
    return out


def merge_aspects(text, changes):
    """Apply ``changes`` ({'Name': 'value'}) to item specifics text: replace a line with the same name
    (case-insensitive) in place, append new names at the end, and remove a line whose new value is ''.
    Other lines, including comments and blank lines, are kept as they are."""
    pending = {k.strip().lower(): (k.strip(), (v or "").strip()) for k, v in changes.items() if k.strip()}
    lines = []
    for line in (text or "").splitlines():
        key = line.split(":", 1)[0].strip().lower() if ":" in line else None
        if key in pending:
            name, value = pending.pop(key)
            if value:
                lines.append(f"{line.split(':', 1)[0].strip()}: {value}")
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    lines += [f"{name}: {value}" for name, value in pending.values() if value]
    return "\n".join(lines)


def make_sku(hint=""):
    """Unique SKU from a hint (e.g. the title) and the current time, e.g. 'SONYWALKMAN-261125203015'."""
    clean = re.sub(r"[^A-Za-z0-9]+", "", hint or "").upper()[:16] or "ITEM"
    return f"{clean}-{time.strftime('%y%m%d%H%M%S')}"


def parse_price(p):
    """'$1,089.50' -> 1089.5. Raises ValueError if it isn't a number."""
    return float(str(p).replace("$", "").replace(",", "").strip())


def text_to_html(text):
    """Plain text -> simple HTML for eBay: blank lines become paragraphs, single newlines <br>."""
    paras = [p.strip() for p in (text or "").strip().split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paras)
