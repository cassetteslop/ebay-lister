"""Matching your saved default names ("30 days returns", "USPS Ground Advantage"...) to the real
business policies and locations returned by eBay."""

import difflib
import re


def best_match(target, labels):
    """Pick the label that best matches a default name (case-insensitive / fuzzy)."""
    if not labels or not target:
        return None
    t = target.lower().strip()
    low = {l.lower().strip(): l for l in labels}
    if t in low:
        return low[t]
    digits = re.findall(r"\d+", t)  # e.g. "30 days": only consider labels mentioning 30
    if digits:
        same = [l for l in labels if all(re.search(rf"\b{d}\b", l) for d in digits)]
        if same:
            labels = same
            low = {l.lower().strip(): l for l in labels}
            if len(same) == 1:
                return same[0]
    for l in labels:
        if t in l.lower():
            return l
    m = difflib.get_close_matches(t, list(low), n=1, cutoff=0.5)
    if m:
        return low[m[0]]
    inside = sorted((l for l in labels if len(l) >= 6 and l.lower() in t), key=len, reverse=True)
    if inside:
        return inside[0]
    # last resort: most shared words
    words = set(re.findall(r"\w+", t))
    scored = sorted(labels, key=lambda l: len(words & set(re.findall(r"\w+", l.lower()))), reverse=True)
    return scored[0] if words & set(re.findall(r"\w+", scored[0].lower())) else None
