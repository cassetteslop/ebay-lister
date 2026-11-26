"""Custom template variables: ``{VARIABLE_NAME}`` placeholders.

Each template defines its own variables (name, default value, single- or multi-line). On the List
Item tab every variable gets a text box, and its value replaces ``{NAME}`` in the template's title,
description, condition description and item specifics.

Rules

* Names start with a letter or underscore and contain only letters, digits and underscores
  (``MODEL``, ``CONDITION_NOTES``, ``Color2``). They are case-sensitive; UPPER_CASE is recommended.
* ``{{`` and ``}}`` produce literal braces.
* A ``{NAME}`` with no matching variable is left as written, so validation can point it out.
* Variables used in the **title** must be filled in; elsewhere they may be left blank.

Example::

    >>> render("Sony Walkman {MODEL} - {{boxed}}", {"MODEL": "WM-2"})
    'Sony Walkman WM-2 - {boxed}'
"""

import re

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TOKEN_RE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")
RENDERED_FIELDS = ("title", "description", "condition_description", "aspects")


def is_valid_name(name):
    return bool(NAME_RE.match(name or ""))


def placeholders(text):
    """Variable names used in ``text``, in order of first appearance (escaped braces ignored)."""
    seen = []
    for m in _TOKEN_RE.finditer(text or ""):
        name = m.group(1)
        if name and name not in seen:
            seen.append(name)
    return seen


def render(text, values):
    """Replace ``{NAME}`` with ``values[NAME]``; unknown names stay as ``{NAME}``; ``{{``/``}}`` -> ``{``/``}``."""
    def sub(m):
        token = m.group(0)
        if token == "{{":
            return "{"
        if token == "}}":
            return "}"
        name = m.group(1)
        return str(values[name]).strip() if name in values else token
    return _TOKEN_RE.sub(sub, text or "")


def variable_names(template):
    return [v["name"] for v in template.get("variables", [])]


def defaults(template):
    """{name: default value} for a template's variables."""
    return {v["name"]: v.get("default", "") for v in template.get("variables", [])}


def used_in_template(template):
    """{field: [names]} for every rendered field of a template."""
    return {f: placeholders(template.get(f, "")) for f in RENDERED_FIELDS}


def undefined(template):
    """Placeholders used in the template that aren't defined as variables: [(field, name)]."""
    names = set(variable_names(template))
    return [(f, n) for f, used in used_in_template(template).items() for n in used if n not in names]


def required(template):
    """Variables that must be filled in on the List Item tab (the ones used in the title)."""
    names = set(variable_names(template))
    return [n for n in placeholders(template.get("title", "")) if n in names]


def render_listing(template, values):
    """Rendered text fields of a listing: {"title", "description", "condition_description", "aspects"}."""
    merged = dict(defaults(template))
    merged.update({k: v for k, v in values.items() if v is not None})
    out = {f: render(template.get(f, ""), merged) for f in RENDERED_FIELDS}
    out["title"] = " ".join(out["title"].split())  # empty optional variables can leave double spaces
    return out
