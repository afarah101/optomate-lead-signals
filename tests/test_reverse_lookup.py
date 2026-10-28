"""No network, no real data: SAMPLE listings, leads and sites for the reverse lookup rules (docs/decisions/reverse-lookup.md)."""

import csv
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads.website_contacts import Response, SiteUnreadable, read_own_site_contacts
from leads.reverse_lookup import (
    BUSINESS_COLUMNS, crawlable_domains, domain_of, draw_sample, judge_site, load_leads, run_reverse_lookup_sample,
)


def listing(fid, name, website, tel=None):
    return {"fsq_place_id": fid, "name": name, "website": website, "tel": tel}


def lead(number, name, entity_flag="likely_corporate", county="Dallas"):
    return {"licence_number": number, "business_name": name, "county": county, "entity_flag": entity_flag}


def site(site_name="", numbers=(), phone="", url="https://sample.example/"):
    return {"website_url": url, "site_name": site_name, "phone": phone, "phone_source_url": url if phone else "",
            "form_url": "", "licence_shown": False, "licence_numbers": sorted(numbers)}


LEADS = {"11111": lead("11111", "SAMPLE COOLING LLC"), "22222": lead("22222", "OTHER AIR INC"),
         "33333": lead("33333", "SAMPLE COOLING LLC", county="Tarrant"),
         "44444": lead("44444", "SOLO HEATING", entity_flag="unconfirmed")}
STATEWIDE = {"11111", "22222", "33333", "44444", "55555"}


@pytest.mark.parametrize("website, domain", [
    ("https://www.Sample-Cooling.example/dallas?x=1", "sample-cooling.example"),
    ("http://dealer.frigidaire.net/abc", "dealer.frigidaire.net"),
    ("not a url", ""),
])
def test_domain_of(website, domain):
    assert domain_of(website) == domain


def test_skip_rules_and_kept_domains():
    kept, skipped = crawlable_domains([
        listing("a", "Carrier", "https://www.carrier.com/dealer/1"),                  # manufacturer
        listing("b", "Bob's Air", "http://dealer.frigidaire.net/bob"),                # manufacturer subdomain
        listing("c", "Caplinger Air", "https://caplinger.rheemteam.net/"),            # dealer's own page: kept
        listing("d", "Some Pro", "https://www.homeadvisor.com/rated.SomePro"),        # platform
        listing("e", "Alpha Heating", "https://network.example/alpha"),               # dealer network
        listing("f", "Beta Cooling", "https://network.example/beta"),
        listing("g", "Accurate Air Fort Worth", "https://accurateair.example/fw"),    # multi-location: kept once
        listing("h", "Accurate Air Dallas", "https://accurateair.example/dallas"),
        listing("i", "Solo HVAC", "https://solo.example/"),
        listing("j", "No Host", "solo.example"),
    ])
    assert sorted(kept) == ["accurateair.example", "caplinger.rheemteam.net", "solo.example"]
    assert [l["fsq_place_id"] for l in kept["accurateair.example"]] == ["h", "g"]  # first website in sorted order
    assert skipped == {"manufacturer": 2, "platform": 1, "dealer_network": 1, "no_domain": 1}


def test_lookalike_of_a_manufacturer_is_not_skipped():
    kept, _ = crawlable_domains([listing("a", "Mycarrier Air", "https://mycarrier.com/")])
    assert list(kept) == ["mycarrier.com"]


def test_sample_is_seeded_and_capped():
    domains = [f"d{i}.example" for i in range(50)]
    first = draw_sample(domains, size=10)
    assert first == draw_sample(reversed(domains), size=10) and len(set(first)) == 10 and set(first) <= set(domains)
    assert sorted(draw_sample(domains[:3], size=10)) == domains[:3]


@pytest.mark.parametrize("the_site, outcome, found", [
    (site("Sample Cooling | Dallas"), "licence_not_shown", []),
    (site("x", ["99999"]), "licence_unknown", []),
    (site("x", ["55555", "99999"]), "licence_not_in_leads", []),
    (site("Sample Cooling", ["11111"], phone="214-555-0100"), "confirmed", [("11111", "confirmed", True)]),
    (site("Sample Cooling", ["11111"]), "no_tel_phone", [("11111", "no_tel_phone", True)]),
    (site("Franchise Brand HVAC", ["11111"], phone="214-555-0100"), "licence_name_mismatch",
     [("11111", "licence_name_mismatch", False)]),
    (site("Sample Cooling", ["11111", "22222"]), "many_licences",
     [("11111", "many_licences", True), ("22222", "many_licences", False)]),
    (site("Sample Cooling", ["11111", "33333"]), "no_tel_phone",     # two leads, same name: each judged
     [("11111", "no_tel_phone", True), ("33333", "no_tel_phone", True)]),
])
def test_join_requires_licence_and_name(the_site, outcome, found):
    domain_outcome, findings = judge_site(the_site, LEADS, STATEWIDE)
    assert domain_outcome == outcome
    assert [(f["lead"]["licence_number"], f["outcome"], f["name_also_matches"]) for f in findings] == found


def test_year_or_phone_after_the_licence_is_not_read_as_another_lead():
    # A copyright year and an area code that are also DFW licence numbers must not make the site many_licences.
    leads = LEADS | {"2022": lead("2022", "YEAR NUMBER LLC"), "972": lead("972", "AREA CODE LLC")}
    markup = ("<html><head><title>Sample Cooling</title></head><body>"
              "<footer>TACLA00011111C &copy; 2022 Call 972-555-0100</footer></body></html>")

    def get(url):
        return Response(404, url, "", "") if url.endswith("/robots.txt") else Response(200, url, "text/html", markup)

    the_site = read_own_site_contacts("https://sample.example/", get=get)
    assert the_site["licence_numbers"] == ["11111"]
    assert judge_site(the_site, leads, STATEWIDE)[0] == "no_tel_phone"


def test_load_leads_never_reads_the_licence_holder(tmp_path):
    path = tmp_path / "leads.csv"
    path.write_text("business_name,licence_holder,licence_number,county,entity_flag\n"
                    "SAMPLE COOLING LLC,SAMPLE PERSON,11111,Dallas,likely_corporate\n", encoding="utf-8")
    assert load_leads(path) == {"11111": lead("11111", "SAMPLE COOLING LLC")}


def run(tmp_path, listings, sites, **kwargs):
    def read_site(url):
        if isinstance(sites[url], Exception):
            raise sites[url]
        return sites[url]

    out, log = tmp_path / "out.csv", tmp_path / "domains.csv"
    report = run_reverse_lookup_sample(out, log, listings, LEADS, STATEWIDE, read_site=read_site,
                                       today=date(2026, 11, 2), **kwargs)
    with out.open() as f, log.open() as g:
        return report, list(csv.DictReader(f)), list(csv.DictReader(g))


def test_sample_run_end_to_end(tmp_path):
    listings = [
        listing("a", "Sample Cooling", "https://sample.example/", tel="+1 214-555-0199"),
        listing("b", "Other Air", "https://other.example/"),
        listing("c", "Solo Heating", "https://solo.example/"),
        listing("d", "Old Sample", "https://old-sample.example/"),
        listing("e", "Blocked Co", "https://blocked.example/"),
        listing("f", "Trane", "https://trane.com/"),
    ]
    sites = {
        "https://sample.example/": site("Sample Cooling", ["11111"], url="https://sample.example/"),
        "https://other.example/": site("Other Air Inc", ["22222"], phone="972-555-0101", url="https://other.example/"),
        "https://solo.example/": site("Solo Heating", ["44444"], phone="817-555-0102", url="https://solo.example/"),
        "https://old-sample.example/": site("Brand X", ["33333"], url="https://old-sample.example/"),
        "https://blocked.example/": SiteUnreadable("robots_blocked"),
    }
    report, rows, domains = run(tmp_path, listings, sites)
    by_licence = {r["licence_number"]: r for r in rows}
    assert set(rows[0]) == set(BUSINESS_COLUMNS) and "licence_holder" not in rows[0]
    assert {"outcome": "no_tel_phone", "identity_label": "verified", "outreach_eligible": "yes",
            "business_phone": "214-555-0199", "phone_source": "Foursquare", "match_by": "licence"}.items() <= by_licence["11111"].items()
    assert by_licence["22222"]["phone_source"] == "site" and by_licence["22222"]["outreach_eligible"] == "yes"
    assert by_licence["44444"]["identity_label"] == "verified" and by_licence["44444"]["outreach_eligible"] == "no"
    assert {"outcome": "licence_name_mismatch", "identity_label": "unresolved", "name_also_matches": "no",
            "business_phone": "", "outreach_eligible": "no"}.items() <= by_licence["33333"].items()
    assert {d["domain"]: d["outcome"] for d in domains}["blocked.example"] == "robots_blocked"
    assert report["skipped"] == {"manufacturer": 1} and report["sampled"] == 5 and report["verified"] == 3
    assert report["pass"] is False


def test_same_licence_on_two_sites_is_unresolved(tmp_path):
    listings = [listing("a", "Sample Cooling", "https://one.example/"), listing("b", "Sample Cooling", "https://two.example/")]
    sites = {u: site("Sample Cooling", ["11111"], phone="214-555-0100", url=u) for u in ("https://one.example/", "https://two.example/")}
    _, rows, domains = run(tmp_path, listings, sites)
    assert [(r["licence_number"], r["outcome"], r["identity_label"], r["sites_found"], r["business_phone"]) for r in rows] == [
        ("11111", "licence_on_many_sites", "unresolved", "2", "")]
    assert [d["outcome"] for d in domains] == ["confirmed", "confirmed"]


def test_outputs_are_never_overwritten(tmp_path):
    (tmp_path / "domains.csv").write_text("keep")
    with pytest.raises(FileExistsError):
        run(tmp_path, [], {})
    assert (tmp_path / "domains.csv").read_text() == "keep" and not (tmp_path / "out.csv").exists()
