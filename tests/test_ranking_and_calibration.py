import csv
import random
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calibration.select_test_groups import NotEnoughEligibleLeads, select_calibration_groups
from ranking.hot_lead_score import lead_band, rank_dfw_leads, score_contact_signals

CALL_COLUMNS = ["licence_number", "business_name", "call_date", "call_time_local", "time_band", "result",
                "voicemail_greeting_present", "caller_initials", "stop_requested", "notes"]
FORM_COLUMNS = ["licence_number", "business_name", "form_url", "sent_at_local", "first_reply_at_local",
                "form_reply_hours", "notes"]
LEAD_COLUMNS = ["licence_number", "business_name", "county", "entity_flag"]
DALLAS = ZoneInfo("America/Chicago")
RANKED_AT = datetime(2026, 10, 31, 12, 0, tzinfo=DALLAS)  # every fixture form is well past 72 h


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def lead(licence, entity_flag="likely_corporate"):
    return {"licence_number": licence, "business_name": f"SAMPLE HVAC {licence} LLC", "county": "Dallas",
            "entity_flag": entity_flag}


def call(licence, result="answered_by_person", band="morning", at="10:30", greeting="", stop="no", day="2026-10-05"):
    return {"licence_number": licence, "business_name": f"SAMPLE HVAC {licence} LLC", "call_date": day,
            "call_time_local": at, "time_band": band, "result": result, "voicemail_greeting_present": greeting,
            "caller_initials": "XX", "stop_requested": stop, "notes": ""}


def form(licence, reply="", sent="2026-10-06 09:00"):
    return {"licence_number": licence, "business_name": f"SAMPLE HVAC {licence} LLC", "form_url": "https://example.invalid",
            "sent_at_local": sent, "first_reply_at_local": reply, "form_reply_hours": "", "notes": ""}


def summary(missed_rate=0.0, greeting="", reply=""):
    return {"missed_rate": missed_rate, "voicemail_greeting_present": greeting, "form_reply_hours": reply}


# --- score points ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("row, expected", [
    (summary(), 0),
    (summary(missed_rate=1.0), 1),            # missed call
    (summary(missed_rate=None), 0),           # no valid call, no point
    (summary(greeting="no"), 1),              # no voicemail greeting
    (summary(greeting="yes"), 0),
    (summary(reply="no_reply"), 1),           # form never answered
    (summary(reply=24.1), 1),                 # slower than 24 h
    (summary(reply=24.0), 0),                 # exactly 24 h is not slow
    (summary(reply=""), 0),                   # no form sent, no point
    (summary(missed_rate=1.0, greeting="no", reply="no_reply"), 3),
    ({}, 0),                                  # lead with no signals at all
])
def test_each_score_point(row, expected):
    assert score_contact_signals(row) == expected


@pytest.mark.parametrize("score, band", [(0, "cold"), (1, "middle"), (2, "hot"), (3, "hot")])
def test_band_edges(score, band):
    assert lead_band(score) == band


# --- ranking and eligibility -------------------------------------------------------------------------------------

@pytest.fixture
def ranked(tmp_path, capsys):
    leads = write_csv(tmp_path / "leads.csv", LEAD_COLUMNS, [
        lead("S1"), lead("S2"), lead("S3"), lead("S4", "unconfirmed"), lead("S5"), lead("S6"), lead("S7"), lead("S8"),
    ])
    calls = write_csv(tmp_path / "calls.csv", CALL_COLUMNS, [
        call("S1", "voicemail", band="evening", at="18:30", greeting="no"),  # 2 points from the call
        call("S2"),                                                          # answered: 0 points
        call("S3", "voicemail", band="evening", at="18:30", greeting="no", stop="yes"),  # hot but asked to stop
        call("S4", "no_answer", band="evening", at="18:30", greeting="no"),  # hot but entity unconfirmed
        call("S5", "invalid"),                                               # no valid call this month
        call("S7", "voicemail", band="evening", at="18:30", greeting="no"),
        call("S7", day="2026-10-20", stop="yes"),                            # rejected second call, stop still counts
        call("S8"),                                                          # answered, but no form sent this month
    ])
    forms = write_csv(tmp_path / "forms.csv", FORM_COLUMNS, [
        form(l) for l in ("S1", "S3", "S4", "S5", "S7")
    ] + [form("S2", reply="2026-10-06 11:00")])
    rows = {r["licence_number"]: r for r in rank_dfw_leads(leads, calls, forms, "2026-10", ranked_at=RANKED_AT)}
    return rows, capsys.readouterr().err


def test_hot_and_cold_leads_are_scored_and_eligible(ranked):
    rows, _ = ranked
    assert (rows["S1"]["score"], rows["S1"]["band"], rows["S1"]["eligible"]) == (3, "hot", "yes")
    assert (rows["S2"]["score"], rows["S2"]["band"], rows["S2"]["eligible"]) == (0, "cold", "yes")


def test_do_not_contact_is_never_eligible(ranked):
    rows, _ = ranked
    assert rows["S3"]["band"] == "hot" and rows["S3"]["eligible"] == "no"
    assert rows["S7"]["band"] == "hot" and rows["S7"]["eligible"] == "no"


def test_unconfirmed_entity_is_not_eligible(ranked):
    rows, _ = ranked
    assert rows["S4"]["band"] == "hot" and rows["S4"]["eligible"] == "no"


def test_no_valid_call_is_not_eligible(ranked):
    rows, _ = ranked
    assert rows["S5"]["eligible"] == "no"   # only an invalid call
    assert rows["S6"]["eligible"] == "no"   # never called


def test_no_form_sent_this_month_is_not_eligible(ranked):
    rows, _ = ranked
    assert (rows["S8"]["score"], rows["S8"]["band"], rows["S8"]["eligible"]) == (0, "cold", "no")


def eligibility_when_ranked(tmp_path, sent, ranked_at):
    leads = write_csv(tmp_path / "leads.csv", LEAD_COLUMNS, [lead("S1")])
    calls = write_csv(tmp_path / "calls.csv", CALL_COLUMNS, [call("S1")])
    forms = write_csv(tmp_path / "forms.csv", FORM_COLUMNS, [form("S1", sent=sent)])
    return rank_dfw_leads(leads, calls, forms, "2026-10", ranked_at=ranked_at)[0]["eligible"]


@pytest.mark.parametrize("ranked_at, expected", [
    (datetime(2026, 10, 9, 9, 0, tzinfo=DALLAS), "yes"),   # exactly 72 h after sending
    (datetime(2026, 10, 9, 8, 59, tzinfo=DALLAS), "no"),   # 1 minute short: no_reply is not final yet
    (datetime(2026, 10, 6, 10, 0, tzinfo=DALLAS), "no"),   # sent an hour ago
])
def test_form_must_be_sent_at_least_72_hours_before_ranking(tmp_path, ranked_at, expected):
    assert eligibility_when_ranked(tmp_path, "2026-10-06 09:00", ranked_at) == expected


@pytest.mark.parametrize("ranked_at, expected", [
    (datetime(2026, 11, 2, 2, 0, tzinfo=DALLAS), "yes"),   # 72 real hours: clocks went back an hour on 1 Nov
    (datetime(2026, 11, 2, 1, 59, tzinfo=DALLAS), "no"),
])
def test_72_hour_wait_counts_real_hours_across_daylight_saving_end(tmp_path, ranked_at, expected):
    assert eligibility_when_ranked(tmp_path, "2026-10-30 03:00", ranked_at) == expected


def test_manual_entity_check_on_every_eligible_row_only(ranked):
    rows, _ = ranked
    assert {r["licence_number"] for r in rows.values() if r["manual_entity_check"] == "required"} == {"S1", "S2"}
    assert all((r["eligible"] == "yes") == (r["manual_entity_check"] == "required") for r in rows.values())


def test_ranked_rows_have_the_listed_columns(ranked):
    rows, _ = ranked
    assert list(rows["S1"]) == ["licence_number", "business_name", "county", "entity_flag", "score", "band",
                                "eligible", "manual_entity_check"]


def test_rejected_log_rows_are_reported(ranked):
    _, err = ranked
    assert "call log line 8 rejected" in err and "STOP REQUESTED" in err


# --- calibration groups ------------------------------------------------------------------------------------------

def ranked_pool(hot=20, cold=20, middle=10):
    rows = [{"licence_number": f"H{i:03d}", "band": "hot", "eligible": "yes"} for i in range(hot)]
    rows += [{"licence_number": f"C{i:03d}", "band": "cold", "eligible": "yes"} for i in range(cold)]
    rows += [{"licence_number": f"M{i:03d}", "band": "middle", "eligible": "yes"} for i in range(middle)]
    rows += [{"licence_number": f"X{i:03d}", "band": "hot", "eligible": "no"} for i in range(10)]
    return rows


def test_same_seed_gives_the_same_groups_whatever_the_row_order():
    rows = ranked_pool()
    shuffled = rows[:]
    random.Random(1).shuffle(shuffled)
    assert select_calibration_groups(rows, seed=20261027) == select_calibration_groups(shuffled, seed=20261027)


def test_different_seed_gives_different_groups():
    rows = ranked_pool()
    assert select_calibration_groups(rows, seed=1)["hot"] != select_calibration_groups(rows, seed=2)["hot"]


def test_groups_hold_only_eligible_hot_and_cold_leads():
    groups = select_calibration_groups(ranked_pool(), seed=20261027)
    assert groups["seed"] == 20261027
    assert len(groups["hot"]) == 15 and len(set(groups["hot"])) == 15 and all(l.startswith("H") for l in groups["hot"])
    assert len(groups["cold"]) == 15 and len(set(groups["cold"])) == 15 and all(l.startswith("C") for l in groups["cold"])


def test_selection_is_pinned_for_the_recorded_seed():
    # Guards against a change in Python's random module altering the groups for the seed in calibration-plan.md.
    groups = select_calibration_groups(ranked_pool(hot=5, cold=5, middle=0), seed=20261027, group_size=2)
    assert groups == PINNED_SMALL_SELECTION


@pytest.mark.parametrize("hot, cold", [(14, 20), (20, 14), (0, 0)])
def test_short_band_raises_with_counts_and_never_uses_middle(hot, cold):
    with pytest.raises(NotEnoughEligibleLeads, match=f"have {hot} hot and {cold} cold"):
        select_calibration_groups(ranked_pool(hot=hot, cold=cold, middle=50), seed=20261027)


# Same result checked on Python 3.11, 3.12, 3.14 and 3.15 on 2026-10-27.
PINNED_SMALL_SELECTION = {"seed": 20261027, "hot": ["H000", "H004"], "cold": ["C000", "C002"]}
