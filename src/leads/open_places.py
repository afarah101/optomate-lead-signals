"""Measure how many queued businesses Overture Places can recover, confirmed on each business's own site.

Rules: docs/decisions/open-places.md. Overture is only a source of candidate websites; identity is decided by the
existing own-site reader (licence number or site name). The licence holder name is never read. Progress output names
licence numbers and outcomes only, never URLs.
"""

import csv
import re
from collections import Counter
from datetime import date
from pathlib import Path

from leads.identity_label import identity_label
from leads.place_match import _main_word_stems, shares_main_words
from leads.website_contacts import SiteUnreadable, read_own_site_contacts

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OVERTURE_RELEASE = "2026-10-21.0"
OVERTURE_PLACES = "s3://overturemaps-us-west-2/release/{}/theme=places/type=place/*"
DFW_BOX = (-98.1, 32.0, -96.0, 33.5)  # xmin, ymin, xmax, ymax around the 9 DFW counties; a pre-filter only
DFW_ZIP = re.compile(r"7[56]\d{3}(-\d{4})?")
TEXAS_REGIONS = {"TX", "TEXAS"}
MAX_SITES_PER_BUSINESS = 5
QUEUE_INPUT_COLUMNS = ("licence_number", "business_name", "county")  # the queue has no licence holder column
OUT_COLUMNS = ["licence_number", "business_name", "county", "outcome", "identity_label", "match_by", "matched_records",
               "records_with_website", "source_record_id", "source_datasets", "website_url", "business_phone",
               "phone_source_url", "form_url", "lookup_date"]


def load_queued_businesses(queue_csv) -> list[dict]:
    with open(queue_csv, newline="", encoding="utf-8") as f:
        return [{column: row[column] for column in QUEUE_INPUT_COLUMNS} for row in csv.DictReader(f)]


def fetch_dfw_places(release: str = OVERTURE_RELEASE) -> list[dict]:
    """Overture places inside DFW_BOX, read live from the official release. Never selects emails, socials or phones."""
    import duckdb  # imported here so the matching code and its tests run without it

    xmin, ymin, xmax, ymax = DFW_BOX
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    rows = con.execute(f"""
        SELECT id, names.primary, confidence, websites,
               [{{'region': a.region, 'postcode': a.postcode}} FOR a IN addresses],
               [s.dataset FOR s IN sources]
        FROM read_parquet('{OVERTURE_PLACES.format(release)}', hive_partitioning = 1)
        WHERE bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ?""", [xmin, xmax, ymin, ymax]).fetchall()
    return [{"id": id_, "name": name, "confidence": confidence or 0.0, "websites": websites or [],
             "addresses": addresses or [], "datasets": sorted(set(datasets or []) - {"Overture", "Overture-signals"})}
            for id_, name, confidence, websites, addresses, datasets in rows]


def has_dfw_zip(record: dict) -> bool:
    return any((a.get("region") or "").upper() in TEXAS_REGIONS and DFW_ZIP.fullmatch(a.get("postcode") or "")
               for a in record["addresses"])


def build_name_index(records: list[dict]) -> dict[str, set[int]]:
    index = {}
    for position, record in enumerate(records):
        for stem in _main_word_stems(record["name"]):
            index.setdefault(stem, set()).add(position)
    return index


def matching_records(business_name: str, records: list[dict], index: dict[str, set[int]]) -> list[dict]:
    """Records whose name has every main word of the licence name (same test as shares_main_words) and a DFW ZIP."""
    stems = _main_word_stems(business_name)
    if not stems:
        return []
    positions = set.intersection(*(index.get(stem, set()) for stem in stems))
    return [records[p] for p in sorted(positions) if has_dfw_zip(records[p])]


def confirm_on_own_site(business: dict, matched: list[dict], read_site=read_own_site_contacts) -> dict:
    """Try the matched records' websites on the existing own-site check; only the site itself confirms identity."""
    with_site = sorted((r for r in matched if r["websites"]), key=lambda r: -r["confidence"])
    result = {"outcome": "no_match" if not matched else "no_website", "matched_records": len(matched),
              "records_with_website": len(with_site)}
    tried, first_reason = set(), None
    for record in with_site:
        website = record["websites"][0]
        if website in tried:
            continue
        if len(tried) == MAX_SITES_PER_BUSINESS:
            break
        tried.add(website)
        try:
            site = read_site(website, licence_number=business["licence_number"])
        except SiteUnreadable as e:
            first_reason = first_reason or e.reason
            continue
        match_by = ("licence" if site["licence_shown"]
                    else "name" if shares_main_words(business["business_name"], site["site_name"]) else None)
        if not match_by:
            first_reason = first_reason or "name_mismatch"
            continue
        return result | {"outcome": "confirmed" if site["phone"] else "no_tel_phone", "match_by": match_by,
                         "source_record_id": record["id"], "source_datasets": ";".join(record["datasets"]),
                         "website_url": site["website_url"], "business_phone": site["phone"],
                         "phone_source_url": site["phone_source_url"], "form_url": site["form_url"]}
    return result | ({"outcome": first_reason} if first_reason else {})


def measure_open_places_recovery(queue_csv, out_csv, records: list[dict], read_site=read_own_site_contacts,
                                 today: date | None = None) -> dict:
    out_csv = Path(out_csv)
    if out_csv.exists():
        raise FileExistsError(f"{out_csv} already exists; it is never overwritten")
    businesses = load_queued_businesses(queue_csv)
    index, lookup_date = build_name_index(records), (today or date.today()).isoformat()
    outcomes, match_by, labels = Counter(), Counter(), Counter()
    totals = Counter()
    with out_csv.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        for business in businesses:
            matched = matching_records(business["business_name"], records, index)
            result = confirm_on_own_site(business, matched, read_site)
            label = identity_label(result["outcome"])
            writer.writerow({column: "" for column in OUT_COLUMNS} | business | result
                            | {"identity_label": label, "lookup_date": lookup_date})
            outcomes[result["outcome"]] += 1
            labels[label] += 1
            if result.get("match_by"):
                match_by[result["match_by"]] += 1
            totals["businesses_matched"] += bool(matched)
            totals["businesses_with_website"] += bool(result["records_with_website"])
            totals["matched_records"] += result["matched_records"]
            totals["records_with_website"] += result["records_with_website"]
            totals["new_phones"] += bool(result.get("business_phone"))
            print(f"{business['licence_number']}: {result['outcome']}", flush=True)
    return {"businesses": len(businesses), **totals, "outcomes": dict(outcomes), "identity_labels": dict(labels),
            "confirmed_on_own_site": sum(match_by.values()), "match_by": dict(match_by), "output": str(out_csv)}


if __name__ == "__main__":
    print(measure_open_places_recovery(DATA_DIR / "logs" / "2026-11_manual_queue_v3.csv",
                                       DATA_DIR / "logs" / "2026-11_open_places_test.csv", fetch_dfw_places()))
