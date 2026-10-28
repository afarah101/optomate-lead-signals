"""Application layer: fill the November lookup automatically, or send each business to the manual queue with a reason.

Rules: docs/decisions/lookup-automation.md. Every business lands in exactly one output. Google's website address is
used live only; the stored website_url is the address the site itself answered on after it was confirmed by licence
number or name.
Progress output names licence numbers and reasons only, never URLs or the API key.
"""

import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from leads.identity_label import VERIFIED, identity_label
from leads.place_match import PlacesUnavailable, fetch_website_live, find_place_candidates, shares_main_words
from leads.website_contacts import SiteUnreadable, read_own_site_contacts
from signals.lookup_sheet import LOOKUP_COLUMNS

AUTO_COLUMNS = LOOKUP_COLUMNS + ["place_id", "identity_label"]
QUEUE_COLUMNS = ["licence_number", "business_name", "county", "place_id", "reason", "website_url", "form_url",
                 "identity_label"]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PLACES_BUDGET = 300


class PlacesBudgetReached(PlacesUnavailable):
    pass


def autofill_lookup(call_list_csv, out_csv, queue_csv, find_candidates=find_place_candidates,
                    website_of=fetch_website_live, read_site=read_own_site_contacts, today: date | None = None,
                    places_budget: int = PLACES_BUDGET) -> dict:
    out_csv, queue_csv = Path(out_csv), Path(queue_csv)
    for path in (out_csv, queue_csv):
        if path.exists():  # checked before any paid API call
            raise FileExistsError(f"{path} already exists; it is never overwritten")
    with open(call_list_csv, newline="", encoding="utf-8") as f:
        businesses = list(csv.DictReader(f))
    lookup_date = (today or date.today()).isoformat()
    reasons, places_calls, filled = Counter(), 0, Counter()

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
                            "website_url": website_url, "form_url": form_url,
                            "identity_label": identity_label(reason)})
            print(f"{business['licence_number']}: manual queue ({reason})", flush=True)

        try:
            for position, business in enumerate(businesses):
                name, licence = business["business_name"], business["licence_number"]
                if places_calls + 1 > places_budget:
                    raise PlacesBudgetReached(f"Places budget of {places_budget} calls reached")
                places_calls += 1
                place_ids, failed_test = find_candidates(name, business["county"])
                if not place_ids:
                    send_to_queue(business, failed_test)
                    continue
                searches_still_needed = len(businesses) - position - 1
                outcomes, accepted = [], None
                for place_id in place_ids:
                    # Keep one call free for every business not searched yet, so the budget is never exceeded.
                    if places_calls + 1 + searches_still_needed > places_budget:
                        outcomes.append((place_id, "places_budget", None))
                        break
                    places_calls += 1
                    website = website_of(place_id)  # Google's value: used live below, never written
                    if not website:
                        outcomes.append((place_id, "no_website", None))
                        continue
                    try:
                        site = read_site(website, licence_number=licence)
                    except SiteUnreadable as e:
                        outcomes.append((place_id, e.reason, None))
                        continue
                    match_by = ("licence" if site["licence_shown"]
                                else "name" if shares_main_words(name, site["site_name"]) else None)
                    if not match_by:
                        outcomes.append((place_id, "name_mismatch", None))
                        continue
                    if not site["phone"]:
                        outcomes.append((place_id, "no_tel_phone", site))  # this site is the business: stop here
                        break
                    accepted = (place_id, site, match_by)
                    break
                if not accepted:
                    # A confirmed site (no_tel_phone) is the most useful lead for the manual lookup; else the first.
                    place_id, reason, site = next((o for o in outcomes if o[2]), outcomes[0])
                    send_to_queue(business, reason, place_id, site["website_url"] if site else "",
                                  site["form_url"] if site else "")
                    continue
                place_id, site, match_by = accepted
                auto.writerow({column: "" for column in AUTO_COLUMNS} | {
                    "licence_number": licence, "business_name": name, "county": business["county"],
                    "website_url": site["website_url"], "business_phone": site["phone"],
                    "phone_source_url": site["phone_source_url"], "form_url": site["form_url"],
                    "lookup_date": lookup_date, "lookup_initials": "auto", "place_id": place_id,
                    "notes": f"auto: site found via Google Places live; match_by={match_by}", "identity_label": VERIFIED,
                })
                filled[match_by] += 1
                print(f"{licence}: auto-filled (match_by={match_by})", flush=True)
        except PlacesUnavailable as error:
            done = sum(filled.values()) + sum(reasons.values())
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
    return {"businesses": len(businesses), "auto_filled": sum(filled.values()), "match_by": dict(filled), "manual_queue": dict(reasons),
            "places_calls": places_calls, "output": str(out_csv), "queue": str(queue_csv)}


if __name__ == "__main__":
    print(autofill_lookup(DATA_DIR / "logs" / "2026-11_call_list.csv", DATA_DIR / "logs" / "2026-11_lookup_auto_v3.csv",
                          DATA_DIR / "logs" / "2026-11_manual_queue_v3.csv"))
