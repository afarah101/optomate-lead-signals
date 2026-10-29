import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads.dfw_filter import LEAD_COLUMNS, filter_active_dfw_contractors, remove_duplicate_licences, to_lead

TODAY = date(2026, 10, 27)


def licence(number, county="DALLAS", expiry="06/03/2027"):
    return {"license_number": number, "license_type": "A/C Contractor", "business_county": county,
            "license_expiration_date_mmddccyy": expiry, "business_name": f"Biz {number}"}


def test_out_of_area_counties_are_removed():
    kept = filter_active_dfw_contractors(
        [licence("1", "HARRIS"), licence("2", "TARRANT"), licence("3", ""), licence("4", "OUT OF STATE"), licence("5", "parker")],
        TODAY,
    )
    assert [l["license_number"] for l in kept] == ["2", "5"]


def test_inactive_licences_are_removed():
    kept = filter_active_dfw_contractors(
        [licence("1", expiry="11/07/2025"), licence("2", expiry="10/27/2026"), licence("3", expiry=""), licence("4")],
        TODAY,
    )
    assert [l["license_number"] for l in kept] == ["2", "4"]


def test_duplicate_licence_numbers_are_removed():
    unique = remove_duplicate_licences([licence("1"), licence("2"), licence("1", "COLLIN")])
    assert [(l["license_number"], l["business_county"]) for l in unique] == [("1", "DALLAS"), ("2", "DALLAS")]


def test_lead_has_every_output_column():
    lead = to_lead(licence("1"), "https://data.texas.gov/x", TODAY)
    assert list(lead) == LEAD_COLUMNS == [
        "business_name", "licence_number", "licence_type", "licence_status", "expiry_date", "address", "city", "county",
        "source", "retrieved_on",
    ]
    assert lead["county"] == "Dallas" and lead["licence_status"] == "" and lead["retrieved_on"] == "2026-10-27"


def test_lead_never_holds_the_licence_holder_name():
    lead = to_lead(licence("1") | {"owner_name": "DOE, JANE Q"}, "https://data.texas.gov/x", TODAY)
    assert "licence_holder" not in lead and "DOE, JANE Q" not in lead.values()
