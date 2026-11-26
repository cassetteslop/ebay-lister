"""Tiny stdlib HTTP layer used by the eBay client (no third-party packages).
"""

import json
import urllib.error
import urllib.request
import uuid


class ApiError(Exception):
    """Any failed API call (HTTP error, network error, missing credentials). The message is user-readable."""
    pass




def http_call(method, url, headers, body=None, timeout=90):
    """Send one HTTP request. Returns ``(status, headers, body_text)``; HTTP errors are returned, not raised.
    Raises :class:`ApiError` only for network failures."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise ApiError(f"Network error: {e.reason}")


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    for k, (fname, content, ctype) in files.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                f"filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
        out += content + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _loads(txt):
    try:
        return json.loads(txt) if txt.strip() else {}
    except ValueError:
        return {"_raw": txt}
