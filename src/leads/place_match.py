"""Leads: find a licence holder's Google place, and its website live. Anti-corruption layer for Places API (New).

Rules: docs/decisions/lookup-automation.md. Only place_id may be stored. fetch_website_live() returns the website for
immediate use; callers must not write it anywhere. The API key travels only in a request header and is never printed.
"""

import json
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{}"
SEARCH_FIELDS = "places.id,places.displayName,places.formattedAddress"
DETAILS_FIELDS = "websiteUri"
TIMEOUT_SECS = 10
IGNORED_WORDS = frozenset({
    "LLC", "INC", "CO", "CORP", "CORPORATION", "INCORPORATED", "LTD", "LP", "LLP", "THE", "AND", "OF",
})
TEXAS_ADDRESS = re.compile(r",\s*TX\s+7\d{4}\b")
TEXAS_WITHOUT_ZIP = re.compile(r",\s*TX\b|\bTexas\b")  # only to name the failure; still rejected (see rule changes)
PLACE_NAME_SHARE = (7, 10)  # at least 70% of the licence name's main words, compared as whole numbers


class PlacesUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=None)
def load_api_key(env_path: Path = ENV_PATH) -> str:
    try:
        lines = Path(env_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        raise PlacesUnavailable(f"cannot read {env_path}") from None
    for line in lines:
        match = re.match(r"\s*(?:export\s+)?GOOGLE_MAPS_API_KEY\s*=\s*(.*)", line)
        if match and (key := match.group(1).strip().strip("'\"")):
            return key
    raise PlacesUnavailable(f"GOOGLE_MAPS_API_KEY missing from {env_path}")


def main_words(name: str | None) -> set[str]:
    text = (name or "").upper().replace(".", "").replace("&", " AND ")
    return {word for word in re.split(r"[^A-Z0-9]+", text) if word and word not in IGNORED_WORDS}


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("S") and not word.endswith("SS") else word


def _main_word_stems(name: str | None) -> set[str]:
    return {_singular(word) for word in main_words(name)}


def shares_main_words(licence_name: str, other_name: str | None) -> bool:
    wanted = _main_word_stems(licence_name)
    return bool(wanted) and wanted <= _main_word_stems(other_name)


def name_matches_place(licence_name: str, google_name: str | None) -> bool:
    wanted = _main_word_stems(licence_name)
    share, out_of = PLACE_NAME_SHARE
    return bool(wanted) and len(wanted & _main_word_stems(google_name)) * out_of >= share * len(wanted)


def _places_request(url: str, api_key: str, field_mask: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        method="GET" if body is None else "POST",
        headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": field_mask, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECS) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        try:
            message = json.load(e).get("error", {}).get("message", "")
        except ValueError:
            message = ""
        # from None: keep the request (and its key header) out of any traceback chain.
        raise PlacesUnavailable(f"Places API HTTP {e.code}: {message}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PlacesUnavailable(f"Places API unreachable: {getattr(e, 'reason', e)}") from None


def find_place(name: str, county: str, api_key: str | None = None, request=_places_request) -> tuple[str | None, str]:
    """Returns (place_id, "") or (None, the queue reason naming which test failed)."""
    places = request(SEARCH_URL, api_key or load_api_key(), SEARCH_FIELDS,
                     {"textQuery": f"{name} {county} County TX", "regionCode": "US"}).get("places", [])
    if not places:
        return None, "no_place_none"
    named = [p for p in places if name_matches_place(name, p.get("displayName", {}).get("text"))]
    if not named:
        return None, "no_place_name"
    addresses = [p.get("formattedAddress", "") for p in named]
    for place, address in zip(named, addresses):
        if TEXAS_ADDRESS.search(address):
            return place.get("id"), ""
    return None, "no_place_zip" if any(TEXAS_WITHOUT_ZIP.search(a) for a in addresses) else "no_place_texas"


def find_place_id(name: str, county: str, api_key: str | None = None, request=_places_request) -> str | None:
    return find_place(name, county, api_key, request)[0]


def fetch_website_live(place_id: str, api_key: str | None = None, request=_places_request) -> str | None:
    return request(DETAILS_URL.format(place_id), api_key or load_api_key(), DETAILS_FIELDS).get("websiteUri") or None
