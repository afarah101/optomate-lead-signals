"""Toy test: can Foursquare OS Places recover the 80 queued businesses, confirmed on each business's own site?

Reuses open_places matching (name + ZIP in any Texas county), the existing own-site check and identity_label().
FSQ_TOKEN is read from .env into an in-memory DuckDB secret only; it is never printed or stored.
Data: Foursquare OS Places, (c) Foursquare Labs, Inc., Apache License 2.0; the full NOTICE is kept beside the cache in
data/raw/fsq/NOTICE.txt (from https://opensource.foursquare.com/places-notice-txt/).

Table: places.datasets.places_os. How it was found (2026-10-28): the portal's Step 4 query
(information_schema.tables WHERE table_catalog = 'places') returned no rows, and SHOW TABLES on each schema
(attribute_packs, datasets, plugins) returned none either. DESCRIBE on likely names in the datasets schema then worked
on the first one tried, places_os (27 columns, including website and tel).

The catalog is read once: Texas rows inside DFW_BOX with date_closed IS NULL are cached as Parquet in data/raw/fsq/,
and later runs read the cache. Delete the cache file to refresh. email, facebook_id, instagram and twitter are never
selected.
"""

import csv
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leads.identity_label import identity_label  # noqa: E402
from leads.open_places import (  # noqa: E402
    DFW_BOX, OUT_COLUMNS, build_name_index, confirm_on_own_site, in_business_county, load_queued_businesses,
    matching_records,
)
from leads.website_contacts import us_phone  # noqa: E402
from leads.zip_county import load_zcta_counties  # noqa: E402

QUEUE = ROOT / "data" / "leads" / "2026-11_open_places_test_v3.csv"
OUT = ROOT / "data" / "leads" / "2026-11_fsq_test_v1.csv"
FSQ_DIR = ROOT / "data" / "raw" / "fsq"
ENDPOINT = "https://catalog.h3-hub.foursquare.com/iceberg"
FSQ_COLUMNS = OUT_COLUMNS + ["fsq_place_id", "phone_source"]


def _token() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if m := re.match(r"\s*(?:export\s+)?FSQ_TOKEN\s*=\s*(.*)", line):
            return m.group(1).strip().strip("'\"")
    sys.exit("FSQ_TOKEN missing from .env")


def fetch_texas_dfw_places() -> list[dict]:
    """Open Texas places inside DFW_BOX, from the Parquet cache, or read once from the catalog to create it."""
    import duckdb

    con = duckdb.connect()  # in-memory: the secret dies with this process
    cached = sorted(FSQ_DIR.glob("places_os_tx_dfw_*.parquet"))
    cache = cached[-1] if cached else FSQ_DIR / f"places_os_tx_dfw_{date.today().isoformat()}.parquet"
    if not cached:
        token = _token()
        try:
            con.sql("INSTALL iceberg; LOAD iceberg; INSTALL httpfs; LOAD httpfs;")
            con.execute("CREATE SECRET iceberg_secret (TYPE iceberg, TOKEN '" + token.replace("'", "''") + "')")
            con.sql(f"ATTACH 'places' AS places (TYPE iceberg, SECRET iceberg_secret, ENDPOINT '{ENDPOINT}')")
            xmin, ymin, xmax, ymax = DFW_BOX
            FSQ_DIR.mkdir(parents=True, exist_ok=True)
            con.sql(f"""COPY (SELECT fsq_place_id, name, region, postcode, website, tel
                              FROM places.datasets.places_os
                              WHERE region = 'TX' AND date_closed IS NULL
                                AND longitude BETWEEN {xmin} AND {xmax} AND latitude BETWEEN {ymin} AND {ymax})
                        TO '{cache}' (FORMAT parquet)""")
        except Exception as e:
            cache.unlink(missing_ok=True)  # never leave a partial cache behind
            sys.exit(f"Foursquare read failed: {type(e).__name__}: {str(e).replace(token, '[TOKEN]')[:300]}")
    rows = con.execute(f"SELECT fsq_place_id, name, region, postcode, website, tel FROM '{cache}'").fetchall()
    # shortcut: FSQ has no confidence score, so candidates keep catalog order; add date_refreshed ordering if kept.
    return [{"id": fid, "name": name, "confidence": 0.0, "websites": [website] if website else [],
             "addresses": [{"region": region, "postcode": postcode}], "datasets": ["Foursquare"], "tel": tel}
            for fid, name, region, postcode, website, tel in rows]


def run() -> dict:
    if OUT.exists():
        sys.exit(f"{OUT} already exists; it is never overwritten")
    records = fetch_texas_dfw_places()
    by_id = {r["id"]: r for r in records}
    zcta = load_zcta_counties()
    businesses = load_queued_businesses(QUEUE)
    index, today = build_name_index(records), date.today().isoformat()
    outcomes, labels = Counter(), Counter()
    with OUT.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FSQ_COLUMNS)
        writer.writeheader()
        for business in businesses:
            matched = matching_records(business["business_name"], records, index, zcta)
            result = confirm_on_own_site(business, matched)
            label = identity_label(result["outcome"])
            extra = {"identity_label": label, "lookup_date": today}
            if fid := result.get("source_record_id"):
                source = by_id[fid]
                extra |= {"fsq_place_id": fid,
                          "zip_county_match": "yes" if in_business_county(source, business["county"], zcta) else "no"}
                if result.get("business_phone"):
                    extra["phone_source"] = "site"
                elif phone := us_phone(source["tel"] or ""):  # verified business, no phone on its site
                    extra |= {"business_phone": phone, "phone_source": "Foursquare"}
            writer.writerow({c: "" for c in FSQ_COLUMNS} | business | result | extra)
            outcomes[result["outcome"]] += 1
            labels[label] += 1
            print(f"{business['licence_number']}: {result['outcome']}", flush=True)
    return {"fsq_records_in_box": len(records), "outcomes": dict(outcomes), "identity_labels": dict(labels),
            "output": str(OUT)}


if __name__ == "__main__":
    print(run())
