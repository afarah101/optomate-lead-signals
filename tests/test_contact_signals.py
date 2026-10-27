import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from signals.contact_signals import (
    do_not_contact_list, load_call_log, load_form_log, missed_call_trend, monthly_missed_rate, summarise_contact_signals,
)

CALL_COLUMNS = ["licence_number", "business_name", "call_date", "call_time_local", "time_band", "result",
                "voicemail_greeting_present", "caller_initials", "stop_requested", "notes"]
FORM_COLUMNS = ["licence_number", "business_name", "form_url", "sent_at_local", "first_reply_at_local",
                "form_reply_hours", "notes"]


def call(licence="S1", day="2026-10-05", at="10:30", band="morning", result="answered_by_person", greeting="", stop="no"):
    return {"licence_number": licence, "business_name": f"SAMPLE HVAC {licence}", "call_date": day,
            "call_time_local": at, "time_band": band, "result": result, "voicemail_greeting_present": greeting,
            "caller_initials": "XX", "stop_requested": stop, "notes": ""}


def form(licence="S1", sent="2026-10-05 09:00", reply="", hours=""):
    return {"licence_number": licence, "business_name": f"SAMPLE HVAC {licence}", "form_url": "https://example.invalid/contact",
            "sent_at_local": sent, "first_reply_at_local": reply, "form_reply_hours": hours, "notes": ""}


def write_log(tmp_path, columns, rows, name="log.csv"):
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_calls(tmp_path, rows):
    return load_call_log(write_log(tmp_path, CALL_COLUMNS, rows))


def load_forms(tmp_path, rows):
    return load_form_log(write_log(tmp_path, FORM_COLUMNS, rows))


# --- call validation -------------------------------------------------------------------------------------------

def test_unknown_result_is_rejected_and_reported(tmp_path):
    calls, rejected = load_calls(tmp_path, [call("S1"), call("S2", result="busy")])
    assert [c["licence_number"] for c in calls] == ["S1"]
    assert rejected[0]["line"] == 3 and "unknown result 'busy'" in rejected[0]["reason"]


@pytest.mark.parametrize("band, at", [("night", "10:30"), ("morning", "12:01"), ("afternoon", "13:59"), ("evening", "19:31")])
def test_wrong_time_band_is_rejected(tmp_path, band, at):
    calls, rejected = load_calls(tmp_path, [call(band=band, at=at)])
    assert calls == [] and len(rejected) == 1


@pytest.mark.parametrize("band, at", [("morning", "10:00"), ("morning", "12:00"), ("afternoon", "16:30"), ("evening", "18:00")])
def test_band_edges_are_inside(tmp_path, band, at):
    greeting = "yes" if band == "evening" else ""
    calls, rejected = load_calls(tmp_path, [call(band=band, at=at, greeting=greeting)])
    assert len(calls) == 1 and rejected == []


def test_greeting_is_recorded_on_evening_calls_only(tmp_path):
    calls, rejected = load_calls(tmp_path, [
        call("S1", result="voicemail", greeting="yes"),                              # morning with greeting: rejected
        call("S2", band="evening", at="18:30", result="voicemail"),                  # evening voicemail, no greeting: rejected
        call("S3", band="evening", at="18:30", result="no_answer", greeting="no"),   # ok
        call("S4", band="evening", at="18:30", result="answered_by_person"),         # ok, nothing heard
    ])
    assert [c["licence_number"] for c in calls] == ["S3", "S4"]
    assert [r["line"] for r in rejected] == [2, 3]


def test_loose_dates_are_normalised_so_months_match(tmp_path):
    calls, rejected = load_calls(tmp_path, [call(day="2026-10-5"), call(day="2026-10-20")])
    assert len(calls) == 1 and calls[0]["call_date"] == "2026-10-05"
    assert "second call" in rejected[0]["reason"]


# --- one call per month ------------------------------------------------------------------------------------------

def test_second_call_in_same_month_is_rejected_even_if_listed_first(tmp_path):
    calls, rejected = load_calls(tmp_path, [call(day="2026-10-20"), call(day="2026-10-05"), call(day="2026-11-03")])
    assert [c["call_date"] for c in calls] == ["2026-10-05", "2026-11-03"]
    assert rejected == [{"line": 2, "row": rejected[0]["row"], "reason": "second call to this business in 2026-10: one call per month"}]


def test_invalid_call_still_uses_the_month(tmp_path):
    calls, rejected = load_calls(tmp_path, [call(result="invalid"), call(day="2026-10-12")])
    assert [c["result"] for c in calls] == ["invalid"] and len(rejected) == 1


# --- missed rate -------------------------------------------------------------------------------------------------

def test_invalid_lines_are_excluded_from_the_rate():
    calls = [call("S1", result="voicemail"), call("S1", result="answered_by_person"), call("S1", result="invalid")]
    assert monthly_missed_rate(calls, "S1", "2026-10") == 0.5


def test_only_invalid_calls_means_no_rate():
    assert monthly_missed_rate([call(result="invalid")], "S1", "2026-10") is None


def test_rate_counts_voicemail_and_no_answer_as_missed():
    calls = [call(result="voicemail"), call(result="no_answer"), call(result="answered_by_person"), call(result="answered_by_person")]
    assert monthly_missed_rate(calls, "S1", "2026-10") == 0.5
    assert monthly_missed_rate(calls, "S1", "2026-09") is None


# --- trend -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("before, now, expected", [
    ("answered_by_person", "voicemail", "rising"),
    ("no_answer", "answered_by_person", "falling"),
    ("voicemail", "no_answer", "flat"),
    (None, "voicemail", "new"),
    ("invalid", "voicemail", "new"),
])
def test_each_trend_value(before, now, expected):
    calls = [call(day="2026-10-05", result=now)] + ([call(day="2026-09-07", result=before)] if before else [])
    assert missed_call_trend(calls, "S1", "2026-10") == expected


def test_trend_across_new_year_uses_december():
    calls = [call(day="2025-12-08", result="voicemail"), call(day="2026-01-12", result="answered_by_person")]
    assert missed_call_trend(calls, "S1", "2026-01") == "falling"


def test_no_rate_this_month_means_no_trend():
    assert missed_call_trend([call(day="2026-09-07")], "S1", "2026-10") is None


# --- stop rule ---------------------------------------------------------------------------------------------------

def test_stop_request_goes_on_do_not_contact_list_forever(tmp_path):
    calls, rejected = load_calls(tmp_path, [call("S1", day="2026-09-07", stop="yes"), call("S1", day="2027-03-01"), call("S2")])
    assert do_not_contact_list(calls) == {"S1"}
    assert [c["licence_number"] for c in calls] == ["S1", "S2"]
    assert "do-not-contact" in rejected[0]["reason"]


def test_stop_request_on_a_rejected_row_is_still_honoured(tmp_path):
    calls, rejected = load_calls(tmp_path, [call("S1"), call("S1", day="2026-10-20", stop="yes")])
    assert do_not_contact_list(calls) == set()
    assert "STOP REQUESTED" in rejected[0]["reason"]
    assert do_not_contact_list(calls + [r["row"] for r in rejected]) == {"S1"}


def test_stop_requested_must_be_yes_or_no(tmp_path):
    calls, rejected = load_calls(tmp_path, [call(stop="")])
    assert calls == [] and "stop_requested" in rejected[0]["reason"]


# --- forms -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("reply, expected", [
    ("2026-10-05 12:30", 3.5),
    ("2026-10-08 09:00", 72.0),       # exactly 72 h counts as a reply
    ("2026-10-08 09:06", "no_reply"),  # 72.1 h
    ("", "no_reply"),
])
def test_72_hour_form_rule(tmp_path, reply, expected):
    forms, rejected = load_forms(tmp_path, [form(reply=reply)])
    assert rejected == [] and forms[0]["form_reply_hours"] == expected


def test_reply_hours_count_real_time_across_daylight_saving_end(tmp_path):
    # Clocks go back 02:00 -> 01:00 in Dallas on 2026-11-01, so 00:30 -> 03:30 local is 4 real hours.
    forms, _ = load_forms(tmp_path, [form(sent="2026-11-01 00:30", reply="2026-11-01 03:30")])
    assert forms[0]["form_reply_hours"] == 4.0


def test_bad_form_rows_are_rejected_and_reported(tmp_path):
    forms, rejected = load_forms(tmp_path, [
        form("S1", reply="2026-10-05 08:00"),                         # reply before send
        form("S2", sent="05/10/2026 09:00"),                          # bad timestamp
        form("S3", reply="2026-10-05 10:00", hours="5"),              # disagrees with computed 1.0
        form("S4", reply="2026-10-05 10:00", hours="1.0"),            # ok
        form("S4", sent="2026-10-20 09:00"),                          # second form in month
    ])
    assert [f["licence_number"] for f in forms] == ["S4"]
    assert [r["line"] for r in rejected] == [2, 3, 4, 6]


# --- summary -----------------------------------------------------------------------------------------------------

def test_summary_has_one_row_per_business(tmp_path):
    calls, _ = load_calls(tmp_path, [
        call("S1", day="2026-09-07", result="answered_by_person"),
        call("S1", day="2026-10-05", band="evening", at="18:15", result="voicemail", greeting="yes"),
        call("S2", day="2026-10-06", stop="yes"),
    ])
    forms, _ = load_forms(tmp_path, [form("S1", reply="2026-10-05 11:00"), form("S3", sent="2026-10-07 09:00")])
    summary = summarise_contact_signals(calls, forms, "2026-10")
    assert summary == [
        {"licence_number": "S1", "business_name": "SAMPLE HVAC S1", "year_month": "2026-10", "missed_rate": 1.0,
         "trend": "rising", "voicemail_greeting_present": "yes", "form_reply_hours": 2.0, "do_not_contact": "no"},
        {"licence_number": "S2", "business_name": "SAMPLE HVAC S2", "year_month": "2026-10", "missed_rate": 0.0,
         "trend": "new", "voicemail_greeting_present": "", "form_reply_hours": "", "do_not_contact": "yes"},
        {"licence_number": "S3", "business_name": "SAMPLE HVAC S3", "year_month": "2026-10", "missed_rate": None,
         "trend": None, "voicemail_greeting_present": "", "form_reply_hours": "no_reply", "do_not_contact": "no"},
    ]
