"""Leads: is a ZIP in a TDLR county? Anti-corruption layer for the Census 2020 ZCTA-to-County relationship file.

Rules: docs/decisions/open-places.md ("ZIP-to-county"). Column names are the file's own header.
"""

import csv
import re
from pathlib import Path

ZCTA_COUNTY_FILE = Path(__file__).resolve().parents[2] / "data" / "raw" / "zcta_county_2020.txt"
DFW_COUNTY_FIPS = {
    "COLLIN": "48085", "DALLAS": "48113", "DENTON": "48121", "ELLIS": "48139", "JOHNSON": "48251",
    "KAUFMAN": "48257", "PARKER": "48367", "ROCKWALL": "48397", "TARRANT": "48439",
}
US_ZIP = re.compile(r"(\d{5})(?:-\d{4})?")


def load_zcta_counties(path=ZCTA_COUNTY_FILE) -> dict[str, set[str]]:
    """5-digit ZCTA -> county FIPS codes it shares land with. Rows with an empty ZCTA are skipped."""
    counties = {}
    with open(path, newline="", encoding="utf-8-sig") as f:  # the Census file starts with a byte-order mark
        for row in csv.DictReader(f, delimiter="|"):
            zcta, land = row["GEOID_ZCTA5_20"].strip(), row["AREALAND_PART"].strip()
            if zcta and land.isdigit() and int(land) > 0:
                counties.setdefault(zcta, set()).add(row["GEOID_COUNTY_20"].strip())
    return counties


def zip_in_county(zip_code: str | None, county: str | None, zcta_counties: dict[str, set[str]]) -> bool:
    match = US_ZIP.fullmatch((zip_code or "").strip())
    fips = DFW_COUNTY_FIPS.get((county or "").strip().upper())
    return bool(match and fips) and fips in zcta_counties.get(match.group(1), ())
