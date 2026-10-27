"""Application layer: fill the November lookup automatically, or send each business to the manual queue with a reason.

Rules: docs/decisions/lookup-automation.md. Every business lands in exactly one output. Google's website address is
used live only; the stored website_url is the address the site itself answered on after it was confirmed by name.
Progress output names licence numbers and reasons only, never URLs or the API key.
"""

import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from leads.place_match import PlacesUnavailable, fetch_website_live, find_place, shares_main_words
from leads.website_contacts import SiteUnreadable, read_own_site_contacts
from signals.lookup_sheet import LOOKUP_COLUMNS

AUTO_COLUMNS = LOOKUP_COLUMNS + ["place_id"]
QUEUE_COLUMNS = ["licence_number", "business_name", "county", "place_id", "reason", "website_url", "form_url"]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def autofill_lookup(call_list_csv, out_csv, queue_csv, find_place=find_place, website_of=fetch_website_live,
                    read_site=read_own_site_contacts, today: date | None = None) -> dict:
    out_csv, queue_csv = Path(out_csv), Path(queue_csv)
    for path in (out_csv, queue_csv):
        if path.exists():  # checked before any paid API call
            raise FileExistsError(f"{path} already exists; it is never overwritten")
    with open(call_list_csv, newline="", encoding="utf-8") as f:
        businesses = list(csv.DictReader(f))
    lookup_date = (today or date.today()).isoformat()
    reasons, places_calls, filled = Counter(), 0, 0

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("x", newline="", encoding="utf-8") as out_f, queue_csv.open("x", newline="", encoding="utf-8") as q_f:
        auto = csv.DictWriter(out_f, fieldnames=AUTO_COLUMNS)
        queue = csv.DictWriter(q_f, fieldnames=QUEUE_COLUMNS)
        auto.writeheader()
        queue.writeheader()

        def send_to_queue(business, reason, place_id="", website_url="", form_url=""):
            reasons[reason] += 1
            queue.writerow({"licence_number": business["licence_number"], "business_name": business["business_name"],
                            "county": business["county"], "place_id": place_id, "reason": reason,
                            "website_url": website_url, "form_url": form_url})
            print(f"{business['licence_number']}: manual queue ({reason})", flush=True)

        try:
            for business in businesses:
                name = business["business_name"]
                places_calls += 1
                place_id, failed_test = find_place(name, business["county"])
                if not place_id:
                    send_to_queue(business, failed_test)
                    continue
                places_calls += 1
                website = website_of(place_id)  # Google's value: used live below, never written
                if not website:
                    send_to_queue(business, "no_website", place_id)
                    continue
                try:
                    site = read_site(website)
                except SiteUnreadable as e:
                    send_to_queue(business, e.reason, place_id)
                    continue
                if not shares_main_words(name, site["site_name"]):
                    send_to_queue(business, "name_mismatch", place_id)
                    continue
                if not site["phone"]:
                    send_to_queue(business, "no_tel_phone", place_id, site["website_url"], site["form_url"])
                    continue
                auto.writerow({column: "" for column in AUTO_COLUMNS} | {
                    "licence_number": business["licence_number"], "business_name": name, "county": business["county"],
                    "website_url": site["website_url"], "business_phone": site["phone"],
                    "phone_source_url": site["phone_source_url"], "form_url": site["form_url"],
                    "lookup_date": lookup_date, "lookup_initials": "auto", "place_id": place_id,
                    "notes": "auto: site found via Google Places live, confirmed by name on the site",
                })
                filled += 1
                print(f"{business['licence_number']}: auto-filled", flush=True)
        except PlacesUnavailable as error:
            done = filled + sum(reasons.values())
            print(f"Places API stopped the run after {done} of {len(businesses)} businesses", file=sys.stderr)
            if done:
                raise
            first_call_error = error
        else:
            first_call_error = None
    if first_call_error:
        # Nothing was written, so remove the two header-only files and let a fixed run start clean.
        out_csv.unlink()
        queue_csv.unlink()
        raise first_call_error
    return {"businesses": len(businesses), "auto_filled": filled, "manual_queue": dict(reasons),
            "places_calls": places_calls, "output": str(out_csv), "queue": str(queue_csv)}


if __name__ == "__main__":
    print(autofill_lookup(DATA_DIR / "logs" / "2026-11_call_list.csv", DATA_DIR / "logs" / "2026-11_lookup_auto.csv",
                          DATA_DIR / "logs" / "2026-11_manual_queue.csv"))
