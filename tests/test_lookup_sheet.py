import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from signals.lookup_sheet import LOOKUP_COLUMNS, check_lookup_sheet, create_lookup_sheet


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def call_list(tmp_path):
    rows = [{"licence_number": f"S{i}", "business_name": f"SAMPLE HVAC {i} LLC", "county": "Dallas", "time_band": "morning"}
            for i in range(3)]
    return write_csv(tmp_path / "call_list.csv", ["licence_number", "business_name", "county", "time_band"], rows)


def lookup(**values):
    row = {c: "" for c in LOOKUP_COLUMNS} | {"licence_number": "S1", "business_name": "SAMPLE HVAC 1 LLC", "county": "Dallas"}
    return row | values


GOOD = dict(website_url="https://www.sample-hvac.example", business_phone="214-555-0100",
            phone_source_url="https://sample-hvac.example/contact", form_url="https://sample-hvac.example/contact",
            contact_email="info@sample-hvac.example", email_source_url="https://www.sample-hvac.example/about",
            lookup_date="2026-10-28", lookup_initials="XX")


def problems(tmp_path, *rows):
    return [p["problem"] for p in check_lookup_sheet(write_csv(tmp_path / "lookup.csv", LOOKUP_COLUMNS, list(rows)))]


def test_sheet_has_one_empty_row_per_business(tmp_path):
    out = tmp_path / "logs" / "lookup.csv"
    assert create_lookup_sheet(call_list(tmp_path), out) == 3
    with out.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert reader.fieldnames == LOOKUP_COLUMNS
    assert [r["licence_number"] for r in rows] == ["S0", "S1", "S2"]
    assert all(r[c] == "" for r in rows for c in LOOKUP_COLUMNS[3:])


def test_overwrite_is_refused(tmp_path):
    out = tmp_path / "lookup.csv"
    out.write_text("filled in by hand\n")
    with pytest.raises(FileExistsError):
        create_lookup_sheet(call_list(tmp_path), out)
    assert out.read_text() == "filled in by hand\n"


def test_complete_row_and_untouched_row_pass(tmp_path):
    assert problems(tmp_path, lookup(**GOOD), lookup()) == []


@pytest.mark.parametrize("blank, expected", [
    ("phone_source_url", "business_phone has no phone_source_url"),
    ("email_source_url", "contact_email has no email_source_url"),
    ("lookup_date", "lookup_date missing"),
])
def test_missing_source_is_flagged(tmp_path, blank, expected):
    assert problems(tmp_path, lookup(**GOOD | {blank: ""})) == [expected]


def test_source_off_the_business_website_is_flagged(tmp_path):
    found = problems(tmp_path, lookup(**GOOD | {"phone_source_url": "https://www.google.com/maps/place/sample"}))
    assert found == ["phone_source_url is not on the business's website (https://www.sample-hvac.example)"]


def test_value_without_any_website_is_flagged(tmp_path):
    found = problems(tmp_path, lookup(business_phone="214-555-0100", phone_source_url="https://sample-hvac.example",
                                      lookup_date="2026-10-28"))
    assert found == ["phone_source_url is not on the business's website (website_url missing)"]


def test_no_website_with_phone_is_flagged(tmp_path):
    found = problems(tmp_path, lookup(website_url="no_website", business_phone="214-555-0100", lookup_date="2026-10-28"))
    assert found == ["business_phone filled in but website_url is no_website"]


def test_no_website_alone_passes_but_needs_a_date(tmp_path):
    assert problems(tmp_path, lookup(website_url="no_website", lookup_date="2026-10-28")) == []
    assert problems(tmp_path, lookup(website_url="no_website")) == ["lookup_date missing"]


def test_report_gives_line_and_licence(tmp_path):
    path = write_csv(tmp_path / "lookup.csv", LOOKUP_COLUMNS, [lookup(**GOOD), lookup(**GOOD | {"phone_source_url": ""})])
    assert check_lookup_sheet(path) == [
        {"line": 3, "licence_number": "S1", "problem": "business_phone has no phone_source_url"},
    ]
