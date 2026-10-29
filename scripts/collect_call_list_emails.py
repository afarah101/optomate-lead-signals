"""Published outreach emails for the businesses on call list v2. Rules: docs/decisions/lookup-automation.md,
2026-10-29 "Outreach email address" (decision 4).

The own-site reader is unchanged (robots.txt, at most 2 pages, 1 request per second, the same User-Agent); it reads
emails only from mailto: links and visible text, and never decodes a hidden one. Progress and the summary print counts
and outcomes only, never an address. The output is never overwritten.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leads.website_contacts import SiteUnreadable, email_type, read_own_site_contacts  # noqa: E402

DATA_DIR = ROOT / "data"
CALL_LIST = DATA_DIR / "logs" / "2026-11_call_list_v2.csv"
WEBSITES = DATA_DIR / "leads" / "2026-11_reverse_lookup_full_v1.csv"
OUT = DATA_DIR / "logs" / "2026-11_call_list_v2_emails.csv"
OUT_COLUMNS = ["licence_number", "primary_email", "email_type", "source_url", "other_emails_count", "status"]
PREFERENCE = {"named": 0, "generic": 1, "TO_CONFIRM": 2}  # other_domain is excluded


def _key(licence: str) -> str:
    return (licence or "").strip().lstrip("0")


def email_row(licence: str, website: str, read_site=read_own_site_contacts) -> tuple[dict, int]:
    """(output row, number of other-domain addresses excluded)."""
    row = {"licence_number": licence, "primary_email": "", "email_type": "", "source_url": "", "other_emails_count": 0}
    if not website:
        return row | {"status": "no_website_in_input"}, 0
    try:
        site = read_site(website, collect_emails=True)
    except SiteUnreadable as e:
        # redirect_off_site has no status of its own in the brief; it is a site that couldn't be read.
        return row | {"status": "robots_blocked" if e.reason == "robots_blocked" else "fetch_failed"}, 0
    typed = [(address, source, email_type(address, site["website_url"])) for address, source in site["emails"]]
    kept = [t for t in typed if t[2] in PREFERENCE]
    if not kept:
        return row | {"status": "email_obfuscated" if site["email_hidden"] else "none"}, len(typed)
    address, source, kind = min(kept, key=lambda t: PREFERENCE[t[2]])  # min keeps page order on a tie
    return row | {"primary_email": address, "email_type": kind, "source_url": source,
                  "other_emails_count": len(kept) - 1, "status": "found"}, len(typed) - len(kept)


def collect(call_list_csv, websites_csv, out_csv, read_site=read_own_site_contacts) -> dict:
    out_csv = Path(out_csv)
    if out_csv.exists():
        raise FileExistsError(f"{out_csv} already exists; it is never overwritten")
    with open(websites_csv, newline="", encoding="utf-8") as f:
        websites = {_key(r["licence_number"]): r["website_url"] for r in csv.DictReader(f)}
    with open(call_list_csv, newline="", encoding="utf-8") as f:
        licences = [r["licence_number"] for r in csv.DictReader(f)]
    statuses, types, excluded = Counter(), Counter(), 0
    with out_csv.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        for position, licence in enumerate(licences, 1):
            row, other_domain = email_row(licence, websites.get(_key(licence), ""), read_site)
            writer.writerow(row)
            f.flush()
            statuses[row["status"]] += 1
            types[row["email_type"]] += bool(row["email_type"])
            excluded += other_domain
            print(f"{position}/{len(licences)}: {row['status']} {row['email_type']}", flush=True)
    return {"businesses": len(licences), "status": dict(statuses), "email_type": dict(+types),
            "other_domain_addresses_excluded": excluded, "output": str(out_csv)}


if __name__ == "__main__":
    print(collect(CALL_LIST, WEBSITES, OUT))
