"""No network: the identity label rule from CONTEXT.md, and a guard that every reason the code emits has a label."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads.identity_label import UNRESOLVED, UNVERIFIED, VERIFIED, identity_label, may_go_to_outreach

LEADS = Path(__file__).resolve().parents[1] / "src" / "leads"


@pytest.mark.parametrize("outcome, label", [
    ("confirmed", VERIFIED), ("no_tel_phone", VERIFIED),
    ("robots_blocked", UNVERIFIED),
    ("name_mismatch", UNRESOLVED), ("fetch_failed", UNRESOLVED), ("redirect_off_site", UNRESOLVED),
    ("no_place_none", UNRESOLVED), ("no_place_zip", UNRESOLVED), ("no_place_texas", UNRESOLVED),
    ("no_website", UNRESOLVED), ("no_match", UNRESOLVED), ("places_budget", UNRESOLVED),
    ("licence_name_mismatch", UNRESOLVED), ("many_licences", UNRESOLVED), ("licence_on_many_sites", UNRESOLVED),
])
def test_label_per_context_md(outcome, label):
    assert identity_label(outcome) == label


@pytest.mark.parametrize("outcome", ["no_place", "no_place_name", "", "something_new"])
def test_unknown_or_retired_outcome_is_an_error(outcome):
    with pytest.raises(ValueError, match="no identity label"):
        identity_label(outcome)


@pytest.mark.parametrize("label, allowed", [(VERIFIED, True), (UNVERIFIED, False), (UNRESOLVED, False), ("", False)])
def test_only_verified_rows_may_go_to_outreach(label, allowed):
    assert may_go_to_outreach({"identity_label": label}) is allowed
    assert may_go_to_outreach({}) is False


def test_every_reason_the_code_emits_has_a_label():
    source = "\n".join(p.read_text() for p in LEADS.glob("*.py") if p.name != "identity_label.py")
    emitted = set(re.findall(r'SiteUnreadable\("(\w+)"', source))
    emitted |= set(re.findall(r'outcomes\.append\(\(\w+, "(\w+)"', source))
    emitted |= set(re.findall(r'"(no_place_\w+|no_match|no_website|confirmed|no_tel_phone|name_mismatch|licence_name_mismatch|many_licences|licence_on_many_sites)"', source))
    assert {"robots_blocked", "fetch_failed", "redirect_off_site", "places_budget", "no_place_none",
            "licence_name_mismatch", "many_licences", "licence_on_many_sites"} <= emitted
    for outcome in emitted:
        identity_label(outcome)  # raises if a reason has no label
