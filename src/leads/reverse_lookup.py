"""Reverse lookup: HVAC contractor websites from the Foursquare cache -> the licence number on the site -> a DFW lead.

Rules: docs/decisions/reverse-lookup.md. The own site is the only judge, and verified needs both the licence number
and the site name. The licence holder column is never read. Progress output names outcomes only, never URLs.
"""

import csv
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from leads.identity_label import VERIFIED, identity_label
from leads.place_match import _main_word_stems, shares_main_words
from leads.tdlr_source import read_licences
from leads.website_contacts import SiteUnreadable, _host, read_own_site_contacts, us_phone

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FSQ_CACHE = DATA_DIR / "raw" / "fsq" / "places_os_tx_dfw_categories_2026-10-28.parquet"
LEADS_CSV = DATA_DIR / "leads" / "tdlr_hvac_dfw.csv"
TDLR_RAW = DATA_DIR / "raw" / "tdlr_ac_contractors_2026-10-27.csv"
HVAC_CONTRACTOR_CATEGORY = "63be6904847c3692a84b9b56"  # ... > Heating, Ventilating and Air Conditioning Contractor
MANUFACTURER_DOMAINS = (
    "carrier.com", "trane.com", "lennox.com", "rheem.com", "goodmanmfg.com", "daikin.com", "mitsubishicomfort.com",
    "americanstandardair.com", "bryant.com", "ruudac.com", "maytaghvac.com", "frigidaire.net", "lennoxpros.com",
    "tranesupply.com",
)
PLATFORM_DOMAINS = ("homeadvisor.com", "servicemagic.com")
SAMPLE_SEED, SAMPLE_SIZE, PASS_VERIFIED = 20261028, 200, 16
LEAD_COLUMNS = ("licence_number", "business_name", "county", "entity_flag")  # never licence_holder
BUSINESS_COLUMNS = ["licence_number", "business_name", "county", "entity_flag", "outcome", "identity_label", "match_by",
                    "name_also_matches", "outreach_eligible", "sites_found", "fsq_place_id", "website_url",
                    "business_phone", "phone_source", "phone_source_url", "form_url", "lookup_date"]
DOMAIN_COLUMNS = ["domain", "website_url", "listings", "outcome", "licence_numbers", "leads_matched", "lookup_date"]


def fetch_hvac_listings(cache=FSQ_CACHE) -> list[dict]:
    """Listings in the HVAC contractor category that have a website, from the local cache only."""
    import duckdb  # imported here so the rules and their tests run without it

    rows = duckdb.connect().execute(f"""
        SELECT fsq_place_id, name, website, tel FROM read_parquet('{cache}')
        WHERE list_contains(fsq_category_ids, ?) AND website <> ''""", [HVAC_CONTRACTOR_CATEGORY]).fetchall()
    return [{"fsq_place_id": fid, "name": name, "website": website, "tel": tel} for fid, name, website, tel in rows]


def load_leads(path=LEADS_CSV) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return {row["licence_number"]: {c: row[c] for c in LEAD_COLUMNS} for row in csv.DictReader(f)}


def load_statewide_numbers(path=TDLR_RAW) -> set[str]:
    return {row["license_number"].strip().lstrip("0") for row in read_licences(Path(path))}


def domain_of(website: str) -> str:
    return _host(website)


def _is_or_under(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def is_dealer_network(listings: list[dict]) -> bool:
    return len(listings) > 1 and not set.intersection(*(_main_word_stems(l["name"]) for l in listings))


def crawlable_domains(listings: list[dict]) -> tuple[dict[str, list[dict]], Counter]:
    """Domain -> its listings (sorted, so the first website is the one crawled), and the skipped domains by rule."""
    by_domain = defaultdict(list)
    for listing in sorted(listings, key=lambda l: (l["website"], l["fsq_place_id"])):
        by_domain[domain_of(listing["website"])].append(listing)
    kept, skipped = {}, Counter()
    for domain, group in by_domain.items():
        skip = ("no_domain" if not domain else "manufacturer" if _is_or_under(domain, MANUFACTURER_DOMAINS)
                else "platform" if _is_or_under(domain, PLATFORM_DOMAINS)
                else "dealer_network" if is_dealer_network(group) else None)
        if skip:
            skipped[skip] += 1
        else:
            kept[domain] = group
    return kept, skipped


def draw_sample(domains, size: int = SAMPLE_SIZE, seed: int = SAMPLE_SEED) -> list[str]:
    pool = sorted(domains)  # the draw doesn't depend on input order
    return random.Random(seed).sample(pool, min(size, len(pool)))


def judge_site(site: dict, leads: dict[str, dict], statewide: set[str]) -> tuple[str, list[dict]]:
    """(domain outcome, one finding per DFW lead whose licence number is on the site)."""
    numbers = site["licence_numbers"]
    if not numbers:
        return "licence_not_shown", []
    matched = [leads[n] for n in numbers if n in leads]
    if not matched:
        return ("licence_not_in_leads" if any(n in statewide for n in numbers) else "licence_unknown"), []
    many = len({frozenset(_main_word_stems(lead["business_name"])) for lead in matched}) > 1
    findings = []
    for lead in matched:
        name_ok = shares_main_words(lead["business_name"], site["site_name"])
        outcome = ("many_licences" if many else ("confirmed" if site["phone"] else "no_tel_phone") if name_ok
                   else "licence_name_mismatch")
        findings.append({"lead": lead, "outcome": outcome, "name_also_matches": name_ok})
    return ";".join(sorted({f["outcome"] for f in findings})), findings


def business_rows(found: list[dict], lookup_date: str) -> list[dict]:
    """One row per lead. `found` holds findings with the domain, site and listings they came from."""
    by_licence = defaultdict(list)
    for item in sorted(found, key=lambda i: i["domain"]):
        by_licence[item["lead"]["licence_number"]].append(item)
    rows = []
    for licence, items in sorted(by_licence.items()):
        first, site = items[0], items[0]["site"]
        outcome = "licence_on_many_sites" if len(items) > 1 else first["outcome"]
        label = identity_label(outcome)
        row = {c: "" for c in BUSINESS_COLUMNS} | first["lead"] | {
            "outcome": outcome, "identity_label": label, "match_by": "licence",
            "name_also_matches": "yes" if first["name_also_matches"] else "no",
            "outreach_eligible": "yes" if label == VERIFIED and first["lead"]["entity_flag"] == "likely_corporate" else "no",
            "sites_found": len(items), "fsq_place_id": first["listings"][0]["fsq_place_id"],
            "website_url": site["website_url"], "form_url": site["form_url"], "lookup_date": lookup_date}
        if label == VERIFIED:
            if site["phone"]:
                row |= {"business_phone": site["phone"], "phone_source": "site", "phone_source_url": site["phone_source_url"]}
            elif phone := next(filter(None, (us_phone(l["tel"] or "") for l in first["listings"])), None):
                row |= {"business_phone": phone, "phone_source": "Foursquare"}  # not checked on the site
        rows.append(row)
    return rows


def run_reverse_lookup_sample(out_csv, domains_csv, listings: list[dict], leads: dict[str, dict], statewide: set[str],
                              read_site=read_own_site_contacts, size: int = SAMPLE_SIZE, today: date | None = None) -> dict:
    out_csv, domains_csv = Path(out_csv), Path(domains_csv)
    for path in (out_csv, domains_csv):
        if path.exists():
            raise FileExistsError(f"{path} already exists; it is never overwritten")
    lookup_date = (today or date.today()).isoformat()
    kept, skipped = crawlable_domains(listings)
    sample = draw_sample(kept, size)
    found, domain_outcomes = [], Counter()
    with domains_csv.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DOMAIN_COLUMNS)
        writer.writeheader()
        for position, domain in enumerate(sample, 1):
            group = kept[domain]
            try:
                site = read_site(group[0]["website"])
            except SiteUnreadable as e:
                site, outcome, findings = None, e.reason, []
            else:
                outcome, findings = judge_site(site, leads, statewide)
            writer.writerow({"domain": domain, "website_url": group[0]["website"], "listings": len(group),
                             "outcome": outcome, "licence_numbers": ";".join(site["licence_numbers"]) if site else "",
                             "leads_matched": len(findings), "lookup_date": lookup_date})
            f.flush()
            found += [finding | {"domain": domain, "site": site, "listings": group} for finding in findings]
            domain_outcomes[outcome] += 1
            print(f"{position}/{len(sample)}: {outcome}", flush=True)
    rows = business_rows(found, lookup_date)
    with out_csv.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BUSINESS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    verified = sum(r["identity_label"] == VERIFIED for r in rows)
    return {"listings": len(listings), "domains": len(kept) + sum(skipped.values()), "skipped": dict(skipped),
            "crawlable": len(kept), "sampled": len(sample), "domain_outcomes": dict(domain_outcomes),
            "business_outcomes": dict(Counter(r["outcome"] for r in rows)),
            "identity_labels": dict(Counter(r["identity_label"] for r in rows)), "verified": verified,
            "outreach_eligible": sum(r["outreach_eligible"] == "yes" for r in rows),
            "phone_sources": dict(Counter(r["phone_source"] for r in rows if r["phone_source"])),
            "pass": verified >= PASS_VERIFIED, "output": str(out_csv), "domain_log": str(domains_csv)}


if __name__ == "__main__":
    print(run_reverse_lookup_sample(DATA_DIR / "leads" / "2026-11_reverse_lookup_sample_v1.csv",
                                    DATA_DIR / "leads" / "2026-11_reverse_lookup_sample_domains_v1.csv",
                                    fetch_hvac_listings(), load_leads(), load_statewide_numbers()))
