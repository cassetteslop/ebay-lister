"""eBay REST API client (Inventory, Account, Media, Taxonomy and Fulfillment APIs).

OAuth uses the authorization-code grant with a RuName; the user pastes the redirect URL back
into the app. Tokens refresh automatically (access token ~2 h, refresh token ~18 months).
"""

import base64
import json
import mimetypes
import os
import threading
import time
import urllib.parse

from ebay_lister.api.http import ApiError, _loads, _multipart, http_call
from ebay_lister.config import EBAY_HOSTS, EBAY_MARKETPLACE, EBAY_SCOPES


class EbayClient:
    """eBay API client. Reads/writes OAuth tokens in the shared ``settings`` dict and calls
    ``save_settings()`` whenever they change. Use ``host(kind)`` for production/sandbox URLs."""
    def __init__(self, settings, save_settings):
        self.s = settings
        self.save = save_settings
        self._lock = threading.Lock()
        self._app_token = (None, 0)

    def host(self, kind):
        return EBAY_HOSTS[self.s.get("ebay_env", "production")][kind]

    def connected(self):
        return bool(self.s.get("ebay_refresh_token"))

    def _creds(self):
        cid, sec = self.s.get("ebay_client_id", "").strip(), self.s.get("ebay_client_secret", "").strip()
        if not cid or not sec:
            raise ApiError("Enter your eBay App ID (Client ID) and Cert ID (Client Secret) on the Settings tab.")
        return cid, sec

    def _token_post(self, data):
        cid, sec = self._creds()
        headers = {"Authorization": "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode(),
                   "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        status, _, txt = http_call("POST", self.host("api") + "/identity/v1/oauth2/token", headers,
                                   urllib.parse.urlencode(data).encode())
        j = _loads(txt)
        if status >= 400:
            raise ApiError(f"eBay sign-in failed (HTTP {status}): {j.get('error_description') or j.get('error') or txt}")
        return j

    def auth_url(self):
        cid, _ = self._creds()
        runame = self.s.get("ebay_runame", "").strip()
        if not runame:
            raise ApiError("Enter your eBay RuName (redirect URL name) on the Settings tab.")
        return self.host("auth") + "/oauth2/authorize?" + urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": runame, "response_type": "code",
            "scope": EBAY_SCOPES, "prompt": "login",
        }, quote_via=urllib.parse.quote)

    def exchange_code(self, pasted):
        pasted = pasted.strip()
        code = None
        if "code=" in pasted:
            u = urllib.parse.urlparse(pasted)
            q = urllib.parse.parse_qs(u.query) or urllib.parse.parse_qs(u.fragment)
            if not q and "?" not in pasted:
                q = urllib.parse.parse_qs(pasted)
            code = (q.get("code") or [None])[0]
        else:
            code = urllib.parse.unquote(pasted)
        if not code:
            raise ApiError("Couldn't find 'code=' in what you pasted. Paste the full address of the page eBay sent you to.")
        tok = self._token_post({"grant_type": "authorization_code", "code": code,
                                "redirect_uri": self.s["ebay_runame"].strip()})
        self._store(tok)

    def _store(self, tok):
        self.s["ebay_access_token"] = tok["access_token"]
        self.s["ebay_token_expires_at"] = time.time() + int(tok.get("expires_in", 7200))
        if tok.get("refresh_token"):
            self.s["ebay_refresh_token"] = tok["refresh_token"]
            self.s["ebay_refresh_expires_at"] = time.time() + int(tok.get("refresh_token_expires_in", 0))
        self.save()

    def _token(self):
        with self._lock:
            if not self.s.get("ebay_refresh_token"):
                raise ApiError("Not connected to eBay. Use 'Connect to eBay' on the Settings tab.")
            if time.time() > float(self.s.get("ebay_token_expires_at", 0)) - 120:
                tok = self._token_post({"grant_type": "refresh_token",
                                        "refresh_token": self.s["ebay_refresh_token"], "scope": EBAY_SCOPES})
                self._store(tok)
            return self.s["ebay_access_token"]

    def _application_token(self):
        tok, exp = self._app_token
        if tok and time.time() < exp - 120:
            return tok
        j = self._token_post({"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"})
        self._app_token = (j["access_token"], time.time() + int(j.get("expires_in", 7200)))
        return j["access_token"]

    def _req(self, method, url, json_body=None, raw=None, ctype=None, app_token=False, ok404=False):
        token = self._application_token() if app_token else self._token()
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json",
                   "Content-Language": "en-US", "Accept-Language": "en-US",
                   "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE}
        body = None
        if raw is not None:
            body, headers["Content-Type"] = raw, ctype
        elif json_body is not None:
            body, headers["Content-Type"] = json.dumps(json_body).encode(), "application/json"
        status, hdrs, txt = http_call(method, url, headers, body)
        j = _loads(txt)
        if status == 404 and ok404:
            return status, hdrs, {}
        if status >= 400:
            errs = j.get("errors") or []
            msg = "; ".join(f"{e.get('errorId')}: {e.get('longMessage') or e.get('message')}" for e in errs) \
                or j.get("_raw") or txt
            err = ApiError(f"eBay HTTP {status} ({method} {urllib.parse.urlparse(url).path}): {msg}")
            err.ebay_errors = errs
            raise err
        return status, hdrs, j

    # ---- account / setup
    def policies(self, kind):
        """kind: fulfillment | payment | return"""
        key = {"fulfillment": "fulfillmentPolicies", "payment": "paymentPolicies", "return": "returnPolicies"}[kind]
        _, _, j = self._req("GET", f"{self.host('api')}/sell/account/v1/{kind}_policy?marketplace_id={EBAY_MARKETPLACE}")
        return j.get(key, [])

    def locations(self):
        _, _, j = self._req("GET", f"{self.host('api')}/sell/inventory/v1/location?limit=100")
        return j.get("locations", [])

    def create_location(self, key, postal_code, name):
        body = {"location": {"address": {"postalCode": postal_code, "country": "US"}},
                "locationTypes": ["WAREHOUSE"], "name": name, "merchantLocationStatus": "ENABLED"}
        self._req("POST", f"{self.host('api')}/sell/inventory/v1/location/{urllib.parse.quote(key)}", json_body=body)

    def suggest_categories(self, q):
        url = (f"{self.host('api')}/commerce/taxonomy/v1/category_tree/0/get_category_suggestions?"
               + urllib.parse.urlencode({"q": q}))
        _, _, j = self._req("GET", url, app_token=True)
        out = []
        for s in j.get("categorySuggestions", []):
            c = s["category"]
            anc = " > ".join(a["categoryName"] for a in reversed(s.get("categoryTreeNodeAncestors", [])))
            out.append({"id": c["categoryId"], "name": c["categoryName"],
                        "path": (anc + " > " if anc else "") + c["categoryName"]})
        return out

    def item_aspects(self, category_id):
        url = (f"{self.host('api')}/commerce/taxonomy/v1/category_tree/0/get_item_aspects_for_category?"
               + urllib.parse.urlencode({"category_id": category_id}))
        _, _, j = self._req("GET", url, app_token=True)
        out = []
        for a in j.get("aspects", []):
            c = a.get("aspectConstraint") or {}
            out.append({"name": a["localizedAspectName"], "required": bool(c.get("aspectRequired")),
                        "recommended": c.get("aspectUsage") == "RECOMMENDED",
                        "free_text": c.get("aspectMode", "FREE_TEXT") == "FREE_TEXT",   # else pick from values
                        "multiple": c.get("itemToAspectCardinality") == "MULTI",
                        "values": [v["localizedValue"] for v in a.get("aspectValues", []) if v.get("localizedValue")]})
        return out

    # ---- listing
    def upload_image(self, path):
        with open(path, "rb") as f:
            content = f.read()
        ctype = mimetypes.guess_type(path)[0] or "image/jpeg"
        body, ct = _multipart({}, {"image": (os.path.basename(path), content, ctype)})
        _, hdrs, j = self._req("POST", f"{self.host('media')}/commerce/media/v1_beta/image/create_image_from_file",
                               raw=body, ctype=ct)
        if j.get("imageUrl"):
            return j["imageUrl"]
        loc = {k.lower(): v for k, v in hdrs.items()}.get("location")
        if not loc:
            raise ApiError("eBay image upload returned no image URL.")
        _, _, j = self._req("GET", loc)
        return j["imageUrl"]

    def put_inventory_item(self, sku, item):
        self._req("PUT", f"{self.host('api')}/sell/inventory/v1/inventory_item/{urllib.parse.quote(sku, safe='')}",
                  json_body=item)

    def create_or_update_offer(self, offer):
        base = f"{self.host('api')}/sell/inventory/v1/offer"
        try:
            _, _, j = self._req("POST", base, json_body=offer)
            return j["offerId"]
        except ApiError as e:
            if not any(str(x.get("errorId")) == "25002" for x in getattr(e, "ebay_errors", [])):
                raise
        _, _, j = self._req("GET", base + "?" + urllib.parse.urlencode(
            {"sku": offer["sku"], "marketplace_id": EBAY_MARKETPLACE}))
        offers = j.get("offers", [])
        if not offers:
            raise ApiError("eBay says an offer exists for this SKU but none was found.")
        oid = offers[0]["offerId"]
        self._req("PUT", f"{base}/{oid}", json_body=offer)
        return oid

    def publish(self, offer_id):
        _, _, j = self._req("POST", f"{self.host('api')}/sell/inventory/v1/offer/{offer_id}/publish")
        return j.get("listingId")

    def get_offer(self, offer_id):
        _, _, j = self._req("GET", f"{self.host('api')}/sell/inventory/v1/offer/{offer_id}")
        return j

    def orders_since(self, since_ts):
        iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(since_ts))
        url = (f"{self.host('api')}/sell/fulfillment/v1/order?"
               + urllib.parse.urlencode({"filter": f"creationdate:[{iso}..]", "limit": 200}))
        out = []
        for _ in range(25):  # up to 5,000 orders
            _, _, j = self._req("GET", url)
            out += j.get("orders", [])
            url = j.get("next")
            if not url:
                break
        return out

    def listing_url(self, listing_id):
        return ("https://www.sandbox.ebay.com/itm/" if self.s.get("ebay_env") == "sandbox"
                else "https://www.ebay.com/itm/") + str(listing_id)
