"""Signals domain: the manual lookup sheet for each business's own published phone, contact form and email.

Rules live in docs/decisions/call-list-plan.md under "Lookup step". Every lookup is done by hand; this code only
creates the empty sheet and checks what people filled in.
"""

import csv
import sys
from pathlib import Path
from urllib.parse import urlparse

LOOKUP_COLUMNS = [
    "licence_number", "business_name", "county", "website_url", "business_phone", "phone_source_url", "form_url",
    "contact_email", "email_source_url", "lookup_date", "lookup_initials", "notes",
]
NO_WEBSITE = "no_website"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def create_lookup_sheet(call_list_csv, out_csv) -> int:
    with open(call_list_csv, newline="", encoding="utf-8") as f:
        businesses = list(csv.DictReader(f))
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    # "x" refuses to overwrite: people fill this sheet in by hand, and a re-run must never wipe their work.
    with out.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOOKUP_COLUMNS)
        writer.writeheader()
        for business in businesses:
            writer.writerow({column: "" for column in LOOKUP_COLUMNS} | {
                key: business.get(key, "") for key in ("licence_number", "business_name", "county")
            })
    return len(businesses)


def _site(url: str) -> str:
    host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    return host.removeprefix("www.")


def _lookup_problems(row: dict) -> list[str]:
    website = row.get("website_url", "")
    filled = [c for c in ("business_phone", "form_url", "contact_email") if row.get(c)]
    problems = []
    if (website or filled) and not row.get("lookup_date"):
        problems.append("lookup_date missing")
    if website == NO_WEBSITE:
        return problems + [f"{c} filled in but website_url is no_website" for c in filled]
    for value_column, source_column in (("business_phone", "phone_source_url"), ("contact_email", "email_source_url")):
        if not row.get(value_column):
            continue
        source = row.get(source_column, "")
        if not source:
            problems.append(f"{value_column} has no {source_column}")
        elif _site(source) != _site(website):
            problems.append(f"{source_column} is not on the business's website ({website or 'website_url missing'})")
    return problems


def check_lookup_sheet(path) -> list[dict]:
    report = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {k: (v or "").strip() for k, v in raw.items() if k is not None}
            report += [{"line": reader.line_num, "licence_number": row.get("licence_number", ""), "problem": p}
                       for p in _lookup_problems(row)]
    return report


if __name__ == "__main__":
    sheet = DATA_DIR / "logs" / "2026-11_lookup.csv"
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        for item in check_lookup_sheet(sheet):
            print(f"line {item['line']} ({item['licence_number']}): {item['problem']}")
    else:
        print({"rows": create_lookup_sheet(DATA_DIR / "logs" / "2026-11_call_list.csv", sheet), "output": str(sheet)})
