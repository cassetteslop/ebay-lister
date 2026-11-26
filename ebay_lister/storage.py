"""Small JSON persistence helpers for settings.json and template.json.

Files are written atomically (write to a temp file, then rename) and chmod 600 because the
settings file contains API secrets and OAuth tokens.
"""

import json
import os

from ebay_lister.config import APP_DIR


def load_json(path, defaults):
    """Load ``path`` and overlay it on ``defaults`` (so new default keys appear after an upgrade)."""
    data = dict(defaults)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not read {path}: {e}")
    return data


def save_json(path, data):
    """Atomically write ``data`` to ``path`` as JSON and restrict it to the current user (chmod 600)."""
    os.makedirs(APP_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)  # settings hold your API secrets and tokens
    except OSError:
        pass
