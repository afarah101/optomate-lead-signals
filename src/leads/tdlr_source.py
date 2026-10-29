"""TDLR licence holders from the Texas Open Data Portal (dataset 7358-krk7), official SODA API, no key."""

import csv
import io
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

DATASET_URL = "https://data.texas.gov/dataset/TDLR-All-Licenses/7358-krk7"
API_URL = "https://data.texas.gov/resource/7358-krk7.csv"
AC_CONTRACTOR = "A/C Contractor"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
# The holder's name is personal data and is never kept, not even in the raw file (data-sources.md, 2026-10-29).
DROPPED_COLUMNS = ("owner_name",)


def drop_personal_columns(body: bytes) -> bytes:
    """The CSV with DROPPED_COLUMNS removed, in the API's own format (every field quoted, LF line ends)."""
    reader = csv.DictReader(io.StringIO(body.decode("utf-8"), newline=""))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=[c for c in reader.fieldnames or [] if c not in DROPPED_COLUMNS],
                            extrasaction="ignore", quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writeheader()
    writer.writerows(reader)
    return out.getvalue().encode("utf-8")


def download_ac_contractor_licences(retrieved_on: date) -> Path:
    query = urllib.parse.urlencode({"license_type": AC_CONTRACTOR, "$order": "license_number", "$limit": 200000})
    with urllib.request.urlopen(f"{API_URL}?{query}", timeout=120) as response:
        body = response.read()
    raw_path = DATA_DIR / "raw" / f"tdlr_ac_contractors_{retrieved_on.isoformat()}.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(drop_personal_columns(body))
    return raw_path


def read_licences(raw_path: Path) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(raw_path.read_text(encoding="utf-8"))))
    # The type filter runs server-side; re-check it so a changed API can't leak other licence types in.
    return [r for r in rows if r.get("license_type") == AC_CONTRACTOR]
