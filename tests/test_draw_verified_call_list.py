"""No network, no real data: SAMPLE overlap and leads files for the v2 call list (docs/decisions/call-list-plan.md)."""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from draw_verified_call_list import draw_verified_call_list, write_verified_call_list  # noqa: E402

OVERLAP_COLUMNS = ["licence_number", "business_name", "group", "reverse_phone", "reverse_phone_source", "auto_phone",
                   "entity_flag", "outreach_eligible"]
LEAD_COLUMNS = ["business_name", "licence_holder", "licence_number", "expiry_date", "county", "entity_flag"]


def write(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def sample_files(tmp_path):
    overlap = [  # licence, phone, phone source, auto phone, outreach_eligible in the overlap file
        ("00101", "214-555-0101", "site", "", "yes"),
        ("102", "214-555-0102", "Foursquare", "", "yes"),
        ("103", "214-555-0103", "site", "", "no"),
        ("104", "", "", "972-555-0104", "unknown"),  # v3 auto only; leads file says likely_corporate
        ("105", "", "", "972-555-0105", "unknown"),  # v3 auto only; leads file says unconfirmed
        ("106", "817-555-0106", "site", "", "yes"),
    ]
    flags = {"101": "likely_corporate", "102": "likely_corporate", "103": "unconfirmed", "104": "likely_corporate",
             "105": "unconfirmed", "106": "likely_corporate", "107": "likely_corporate"}  # 107: never verified
    o = write(tmp_path / "overlap.csv", OVERLAP_COLUMNS, [
        {"licence_number": n, "business_name": f"SAMPLE {n} LLC", "group": "", "reverse_phone": p,
         "reverse_phone_source": s, "auto_phone": a, "entity_flag": "", "outreach_eligible": e}
        for n, p, s, a, e in overlap])
    leads = write(tmp_path / "leads.csv", LEAD_COLUMNS, [
        {"business_name": f"SAMPLE {n} LLC", "licence_holder": "SAMPLE PERSON", "licence_number": n,
         "expiry_date": "06/03/2027", "county": "Dallas", "entity_flag": flag} for n, flag in flags.items()])
    return o, leads


def test_only_verified_eligible_businesses_are_drawn(tmp_path):
    rows, summary = draw_verified_call_list(*sample_files(tmp_path))
    assert [r["licence_number"] for r in rows] == ["101", "102", "104", "106"]
    assert summary["judged"] == {"eligible": 3, "not_eligible": 1, "eligible_was_unknown": 1,
                                 "not_eligible_was_unknown": 1}
    assert {r["licence_number"]: r["business_phone"] for r in rows}["104"] == "972-555-0104"


def test_same_seed_gives_the_same_list(tmp_path):
    files = sample_files(tmp_path)
    assert draw_verified_call_list(*files, seed=20261102) == draw_verified_call_list(*files, seed=20261102)
    assert sorted(r["time_band"] for r in draw_verified_call_list(*files)[0]) == [
        "afternoon", "evening", "morning", "morning"]


def test_foursquare_phones_are_flagged(tmp_path):
    rows, _ = draw_verified_call_list(*sample_files(tmp_path))
    assert {r["licence_number"] for r in rows if r["phone_unconfirmed"] == "yes"} == {"102"}


def test_output_has_no_email_or_holder_columns_and_is_never_overwritten(tmp_path):
    rows, _ = draw_verified_call_list(*sample_files(tmp_path))
    out = tmp_path / "call_list_v2.csv"
    write_verified_call_list(rows, out)
    with out.open(newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert not {"contact_email", "email_source_url", "licence_holder"} & set(header) and "phone_unconfirmed" in header
    assert all("@" not in value for row in rows for value in row.values())
    try:
        write_verified_call_list(rows, out)
    except FileExistsError:
        pass
    else:
        raise AssertionError("the call sheet was overwritten")
