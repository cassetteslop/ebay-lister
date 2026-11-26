"""Named listing templates, saved in ``templates.json``.

A template holds everything that's the same for a kind of item: title and description patterns
with ``{VARIABLES}``, condition, category, item specifics, package size, business policies,
ship-from location, standard photos and the variable definitions themselves (see
:data:`ebay_lister.config.TEMPLATE_DEFAULTS` for every key).

File format::

    {"version": 1, "templates": [{"id": "t_1a2b3c4d", "name": "Sony Walkman", ...}, ...]}

Templates are identified by ``id`` (stable across renames); names must be unique
(case-insensitive). The store always keeps at least one template: the starter templates are
created on first run, and the last remaining template can't be deleted.
"""

import copy
import os
import shutil
import threading
import uuid

from ebay_lister.config import (
    DEFAULT_LIST_FIELDS,
    LIST_FIELD_MODES,
    LIST_FIELDS,
    STARTER_TEMPLATES,
    TEMPLATE_DEFAULTS,
    TEMPLATE_PHOTO_DIR,
)
from ebay_lister.storage import load_json, save_json

FORMAT_VERSION = 1


class TemplateError(ValueError):
    """A template operation that can't be done (duplicate name, deleting the last template...)."""


def normalize(template):
    """Fill in any keys missing from an older file with their defaults (returns a new dict)."""
    t = copy.deepcopy(TEMPLATE_DEFAULTS)
    t.update(copy.deepcopy(template))
    t["name"] = str(t.get("name") or "").strip()
    t["variables"] = [{"name": v.get("name", ""), "default": v.get("default", ""),
                       "multiline": bool(v.get("multiline"))} for v in t.get("variables") or []]
    modes = {m for _, m in LIST_FIELD_MODES}
    fields = t.get("list_fields") if isinstance(t.get("list_fields"), dict) else {}
    t["list_fields"] = {k: fields.get(k) if fields.get(k) in modes else DEFAULT_LIST_FIELDS[k] for k, _ in LIST_FIELDS}
    return t


def new_id():
    return "t_" + uuid.uuid4().hex[:8]


class TemplateStore:
    """All templates, kept in memory and written to disk on every change."""

    def __init__(self, path, photo_dir=TEMPLATE_PHOTO_DIR):
        self.path = path
        self.photo_dir = photo_dir
        self._lock = threading.Lock()
        data = load_json(path, {"version": FORMAT_VERSION, "templates": []})
        self._templates = [normalize(t) for t in data.get("templates", []) if t.get("id")]
        if not self._templates:
            for starter in STARTER_TEMPLATES:
                self._templates.append(normalize(dict(starter, id=new_id())))
            self._save()

    # ---- reading
    def all(self):
        """Copies of every template, in creation order."""
        return [copy.deepcopy(t) for t in self._templates]

    def names(self):
        return [t["name"] for t in self._templates]

    def get(self, template_id):
        """A copy of the template with this id, or None."""
        for t in self._templates:
            if t["id"] == template_id:
                return copy.deepcopy(t)
        return None

    def first(self):
        return copy.deepcopy(self._templates[0])

    def by_name(self, name):
        for t in self._templates:
            if t["name"].lower() == (name or "").strip().lower():
                return copy.deepcopy(t)
        return None

    # ---- changing
    def unique_name(self, base):
        """'Walkman' -> 'Walkman (copy)', 'Walkman (copy 2)'... - the first name not taken."""
        taken = {n.lower() for n in self.names()}
        if base.lower() not in taken:
            return base
        for n in range(1, 1000):
            candidate = f"{base} (copy)" if n == 1 else f"{base} (copy {n})"
            if candidate.lower() not in taken:
                return candidate
        raise TemplateError("Too many copies of this template.")

    def _check_name(self, name, template_id=None):
        name = (name or "").strip()
        if not name:
            raise TemplateError("A template needs a name.")
        for t in self._templates:
            if t["id"] != template_id and t["name"].lower() == name.lower():
                raise TemplateError(f"There's already a template called '{t['name']}'.")
        return name

    def create(self, name, base_id=None):
        """New template named ``name``: a copy of template ``base_id``, or the defaults if None."""
        with self._lock:
            name = self._check_name(name)
            if base_id:
                base = self.get(base_id)
                if base is None:
                    raise TemplateError("The template to copy no longer exists.")
            else:
                base = copy.deepcopy(TEMPLATE_DEFAULTS)
            t = normalize(dict(base, id=new_id(), name=name))
            t["fixed_photos"] = [dict(fp, path=self._copy_photo(fp["path"], t["id"]))
                                 for fp in t["fixed_photos"] if fp.get("path")]
            self._templates.append(t)
            self._save()
            return copy.deepcopy(t)

    def save(self, template):
        """Insert or replace a template (matched by id). Returns the stored copy."""
        with self._lock:
            t = normalize(template)
            if not t.get("id"):
                t["id"] = new_id()
            t["name"] = self._check_name(t["name"], t["id"])
            for i, existing in enumerate(self._templates):
                if existing["id"] == t["id"]:
                    self._templates[i] = t
                    break
            else:
                self._templates.append(t)
            self._save()
            return copy.deepcopy(t)

    def rename(self, template_id, new_name):
        t = self.get(template_id)
        if t is None:
            raise TemplateError("That template no longer exists.")
        t["name"] = new_name
        return self.save(t)

    def delete(self, template_id):
        """Delete a template and its standard-photo copies. The last template can't be deleted."""
        with self._lock:
            if len(self._templates) <= 1:
                raise TemplateError("You need at least one template - create another one before deleting this.")
            keep = [t for t in self._templates if t["id"] != template_id]
            gone = [t for t in self._templates if t["id"] == template_id]
            self._templates = keep
            self._save()
        for t in gone:
            for fp in t["fixed_photos"]:
                self.remove_photo_copy(fp.get("path"))

    # ---- standard photos
    def copy_photo_in(self, src, template_id):
        """Copy a chosen standard photo into the app's folder; returns the new path."""
        return self._copy_photo(src, template_id)

    def _copy_photo(self, src, template_id):
        if not src or not os.path.isfile(src):
            return src
        os.makedirs(self.photo_dir, exist_ok=True)
        dest = os.path.join(self.photo_dir, f"{template_id}_{uuid.uuid4().hex[:6]}_{os.path.basename(src)}")
        shutil.copy2(src, dest)
        return dest

    def remove_photo_copy(self, path):
        """Delete a photo only if it's one of our copies (never the user's original)."""
        if path and os.path.dirname(os.path.abspath(path)) == os.path.abspath(self.photo_dir):
            try:
                os.remove(path)
            except OSError:
                pass

    # ---- disk
    def _save(self):
        save_json(self.path, {"version": FORMAT_VERSION, "templates": self._templates})
