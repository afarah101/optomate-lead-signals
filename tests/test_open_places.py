"""No network: SAMPLE Overture-shaped records, and SAMPLE HTML read by the unchanged own-site reader via a fake fetcher."""

import csv
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads import open_places
from leads.open_places import (
    OUT_COLUMNS, build_name_index, confirm_on_own_site, has_dfw_zip, load_queued_businesses, matching_records,
    measure_open_places_recovery,
)
from leads.place_match import shares_main_words
from leads.website_contacts import Response, SiteUnreadable, read_own_site_contacts

SITE = "https://www.sample-cooling.example/"
QUEUE_COLUMNS = ["licence_number", "business_name", "county", "place_id", "reason", "website_url", "form_url"]


def record(name, website=SITE, postcode="75201", region="TX", confidence=0.9, id_="ovt-1", datasets=("meta",)):
    return {"id": id_, "name": name, "confidence": confidence, "websites": [website] if website else [],
            "addresses": [{"region": region, "postcode": postcode}], "datasets": list(datasets)}


def html(title, body=""):
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def reader(pages):
    """The real read_own_site_contacts over local SAMPLE pages, so the existing check is what decides."""
    def get(url):
        if url.endswith("/robots.txt"):
            return Response(404, url, "", "")
        return Response(200, url, "text/html", pages[url]) if url in pages else Response(404, url, "", "")
    return lambda url, licence_number=None: read_own_site_contacts(url, get=get, licence_number=licence_number)


BUSINESS = {"licence_number": "113684", "business_name": "SAMPLE COOLING LLC", "county": "DALLAS"}
PHONE_LINK = '<a href="tel:+12145550100">Call</a>'


# Name normalisation

def test_name_normalisation_matches_the_existing_main_words_rule():
    records = [record("Sample Cooling"), record("S.A.M.P.L.E. Coolings & Co"), record("Sample Plumbing")]
    index = build_name_index(records)
    # dots removed, & and Co dropped, plural = singular
    assert [r["name"] for r in matching_records("SAMPLE COOLING, LLC", records, index)] == [
        "Sample Cooling", "S.A.M.P.L.E. Coolings & Co"]


def test_matching_is_the_same_test_as_shares_main_words():
    names = ["Sample Cooling", "Sample Cooling & Heating", "Cooling Sample Inc", "Sample", "Sample Heating", ""]
    records = [record(n) for n in names]
    index = build_name_index(records)
    for licence_name in ["SAMPLE COOLING LLC", "SAMPLE LLC", "SAMPLE HEATING AND COOLING", "LLC"]:
        expected = [r["name"] for r in records if shares_main_words(licence_name, r["name"])]
        assert [r["name"] for r in matching_records(licence_name, records, index)] == expected


# ZIP

@pytest.mark.parametrize("region,postcode,ok", [
    ("TX", "75201", True), ("TX", "76132-1234", True), ("Texas", "76033", True),
    ("TX", "73460", False), ("OK", "75201", False), ("", "75201", False), (None, "75201", False),
    ("TX", None, False), ("TX", "7520", False),
])
def test_dfw_zip_rule(region, postcode, ok):
    assert has_dfw_zip(record("Sample Cooling", region=region, postcode=postcode)) is ok


def test_a_name_match_without_a_dfw_zip_is_not_matched():
    records = [record("Sample Cooling", postcode="73460")]
    assert matching_records("SAMPLE COOLING LLC", records, build_name_index(records)) == []


# The existing own-site check is required

def test_matched_record_is_not_confirmed_when_the_site_fails_the_existing_check():
    read = reader({SITE: html("Someone Else HVAC", PHONE_LINK)})
    result = confirm_on_own_site(BUSINESS, [record("Sample Cooling")], read)
    assert result["outcome"] == "name_mismatch"
    assert not result.get("website_url") and not result.get("business_phone")


def test_site_confirmed_by_licence_number():
    read = reader({SITE: html("Best HVAC in Dallas", PHONE_LINK + " TACLA00113684C")})
    result = confirm_on_own_site(BUSINESS, [record("Sample Cooling")], read)
    assert (result["outcome"], result["match_by"], result["business_phone"]) == ("confirmed", "licence", "214-555-0100")
    assert result["source_record_id"] == "ovt-1" and result["source_datasets"] == "meta"


def test_site_confirmed_by_site_name():
    read = reader({SITE: html("Sample Cooling | Dallas", PHONE_LINK)})
    assert confirm_on_own_site(BUSINESS, [record("Sample Cooling")], read)["match_by"] == "name"


def test_confirmed_site_without_a_phone_stops_and_is_no_tel_phone():
    other = "https://other.example/"
    calls = []
    read = reader({SITE: html("Sample Cooling"), other: html("Sample Cooling", PHONE_LINK)})
    result = confirm_on_own_site(BUSINESS, [record("Sample Cooling", confidence=0.9),
                                            record("Sample Cooling", website=other, confidence=0.5)],
                                 lambda url, licence_number=None: calls.append(url) or read(url, licence_number))
    assert result["outcome"] == "no_tel_phone" and calls == [SITE]


def test_sites_are_tried_by_confidence_deduplicated_and_capped():
    calls = []

    def read(url, licence_number=None):
        calls.append(url)
        raise SiteUnreadable("fetch_failed")
    matched = [record("Sample Cooling", website=f"https://s{i}.example/", confidence=i / 10) for i in range(8)]
    matched.append(record("Sample Cooling", website="https://s7.example/", confidence=0.95))
    result = confirm_on_own_site(BUSINESS, matched, read)
    assert calls == ["https://s7.example/"] + [f"https://s{i}.example/" for i in (6, 5, 4, 3)]
    assert result["outcome"] == "fetch_failed"


def test_no_match_and_no_website_outcomes():
    assert confirm_on_own_site(BUSINESS, [], reader({}))["outcome"] == "no_match"
    assert confirm_on_own_site(BUSINESS, [record("Sample Cooling", website=None)], reader({}))["outcome"] == "no_website"


# The licence holder name is never used

def test_licence_holder_name_is_never_read_or_matched(tmp_path):
    queue = tmp_path / "queue.csv"
    with queue.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_COLUMNS + ["licence_holder"])
        writer.writeheader()
        writer.writerow({"licence_number": "113684", "business_name": "SAMPLE COOLING LLC", "county": "DALLAS",
                         "reason": "name_mismatch", "licence_holder": "DOE, JANE Q"})
    businesses = load_queued_businesses(queue)
    assert all("licence_holder" not in b for b in businesses)
    records = [record("Jane Doe Air Conditioning")]  # a record named after the holder must not match
    out = tmp_path / "out.csv"
    summary = measure_open_places_recovery(queue, out, records, reader({SITE: html("Jane Doe A/C")}))
    assert summary["outcomes"] == {"no_match": 1}
    assert "DOE" not in out.read_text().upper() and "JANE" not in out.read_text().upper()


# v1–v4 files are untouched; output never overwritten

def _queue_file(tmp_path, rows):
    path = tmp_path / "2026-11_manual_queue_v3.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_COLUMNS)
        writer.writeheader()
        writer.writerows({c: "" for c in QUEUE_COLUMNS} | r for r in rows)
    return path


def test_measurement_writes_only_its_own_file_and_never_overwrites(tmp_path):
    queue = _queue_file(tmp_path, [BUSINESS, {"licence_number": "2", "business_name": "NOBODY LLC", "county": "DALLAS"}])
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
    out = tmp_path / "2026-11_open_places_test.csv"
    summary = measure_open_places_recovery(queue, out, [record("Sample Cooling")],
                                           reader({SITE: html("Sample Cooling", PHONE_LINK)}), today=date(2026, 10, 28))
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir() if p != out}
    assert before == after
    rows = list(csv.DictReader(out.open()))
    assert list(rows[0]) == OUT_COLUMNS and len(rows) == 2
    assert rows[0]["website_url"] == SITE and rows[0]["lookup_date"] == "2026-10-28"
    assert rows[1]["outcome"] == "no_match" and rows[1]["website_url"] == ""
    assert summary["confirmed_on_own_site"] == 1 and summary["new_phones"] == 1
    with pytest.raises(FileExistsError):
        measure_open_places_recovery(queue, out, [], reader({}))


def test_main_reads_only_the_v3_queue_and_writes_only_its_own_file():
    main = Path(open_places.__file__).read_text().split('if __name__ == "__main__":')[1]
    assert set(re.findall(r"2026-11_\w+\.csv", main)) == {"2026-11_manual_queue_v3.csv", "2026-11_open_places_test.csv"}


def test_overture_query_never_selects_contact_columns_overture_holds():
    source = Path(open_places.__file__).read_text()
    query = re.search(r"SELECT(.*?)FROM", source, re.S).group(1)
    assert not re.search(r"emails|socials|phones", query)
