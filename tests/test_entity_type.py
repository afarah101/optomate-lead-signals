import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads.entity_type import flag_likely_corporate_entity


@pytest.mark.parametrize("name", [
    "3 PILLARS MECHANICAL, LLC", "ACME AIR INC", "ACME AIR INC.", "ACME AIR INCORPORATED", "ACME CORP",
    "ACME CORPORATION", "ACME LTD", "SMITH & JONES LLP", "COOL AIR (LLC)",
])
def test_corporate_suffix_as_whole_word(name):
    assert flag_likely_corporate_entity(name) == "likely_corporate"


@pytest.mark.parametrize("name", [
    "INCREDIBLE PLUMBING", "CORPUS CHRISTI AIR", "HELP AIR", "LLCOOL HEATING", "ALPHA LTDX", "INCAIR", "SCOTT A TOMLIN",
])
def test_suffix_inside_a_word_does_not_match(name):
    assert flag_likely_corporate_entity(name) == "unconfirmed"


@pytest.mark.parametrize("name", ["acme air llc", "Acme Air Inc", "acme Corp"])
def test_any_case(name):
    assert flag_likely_corporate_entity(name) == "likely_corporate"


@pytest.mark.parametrize("name", ["ACME AIR L.L.C.", "ACME AIR L.L.C", "acme air l.l.c.", "ACME AIR, L.L.C., DALLAS"])
def test_punctuated_llc(name):
    assert flag_likely_corporate_entity(name) == "likely_corporate"


@pytest.mark.parametrize("name", ["", "   ", None])
def test_empty_name_is_unconfirmed(name):
    assert flag_likely_corporate_entity(name) == "unconfirmed"


@pytest.mark.parametrize("name", ["ACME HOLDINGS LP", "ACME AIR, LP", "acme air lp"])
def test_lp_alone_is_not_corporate(name):
    # LP removed 2026-10-29 (data-sources.md change log); LLP and LP treatment: TO CONFIRM with adviser.
    assert flag_likely_corporate_entity(name) == "unconfirmed"
