"""No network, no real file: SAMPLE rows in the Census ZCTA-to-County layout (pipe-delimited, byte-order mark)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads.dfw_filter import DFW_COUNTIES
from leads.zip_county import DFW_COUNTY_FIPS, load_zcta_counties, zip_in_county, zip_in_texas

HEADER = ("OID_ZCTA5_20|GEOID_ZCTA5_20|NAMELSAD_ZCTA5_20|AREALAND_ZCTA5_20|AREAWATER_ZCTA5_20|MTFCC_ZCTA5_20|"
          "CLASSFP_ZCTA5_20|FUNCSTAT_ZCTA5_20|OID_COUNTY_20|GEOID_COUNTY_20|NAMELSAD_COUNTY_20|AREALAND_COUNTY_20|"
          "AREAWATER_COUNTY_20|MTFCC_COUNTY_20|CLASSFP_COUNTY_20|FUNCSTAT_COUNTY_20|AREALAND_PART|AREAWATER_PART")


def row(zcta, county_fips, county_name, land_part):
    return f"1|{zcta}|ZCTA5 {zcta}|1000|0|G6350|B5|S|2|{county_fips}|{county_name}|9000|10|G4020|H1|A|{land_part}|0"


SAMPLE_ROWS = [
    row("75201", "48113", "Dallas County", 3000),       # Dallas only
    row("76132", "48439", "Tarrant County", 2000),      # Tarrant only
    row("75007", "48113", "Dallas County", 500),        # crosses Dallas / Denton / Collin
    row("75007", "48121", "Denton County", 4000),
    row("75007", "48085", "Collin County", 100),
    row("75189", "48397", "Rockwall County", 0),        # water-only overlap: not a link
    row("", "48257", "Kaufman County", 70000),          # county area outside any ZCTA: skipped
    row("75401", "48231", "Hunt County", 8000),         # Texas, outside the 9 DFW counties
    row("74103", "40143", "Tulsa County", 6000),        # not Texas
]


@pytest.fixture
def zcta_counties(tmp_path):
    path = tmp_path / "zcta_county_2020.txt"
    path.write_text("﻿" + "\n".join([HEADER] + SAMPLE_ROWS) + "\n", encoding="utf-8")
    return load_zcta_counties(path)


def test_loader_reads_the_real_header_and_skips_empty_zcta_rows(zcta_counties):
    assert zcta_counties == {"75201": {"48113"}, "76132": {"48439"}, "75007": {"48113", "48121", "48085"},
                             "75401": {"48231"}, "74103": {"40143"}}
    assert "" not in zcta_counties


def test_zip_in_its_county_is_accepted(zcta_counties):
    assert zip_in_county("75201", "Dallas", zcta_counties) is True
    assert zip_in_county("76132", "TARRANT", zcta_counties) is True  # TDLR county case doesn't matter


def test_zip_only_in_another_dfw_county_is_rejected(zcta_counties):
    assert zip_in_county("75201", "Tarrant", zcta_counties) is False
    assert zip_in_county("76132", "Dallas", zcta_counties) is False


@pytest.mark.parametrize("county", ["Dallas", "Denton", "Collin"])
def test_multi_county_zip_is_accepted_for_each_county(zcta_counties, county):
    assert zip_in_county("75007", county, zcta_counties) is True


def test_zip_plus_four_is_trimmed(zcta_counties):
    assert zip_in_county("75201-1234", "Dallas", zcta_counties) is True


@pytest.mark.parametrize("zip_code", [None, "", "7520", "752011", "75201-12", "ABCDE", "75999"])
def test_missing_malformed_or_unknown_zip_is_rejected(zcta_counties, zip_code):
    assert zip_in_county(zip_code, "Dallas", zcta_counties) is False


def test_water_only_overlap_and_unknown_county_are_rejected(zcta_counties):
    assert zip_in_county("75189", "Rockwall", zcta_counties) is False
    assert zip_in_county("75201", "Harris", zcta_counties) is False
    assert zip_in_county("75201", None, zcta_counties) is False


@pytest.mark.parametrize("zip_code, in_texas", [
    ("75201", True), ("75401", True), ("75401-0001", True),   # a DFW county, Hunt County, ZIP+4
    ("74103", False),                                          # Oklahoma
    ("75189", False), ("75999", False), (None, False), ("", False), ("7540", False),  # water-only, unknown, bad
])
def test_zip_in_any_texas_county(zcta_counties, zip_code, in_texas):
    assert zip_in_texas(zip_code, zcta_counties) is in_texas


def test_fips_map_covers_exactly_the_dfw_counties():
    assert set(DFW_COUNTY_FIPS) == DFW_COUNTIES
    assert all(f.startswith("48") and len(f) == 5 for f in DFW_COUNTY_FIPS.values())
